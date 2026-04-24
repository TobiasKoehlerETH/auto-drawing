from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pythoncom
from win32com.client import Dispatch, VARIANT, gencache, makepy

from .models import BoundingBox, DrawingPlan, GenerationRequest, OutputPaths, PartProfile, ValidationReport, ViewSpec
from .standards import ISOMETRIC_VIEW_SCALE, ORTHOGRAPHIC_VIEW_SCALE

SKILL_SCRIPTS = Path(r"C:\Users\KOETOB\.codex\skills\solidworks-automation\scripts")
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from sw_connect import connect_solidworks, get_com_member, new_document  # noqa: E402

DEFAULT_DRAW_TEMPLATE = Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\data\templates\iso.drwdot")
DEFAULT_SHEET_FORMAT = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\lang\english\sheetformat\a3 - iso.slddrt")
SLDWORKS_TLB = Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.tlb")
SWDIMXPERT_TLB = Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swdimxpert.tlb")

TARGET_SHEET = "A3ISO_RESET"
A3_PAPER_SIZE = 6
SHEET_TEMPLATE_CUSTOM = 12
MMGS_UNITS = (0, 1, 8, 2, False)
WHITE_RGB = 16777215
SYSTEM_COLOR_DRAWINGS_PAPER = 217
SYSTEM_COLOR_DRAWINGS_BACKGROUND = 218
DISPLAY_MODE_HIDDEN_LINES_VISIBLE = 1
DISPLAY_MODE_SHADED_WITH_EDGES = 3
IMPORT_MODEL_ITEMS_ENTIRE_MODEL = 0
INSERT_DIMENSIONS = 8
INSERT_DIMENSIONS_MARKED_FOR_DRAWING = 32768
INSERT_DIMENSIONS_NOT_MARKED_FOR_DRAWING = 524288
AUTO_DIM_ENTITIES_ALL = 1
AUTO_DIM_SCHEME_BASELINE = 1
AUTO_DIM_SCHEME_ORDINATE = 2
AUTO_DIM_HORIZONTAL_PLACEMENT_ABOVE = 1
AUTO_DIM_VERTICAL_PLACEMENT_RIGHT = 1
PREF_TOGGLE_DISPLAY_REFERENCE_DIMENSIONS = 33
PREF_TOGGLE_SHOW_PARENTHESES_BY_DEFAULT = 48
PREF_TOGGLE_TOLERANCE_USE_PARENTHESES = 156
PREF_TOGGLE_ANGULAR_TOLERANCE_USE_PARENTHESES = 187
PREF_TOGGLE_AUTO_JOG_ORDINATES = 259
PREF_TOGGLE_ORDINATE_DISPLAY_AS_CHAIN = 382
DIMXPERT_PART_TYPE_PRISMATIC = 0
DIMXPERT_TOLERANCE_TYPE_PLUS_MINUS = 0
DIMXPERT_PATTERN_TYPE_LINEAR = 0
DIMXPERT_FEATURE_FILTERS_ALL = 65535
DIMXPERT_FEATURE_FILTERS_HOLES = 33664
DIMXPERT_FEATURE_FILTERS_PRISMATIC_CORE = 7281
SUPPORTED_INPUT_SUFFIXES = {".sldprt": "sldprt", ".step": "step", ".stp": "step"}
SUPPORTED_FAMILIES = {"auto", "prismatic", "plate", "turned"}

VIEW_POSITIONS = {
    "first-angle": {
        "main": (0.155, 0.220),
        "secondary_vertical": (0.155, 0.145),
        "secondary_side": (0.070, 0.220),
        "recognition": (0.315, 0.105),
    },
    "third-angle": {
        "main": (0.155, 0.220),
        "secondary_vertical": (0.155, 0.295),
        "secondary_side": (0.240, 0.220),
        "recognition": (0.315, 0.105),
    },
}
DISPLAY_MODE_BY_NAME = {
    "hidden-lines-visible": DISPLAY_MODE_HIDDEN_LINES_VISIBLE,
    "shaded-with-edges": DISPLAY_MODE_SHADED_WITH_EDGES,
}
TITLE_BLOCK_ZONE = {"min_x": 0.320, "max_x": 0.420, "min_y": 0.000, "max_y": 0.080}
UNSUPPORTED_FEATURE_MARKERS = (
    "sheetmetal",
    "sweep",
    "loft",
    "boundary",
    "flex",
    "deform",
    "mold",
    "weldment",
    "routing",
)
NON_MODELED_FEATURE_TYPES = {
    "RefPlane",
    "OriginProfileFeature",
    "CommentsFolder",
    "FavoriteFolder",
    "HistoryFolder",
    "SelectionSetFolder",
    "SensorFolder",
    "DocsFolder",
    "DetailCabinet",
    "SurfaceBodyFolder",
    "SolidBodyFolder",
    "EnvFolder",
    "InkMarkupFolder",
    "EqnFolder",
    "MaterialFolder",
}

SWMOD = None
SWDXMOD = None


