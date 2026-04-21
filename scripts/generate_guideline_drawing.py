import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import pythoncom
from win32com.client import Dispatch, VARIANT, gencache, makepy


SKILL_SCRIPTS = Path(r"C:\Users\KOETOB\.codex\skills\solidworks-automation\scripts")
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from sw_connect import (  # noqa: E402
    connect_solidworks,
    get_com_member,
    new_document,
)


ROOT = Path(r"C:\Code\auto-drawing")
SAMPLE_PART = ROOT / "sample_part" / "sample.SLDPRT"
OUT_DIR = ROOT / ".generated" / "guideline_drawing"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DRAWING_PATH = OUT_DIR / "sample_guideline_attempt.SLDDRW"
PDF_PATH = OUT_DIR / "sample_guideline_attempt.pdf"
PREVIEW_PNG_PATH = OUT_DIR / "sample_guideline_attempt.preview.png"
TRACE_PATH = OUT_DIR / "sample_guideline_attempt.trace.log"
WORKING_PART_PATH = OUT_DIR / "sample_guideline_attempt.source.SLDPRT"

DRAW_TEMPLATE = Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\data\templates\iso.drwdot")
SHEET_FORMAT = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\lang\english\sheetformat\a3 - iso.slddrt")
SLDWORKS_TLB = Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\sldworks.tlb")
SWDIMXPERT_TLB = Path(r"C:\Program Files\SOLIDWORKS Corp\SOLIDWORKS\swdimxpert.tlb")


TARGET_SHEET = "A3ISO_RESET"
DRAWING_TITLE = "SAMPLE PART"
DRAWING_NUMBER = "AD-SAMPLE-001"
DRAWING_REVISION = "A"

MMGS_UNITS = (0, 1, 8, 2, False)
DISPLAY_MODE_HIDDEN_LINES_VISIBLE = 1
DISPLAY_MODE_SHADED_WITH_EDGES = 3
SYSTEM_COLOR_DRAWINGS_PAPER = 217
SYSTEM_COLOR_DRAWINGS_BACKGROUND = 218
WHITE_RGB = 16777215

ORTHO_SCALE = 1.0
ISO_SCALE = 0.5
ENABLE_AUTO_DIMENSIONS = True
FORCE_RECREATE_DRAWING = True
A3_PAPER_SIZE = 6
SHEET_TEMPLATE_CUSTOM = 12
IMPORT_MODEL_ITEMS_ENTIRE_MODEL = 0
INSERT_DIMENSIONS = 8
INSERT_DIMENSIONS_MARKED_FOR_DRAWING = 32768
INSERT_DIMENSIONS_NOT_MARKED_FOR_DRAWING = 524288
AUTO_DIM_ENTITIES_BASED_ON_PRESELECT = 0
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
VIEW_POSITIONS = {
    "front": (0.155, 0.220),
    "top": (0.155, 0.145),
    "right": (0.070, 0.220),
    "iso": (0.315, 0.105),
}

SWMOD = None
SWDXMOD = None


