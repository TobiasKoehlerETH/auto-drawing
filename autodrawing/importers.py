from __future__ import annotations

import re
from collections import Counter
from math import acos
from pathlib import Path

from .contracts import BoundingBox3D, CanonicalCadModel, ComponentNode, Diagnostic, FeatureHint, ImportedMeshPayload, Point3D, ShapeSummary, SourceEdge3D, SourceTriangle3D
from .standards import SUPPORTED_STEP_SUFFIXES

FLOAT_RE = r"[-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?"


class StepImportError(RuntimeError):
    pass


class StepImportService:
    def import_file(self, path: str | Path) -> CanonicalCadModel:
        file_path = Path(path)
        if file_path.suffix.lower() not in SUPPORTED_STEP_SUFFIXES:
            raise StepImportError(f"Unsupported input type: {file_path.suffix}")
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        return self.import_text(text, source_name=file_path.name)

    def import_text(self, text: str, source_name: str = "uploaded.step") -> CanonicalCadModel:
        stripped = text.strip()
        if "FILE_SCHEMA" not in stripped and "ISO-10303-21" not in stripped:
            raise StepImportError("Input does not look like a STEP file")

        diagnostics: list[Diagnostic] = []
        units = self._detect_units(stripped, diagnostics)
        product_names = self._extract_product_names(stripped)
        bbox = self._extract_bbox(stripped, diagnostics)
        feature_hints = self._extract_feature_hints(stripped, bbox)
        source_edges = self._extract_source_edges(stripped)
        if not source_edges:
            source_edges = self._bbox_edges(bbox)

        primary_name = product_names[0] if product_names else Path(source_name).stem
        shape = ShapeSummary(
            id="shape-1",
            name=primary_name,
            kind="part",
            bounding_box=bbox,
            principal_axes=self._principal_axes(bbox),
            feature_hints=feature_hints,
            source_edges=source_edges,
            source_triangles=[],
            source_ids=product_names[1:],
        )

        root = ComponentNode(
            id="component-root",
            name=primary_name,
            shape_id=shape.id,
            quantity=1,
            children=[
                ComponentNode(
                    id=f"component-{index + 1}",
                    name=name,
                    shape_id=shape.id,
                    quantity=1,
                    repeated_group_id=(name.lower().replace(" ", "-") if count > 1 else None),
                )
                for index, (name, count) in enumerate(Counter(product_names).items())
            ]
            if product_names
            else [],
        )

        metadata = {"source_name": source_name, "detected_products": ", ".join(product_names[:5])}
        if not product_names:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="missing-product-name",
                    message="No PRODUCT entities were found; using file name as the model name.",
                )
            )

        return CanonicalCadModel(
            source_name=source_name,
            units=units,
            metadata=metadata,
            diagnostics=diagnostics,
            shapes=[shape],
            root_component=root,
            gdandt_notes=self._extract_gdandt_notes(stripped),
        )

    def import_occt_meshes(
        self,
        meshes: list[ImportedMeshPayload],
        *,
        source_name: str = "uploaded.step",
        units: str = "mm",
    ) -> CanonicalCadModel:
        diagnostics: list[Diagnostic] = []
        bbox = self._bbox_from_meshes(meshes, diagnostics)
        feature_hints = self._extract_feature_hints_from_bbox(bbox)
        source_edges = self._extract_feature_edges_from_meshes(meshes) or self._bbox_edges(bbox)
        source_triangles = self._extract_triangles_from_meshes(meshes)
        primary_name = Path(source_name).stem

        shape = ShapeSummary(
            id="shape-1",
            name=primary_name,
            kind="part",
            bounding_box=bbox,
            principal_axes=self._principal_axes(bbox),
            feature_hints=feature_hints,
            source_edges=source_edges,
            source_triangles=source_triangles,
        )
        root = ComponentNode(id="component-root", name=primary_name, shape_id=shape.id, quantity=1)

        return CanonicalCadModel(
            source_name=source_name,
            units=units,  # type: ignore[arg-type]
            metadata={"source_name": source_name, "mesh_count": str(len(meshes))},
            diagnostics=diagnostics,
            shapes=[shape],
            root_component=root,
            gdandt_notes=[],
        )

    def _detect_units(self, text: str, diagnostics: list[Diagnostic]) -> str:
        if ".MILLI." in text and ".METRE." in text:
            return "mm"
        if ".CENTI." in text and ".METRE." in text:
            return "cm"
        if ".METRE." in text:
            return "m"
        if ".INCH." in text:
            return "in"
        diagnostics.append(
            Diagnostic(
                severity="warning",
                code="units-defaulted",
                message="No explicit STEP unit was detected; defaulting to millimeters.",
            )
        )
        return "mm"

    def _extract_product_names(self, text: str) -> list[str]:
        return [match.group(1) for match in re.finditer(r"PRODUCT\('([^']+)'", text)]

    def _extract_bbox(self, text: str, diagnostics: list[Diagnostic]) -> BoundingBox3D:
        coords: list[tuple[float, float, float]] = []
        for line in text.splitlines():
            if "CARTESIAN_POINT" not in line:
                continue
            values = re.findall(FLOAT_RE, line)
            if len(values) >= 3:
                coords.append((float(values[-3]), float(values[-2]), float(values[-1])))
        if not coords:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="bbox-fallback",
                    message="No explicit CARTESIAN_POINT entities were found; using a 100 x 60 x 40 mm fallback box.",
                )
            )
            return BoundingBox3D.from_extents(0.0, 0.0, 0.0, 100.0, 60.0, 40.0)

        xs = [x for x, _, _ in coords]
        ys = [y for _, y, _ in coords]
        zs = [z for _, _, z in coords]
        if max(xs) == min(xs):
            xs.extend([0.0, 100.0])
        if max(ys) == min(ys):
            ys.extend([0.0, 60.0])
        if max(zs) == min(zs):
            zs.extend([0.0, 40.0])
        return BoundingBox3D.from_extents(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def _extract_feature_hints(self, text: str, bbox: BoundingBox3D) -> list[FeatureHint]:
        hints: list[FeatureHint] = []
        circle_count = len(re.findall(r"CIRCLE\(", text))
        if circle_count:
            radius = max(min(bbox.size.x, bbox.size.y, bbox.size.z) / 10.0, 2.0)
            hints.append(
                FeatureHint(
                    id="hint-hole-1",
                    kind="circular-hole",
                    axis=bbox.longest_axis,
                    center=Point3D(
                        x=bbox.min.x + bbox.size.x / 2.0,
                        y=bbox.min.y + bbox.size.y / 2.0,
                        z=bbox.min.z + bbox.size.z / 2.0,
                    ),
                    radius=radius,
                )
            )
        if circle_count >= 4:
            hints.append(
                FeatureHint(
                    id="hint-pattern-1",
                    kind="hole-pattern",
                    axis=bbox.longest_axis,
                    count=circle_count,
                    note="Detected repeated circular features in the STEP source.",
                )
            )
        if "CYLINDRICAL_SURFACE" in text:
            hints.append(
                FeatureHint(
                    id="hint-cylinder-axis",
                    kind="cylindrical-axis",
                    axis=bbox.longest_axis,
                    center=Point3D(
                        x=bbox.min.x + bbox.size.x / 2.0,
                        y=bbox.min.y + bbox.size.y / 2.0,
                        z=bbox.min.z + bbox.size.z / 2.0,
                    ),
                )
            )
        if bbox.size.z < max(bbox.size.x, bbox.size.y) * 0.35:
            hints.append(
                FeatureHint(
                    id="hint-section-candidate",
                    kind="section-candidate",
                    axis="z",
                    note="Thin wall geometry suggests a useful section view.",
                )
            )
        return hints

    def _extract_feature_hints_from_bbox(self, bbox: BoundingBox3D) -> list[FeatureHint]:
        hints: list[FeatureHint] = []
        if bbox.size.z < max(bbox.size.x, bbox.size.y) * 0.35:
            hints.append(
                FeatureHint(
                    id="hint-section-candidate",
                    kind="section-candidate",
                    axis="z",
                    note="Thin wall geometry suggests a useful section view.",
                )
            )
        return hints

    def _bbox_from_meshes(self, meshes: list[ImportedMeshPayload], diagnostics: list[Diagnostic]) -> BoundingBox3D:
        coords: list[tuple[float, float, float]] = []
        for mesh in meshes:
            values = mesh.attributes.position.array
            for index in range(0, len(values), 3):
                if index + 2 >= len(values):
                    break
                coords.append((float(values[index]), float(values[index + 1]), float(values[index + 2])))
        if not coords:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code="bbox-fallback",
                    message="Imported mesh contained no vertices; using a 100 x 60 x 40 mm fallback box.",
                )
            )
            return BoundingBox3D.from_extents(0.0, 0.0, 0.0, 100.0, 60.0, 40.0)

        xs = [x for x, _, _ in coords]
        ys = [y for _, y, _ in coords]
        zs = [z for _, _, z in coords]
        return BoundingBox3D.from_extents(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

    def _extract_source_edges(self, text: str) -> list[SourceEdge3D]:
        points: dict[str, Point3D] = {}
        vertex_points: dict[str, str] = {}
        curve_kinds: dict[str, str] = {}

        for match in re.finditer(r"#(\d+)\s*=\s*([A-Z0-9_]+)\s*\((.*?)\)\s*;", text, re.DOTALL):
            entity_id, entity_type, body = match.groups()
            ref = f"#{entity_id}"
            if entity_type == "CARTESIAN_POINT":
                values = re.findall(FLOAT_RE, body)
                if len(values) >= 3:
                    points[ref] = Point3D(x=float(values[-3]), y=float(values[-2]), z=float(values[-1]))
            elif entity_type == "VERTEX_POINT":
                refs = re.findall(r"#\d+", body)
                if refs:
                    vertex_points[ref] = refs[-1]
            elif entity_type in {"LINE", "CIRCLE"}:
                curve_kinds[ref] = entity_type.lower()

        edges: list[SourceEdge3D] = []
        seen: set[tuple[tuple[float, float, float], tuple[float, float, float]]] = set()
        for match in re.finditer(r"#(\d+)\s*=\s*EDGE_CURVE\s*\((.*?)\)\s*;", text, re.DOTALL):
            entity_id, body = match.groups()
            refs = re.findall(r"#\d+", body)
            if len(refs) < 3:
                continue
            start = points.get(vertex_points.get(refs[0], ""))
            end = points.get(vertex_points.get(refs[1], ""))
            if not start or not end:
                continue
            start_key = self._point_key(start)
            end_key = self._point_key(end)
            if start_key == end_key:
                continue
            dedupe_key = tuple(sorted([start_key, end_key]))  # type: ignore[arg-type]
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            curve_kind = curve_kinds.get(refs[2], "curve")
            edges.append(
                SourceEdge3D(
                    id=f"step-edge-{entity_id}",
                    start=start,
                    end=end,
                    curve_kind="circle" if curve_kind == "circle" else ("line" if curve_kind == "line" else "curve"),
                )
            )
        return edges

    def _bbox_edges(self, bbox: BoundingBox3D) -> list[SourceEdge3D]:
        min_pt = bbox.min
        max_pt = bbox.max
        corners = {
            "000": Point3D(x=min_pt.x, y=min_pt.y, z=min_pt.z),
            "100": Point3D(x=max_pt.x, y=min_pt.y, z=min_pt.z),
            "110": Point3D(x=max_pt.x, y=max_pt.y, z=min_pt.z),
            "010": Point3D(x=min_pt.x, y=max_pt.y, z=min_pt.z),
            "001": Point3D(x=min_pt.x, y=min_pt.y, z=max_pt.z),
            "101": Point3D(x=max_pt.x, y=min_pt.y, z=max_pt.z),
            "111": Point3D(x=max_pt.x, y=max_pt.y, z=max_pt.z),
            "011": Point3D(x=min_pt.x, y=max_pt.y, z=max_pt.z),
        }
        pairs = [
            ("000", "100"),
            ("100", "110"),
            ("110", "010"),
            ("010", "000"),
            ("001", "101"),
            ("101", "111"),
            ("111", "011"),
            ("011", "001"),
            ("000", "001"),
            ("100", "101"),
            ("110", "111"),
            ("010", "011"),
        ]
        return [
            SourceEdge3D(id=f"bbox-edge-{start}-{end}", start=corners[start], end=corners[end], curve_kind="line")
            for start, end in pairs
        ]

    def _extract_feature_edges_from_meshes(self, meshes: list[ImportedMeshPayload]) -> list[SourceEdge3D]:
        edge_records: dict[tuple[tuple[float, float, float], tuple[float, float, float]], dict[str, object]] = {}
        for mesh_index, mesh in enumerate(meshes):
            positions = mesh.attributes.position.array
            if not positions:
                continue
            points = [
                Point3D(x=float(positions[index]), y=float(positions[index + 1]), z=float(positions[index + 2]))
                for index in range(0, len(positions) - 2, 3)
            ]
            indices = mesh.index.array or list(range(len(points)))
            for tri_offset in range(0, len(indices) - 2, 3):
                i0, i1, i2 = indices[tri_offset], indices[tri_offset + 1], indices[tri_offset + 2]
                if max(i0, i1, i2) >= len(points):
                    continue
                p0, p1, p2 = points[i0], points[i1], points[i2]
                normal = self._triangle_normal(p0, p1, p2)
                if normal is None:
                    continue
                for start_idx, end_idx in ((i0, i1), (i1, i2), (i2, i0)):
                    start = points[start_idx]
                    end = points[end_idx]
                    start_key = self._point_key(start)
                    end_key = self._point_key(end)
                    if start_key == end_key:
                        continue
                    key = tuple(sorted([start_key, end_key]))  # type: ignore[arg-type]
                    record = edge_records.setdefault(
                        key,
                        {
                            "id": f"mesh-{mesh_index}-{len(edge_records) + 1}",
                            "start": start if start_key <= end_key else end,
                            "end": end if start_key <= end_key else start,
                            "normals": [],
                        },
                    )
                    normals = record["normals"]
                    if isinstance(normals, list):
                        normals.append(normal)

        feature_edges: list[SourceEdge3D] = []
        for record in edge_records.values():
            normals = record["normals"]
            if not isinstance(normals, list) or not normals:
                continue
            keep_edge = len(normals) == 1
            if not keep_edge:
                base = normals[0]
                for candidate in normals[1:]:
                    if self._normal_angle_degrees(base, candidate) >= 30.0:
                        keep_edge = True
                        break
            if keep_edge:
                feature_edges.append(
                    SourceEdge3D(
                        id=str(record["id"]),
                        start=record["start"],  # type: ignore[arg-type]
                        end=record["end"],  # type: ignore[arg-type]
                        curve_kind="line",
                        adjacent_normals=[
                            Point3D(x=normal[0], y=normal[1], z=normal[2])
                            for normal in self._unique_normals(normals)
                        ],
                    )
                )
        return feature_edges

    def _extract_triangles_from_meshes(self, meshes: list[ImportedMeshPayload]) -> list[SourceTriangle3D]:
        triangles: list[SourceTriangle3D] = []
        for mesh_index, mesh in enumerate(meshes):
            positions = mesh.attributes.position.array
            if not positions:
                continue
            points = [
                Point3D(x=float(positions[index]), y=float(positions[index + 1]), z=float(positions[index + 2]))
                for index in range(0, len(positions) - 2, 3)
            ]
            indices = mesh.index.array or list(range(len(points)))
            for tri_offset in range(0, len(indices) - 2, 3):
                i0, i1, i2 = indices[tri_offset], indices[tri_offset + 1], indices[tri_offset + 2]
                if max(i0, i1, i2) >= len(points):
                    continue
                triangles.append(
                    SourceTriangle3D(
                        id=f"mesh-triangle-{mesh_index}-{tri_offset // 3}",
                        a=points[i0],
                        b=points[i1],
                        c=points[i2],
                    )
                )
        return triangles

    def _point_key(self, point: Point3D) -> tuple[float, float, float]:
        return (round(point.x, 6), round(point.y, 6), round(point.z, 6))

    def _triangle_normal(self, a: Point3D, b: Point3D, c: Point3D) -> tuple[float, float, float] | None:
        ab = (b.x - a.x, b.y - a.y, b.z - a.z)
        ac = (c.x - a.x, c.y - a.y, c.z - a.z)
        nx = ab[1] * ac[2] - ab[2] * ac[1]
        ny = ab[2] * ac[0] - ab[0] * ac[2]
        nz = ab[0] * ac[1] - ab[1] * ac[0]
        length = (nx * nx + ny * ny + nz * nz) ** 0.5
        if length <= 1e-9:
            return None
        return (nx / length, ny / length, nz / length)

    def _normal_angle_degrees(self, a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
        dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
        return acos(dot) * 180.0 / 3.141592653589793

    def _unique_normals(self, normals: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
        unique: list[tuple[float, float, float]] = []
        for candidate in normals:
            if any(self._normal_angle_degrees(candidate, existing) < 1.0 for existing in unique):
                continue
            unique.append(candidate)
        return unique

    def _extract_gdandt_notes(self, text: str) -> list[str]:
        notes: list[str] = []
        if "GEOMETRIC_TOLERANCE" in text:
            notes.append("STEP source includes geometric tolerance entities.")
        if "DIMENSIONAL_LOCATION" in text or "DIMENSIONAL_SIZE" in text:
            notes.append("STEP source includes PMI dimension entities.")
        return notes

    def _principal_axes(self, bbox: BoundingBox3D) -> list[str]:
        axes = [("x", bbox.size.x), ("y", bbox.size.y), ("z", bbox.size.z)]
        return [name for name, _ in sorted(axes, key=lambda item: item[1], reverse=True)]