class TraceLogger:
    def __init__(self, path: Path) -> None:
        self.path = path

    def clear(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")


class DrawingEngine:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or Path.cwd())

    def generate(self, request: GenerationRequest) -> ValidationReport:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
        request = self._normalize_request(request)
        paths = self._resolve_output_paths(request)
        logger = TraceLogger(paths.trace_log)
        logger.clear()
        ensure_com_modules()

        report = ValidationReport(status="fail", input_path=str(request.input_path), output_paths=paths.to_dict())
        sw = None
        part_model = None
        drawing_model = None
        profile = None
        plan = None
        execution: dict[str, Any] = {
            "metadata_applied": False,
            "notes_added": False,
            "notes": [],
            "dimxpert_attempted": False,
            "dimxpert_usable": False,
            "dimxpert_results": [],
            "view_dimension_counts": {},
            "dedupe_deleted": 0,
            "dedupe_warnings": [],
            "normalized_dimensions": False,
            "views_created": {},
            "view_outlines": {},
            "artifacts": {},
        }

        try:
            logger.log("main:connect_solidworks")
            sw, _ = connect_solidworks(wait_seconds=1)
            logger.log("main:connected")
            self._prepare_output_paths(sw, paths, logger)
            staged_input = self._stage_input(sw, request, paths, logger)

            logger.log("main:open_input")
            part_model = open_document_safe(sw, str(staged_input), read_only=False)
            if part_model is None:
                raise RuntimeError(f"Unable to open input model: {staged_input}")

            source_type = SUPPORTED_INPUT_SUFFIXES[request.input_path.suffix.lower()]
            drawing_source = staged_input
            if source_type == "step" and paths.working_source is not None:
                saved_import = self._persist_imported_working_copy(part_model, paths.working_source, logger)
                if saved_import is not None:
                    drawing_source = saved_import
            profile = self._inspect_part(part_model, request, source_type, logger)
            plan = self._build_plan(profile, request)
            report.profile = profile.to_dict()
            report.plan = plan.to_dict()

            if source_type == "sldprt":
                execution["dimxpert_attempted"] = True
                execution["dimxpert_results"] = self._try_dimxpert_auto_dimension(part_model, logger)
                execution["dimxpert_usable"] = any(result[1] is True for result in execution["dimxpert_results"])

            drawing_template = resolve_drawing_template(sw, logger)
            sheet_format = resolve_sheet_format(sw, logger)
            logger.log("main:configure_drawing_environment")
            set_white_drawing_background(sw)
            drawing_model, _ = open_or_create_drawing(sw, paths.drawing, drawing_template, logger)
            drawing = wrap_dispatch(drawing_model, SWMOD.IDrawingDoc, "IDrawingDoc")
            set_active_sheet(drawing, request.projection, sheet_format, logger)
            ensure_mmgs_units(drawing_model)
            set_dimension_preferences(drawing_model)

            created_views = self._create_views(drawing, plan, str(drawing_source), logger)
            execution["views_created"] = {role: info["actual_name"] for role, info in created_views.items()}

            self._set_title_block_properties(drawing_model, plan.metadata)
            execution["metadata_applied"] = True
            execution["notes"] = self._add_general_notes(drawing_model, plan.review_level)
            execution["notes_added"] = bool(execution["notes"])

            dim_metrics = self._apply_dimension_strategy(drawing, created_views, plan, profile, logger)
            execution["view_dimension_counts"] = dim_metrics["view_counts"]

            dedupe_result = self._dedupe_dimensions(drawing, created_views, logger)
            execution["dedupe_deleted"] = dedupe_result["deleted"]
            execution["dedupe_warnings"] = dedupe_result["warnings"]

            normalize_dimension_display(created_views)
            execution["normalized_dimensions"] = True
            drawing_model.ForceRebuild3(False)
            drawing_model.ViewZoomtofit2()
            execution["view_outlines"] = collect_view_outlines(created_views, logger)

            logger.log("main:save_and_export")
            save_ok = save_document_safe(drawing_model, str(paths.drawing))
            pdf_ok = export_pdf(sw, drawing_model, paths.pdf, sheet_names=(TARGET_SHEET,), logger=logger)
            png_ok = export_preview_png(drawing_model, paths.preview_png, logger=logger)
            execution["artifacts"] = {
                "drawing": save_ok and paths.drawing.exists(),
                "pdf": pdf_ok and paths.pdf.exists(),
                "preview_png": png_ok and paths.preview_png.exists(),
                "trace_log": paths.trace_log.exists(),
            }

            report = self._validate(request, paths, profile, plan, created_views, execution)
        except Exception as exc:
            logger.log(f"main:error {exc!r}")
            report.errors.append(str(exc))
            report.status = "fail"
            if profile is not None:
                report.profile = profile.to_dict()
            if plan is not None:
                report.plan = plan.to_dict()
            report.metrics = {
                "view_dimension_counts": execution.get("view_dimension_counts", {}),
                "dedupe_deleted": execution.get("dedupe_deleted", 0),
                "dedupe_warnings": execution.get("dedupe_warnings", []),
            }
        finally:
            logger.log("main:cleanup")
            if sw is not None:
                close_model(sw, drawing_model)
                close_model(sw, part_model)
            logger.log("main:cleanup_done")
            report.output_paths = paths.to_dict()
            paths.validation_json.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")

        return report

    def _normalize_request(self, request: GenerationRequest) -> GenerationRequest:
        input_path = Path(request.input_path).resolve()
        out_dir = Path(request.out_dir).resolve()
        family = request.family.lower()
        if input_path.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
            raise ValueError(f"Unsupported input type: {input_path.suffix}")
        if family not in SUPPORTED_FAMILIES:
            raise ValueError(f"Unsupported family override: {request.family}")
        if request.sheet != "A3":
            raise ValueError("Only A3 is supported in v1")
        if request.projection not in VIEW_POSITIONS:
            raise ValueError(f"Unsupported projection: {request.projection}")
        return GenerationRequest(
            input_path=input_path,
            out_dir=out_dir,
            family=family,
            sheet=request.sheet,
            projection=request.projection,
            base_name=request.base_name,
        )

    def _resolve_output_paths(self, request: GenerationRequest) -> OutputPaths:
        base_name = request.base_name or request.input_path.stem
        request.out_dir.mkdir(parents=True, exist_ok=True)
        working_source = request.out_dir / f"{base_name}.source.SLDPRT"
        return OutputPaths(
            drawing=request.out_dir / f"{base_name}.SLDDRW",
            pdf=request.out_dir / f"{base_name}.pdf",
            preview_png=request.out_dir / f"{base_name}.preview.png",
            trace_log=request.out_dir / f"{base_name}.trace.log",
            validation_json=request.out_dir / f"{base_name}.validation.json",
            working_source=working_source,
        )

    def _prepare_output_paths(self, sw, paths: OutputPaths, logger: TraceLogger) -> None:
        logger.log("prepare_output_paths:start")
        for path in (paths.drawing, paths.pdf, paths.preview_png, paths.validation_json, paths.working_source):
            if path is None:
                continue
            close_document_variants(sw, path, TARGET_SHEET)
            remove_stale_lock_file(path)
        for path in (paths.drawing, paths.pdf, paths.preview_png, paths.validation_json, paths.working_source):
            if path is None:
                continue
            remove_existing_output(path)
        time.sleep(1)
        logger.log("prepare_output_paths:done")

    def _stage_input(self, sw, request: GenerationRequest, paths: OutputPaths, logger: TraceLogger) -> Path:
        if request.input_path.suffix.lower() != ".sldprt":
            logger.log(f"input:using_original path={request.input_path}")
            return request.input_path
        close_document_variants(sw, paths.working_source, TARGET_SHEET)
        remove_stale_lock_file(paths.working_source)
        remove_existing_output(paths.working_source)
        shutil.copy2(request.input_path, paths.working_source)
        logger.log(f"input:staged_copy path={paths.working_source}")
        return paths.working_source

    def _persist_imported_working_copy(self, model, output_path: Path, logger: TraceLogger) -> Path | None:
        remove_stale_lock_file(output_path)
        remove_existing_output(output_path)
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        success = model.Extension.SaveAs(str(output_path), 0, 1, create_empty_dispatch_variant(), errors, warnings)
        logger.log(
            f"input:persist_imported_copy success={bool(success)} errors={errors.value} warnings={warnings.value} path={output_path}"
        )
        return output_path if success or output_path.exists() else None

    def _inspect_part(self, model, request: GenerationRequest, source_type: str, logger: TraceLogger) -> PartProfile:
        features = self._extract_feature_records(model)
        bbox = self._get_bounding_box(model)
        if not features or bbox.longest <= 0:
            for attempt in range(2):
                time.sleep(0.5 * (attempt + 1))
                try:
                    model.ForceRebuild3(False)
                except Exception:
                    pass
                features = self._extract_feature_records(model)
                bbox = self._get_bounding_box(model)
                if features and bbox.longest > 0:
                    logger.log(f"inspect:retry_success attempt={attempt + 1}")
                    break
        feature_types = [feature["type"] for feature in features]
        feature_names = [feature["name"] for feature in features]
        family = self._classify_family(source_type, request.family, bbox, feature_types, feature_names)
        hole_pattern = self._detect_hole_pattern(feature_types, feature_names, bbox)
        complexity = self._estimate_complexity(feature_types)
        needs_section = family == "turned" and any("ice" in feature.lower() or "cut" in feature.lower() for feature in feature_types)
        needs_detail = hole_pattern and bbox.shortest < 0.006
        preferred_main_axis = self._preferred_main_axis(bbox)
        unsupported_reasons = []
        if family == "unsupported":
            unsupported_reasons = self._unsupported_reasons(feature_types)
        profile = PartProfile(
            source_type=source_type,
            family=family,
            complexity=complexity,
            bounding_box=bbox,
            has_hole_pattern=hole_pattern,
            needs_section=needs_section,
            needs_detail=needs_detail,
            preferred_main_axis=preferred_main_axis,
            feature_types=feature_types,
            feature_names=feature_names,
            imported=source_type == "step",
            unsupported_reasons=unsupported_reasons,
        )
        logger.log(f"inspect:profile family={profile.family} complexity={profile.complexity} bbox={profile.bounding_box.to_dict()}")
        return profile

    def _extract_feature_records(self, model) -> list[dict[str, str]]:
        features: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        def append_feature(feature: Any) -> None:
            wrapped = self._wrap_feature(feature)
            if wrapped is None:
                return
            name = str(call_member(wrapped, "Name") or "")
            feature_type = str(call_member(wrapped, "GetTypeName2") or call_member(wrapped, "GetTypeName") or "")
            if not name and not feature_type:
                return
            identity = (name, feature_type)
            if identity in seen:
                return
            seen.add(identity)
            features.append({"name": name, "type": feature_type})

        feature = self._wrap_feature(call_member(model, "FirstFeature"))
        guard = 0
        while feature is not None and guard < 10000:
            append_feature(feature)
            feature = self._wrap_feature(call_member(feature, "GetNextFeature"))
            guard += 1

        if features and self._has_meaningful_features(features):
            return features

        feature_count = self._get_feature_count(model)
        if feature_count <= 0:
            return features

        # Different wrappers expose reverse positions as either 1-based or 0-based.
        # We try both patterns and dedupe by name/type, keeping whichever succeeds.
        for reverse_pos in range(1, feature_count + 1):
            append_feature(call_member(model, "FeatureByPositionReverse", reverse_pos))
        for reverse_pos in range(0, feature_count):
            append_feature(call_member(model, "FeatureByPositionReverse", reverse_pos))
        return features

    def _wrap_feature(self, feature: Any):
        if feature is None or SWMOD is None:
            return feature
        try:
            return wrap_dispatch(feature, SWMOD.IFeature, "IFeature")
        except Exception:
            return feature

    def _has_meaningful_features(self, features: list[dict[str, str]]) -> bool:
        return any(feature.get("type") not in NON_MODELED_FEATURE_TYPES for feature in features)

    def _get_feature_count(self, model) -> int:
        feature_manager = get_optional_member(model, "FeatureManager")
        for candidate in (
            lambda: get_optional_member(feature_manager, "GetFeatureCount", True),
            lambda: get_optional_member(feature_manager, "GetFeatureCount"),
            lambda: get_optional_member(model, "GetFeatureCount"),
        ):
            try:
                value = candidate()
            except Exception:
                value = None
            if value is None:
                continue
            try:
                count = int(value)
            except (TypeError, ValueError):
                continue
            if count > 0:
                return count
        return 0

    def _get_bounding_box(self, model) -> BoundingBox:
        part = wrap_dispatch(model, SWMOD.IPartDoc, "IPartDoc")
        raw_box = get_optional_member(part, "GetPartBox", True) or (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return BoundingBox(
            x=abs(raw_box[3] - raw_box[0]),
            y=abs(raw_box[4] - raw_box[1]),
            z=abs(raw_box[5] - raw_box[2]),
        )

    def _classify_family(self, source_type: str, override: str, bbox: BoundingBox, feature_types: list[str], feature_names: list[str]) -> str:
        if override != "auto":
            return override

        feature_blob = " ".join(f"{feature_types} {feature_names}").lower()
        if any(marker in feature_blob for marker in UNSUPPORTED_FEATURE_MARKERS):
            return "unsupported"
        if any("revol" in feature.lower() for feature in feature_types) or any("revol" in name.lower() for name in feature_names):
            return "turned"
        if source_type == "step":
            if bbox.thickness_ratio <= 0.12:
                return "plate"
            return "imported"
        if bbox.thickness_ratio <= 0.18:
            return "plate"
        return "prismatic"

    def _unsupported_reasons(self, feature_types: list[str]) -> list[str]:
        reasons = []
        for marker in UNSUPPORTED_FEATURE_MARKERS:
            if any(marker in feature.lower() for feature in feature_types):
                reasons.append(marker)
        return sorted(set(reasons))

    def _detect_hole_pattern(self, feature_types: list[str], feature_names: list[str], bbox: BoundingBox) -> bool:
        lowered = [value.lower() for value in feature_types + feature_names]
        if any("hole" in value for value in lowered):
            return True
        cut_like = sum(1 for value in lowered if "ice" in value or "cut" in value)
        return bbox.thickness_ratio <= 0.18 and cut_like > 0

    def _estimate_complexity(self, feature_types: list[str]) -> str:
        modeled = [
            feature for feature in feature_types
            if feature not in NON_MODELED_FEATURE_TYPES
        ]
        count = len(modeled)
        if count >= 14:
            return "high"
        if count >= 7:
            return "medium"
        return "low"

    def _preferred_main_axis(self, bbox: BoundingBox) -> str:
        axes = {"x": bbox.x, "y": bbox.y, "z": bbox.z}
        return max(axes, key=axes.get)

    def _build_plan(self, profile: PartProfile, request: GenerationRequest) -> DrawingPlan:
        ortho_scale = self._compute_ortho_scale(profile)
        recognition_scale = ISOMETRIC_VIEW_SCALE
        slots = VIEW_POSITIONS[request.projection]
        projection_text = request.projection.upper().replace("-", " ")
        title = request.input_path.stem.replace("_", " ").upper()
        metadata = {
            "Title": title,
            "Description": f"AUTO DRAWING V1 ({profile.family})",
            "Number": f"AD-{request.input_path.stem.upper()}",
            "Revision": "A",
            "DrawnBy": "Codex",
            "CheckedBy": "Codex",
            "ApprovedBy": "N/A",
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Scale": "AS NOTED",
            "SheetSize": request.sheet,
            "Units": "MMGS",
            "Material": "UNSPECIFIED",
            "Mass": "N/A",
            "Projection": projection_text,
            "GeneralTolerance": "ISO 2768-mK",
            "Standards": "ISO 8015",
        }

        if profile.family == "plate":
            view_specs = [
                ViewSpec("*Top", "main", slots["main"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Front", "support_below", slots["secondary_vertical"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Right", "support_left", slots["secondary_side"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Isometric", "recognition", slots["recognition"], recognition_scale, "shaded-with-edges"),
            ]
            dimension_roles = ["main", "support_below"]
            review_level = "warning"
            strategy = "plate-ordinate-first"
        elif profile.family == "turned":
            view_specs = [
                ViewSpec("*Front", "main", slots["main"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Right", "support_left", slots["secondary_side"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Isometric", "recognition", slots["recognition"], recognition_scale, "shaded-with-edges"),
            ]
            dimension_roles = ["main", "support_left"]
            review_level = "warning" if profile.needs_section else "pass"
            strategy = "turned-baseline-first"
        elif profile.family == "imported":
            view_specs = [
                ViewSpec("*Front", "main", slots["main"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Top", "support_below", slots["secondary_vertical"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Right", "support_left", slots["secondary_side"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Isometric", "recognition", slots["recognition"], recognition_scale, "shaded-with-edges"),
            ]
            dimension_roles = ["main"]
            review_level = "needs_review"
            strategy = "imported-conservative"
        elif profile.family == "unsupported":
            view_specs = [
                ViewSpec("*Front", "main", slots["main"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Top", "support_below", slots["secondary_vertical"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Right", "support_left", slots["secondary_side"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Isometric", "recognition", slots["recognition"], recognition_scale, "shaded-with-edges"),
            ]
            dimension_roles = []
            review_level = "needs_review"
            strategy = "unsupported-views-only"
        else:
            view_specs = [
                ViewSpec("*Front", "main", slots["main"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Top", "support_below", slots["secondary_vertical"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Right", "support_left", slots["secondary_side"], ortho_scale, "hidden-lines-visible"),
                ViewSpec("*Isometric", "recognition", slots["recognition"], recognition_scale, "shaded-with-edges"),
            ]
            dimension_roles = ["main", "support_below", "support_left"]
            review_level = "pass"
            strategy = "prismatic-ordinate-first"

        return DrawingPlan(
            sheet_size=request.sheet,
            projection=request.projection,
            view_specs=view_specs,
            dimension_strategy=strategy,
            metadata=metadata,
            review_level=review_level,
            required_dimension_roles=dimension_roles,
        )

    def _compute_ortho_scale(self, profile: PartProfile) -> float:
        _ = profile
        return ORTHOGRAPHIC_VIEW_SCALE

    def _create_views(self, drawing, plan: DrawingPlan, model_path: str, logger: TraceLogger) -> dict[str, dict[str, Any]]:
        clear_sheet_views(drawing)
        created: dict[str, dict[str, Any]] = {}
        for spec in plan.view_specs:
            view = drawing.CreateDrawViewFromModelView3(model_path, spec.model_view, spec.position[0], spec.position[1], 0)
            logger.log(f"view:create role={spec.role} model_view={spec.model_view} ok={view is not None}")
            if view is None:
                continue
            set_view_layout(
                view,
                spec.position,
                spec.scale,
                DISPLAY_MODE_BY_NAME[spec.display_mode],
                show_shaded_edges=spec.display_mode == "shaded-with-edges",
            )
            created[spec.role] = {
                "spec": spec,
                "view": view,
                "actual_name": getattr(view, "Name", spec.role),
            }
        return created

    def _set_title_block_properties(self, model, metadata: dict[str, str]) -> None:
        prop_mgr = model.Extension.CustomPropertyManager("")
        for key, value in metadata.items():
            try:
                result = prop_mgr.Add3(key, 30, value, 1)
                if result == 0:
                    prop_mgr.Set2(key, value)
            except Exception:
                try:
                    prop_mgr.Set2(key, value)
                except Exception:
                    pass

    def _add_general_notes(self, model, review_level: str) -> list[str]:
        notes = [
            "UNLESS OTHERWISE SPECIFIED: ALL DIMENSIONS IN mm",
            "GENERAL TOLERANCES: ISO 2768-mK  |  ISO 8015",
        ]
        if review_level == "needs_review":
            notes.append("AUTO-GENERATED DRAWING: MANUAL REVIEW REQUIRED")
        positions = [(0.090, 0.078), (0.090, 0.072), (0.090, 0.066)]
        added: list[str] = []
        for text, (x_m, y_m) in zip(notes, positions):
            if add_note_with_position(model, text, x_m, y_m):
                added.append(text)
        return added

    def _apply_dimension_strategy(self, drawing, created_views: dict[str, dict[str, Any]], plan: DrawingPlan, profile: PartProfile, logger: TraceLogger) -> dict[str, Any]:
        if plan.dimension_strategy == "unsupported-views-only":
            return {"view_counts": {role: 0 for role in created_views}}

        if profile.source_type == "sldprt" and not profile.imported:
            try:
                result = drawing.InsertModelAnnotations3(
                    IMPORT_MODEL_ITEMS_ENTIRE_MODEL,
                    INSERT_DIMENSIONS_MARKED_FOR_DRAWING,
                    False,
                    True,
                    False,
                    False,
                )
                logger.log(f"dimensions:insert_marked result={result}")
            except Exception as exc:
                logger.log(f"dimensions:insert_marked_failed error={exc}")
            try:
                result = drawing.InsertModelAnnotations4(
                    IMPORT_MODEL_ITEMS_ENTIRE_MODEL,
                    INSERT_DIMENSIONS + INSERT_DIMENSIONS_MARKED_FOR_DRAWING + INSERT_DIMENSIONS_NOT_MARKED_FOR_DRAWING,
                    False,
                    True,
                    False,
                    False,
                    True,
                    False,
                )
                logger.log(f"dimensions:insert_all result={result}")
            except Exception as exc:
                logger.log(f"dimensions:insert_all_failed error={exc}")

        scheme = AUTO_DIM_SCHEME_BASELINE if profile.family == "turned" else AUTO_DIM_SCHEME_ORDINATE
        view_counts: dict[str, int] = {}
        total_dimensions = 0
        ordered_roles = ["main", *[role for role in plan.required_dimension_roles if role != "main"]]
        for role in ordered_roles:
            info = created_views.get(role)
            if info is None:
                continue
            view = info["view"]
            before_count = count_view_dimensions(view)
            should_dimension = role == "main"
            if not should_dimension:
                if profile.family == "plate" and role == "support_below":
                    should_dimension = True
                elif profile.family == "turned" and role == "support_left":
                    should_dimension = True
                elif total_dimensions < 2 or before_count == 0:
                    should_dimension = True
            if should_dimension:
                self._auto_dimension_view(drawing, info["actual_name"], scheme, logger)
            after_count = count_view_dimensions(view)
            view_counts[role] = after_count
            total_dimensions += after_count
            logger.log(f"dimensions:view role={role} before={before_count} after={after_count}")

        if total_dimensions == 0 and created_views.get("main") is not None:
            self._auto_dimension_view(drawing, created_views["main"]["actual_name"], scheme, logger)
            view_counts["main"] = count_view_dimensions(created_views["main"]["view"])

        return {"view_counts": view_counts}

    def _auto_dimension_view(self, drawing, view_name: str, scheme: int, logger: TraceLogger) -> None:
        feature = drawing.FeatureByName(view_name)
        if feature is None:
            logger.log(f"dimensions:auto missing_feature view={view_name}")
            return
        try:
            drawing.ClearSelection2(True)
        except Exception:
            pass
        if not feature.Select2(False, 0):
            logger.log(f"dimensions:auto select_failed view={view_name}")
            return
        result = drawing.AutoDimension(
            AUTO_DIM_ENTITIES_ALL,
            scheme,
            AUTO_DIM_HORIZONTAL_PLACEMENT_ABOVE,
            scheme,
            AUTO_DIM_VERTICAL_PLACEMENT_RIGHT,
        )
        logger.log(f"dimensions:auto view={view_name} scheme={scheme} result={result}")
        try:
            drawing.ClearSelection2(True)
        except Exception:
            pass

    def _dedupe_dimensions(self, drawing, created_views: dict[str, dict[str, Any]], logger: TraceLogger) -> dict[str, Any]:
        entries = collect_dimension_entries(created_views)
        seen_high: dict[str, dict[str, Any]] = {}
        low_confidence_seen: dict[str, dict[str, Any]] = {}
        to_delete: list[dict[str, Any]] = []
        warnings: list[str] = []

        for entry in entries:
            identity = entry["identity"]
            if not identity:
                continue
            if entry["confidence"] == "high":
                if identity in seen_high:
                    to_delete.append(entry)
                    logger.log(f"dedupe:delete identity={identity} view={entry['view_name']}")
                else:
                    seen_high[identity] = entry
            else:
                if identity in low_confidence_seen:
                    warnings.append(
                        f"Possible duplicate dimension kept for review: {entry['text']} ({low_confidence_seen[identity]['view_name']} vs {entry['view_name']})"
                    )
                else:
                    low_confidence_seen[identity] = entry

        delete_dimension_entries(drawing, to_delete)
        return {"deleted": len(to_delete), "warnings": sorted(set(warnings))}

    def _validate(
        self,
        request: GenerationRequest,
        paths: OutputPaths,
        profile: PartProfile,
        plan: DrawingPlan,
        created_views: dict[str, dict[str, Any]],
        execution: dict[str, Any],
    ) -> ValidationReport:
        entries = collect_dimension_entries(created_views)
        check_results = {
            "drawing_exists": paths.drawing.exists(),
            "pdf_exists": paths.pdf.exists(),
            "preview_png_exists": paths.preview_png.exists(),
            "required_views_exist": all(spec.role in created_views for spec in plan.view_specs),
            "metadata_applied": execution["metadata_applied"],
            "notes_added": execution["notes_added"],
            "no_parenthesized_dimension_text": not any(has_parenthesized_dimension_text(entry["text"]) for entry in entries),
            "no_duplicate_controlling_dimensions": not has_high_confidence_duplicates(entries),
            "dedupe_pass_ran": True,
        }
        errors: list[str] = []
        warnings = list(execution["dedupe_warnings"])
        overlapping_views = detect_overlapping_view_roles(execution.get("view_outlines", {}))
        title_block_intrusions = detect_title_block_intrusions(execution.get("view_outlines", {}))
        if overlapping_views:
            warnings.append(f"View outlines overlap and likely need manual spacing review: {', '.join(overlapping_views)}")
        if title_block_intrusions:
            warnings.append(f"View outline enters the protected title-block zone: {', '.join(title_block_intrusions)}")

        if not check_results["drawing_exists"]:
            errors.append("Drawing file was not created")
        if not check_results["pdf_exists"]:
            errors.append("PDF export was not created")
        if not check_results["preview_png_exists"]:
            errors.append("Preview PNG export was not created")
        if not check_results["required_views_exist"]:
            errors.append("One or more planned views were not created")
        if not check_results["no_parenthesized_dimension_text"]:
            errors.append("Visible parenthesized dimension text remains")
        if not check_results["no_duplicate_controlling_dimensions"]:
            errors.append("Duplicate controlling dimensions remain after dedupe")
        if not check_results["metadata_applied"] or not check_results["notes_added"]:
            errors.append("Required metadata notes were not added")

        total_dimensions = len(entries)
        if profile.family in {"prismatic", "plate", "turned"} and total_dimensions == 0:
            errors.append("No dimensions were created for a supported family")
        if profile.imported:
            warnings.append("Review required for STEP-based imported input")
        if profile.family in {"imported", "unsupported"}:
            warnings.append(f"Review required for {profile.family} input")
        if profile.needs_section:
            warnings.append("Part likely needs a section view for a fully manufacturable drawing")
        if profile.needs_detail:
            warnings.append("Part likely needs a detail view for a fully manufacturable drawing")
        if execution["dimxpert_attempted"] and not execution["dimxpert_usable"]:
            warnings.append("DimXpert did not produce usable annotations; drawing relied on drawing-side dimensions")

        if errors:
            status = "fail"
        elif profile.imported or profile.family in {"imported", "unsupported"} or profile.needs_section or profile.needs_detail:
            status = "needs_review"
        elif overlapping_views or title_block_intrusions:
            status = "needs_review"
        elif warnings:
            status = "warning"
        else:
            status = "pass"

        metrics = {
            "total_dimensions": total_dimensions,
            "view_dimension_counts": execution["view_dimension_counts"],
            "dedupe_deleted": execution["dedupe_deleted"],
            "dedupe_warnings": execution["dedupe_warnings"],
            "dimxpert_attempted": execution["dimxpert_attempted"],
            "dimxpert_usable": execution["dimxpert_usable"],
            "views_created": execution["views_created"],
            "view_outlines": execution["view_outlines"],
            "artifacts": execution["artifacts"],
        }

        return ValidationReport(
            status=status,
            errors=errors,
            warnings=sorted(set(warnings)),
            check_results=check_results,
            input_path=str(request.input_path),
            output_paths=paths.to_dict(),
            profile=profile.to_dict(),
            plan=plan.to_dict(),
            metrics=metrics,
        )

    def _try_dimxpert_auto_dimension(self, part_model, logger: TraceLogger) -> list[tuple[str, object]]:
        results: list[tuple[str, object]] = []
        try:
            typed_extension = wrap_dispatch(part_model.Extension, SWMOD.IModelDocExtension, "IModelDocExtension")
            configuration_name = part_model.ConfigurationManager.ActiveConfiguration.Name
            manager = typed_extension.DimXpertManager(configuration_name, True)
            dimxpert_part = wrap_dispatch(manager.DimXpertPart, SWDXMOD.IDimXpertPart, "IDimXpertPart")
        except Exception as exc:
            logger.log(f"dimxpert:setup_failed error={exc}")
            return [("setup", exc)]

        logger.log(f"dimxpert:schema={getattr(manager, 'SchemaName', '')}")
        for label, feature_filters, scope_all in (
            ("all_features", DIMXPERT_FEATURE_FILTERS_ALL, True),
            ("holes_only", DIMXPERT_FEATURE_FILTERS_HOLES, False),
            ("prismatic_core", DIMXPERT_FEATURE_FILTERS_PRISMATIC_CORE, False),
        ):
            try:
                dimxpert_part.DeleteAllTolerances()
            except Exception:
                pass
            try:
                option = dimxpert_part.GetAutoDimSchemeOption()
                option.PartType = DIMXPERT_PART_TYPE_PRISMATIC
                option.ToleranceType = DIMXPERT_TOLERANCE_TYPE_PLUS_MINUS
                option.PatternType = DIMXPERT_PATTERN_TYPE_LINEAR
                option.ScopeAllFeature = scope_all
                option.FeatureFilters = feature_filters
                result = dimxpert_part.AutoDimensionScheme(option)
            except Exception as exc:
                result = exc
                logger.log(f"dimxpert:auto_dimension_failed label={label} error={exc}")
                results.append((label, result))
                break
            else:
                logger.log(f"dimxpert:auto_dimension label={label} result={result}")
                results.append((label, result))
        return results


def ensure_com_modules() -> None:
    global SWMOD, SWDXMOD
    if SWMOD is not None and SWDXMOD is not None:
        return
    makepy.GenerateFromTypeLibSpec(str(SLDWORKS_TLB))
    makepy.GenerateFromTypeLibSpec(str(SWDIMXPERT_TLB))
    SWMOD = gencache.EnsureModule("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
    SWDXMOD = gencache.EnsureModule("{582D0D5B-FF58-42CD-8968-A8A001A52454}", 0, 32, 0)


def wrap_dispatch(obj, interface_cls, interface_name: str):
    if obj is None:
        return None
    if hasattr(obj, "_oleobj_"):
        return Dispatch(obj._oleobj_, interface_name, interface_cls.CLSID)
    return Dispatch(obj, interface_name, interface_cls.CLSID)


def get_optional_member(obj, attr_name: str, *args):
    if obj is None:
        return None
    try:
        return get_com_member(obj, attr_name, *args)
    except Exception:
        return None


def call_member(obj, attr_name: str, *args):
    if obj is None:
        return None
    try:
        attr = getattr(obj, attr_name)
        return attr(*args) if callable(attr) else attr
    except Exception:
        return None


def create_empty_dispatch_variant():
    return VARIANT(pythoncom.VT_DISPATCH, None)


def open_document_safe(sw, file_path: str, read_only: bool = False):
    ext = Path(file_path).suffix.lower()
    type_map = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3, ".step": 1, ".stp": 1, ".igs": 1, ".iges": 1}
    doc_type = type_map.get(ext, 1)
    options = 2 if read_only else 0
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    if ext in {".step", ".stp", ".igs", ".iges"}:
        model = sw.OpenDoc6(file_path, doc_type, options, "", errors, warnings)
        if model is not None:
            return model
        loaded = sw.LoadFile2(file_path, "r" if read_only else "")
        if loaded:
            try:
                return getattr(sw, "ActiveDoc")
            except Exception:
                return get_optional_member(sw, "IActiveDoc2")
        return None
    model = sw.OpenDoc6(file_path, doc_type, options, "", errors, warnings)
    return model


def save_document_safe(model, file_path: str | None = None) -> bool:
    current_path = get_optional_member(model, "GetPathName")
    if file_path and current_path and Path(current_path) == Path(file_path):
        for attempt in range(3):
            try:
                success, _, _ = model.Save3(1, 0, 0)
            except Exception:
                success = False
            if success or Path(file_path).exists():
                return True
            time.sleep(0.3 * (attempt + 1))
        return False
    if file_path:
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        for attempt in range(3):
            try:
                success = model.Extension.SaveAs(file_path, 0, 1, create_empty_dispatch_variant(), errors, warnings)
            except Exception:
                success = False
            if success or Path(file_path).exists():
                return True
            time.sleep(0.3 * (attempt + 1))
        return False
    for attempt in range(3):
        try:
            success, _, _ = model.Save3(1, 0, 0)
        except Exception:
            success = False
        if success:
            return True
        time.sleep(0.3 * (attempt + 1))
    return False


def export_pdf(sw, model, output_path: Path, sheet_names=None, logger: TraceLogger | None = None) -> bool:
    if logger is not None:
        logger.log("export_pdf:start")
    pdf_data = sw.GetExportFileData(1)
    sheet_names = sheet_names or get_optional_member(model, "GetSheetNames")
    pdf_data.SetSheets(0, sheet_names)
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    success = False
    for attempt in range(3):
        try:
            success = model.Extension.SaveAs(str(output_path), 0, 1, pdf_data, errors, warnings)
        except Exception as exc:
            if logger is not None:
                logger.log(f"export_pdf:attempt_failed attempt={attempt + 1} error={exc}")
        if success or output_path.exists():
            success = True
            break
        time.sleep(0.3 * (attempt + 1))
    if logger is not None:
        logger.log(f"export_pdf:done success={bool(success)} errors={errors.value} warnings={warnings.value}")
    return bool(success)


def export_preview_png(model, output_path: Path, logger: TraceLogger | None = None) -> bool:
    if logger is not None:
        logger.log("export_preview_png:start")
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    success = False
    for attempt in range(3):
        try:
            success = model.Extension.SaveAs(str(output_path), 0, 1, create_empty_dispatch_variant(), errors, warnings)
        except Exception as exc:
            if logger is not None:
                logger.log(f"export_preview_png:attempt_failed attempt={attempt + 1} error={exc}")
        if success or output_path.exists():
            success = True
            break
        time.sleep(0.3 * (attempt + 1))
    if logger is not None:
        logger.log(f"export_preview_png:done success={bool(success)} errors={errors.value} warnings={warnings.value}")
    return bool(success)


def open_or_create_drawing(sw, drawing_path: Path, template_path: Path | None, logger: TraceLogger | None = None):
    close_document_variants(sw, drawing_path, TARGET_SHEET)
    remove_stale_lock_file(drawing_path)
    remove_existing_output(drawing_path)
    template_candidates = [template_path] if template_path is not None else []
    if DEFAULT_DRAW_TEMPLATE not in template_candidates:
        template_candidates.append(DEFAULT_DRAW_TEMPLATE)
    for candidate in template_candidates:
        try:
            if candidate is not None:
                model = new_document(sw, "drawing", template_path=str(candidate))
            else:
                model = new_document(sw, "drawing")
            if model is not None:
                if logger is not None:
                    logger.log(f"drawing:create template={candidate}")
                return model, True
        except Exception as exc:
            if logger is not None:
                logger.log(f"drawing:create_failed template={candidate} error={exc}")
    model = new_document(sw, "drawing")
    return model, True


def close_document_variants(sw, path: Path, target_sheet: str) -> None:
    candidates = {str(path), path.name, path.stem, f"{path.stem} - {target_sheet}"}
    for candidate in candidates:
        try:
            sw.CloseDoc(candidate)
        except Exception:
            pass


def remove_existing_output(path: Path) -> None:
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass


def remove_stale_lock_file(path: Path) -> None:
    lock_path = path.with_name(f"~${path.name}")
    if lock_path.exists():
        try:
            lock_path.unlink()
        except Exception:
            pass


def close_model(sw, model) -> None:
    if model is None:
        return
    for accessor in ("GetPathName", "GetTitle"):
        candidate = get_optional_member(model, accessor)
        if not candidate:
            continue
        try:
            sw.CloseDoc(candidate)
        except Exception:
            pass


def set_active_sheet(drawing, projection: str, sheet_format: Path | None, logger: TraceLogger | None = None) -> bool:
    sheet_names = get_com_member(drawing, "GetSheetNames")
    activate = getattr(drawing, "ActivateSheet", None)
    sheet_format_str = str(sheet_format) if sheet_format is not None else ""
    if sheet_names and TARGET_SHEET in sheet_names:
        if callable(activate):
            activate(TARGET_SHEET)
    else:
        if sheet_names and callable(activate):
            activate(sheet_names[0])
        create_sheet = getattr(drawing, "NewSheet4", None)
        if callable(create_sheet):
            create_sheet(
                TARGET_SHEET,
                A3_PAPER_SIZE,
                SHEET_TEMPLATE_CUSTOM,
                1,
                1,
                projection == "first-angle",
                sheet_format_str,
                0.42,
                0.297,
                "",
                0,
                0,
                0,
                0,
                0,
                0,
            )
            if callable(activate):
                activate(TARGET_SHEET)
    sheet = get_optional_member(drawing, "GetCurrentSheet")
    set_template = getattr(sheet, "SetTemplateName", None)
    reload_template = getattr(sheet, "ReloadTemplate", None)
    if sheet_format is not None and callable(set_template):
        set_template(sheet_format_str)
    if sheet_format is not None and callable(reload_template):
        reload_template(True)
    delete_sheet = getattr(drawing, "DeleteSheet", None)
    if callable(delete_sheet):
        for sheet_name in get_com_member(drawing, "GetSheetNames") or ():
            if sheet_name != TARGET_SHEET:
                try:
                    delete_sheet(sheet_name)
                except Exception:
                    pass
    if logger is not None:
        logger.log(f"sheet:active target={TARGET_SHEET} projection={projection} format={sheet_format_str}")
    return True


def set_white_drawing_background(sw) -> None:
    for pref in (SYSTEM_COLOR_DRAWINGS_PAPER, SYSTEM_COLOR_DRAWINGS_BACKGROUND):
        try:
            sw.SetUserPreferenceIntegerValue(pref, WHITE_RGB)
        except Exception:
            pass


def ensure_mmgs_units(model) -> None:
    try:
        model.SetUnits(*MMGS_UNITS)
    except Exception:
        pass
    try:
        model.SetUserPreferenceIntegerValue(22, 0)
    except Exception:
        pass


def set_dimension_preferences(model) -> None:
    for pref, value in (
        (PREF_TOGGLE_DISPLAY_REFERENCE_DIMENSIONS, True),
        (PREF_TOGGLE_SHOW_PARENTHESES_BY_DEFAULT, False),
        (PREF_TOGGLE_TOLERANCE_USE_PARENTHESES, False),
        (PREF_TOGGLE_ANGULAR_TOLERANCE_USE_PARENTHESES, False),
        (PREF_TOGGLE_AUTO_JOG_ORDINATES, True),
        (PREF_TOGGLE_ORDINATE_DISPLAY_AS_CHAIN, False),
    ):
        try:
            model.SetUserPreferenceToggle(pref, value)
        except Exception:
            pass


def clear_sheet_views(drawing) -> None:
    sheet = get_optional_member(drawing, "GetCurrentSheet")
    views = get_optional_member(sheet, "GetViews") or ()
    for view in list(views):
        view_name = getattr(view, "Name", "")
        if not view_name:
            continue
        feature = drawing.FeatureByName(view_name)
        if feature is None:
            continue
        try:
            drawing.ClearSelection2(True)
        except Exception:
            pass
        try:
            if feature.Select2(False, 0):
                drawing.EditDelete()
        except Exception:
            pass


def set_view_layout(view, position, scale: float, display_mode: int, *, show_shaded_edges: bool = False) -> None:
    if view is None:
        return
    try:
        view.UseSheetScale = False
    except Exception:
        pass
    try:
        view.ScaleDecimal = scale
    except Exception:
        pass
    try:
        view.Position = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, (position[0], position[1], 0.0))
    except Exception:
        pass
    try:
        view.SetDisplayMode3(False, display_mode, False, show_shaded_edges)
    except Exception:
        pass


def add_note_with_position(model, text: str, x_m: float, y_m: float) -> bool:
    try:
        note = model.InsertNote(text)
        if note is None:
            return False
        note.SetTextPoint(x_m, y_m, 0.0)
        return True
    except Exception:
        return False


def count_view_dimensions(view) -> int:
    total = 0
    current = get_first_display_dimension(view)
    while current is not None:
        total += 1
        current = get_next_display_dimension(view, current)
    return total


def get_first_display_dimension(view):
    current = get_optional_member(view, "GetFirstDisplayDimension5")
    if current is not None:
        return current
    return get_optional_member(view, "GetFirstDisplayDimension")


def get_next_display_dimension(view, current):
    next_dim = get_optional_member(view, "GetNextDisplayDimension5", current)
    if next_dim is not None:
        return next_dim
    next_dim = get_optional_member(view, "GetNextDisplayDimension", current)
    if next_dim is not None:
        return next_dim
    return get_optional_member(current, "GetNext")


def collect_view_outlines(created_views: dict[str, dict[str, Any]], logger: TraceLogger | None = None) -> dict[str, dict[str, float]]:
    outlines: dict[str, dict[str, float]] = {}
    for role, info in created_views.items():
        view = info.get("view")
        outline = get_view_outline(view)
        if outline is None:
            continue
        outlines[role] = outline
        if logger is not None:
            logger.log(f"view:outline role={role} outline={outline}")
    return outlines


def get_view_outline(view) -> dict[str, float] | None:
    if view is None:
        return None
    outline = get_optional_member(view, "GetOutline")
    if outline is None or len(outline) < 4:
        return None
    try:
        return {
            "min_x": float(outline[0]),
            "min_y": float(outline[1]),
            "max_x": float(outline[2]),
            "max_y": float(outline[3]),
        }
    except Exception:
        return None


def detect_overlapping_view_roles(outlines: dict[str, dict[str, float]]) -> list[str]:
    overlaps: list[str] = []
    tolerance = 0.004
    roles = list(outlines)
    for index, left_role in enumerate(roles):
        left = outlines[left_role]
        for right_role in roles[index + 1 :]:
            right = outlines[right_role]
            separated = (
                left["max_x"] <= right["min_x"] + tolerance
                or right["max_x"] <= left["min_x"] + tolerance
                or left["max_y"] <= right["min_y"] + tolerance
                or right["max_y"] <= left["min_y"] + tolerance
            )
            if not separated:
                overlaps.append(f"{left_role} vs {right_role}")
    return overlaps


def detect_title_block_intrusions(outlines: dict[str, dict[str, float]]) -> list[str]:
    intrusions: list[str] = []
    zone = TITLE_BLOCK_ZONE
    tolerance = 0.010
    for role, outline in outlines.items():
        separated = (
            outline["max_x"] <= zone["min_x"] + tolerance
            or zone["max_x"] <= outline["min_x"] + tolerance
            or outline["max_y"] <= zone["min_y"] + tolerance
            or zone["max_y"] <= outline["min_y"] + tolerance
        )
        if not separated:
            intrusions.append(role)
    return intrusions


def collect_dimension_entries(created_views: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    order = {role: index for index, role in enumerate(created_views.keys())}
    for role, info in created_views.items():
        current = get_first_display_dimension(info["view"])
        while current is not None:
            display_dimension = wrap_dispatch(current, SWMOD.IDisplayDimension, "IDisplayDimension")
            annotation = get_optional_member(display_dimension, "GetAnnotation") or get_optional_member(current, "GetAnnotation")
            text = annotation_text(annotation)
            full_name, name = dimension_source_names(display_dimension)
            numeric = extract_numeric_value(text)
            measure_kind = measurement_type(text)
            if full_name:
                identity = f"model:{full_name}"
                confidence = "high"
            elif name:
                identity = f"model-name:{name}"
                confidence = "high"
            else:
                identity = f"fingerprint:{measure_kind}|{numeric}|{role}|{normalize_text(text)}"
                confidence = "low"
            entries.append(
                {
                    "role": role,
                    "view_name": info["actual_name"],
                    "order": order[role],
                    "text": text,
                    "identity": identity,
                    "confidence": confidence,
                    "annotation": annotation,
                }
            )
            current = get_next_display_dimension(info["view"], current)
    return entries


def dimension_source_names(display_dimension) -> tuple[str | None, str | None]:
    dim_obj = get_optional_member(display_dimension, "GetDimension2", 0)
    if dim_obj is None:
        dim_obj = get_optional_member(display_dimension, "GetDimension")
    full_name = str(get_optional_member(dim_obj, "FullName") or "") or None
    name = str(get_optional_member(dim_obj, "Name") or "") or None
    return full_name, name


def annotation_text(annotation) -> str:
    if annotation is None:
        return ""
    text = get_optional_member(annotation, "GetText")
    if isinstance(text, tuple):
        text = " ".join(str(part) for part in text if part)
    return normalize_text(str(text or ""))


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_numeric_value(text: str) -> str:
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def measurement_type(text: str) -> str:
    if any(symbol in text for symbol in ("\u00D8", "\u2300")):
        return "diameter"
    if text.startswith("R"):
        return "radius"
    if text.startswith("M"):
        return "thread"
    return "linear"


def delete_dimension_entries(drawing, entries: list[dict[str, Any]]) -> None:
    if not entries:
        return
    try:
        drawing.ClearSelection2(True)
    except Exception:
        pass
    selected = 0
    for entry in entries:
        annotation = entry.get("annotation")
        if annotation is None:
            continue
        try:
            if annotation.Select2(selected > 0, 0):
                selected += 1
        except Exception:
            pass
    if selected:
        try:
            drawing.EditDelete()
        except Exception:
            pass


def has_parenthesized_dimension_text(text: str) -> bool:
    return bool(text) and "(" in text and ")" in text


def has_high_confidence_duplicates(entries: list[dict[str, Any]]) -> bool:
    seen: set[str] = set()
    for entry in entries:
        if entry["confidence"] != "high":
            continue
        if entry["identity"] in seen:
            return True
        seen.add(entry["identity"])
    return False


def normalize_dimension_display(created_views: dict[str, dict[str, Any]]) -> None:
    for info in created_views.values():
        current = get_first_display_dimension(info["view"])
        while current is not None:
            try:
                current.SetUnits2(False, 0, 2, 2, False, 0)
                current.SetDual2(False, False)
                current.SetDual(False)
                display_dimension = wrap_dispatch(current, SWMOD.IDisplayDimension, "IDisplayDimension")
                display_dimension.ShowParenthesis = False
                display_dimension.ShowLowerParenthesis = False
                display_dimension.ShowTolParenthesis = False
                display_dimension.DisplayAsChain = False
            except Exception:
                pass
            current = get_next_display_dimension(info["view"], current)


def resolve_drawing_template(sw, logger: TraceLogger | None = None) -> Path | None:
    candidates: list[Path] = []
    user_template = get_optional_member(sw, "GetUserPreferenceStringValue", 8)
    if user_template:
        user_template_path = Path(str(user_template))
        if user_template_path.suffix.lower() == ".drwdot":
            candidates.append(user_template_path)
    revision = get_solidworks_revision(sw)
    year_match = re.match(r"^(\d{4})", revision)
    if year_match:
        year = year_match.group(1)
        candidates.append(Path(f"C:/ProgramData/SolidWorks/SOLIDWORKS {year}/templates/Drawing.drwdot"))
        candidates.append(Path(f"C:/ProgramData/SolidWorks/SOLIDWORKS {year}/templates/drawing.drwdot"))
    candidates.extend(
        [
            DEFAULT_DRAW_TEMPLATE,
            Path(r"C:\ProgramData\SolidWorks\templates\Drawing.drwdot"),
            Path(r"C:\ProgramData\SolidWorks\templates\drawing.drwdot"),
        ]
    )
    resolved = first_existing_path(candidates)
    if logger is not None:
        logger.log(f"template:drawing resolved={resolved} revision={revision}")
    return resolved


def resolve_sheet_format(sw, logger: TraceLogger | None = None) -> Path | None:
    candidates: list[Path] = [DEFAULT_SHEET_FORMAT]
    revision = get_solidworks_revision(sw)
    year_match = re.match(r"^(\d{4})", revision)
    if year_match:
        year = year_match.group(1)
        base = Path(f"C:/ProgramData/SolidWorks/SOLIDWORKS {year}/lang/english/sheetformat")
        candidates.extend(
            [
                base / "a3 - iso.slddrt",
                base / "A3 - ISO.slddrt",
                base / "a3 iso.slddrt",
            ]
        )
    candidates.extend(
        [
            Path(r"C:\ProgramData\SolidWorks\sheetformat\a3 - iso.slddrt"),
            Path(r"C:\ProgramData\SolidWorks\sheetformat\A3 - ISO.slddrt"),
        ]
    )
    resolved = first_existing_path(candidates)
    if logger is not None:
        logger.log(f"template:sheet_format resolved={resolved} revision={revision}")
    return resolved


def first_existing_path(candidates: list[Path]) -> Path | None:
    seen: set[str] = set()
    for candidate in candidates:
        normalized = os.path.normcase(str(candidate))
        if normalized in seen:
            continue
        seen.add(normalized)
        if candidate.exists():
            return candidate
    return None


def get_solidworks_revision(sw) -> str:
    for attr_name in ("RevisionNumber", "RevisionNumber2"):
        try:
            attr = getattr(sw, attr_name)
            value = attr() if callable(attr) else attr
            if value:
                return str(value)
        except Exception:
            continue
    return ""