def trace(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


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


def recreate_working_part_copy(sw) -> Path:
    close_document_variants(sw, WORKING_PART_PATH)
    remove_stale_lock_file(WORKING_PART_PATH)
    remove_existing_output(WORKING_PART_PATH)
    shutil.copy2(SAMPLE_PART, WORKING_PART_PATH)
    trace(f"working_part_copy={WORKING_PART_PATH}")
    print(f"working_part_copy={WORKING_PART_PATH.name}")
    return WORKING_PART_PATH


def export_pdf(sw, model, output_path: Path, sheet_names=None) -> bool:
    trace("export_pdf:start")
    pdf_data = sw.GetExportFileData(1)
    if sheet_names is None:
        sheet_names = get_com_member(model, "GetSheetNames")
    pdf_data.SetSheets(0, sheet_names)
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    success = model.Extension.SaveAs(str(output_path), 0, 1, pdf_data, errors, warnings)
    trace(f"export_pdf:done success={bool(success)} errors={errors.value} warnings={warnings.value}")
    print(f"export_pdf={bool(success)} errors={errors.value} warnings={warnings.value}")
    return bool(success)


def export_preview_png(model, output_path: Path) -> bool:
    trace("export_preview_png:start")
    errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    success = model.Extension.SaveAs(
        str(output_path),
        0,
        1,
        create_empty_dispatch_variant(),
        errors,
        warnings,
    )
    trace(
        f"export_preview_png:done success={bool(success)} "
        f"errors={errors.value} warnings={warnings.value}"
    )
    print(f"export_preview_png={bool(success)} errors={errors.value} warnings={warnings.value}")
    return bool(success)


def create_empty_dispatch_variant():
    return VARIANT(pythoncom.VT_DISPATCH, None)


def open_document_safe(sw, file_path: str, read_only: bool = False):
    ext = Path(file_path).suffix.lower()
    type_map = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3, ".step": 1, ".stp": 1, ".igs": 1, ".iges": 1}
    doc_type = type_map.get(ext, 1)
    options = 2 if read_only else 0
    model, errors, warnings = sw.OpenDoc6(file_path, doc_type, options, "", 0, 0)
    if model:
        print(f"open_document=True path={Path(file_path).name} errors={errors} warnings={warnings}")
    else:
        print(f"open_document=False path={Path(file_path).name} errors={errors} warnings={warnings}")
    return model


def save_document_safe(model, file_path: str | None = None) -> bool:
    current_path = get_com_member(model, "GetPathName")

    if file_path and current_path and Path(current_path) == Path(file_path):
        success, errors, warnings = model.Save3(1, 0, 0)
        error_code = errors
        warning_code = warnings
    elif file_path:
        errors = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        warnings = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        success = model.Extension.SaveAs(
            file_path,
            0,
            1,
            create_empty_dispatch_variant(),
            errors,
            warnings,
        )
        error_code = errors.value
        warning_code = warnings.value
    else:
        success, errors, warnings = model.Save3(1, 0, 0)
        error_code = errors
        warning_code = warnings

    target = file_path or current_path
    print(f"save_document={bool(success)} path={target} errors={error_code} warnings={warning_code}")
    return bool(success)


def open_or_create_drawing(sw):
    trace("open_or_create_drawing:start")
    close_document_variants(sw, DRAWING_PATH)
    remove_stale_lock_file(DRAWING_PATH)

    if FORCE_RECREATE_DRAWING and DRAWING_PATH.exists():
        remove_existing_output(DRAWING_PATH)
        trace("open_or_create_drawing:removed_existing_output")
    elif DRAWING_PATH.exists():
        drawing_model = open_document_safe(sw, str(DRAWING_PATH), read_only=False)
        if drawing_model is not None:
            trace("open_or_create_drawing:opened_existing")
            print("created_new_drawing=False")
            return drawing_model, False

    drawing_model = new_document(sw, "drawing", template_path=str(DRAW_TEMPLATE))
    trace("open_or_create_drawing:done")
    print("created_new_drawing=True")
    return drawing_model, True


def close_document_variants(sw, path: Path) -> None:
    candidates = {
        str(path),
        path.name,
        path.stem,
        f"{path.stem} - {TARGET_SHEET}",
    }
    for candidate in candidates:
        try:
            sw.CloseDoc(candidate)
            print(f"close_doc={candidate}")
        except Exception:
            pass


def remove_existing_output(path: Path) -> None:
    if not path.exists():
        return
    try:
        path.unlink()
        print(f"remove_output=True path={path.name}")
    except Exception as exc:
        print(f"remove_output=False path={path.name} error={exc}")


def remove_stale_lock_file(path: Path) -> None:
    lock_path = path.with_name(f"~${path.name}")
    if not lock_path.exists():
        return
    try:
        lock_path.unlink()
        print(f"remove_lock=True path={lock_path.name}")
    except Exception as exc:
        print(f"remove_lock=False path={lock_path.name} error={exc}")


def close_model(sw, model) -> None:
    if model is None:
        return

    candidates = []
    for accessor in ("GetPathName", "GetTitle"):
        try:
            value = get_com_member(model, accessor)
        except Exception:
            value = None
        if value:
            candidates.append(value)

    for candidate in candidates:
        try:
            sw.CloseDoc(candidate)
            print(f"close_model={candidate}")
        except Exception as exc:
            print(f"close_model_error={candidate} error={exc}")


def prepare_output_paths(sw) -> None:
    trace("prepare_output_paths:start")
    close_document_variants(sw, DRAWING_PATH)
    close_document_variants(sw, WORKING_PART_PATH)
    close_document_variants(sw, PDF_PATH)
    remove_stale_lock_file(DRAWING_PATH)
    remove_stale_lock_file(WORKING_PART_PATH)
    remove_existing_output(WORKING_PART_PATH)
    remove_existing_output(PDF_PATH)
    remove_existing_output(PREVIEW_PNG_PATH)
    time.sleep(1)
    trace("prepare_output_paths:done")


def get_optional_member(obj, attr_name: str, *args):
    if obj is None:
        return None
    try:
        return get_com_member(obj, attr_name, *args)
    except Exception:
        return None


def get_current_sheet(drawing):
    return get_optional_member(drawing, "GetCurrentSheet")


def get_sheet_views(sheet):
    views = get_optional_member(sheet, "GetViews")
    return list(views) if views else []


def get_first_display_dimension(view):
    return get_optional_member(view, "GetFirstDisplayDimension")


def get_next_display_dimension(view, current):
    next_dim = get_optional_member(view, "GetNextDisplayDimension", current)
    if next_dim is not None:
        return next_dim
    return get_optional_member(current, "GetNext")


def set_active_sheet_a3_first_angle(drawing) -> bool:
    sheet_names = get_com_member(drawing, "GetSheetNames")
    activate = getattr(drawing, "ActivateSheet", None)
    created_target_sheet = False
    if sheet_names and TARGET_SHEET in sheet_names:
        if callable(activate):
            activate(TARGET_SHEET)
        print(f"activate_existing_sheet={TARGET_SHEET}")
    else:
        if sheet_names and callable(activate):
            activate(sheet_names[0])
        create_sheet = getattr(drawing, "NewSheet4", None)
        if callable(create_sheet):
            ok = create_sheet(
                TARGET_SHEET,
                A3_PAPER_SIZE,
                SHEET_TEMPLATE_CUSTOM,
                1,
                1,
                True,  # first-angle
                str(SHEET_FORMAT),
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
            created_target_sheet = bool(ok)
            print(f"new_sheet4={created_target_sheet}")
            if callable(activate):
                activate(TARGET_SHEET)
    try:
        sheet = get_current_sheet(drawing)
        set_template = getattr(sheet, "SetTemplateName", None)
        reload_template = getattr(sheet, "ReloadTemplate", None)
        if callable(set_template):
            print(f"set_sheet_template={set_template(str(SHEET_FORMAT))}")
        if callable(reload_template):
            print(f"reload_sheet_template={reload_template(True)}")
    except Exception as exc:
        print(f"set_sheet_template error={exc}")

    delete_sheet = getattr(drawing, "DeleteSheet", None)
    if callable(delete_sheet):
        current_sheet_names = get_com_member(drawing, "GetSheetNames") or ()
        for sheet_name in current_sheet_names:
            if sheet_name == TARGET_SHEET:
                continue
            try:
                result = delete_sheet(sheet_name)
                print(f"delete_sheet name={sheet_name} result={result}")
            except Exception as exc:
                print(f"delete_sheet name={sheet_name} error={exc}")
    return created_target_sheet


def set_white_drawing_background(sw) -> None:
    for pref in (SYSTEM_COLOR_DRAWINGS_PAPER, SYSTEM_COLOR_DRAWINGS_BACKGROUND):
        try:
            sw.SetUserPreferenceIntegerValue(pref, WHITE_RGB)
            print(f"set_color pref={pref} value={WHITE_RGB}")
        except Exception as exc:
            print(f"set_color pref={pref} error={exc}")


def ensure_mmgs_units(model) -> None:
    try:
        model.SetUnits(*MMGS_UNITS)
        print(f"set_units={MMGS_UNITS}")
    except Exception as exc:
        print(f"set_units error={exc}")
    try:
        model.SetUserPreferenceIntegerValue(22, 0)
        print("set_dim_units=mm")
    except Exception as exc:
        print(f"set_dim_units error={exc}")


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
            print(f"set_toggle pref={pref} value={value}")
        except Exception as exc:
            print(f"set_toggle pref={pref} error={exc}")


def set_title_block_properties(model) -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    prop_mgr = model.Extension.CustomPropertyManager("")
    properties = {
        "Title": DRAWING_TITLE,
        "Description": "ISO guideline drawing attempt",
        "Number": DRAWING_NUMBER,
        "Revision": DRAWING_REVISION,
        "DrawnBy": "Codex",
        "CheckedBy": "Codex",
        "ApprovedBy": "N/A",
        "Date": today,
        "Scale": "AS NOTED",
        "SheetSize": "A3",
        "Units": "MMGS",
        "Material": "UNSPECIFIED",
        "Mass": "N/A",
        "Projection": "FIRST ANGLE",
        "GeneralTolerance": "ISO 2768-mK",
        "Standards": "ISO 8015",
    }

    for key, value in properties.items():
        try:
            result = prop_mgr.Add3(key, 30, value, 1)
            print(f"property={key} result={result}")
        except Exception as exc:
            print(f"property={key} error={exc}")


def add_general_notes(model) -> None:
    notes = [
        ("UNLESS OTHERWISE SPECIFIED: ALL DIMENSIONS IN mm", 0.090, 0.078),
        ("GENERAL TOLERANCES: ISO 2768-mK  |  ISO 8015", 0.090, 0.072),
    ]
    for text, x_m, y_m in notes:
        add_note_with_position(model, text, x_m, y_m)


def add_note_with_position(model, text: str, x_m: float, y_m: float) -> None:
    try:
        note = model.InsertNote(text)
        if note is None:
            print(f"note=False text={text}")
            return
        note.SetTextPoint(x_m, y_m, 0.0)
        print(f"note=True text={text}")
    except Exception as exc:
        print(f"note=False text={text} error={exc}")


def apply_view_style(view, display_mode: int, *, show_shaded_edges: bool = False) -> None:
    if view is None:
        return
    try:
        view.SetDisplayMode3(False, display_mode, False, show_shaded_edges)
        print(f"set_display_mode={display_mode} shaded_edges={show_shaded_edges}")
    except Exception as exc:
        print(f"set_display_mode error={exc}")


def set_view_layout(view, position, scale: float, display_mode: int, *, show_shaded_edges: bool = False) -> None:
    if view is None:
        return
    try:
        view.UseSheetScale = False
    except Exception:
        pass
    try:
        view.ScaleDecimal = scale
    except Exception as exc:
        print(f"set_scale error={exc}")
    try:
        view.Position = VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            (position[0], position[1], 0.0),
        )
    except Exception as exc:
        print(f"set_position error={exc}")
    apply_view_style(view, display_mode, show_shaded_edges=show_shaded_edges)


def clear_view_dimensions(view, drawing) -> None:
    annotations = []
    current = get_first_display_dimension(view)
    while current is not None:
        annotation = get_com_member(current, "GetAnnotation")
        if annotation is not None:
            annotations.append(annotation)
        current = get_next_display_dimension(view, current)

    if not annotations:
        return

    try:
        drawing.ClearSelection2(True)
    except Exception:
        pass

    selected = 0
    for index, annotation in enumerate(annotations):
        try:
            if annotation.Select2(index > 0, 0):
                selected += 1
        except Exception as exc:
            print(f"select_dimension_for_delete error={exc}")

    if selected:
        try:
            drawing.EditDelete()
            print(f"clear_view_dimensions deleted={selected}")
        except Exception as exc:
            print(f"clear_view_dimensions error={exc}")


def get_sheet_view_by_name(drawing, view_name: str):
    sheet = get_current_sheet(drawing)
    views = get_sheet_views(sheet)
    for view in views:
        if getattr(view, "Name", "") == view_name:
            return view
    return None


def clear_sheet_views(drawing) -> None:
    sheet = get_current_sheet(drawing)
    for view in get_sheet_views(sheet):
        view_name = getattr(view, "Name", "")
        if not view_name:
            continue
        feat = drawing.FeatureByName(view_name)
        if feat is None:
            continue
        try:
            drawing.ClearSelection2(True)
        except Exception:
            pass
        try:
            if feat.Select2(False, 0):
                drawing.EditDelete()
                print(f"delete_view name={view_name}")
        except Exception as exc:
                print(f"delete_view name={view_name} error={exc}")


def count_view_dimensions(view) -> int:
    if view is None:
        return 0

    total = 0
    current = get_optional_member(view, "GetFirstDisplayDimension5")
    if current is None:
        current = get_first_display_dimension(view)

    while current is not None:
        total += 1
        next_dim = get_optional_member(view, "GetNextDisplayDimension5", current)
        if next_dim is None:
            next_dim = get_next_display_dimension(view, current)
        current = next_dim
    return total


def count_part_dimxpert_annotations(part_model) -> tuple[int, int]:
    ensure_com_modules()
    typed_part = wrap_dispatch(part_model, SWMOD.IModelDoc2, "IModelDoc2")
    current = typed_part.GetFirstAnnotation2()
    total = 0
    dimxpert_total = 0

    while current is not None:
        annotation = wrap_dispatch(current, SWMOD.IAnnotation, "IAnnotation")
        total += 1
        if bool(getattr(annotation, "IsDimXpert", False)):
            dimxpert_total += 1
        current = annotation.GetNext3()

    return total, dimxpert_total


def try_dimxpert_auto_dimension(part_model) -> list[tuple[str, object]]:
    ensure_com_modules()
    results: list[tuple[str, object]] = []

    try:
        typed_extension = wrap_dispatch(part_model.Extension, SWMOD.IModelDocExtension, "IModelDocExtension")
        configuration_name = part_model.ConfigurationManager.ActiveConfiguration.Name
        manager = typed_extension.DimXpertManager(configuration_name, True)
        dimxpert_part = wrap_dispatch(manager.DimXpertPart, SWDXMOD.IDimXpertPart, "IDimXpertPart")
    except Exception as exc:
        trace(f"dimxpert:setup_failed error={exc}")
        print(f"dimxpert_setup=False error={exc}")
        return [("setup", exc)]

    trace(f"dimxpert:schema={getattr(manager, 'SchemaName', '')}")
    print(f"dimxpert_schema={getattr(manager, 'SchemaName', '')}")

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
            trace(
                "dimxpert:auto_dimension_failed "
                f"label={label} filters={feature_filters} scope_all={scope_all} error={exc}"
            )
            print(
                "dimxpert_auto_dimension "
                f"label={label} filters={feature_filters} scope_all={scope_all} result={exc}"
            )
            results.append((label, result))
            break
        else:
            results.append((label, result))
            trace(
                "dimxpert:auto_dimension "
                f"label={label} filters={feature_filters} scope_all={scope_all} result={result}"
            )
            print(
                "dimxpert_auto_dimension "
                f"label={label} filters={feature_filters} scope_all={scope_all} result={result}"
            )
    try:
        total_annotations, dimxpert_annotations = count_part_dimxpert_annotations(part_model)
    except Exception as exc:
        trace(f"dimxpert:annotation_count_failed error={exc}")
        print(f"dimxpert_annotations=False error={exc}")
        return results
    trace(
        "dimxpert:annotation_count "
        f"total={total_annotations} dimxpert={dimxpert_annotations}"
    )
    print(f"dimxpert_annotations total={total_annotations} dimxpert={dimxpert_annotations}")
    return results


def ensure_views(drawing, model_path: str):
    # Manual first-angle layout:
    # top view below front, right view to the left of front.
    clear_sheet_views(drawing)

    front = drawing.CreateDrawViewFromModelView3(model_path, "*Front", *VIEW_POSITIONS["front"], 0)
    top = drawing.CreateDrawViewFromModelView3(model_path, "*Top", *VIEW_POSITIONS["top"], 0)
    right = drawing.CreateDrawViewFromModelView3(model_path, "*Right", *VIEW_POSITIONS["right"], 0)
    iso = drawing.CreateDrawViewFromModelView3(model_path, "*Isometric", *VIEW_POSITIONS["iso"], 0)

    print(f"add_front_view={front is not None}")
    print(f"add_top_view={top is not None}")
    print(f"add_right_view={right is not None}")
    print(f"add_isometric_view={iso is not None}")

    for name, view in (("front", front), ("top", top), ("right", right)):
        set_view_layout(view, VIEW_POSITIONS[name], ORTHO_SCALE, DISPLAY_MODE_HIDDEN_LINES_VISIBLE)

    set_view_layout(
        iso,
        VIEW_POSITIONS["iso"],
        ISO_SCALE,
        DISPLAY_MODE_SHADED_WITH_EDGES,
        show_shaded_edges=True,
    )

    return {
        "front": front,
        "top": top,
        "right": right,
        "iso": iso,
    }


def try_auto_dimension(drawing, views) -> None:
    if not ENABLE_AUTO_DIMENSIONS:
        print("auto_dimension skipped")
        return

    marked_import_result = None
    all_dimension_import_result = None

    try:
        marked_import_result = drawing.InsertModelAnnotations3(
            IMPORT_MODEL_ITEMS_ENTIRE_MODEL,
            INSERT_DIMENSIONS_MARKED_FOR_DRAWING,
            False,
            True,
            False,
            False,
        )
        print(f"insert_marked_dimensions={marked_import_result}")
        trace(f"insert_marked_dimensions={marked_import_result}")
    except Exception as exc:
        print(f"insert_marked_dimensions=False error={exc}")
        trace(f"insert_marked_dimensions_failed error={exc}")

    try:
        all_dimension_import_result = drawing.InsertModelAnnotations4(
            IMPORT_MODEL_ITEMS_ENTIRE_MODEL,
            INSERT_DIMENSIONS + INSERT_DIMENSIONS_MARKED_FOR_DRAWING + INSERT_DIMENSIONS_NOT_MARKED_FOR_DRAWING,
            False,
            True,
            False,
            False,
            True,
            False,
        )
        print(f"insert_all_dimension_annotations={all_dimension_import_result}")
        trace(f"insert_all_dimension_annotations={all_dimension_import_result}")
    except Exception as exc:
        print(f"insert_all_dimension_annotations=False error={exc}")
        trace(f"insert_all_dimension_annotations_failed error={exc}")

    try:
        for key in ("front", "top", "right"):
            view = views.get(key)
            before_count = count_view_dimensions(view)
            view_name = getattr(view, "Name", "")
            if before_count > 0 and key == "front":
                print(f"auto_dimension_skip view={view_name} reason=existing_dims count={before_count}")
                continue

            feat = drawing.FeatureByName(view_name)
            if feat is None:
                print(f"auto_dimension_view={view_name} missing")
                continue

            selected = feat.Select2(False, 0)
            print(f"select_view_for_dimension {view_name}={bool(selected)} before={before_count}")
            result = drawing.AutoDimension(
                AUTO_DIM_ENTITIES_ALL,
                AUTO_DIM_SCHEME_ORDINATE,
                AUTO_DIM_HORIZONTAL_PLACEMENT_ABOVE,
                AUTO_DIM_SCHEME_ORDINATE,
                AUTO_DIM_VERTICAL_PLACEMENT_RIGHT,
            )
            after_count = count_view_dimensions(view)
            print(
                f"auto_dimension {view_name} "
                f"scheme=ordinate result={result} before={before_count} after={after_count}"
            )
            trace(
                f"auto_dimension view={view_name} result={result} "
                f"before={before_count} after={after_count}"
            )
            try:
                drawing.ClearSelection2(True)
            except Exception:
                pass
    except Exception as exc:
        print(f"auto_dimension=False error={exc}")


def normalize_dimension_display(views) -> None:
    try:
        total = 0
        for view in views.values():
            if view is None:
                continue
            current = get_first_display_dimension(view)
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
                    total += 1
                except Exception as exc:
                    print(f"normalize_dimension error={exc}")
                current = get_next_display_dimension(view, current)
        print(f"normalize_dimension_display count={total}")
    except Exception as exc:
        print(f"normalize_dimension_display=False error={exc}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    TRACE_PATH.write_text("", encoding="utf-8")
    ensure_com_modules()

    if not SAMPLE_PART.exists():
        raise FileNotFoundError(f"Missing sample part: {SAMPLE_PART}")

    sw = None
    part_model = None
    drawing_model = None
    working_part_path = SAMPLE_PART

    try:
        trace("main:connect_solidworks")
        sw, _ = connect_solidworks(wait_seconds=1)
        trace("main:connected")
        prepare_output_paths(sw)
        working_part_path = recreate_working_part_copy(sw)

        trace("main:open_part")
        part_model = open_document_safe(sw, str(working_part_path), read_only=False)
        trace(f"main:open_part_done success={part_model is not None}")
        print(f"open_part={part_model is not None}")
        trace("main:dimxpert_auto_dimension")
        try_dimxpert_auto_dimension(part_model)
        trace("main:save_working_part")
        save_part_ok = save_document_safe(part_model, str(working_part_path))
        print(f"save_working_part={save_part_ok}")

        trace("main:set_background")
        set_white_drawing_background(sw)
        drawing_model, is_new_drawing = open_or_create_drawing(sw)
        drawing = wrap_dispatch(drawing_model, SWMOD.IDrawingDoc, "IDrawingDoc")

        trace("main:set_sheet")
        created_target_sheet = set_active_sheet_a3_first_angle(drawing)
        trace("main:set_units")
        ensure_mmgs_units(drawing_model)
        trace("main:set_dimension_preferences")
        set_dimension_preferences(drawing_model)
        trace("main:ensure_views")
        views = ensure_views(drawing, str(working_part_path))
        trace("main:title_block")
        set_title_block_properties(drawing_model)
        if is_new_drawing or created_target_sheet:
            trace("main:notes")
            add_general_notes(drawing_model)
        trace("main:auto_dimension")
        try_auto_dimension(drawing, views)

        trace("main:rebuild")
        drawing_model.ForceRebuild3(False)
        trace("main:normalize_dimensions")
        normalize_dimension_display(views)
        drawing_model.ForceRebuild3(False)
        drawing_model.ViewZoomtofit2()

        trace("main:save_drawing")
        save_ok = save_document_safe(drawing_model, str(DRAWING_PATH))
        trace(f"main:save_drawing_done success={save_ok}")
        print(f"save_drawing={save_ok}")
        trace("main:export_pdf")
        pdf_ok = export_pdf(sw, drawing_model, PDF_PATH, sheet_names=(TARGET_SHEET,))
        trace(f"main:export_pdf_done success={pdf_ok}")
        print(f"pdf_exists={PDF_PATH.exists()} save_pdf={pdf_ok}")
        trace("main:export_preview_png")
        png_ok = export_preview_png(drawing_model, PREVIEW_PNG_PATH)
        trace(f"main:export_preview_png_done success={png_ok}")
        print(f"preview_png_exists={PREVIEW_PNG_PATH.exists()} save_preview_png={png_ok}")
    finally:
        trace("main:cleanup")
        if sw is not None:
            close_model(sw, drawing_model)
            close_model(sw, part_model)
        trace("main:cleanup_done")


if __name__ == "__main__":
    main()
