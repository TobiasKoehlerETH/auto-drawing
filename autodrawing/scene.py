from __future__ import annotations

from .contracts import (
    Bounds2D,
    DrawingDocument,
    PipelineBundle,
    Point2D,
    ProjectionBundle,
    SceneGraph,
    SceneItem,
)
from .standards import PROJECTION_SYMBOL_BOUNDS_MM, TITLE_BLOCK_BOUNDS_MM
from .view_planner import placed_bounds


DIMENSION_TEXT_OFFSET_MM = 3.0
RADIAL_TEXT_GAP_MM = 3.0


class SceneGraphService:
    def build_scene(self, document: DrawingDocument, projection: ProjectionBundle) -> SceneGraph:
        use_exact_template = bool(document.page_template.source_path and document.page_template.svg_source.strip())
        layers = {  # type: ignore[var-annotated]
            "frame": [],
            "titleBlock": [],
            "viewGeometryVisible": [],
            "viewGeometryHidden": [],
            "sectionHatch": [],
            "centerlines": [],
            "dimensions": [],
            "notes": [],
            "bom": [],
            "selectionOverlay": [],
        }

        if not use_exact_template:
            layers["frame"].append(
                SceneItem(
                    id="sheet-frame",
                    layer="frame",
                    kind="rect",
                    x=5.0,
                    y=5.0,
                    width=document.sheet.width_mm - 10.0,
                    height=document.sheet.height_mm - 10.0,
                    classes=["sheet-frame"],
                )
            )

            layers["titleBlock"].extend(self._template_items())
            for field in document.title_block_fields:
                layers["titleBlock"].append(
                    SceneItem(
                        id=field.id,
                        layer="titleBlock",
                        kind="text",
                        x=field.placement.x_mm,
                        y=field.placement.y_mm,
                        text=f"{field.label}: {field.value}",
                        classes=["title-block-field"],
                        meta={"target_id": field.id},
                    )
                )

        geometry_by_id = {geometry.id: geometry for geometry in projection.views}
        for view in document.views:
            geometry = geometry_by_id[view.geometry_id]
            bounds = placed_bounds(geometry.bounds, view.placement)
            group_classes = [f"view-{view.kind}"]
            view_meta = {
                "view_id": view.id,
                "view_kind": view.kind,
                "view_label": view.label,
                "selection_bounds": bounds.model_dump(mode="json"),
            }

            if geometry.kind == "isometric":
                layers["viewGeometryVisible"].extend(self._isometric_shaded_faces(geometry, view, view_meta))

            for edge in geometry.visible_edges + geometry.smooth_edges:
                layers["viewGeometryVisible"].append(
                    self._path_item(
                        edge.id,
                        "viewGeometryVisible",
                        edge.points,
                        view.placement.x_mm,
                        view.placement.y_mm,
                        view.placement.scale,
                        classes=group_classes + ([edge.style_role] if edge.style_role != "visible" else []),
                        meta=view_meta,
                        group_id=view.id,
                    )
                )
            for circle in geometry.circles:
                layers["viewGeometryVisible"].append(
                    SceneItem(
                        id=circle.id,
                        layer="viewGeometryVisible",
                        kind="circle",
                        group_id=view.id,
                        x=view.placement.x_mm + circle.center.x * view.placement.scale,
                        y=view.placement.y_mm - circle.center.y * view.placement.scale,
                        radius=circle.radius * view.placement.scale,
                        classes=group_classes,
                        meta=view_meta,
                    )
                )
            for arc in geometry.arcs:
                layers["viewGeometryVisible"].append(
                    self._arc_item(arc.id, arc.center.x, arc.center.y, arc.radius, arc.start, arc.end, view, view_meta)
                )
            for edge in geometry.hidden_edges:
                layers["viewGeometryHidden"].append(
                    self._path_item(
                        edge.id,
                        "viewGeometryHidden",
                        edge.points,
                        view.placement.x_mm,
                        view.placement.y_mm,
                        view.placement.scale,
                        classes=group_classes + ["hidden"],
                        meta=view_meta,
                        group_id=view.id,
                    )
                )
            for edge in geometry.centerlines:
                layers["centerlines"].append(
                    self._path_item(
                        edge.id,
                        "centerlines",
                        edge.points,
                        view.placement.x_mm,
                        view.placement.y_mm,
                        view.placement.scale,
                        classes=group_classes + ["centerline"],
                        meta=view_meta,
                        group_id=view.id,
                    )
                )

            layers["notes"].append(
                SceneItem(
                    id=f"{view.id}-label",
                    layer="notes",
                    kind="text",
                    group_id=view.id,
                    x=view.placement.x_mm,
                    y=max(bounds.y_min - 6.0, 10.0),
                    text=view.label,
                    classes=["view-label"],
                    meta={"view_id": view.id},
                )
            )
            if geometry.kind == "isometric":
                layers["notes"].append(
                    SceneItem(
                        id=f"{view.id}-scale",
                        layer="notes",
                        kind="text",
                        group_id=view.id,
                        x=view.placement.x_mm,
                        y=max(bounds.y_min - 12.0, 4.0),
                        text=_format_scale_text(view.placement.scale),
                        classes=["view-label", "view-scale"],
                        meta={"view_id": view.id},
                    )
                )
            layers["selectionOverlay"].append(
                SceneItem(
                    id=f"{view.id}-selection",
                    layer="selectionOverlay",
                    kind="rect",
                    group_id=view.id,
                    x=bounds.x_min,
                    y=bounds.y_min,
                    width=bounds.width,
                    height=bounds.height,
                    classes=["selection-outline"],
                    meta=view_meta,
                )
            )

        for note in document.notes:
            layers["notes"].append(
                SceneItem(
                    id=note.id,
                    layer="notes",
                    kind="text",
                    x=note.placement.x_mm,
                    y=note.placement.y_mm,
                    text=note.text,
                    classes=["note"],
                    meta={"target_id": note.id},
                )
            )

        for dimension in document.dimensions:
            layers["dimensions"].extend(self._dimension_items(dimension))

        return SceneGraph(schema_version="1.0", width_mm=document.sheet.width_mm, height_mm=document.sheet.height_mm, layers=layers)

    def _dimension_items(self, dimension) -> list[SceneItem]:
        geometry = dimension.computed_geometry or {}
        text = dimension.formatted_text or dimension.label
        classes = ["dimension", "dimension-line", dimension.dimension_type.lower()]
        meta = {"target_id": dimension.id, "view_id": dimension.view_id, "dimension_type": dimension.dimension_type}

        if geometry.get("kind") == "linear":
            line_start = geometry.get("line_start", {})
            line_end = geometry.get("line_end", {})
            extension_start = geometry.get("extension_start", {})
            extension_end = geometry.get("extension_end", {})
            label = geometry.get("label", {"x": dimension.placement.x_mm, "y": dimension.placement.y_mm})
            label_point = _linear_label_point(label, line_start, line_end)
            return [
                SceneItem(
                    id=f"{dimension.id}-extension-a",
                    layer="dimensions",
                    kind="path",
                    path_data=_path_from_points(extension_start, line_start),
                    classes=classes + ["extension-line"],
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-extension-b",
                    layer="dimensions",
                    kind="path",
                    path_data=_path_from_points(extension_end, line_end),
                    classes=classes + ["extension-line"],
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-line",
                    layer="dimensions",
                    kind="path",
                    path_data=_path_from_points(line_start, line_end),
                    classes=classes,
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-arrow-a",
                    layer="dimensions",
                    kind="path",
                    path_data=_arrow_path(line_start, line_end),
                    classes=classes + ["arrowhead"],
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-arrow-b",
                    layer="dimensions",
                    kind="path",
                    path_data=_arrow_path(line_end, line_start),
                    classes=classes + ["arrowhead"],
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-text",
                    layer="dimensions",
                    kind="text",
                    x=label_point["x"],
                    y=label_point["y"],
                    text=text,
                    classes=["dimension", "dimension-text", "user-locked" if dimension.placement.user_locked else "auto"],
                    meta=meta,
                ),
            ]

        if geometry.get("kind") == "radial":
            anchor = geometry.get("anchor", {})
            label = geometry.get("label", {"x": dimension.placement.x_mm, "y": dimension.placement.y_mm})
            leader_end = _leader_end_before_label(anchor, label)
            return [
                SceneItem(
                    id=f"{dimension.id}-leader",
                    layer="dimensions",
                    kind="path",
                    path_data=_path_from_points(anchor, leader_end),
                    classes=classes + ["leader-line"],
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-arrow",
                    layer="dimensions",
                    kind="path",
                    path_data=_arrow_path(anchor, leader_end),
                    classes=classes + ["arrowhead"],
                    meta=meta,
                ),
                SceneItem(
                    id=f"{dimension.id}-text",
                    layer="dimensions",
                    kind="text",
                    x=float(label.get("x", dimension.placement.x_mm)),
                    y=float(label.get("y", dimension.placement.y_mm)),
                    text=text,
                    classes=["dimension", "dimension-text", "user-locked" if dimension.placement.user_locked else "auto"],
                    meta=meta,
                ),
            ]

        return [
            SceneItem(
                id=f"{dimension.id}-text",
                layer="dimensions",
                kind="text",
                x=dimension.placement.x_mm,
                y=dimension.placement.y_mm,
                text=text,
                classes=["dimension", "dimension-text"],
                meta=meta,
            )
        ]

    def _template_items(self) -> list[SceneItem]:
        items = [
            SceneItem(
                id="title-block-frame",
                layer="titleBlock",
                kind="rect",
                x=TITLE_BLOCK_BOUNDS_MM["x"],
                y=TITLE_BLOCK_BOUNDS_MM["y"],
                width=TITLE_BLOCK_BOUNDS_MM["width"],
                height=TITLE_BLOCK_BOUNDS_MM["height"],
                classes=["title-block"],
            ),
            SceneItem(
                id="title-block-row-1",
                layer="titleBlock",
                kind="path",
                path_data=f"M {TITLE_BLOCK_BOUNDS_MM['x']:.2f} 252.00 L {TITLE_BLOCK_BOUNDS_MM['x'] + TITLE_BLOCK_BOUNDS_MM['width']:.2f} 252.00",
                classes=["title-block-grid"],
            ),
            SceneItem(
                id="title-block-row-2",
                layer="titleBlock",
                kind="path",
                path_data=f"M {TITLE_BLOCK_BOUNDS_MM['x']:.2f} 262.00 L {TITLE_BLOCK_BOUNDS_MM['x'] + TITLE_BLOCK_BOUNDS_MM['width']:.2f} 262.00",
                classes=["title-block-grid"],
            ),
            SceneItem(
                id="title-block-col-1",
                layer="titleBlock",
                kind="path",
                path_data=f"M 356.00 {TITLE_BLOCK_BOUNDS_MM['y']:.2f} L 356.00 {TITLE_BLOCK_BOUNDS_MM['y'] + TITLE_BLOCK_BOUNDS_MM['height']:.2f}",
                classes=["title-block-grid"],
            ),
            SceneItem(
                id="projection-symbol-frame",
                layer="titleBlock",
                kind="rect",
                x=PROJECTION_SYMBOL_BOUNDS_MM["x"],
                y=PROJECTION_SYMBOL_BOUNDS_MM["y"],
                width=PROJECTION_SYMBOL_BOUNDS_MM["width"],
                height=PROJECTION_SYMBOL_BOUNDS_MM["height"],
                classes=["projection-symbol"],
            ),
        ]
        return items

    def _path_item(
        self,
        item_id: str,
        layer: str,
        points: list[Point2D],
        origin_x: float,
        origin_y: float,
        scale: float,
        *,
        classes: list[str],
        meta: dict[str, object],
        group_id: str | None = None,
    ) -> SceneItem:
        transformed = [self._project_point(point, origin_x, origin_y, scale) for point in points]
        if item_id.endswith("-outline") and len(transformed) >= 5:
            xs = [point.x for point in transformed]
            ys = [point.y for point in transformed]
            bounds = Bounds2D.from_extents(min(xs), min(ys), max(xs), max(ys))
            return SceneItem(
                id=item_id,
                layer=layer,  # type: ignore[arg-type]
                kind="rect",
                x=bounds.x_min,
                y=bounds.y_min,
                width=bounds.width,
                height=bounds.height,
                classes=classes,
                meta=dict(meta),
                group_id=group_id,
            )
        path_data = "M " + " L ".join(f"{point.x:.2f} {point.y:.2f}" for point in transformed)
        return SceneItem(
            id=item_id,
            layer=layer,  # type: ignore[arg-type]
            kind="path",
            path_data=path_data,
            classes=classes,
            meta=dict(meta),
            group_id=group_id,
        )

    def _arc_item(self, item_id: str, cx: float, cy: float, radius: float, start: Point2D, end: Point2D, view, meta) -> SceneItem:
        start_pt = self._project_point(start, view.placement.x_mm, view.placement.y_mm, view.placement.scale)
        end_pt = self._project_point(end, view.placement.x_mm, view.placement.y_mm, view.placement.scale)
        scaled_radius = radius * view.placement.scale
        path_data = (
            f"M {start_pt.x:.2f} {start_pt.y:.2f} "
            f"A {scaled_radius:.2f} {scaled_radius:.2f} 0 0 0 {end_pt.x:.2f} {end_pt.y:.2f}"
        )
        return SceneItem(
            id=item_id,
            layer="viewGeometryVisible",
            kind="path",
            group_id=view.id,
            path_data=path_data,
            classes=[f"view-{view.kind}"],
            meta=dict(meta),
        )

    def _isometric_shaded_faces(self, geometry, view, meta) -> list[SceneItem]:
        edge_points = {edge.id: edge.points for edge in geometry.visible_edges}
        required = ["iso-visible-1", "iso-visible-2", "iso-visible-3", "iso-visible-5", "iso-visible-6", "iso-visible-7", "iso-visible-8"]
        if any(edge_id not in edge_points for edge_id in required):
            return self._isometric_shaded_silhouette(geometry, view, meta)

        vertices = {
            "B": edge_points["iso-visible-1"][0],
            "C": edge_points["iso-visible-1"][1],
            "G": edge_points["iso-visible-2"][1],
            "F": edge_points["iso-visible-3"][1],
            "D": edge_points["iso-visible-5"][0],
            "H": edge_points["iso-visible-6"][0],
            "E": edge_points["iso-visible-7"][0],
        }
        faces = [
            ("iso-face-top", ["E", "F", "G", "H"], "iso-face-top"),
            ("iso-face-right", ["B", "C", "G", "F"], "iso-face-right"),
            ("iso-face-front", ["D", "C", "G", "H"], "iso-face-front"),
        ]
        items: list[SceneItem] = []
        for item_id, vertex_keys, face_class in faces:
            transformed = [self._project_point(vertices[key], view.placement.x_mm, view.placement.y_mm, view.placement.scale) for key in vertex_keys]
            path_data = "M " + " L ".join(f"{point.x:.2f} {point.y:.2f}" for point in transformed) + " Z"
            items.append(
                SceneItem(
                    id=f"{view.id}-{item_id}",
                    layer="viewGeometryVisible",
                    kind="path",
                    group_id=view.id,
                    path_data=path_data,
                    classes=["view-isometric-shaded-face", face_class],
                    meta=dict(meta),
                )
            )
        return items

    def _isometric_shaded_silhouette(self, geometry, view, meta) -> list[SceneItem]:
        points = [point for edge in geometry.visible_edges for point in edge.points]
        if len(points) < 3:
            return []
        hull = self._convex_hull(points)
        if len(hull) < 3:
            return []
        transformed = [self._project_point(point, view.placement.x_mm, view.placement.y_mm, view.placement.scale) for point in hull]
        path_data = "M " + " L ".join(f"{point.x:.2f} {point.y:.2f}" for point in transformed) + " Z"
        return [
            SceneItem(
                id=f"{view.id}-iso-face-silhouette",
                layer="viewGeometryVisible",
                kind="path",
                group_id=view.id,
                path_data=path_data,
                classes=["view-isometric-shaded-face", "iso-face-silhouette"],
                meta=dict(meta),
            )
        ]

    def _convex_hull(self, points: list[Point2D]) -> list[Point2D]:
        unique = sorted({(round(point.x, 6), round(point.y, 6)) for point in points})
        if len(unique) <= 1:
            return [Point2D(x=x, y=y) for x, y in unique]

        def cross(origin: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
            return (a[0] - origin[0]) * (b[1] - origin[1]) - (a[1] - origin[1]) * (b[0] - origin[0])

        lower: list[tuple[float, float]] = []
        for point in unique:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
                lower.pop()
            lower.append(point)

        upper: list[tuple[float, float]] = []
        for point in reversed(unique):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
                upper.pop()
            upper.append(point)

        return [Point2D(x=x, y=y) for x, y in lower[:-1] + upper[:-1]]

    def _project_point(self, point: Point2D, origin_x: float, origin_y: float, scale: float) -> Point2D:
        return Point2D(x=origin_x + point.x * scale, y=origin_y - point.y * scale)


def _format_scale_text(scale: float) -> str:
    rounded = round(scale, 2)
    if rounded <= 0:
        return "Scale 1 : 1"
    if rounded < 1:
        return f"Scale 1 : {round(1 / rounded, 2):g}"
    return f"Scale {rounded:g} : 1"


def _path_from_points(start: dict, end: dict) -> str:
    return f"M {float(start.get('x', 0.0)):.2f} {float(start.get('y', 0.0)):.2f} L {float(end.get('x', 0.0)):.2f} {float(end.get('y', 0.0)):.2f}"


def _linear_label_point(label: dict, line_start: dict, line_end: dict) -> dict[str, float]:
    label_x = float(label.get("x", 0.0))
    label_y = float(label.get("y", 0.0))
    start_x = float(line_start.get("x", label_x))
    start_y = float(line_start.get("y", label_y))
    end_x = float(line_end.get("x", label_x))
    end_y = float(line_end.get("y", label_y))
    dx = end_x - start_x
    dy = end_y - start_y
    length = max((dx * dx + dy * dy) ** 0.5, 0.001)

    if abs(dy) <= abs(dx) * 0.25:
        return {"x": label_x, "y": label_y - DIMENSION_TEXT_OFFSET_MM}
    if abs(dx) <= abs(dy) * 0.25:
        return {"x": label_x + DIMENSION_TEXT_OFFSET_MM, "y": label_y}

    normal_x = -dy / length
    normal_y = dx / length
    return {"x": label_x + normal_x * DIMENSION_TEXT_OFFSET_MM, "y": label_y + normal_y * DIMENSION_TEXT_OFFSET_MM}


def _leader_end_before_label(anchor: dict, label: dict) -> dict[str, float]:
    anchor_x = float(anchor.get("x", 0.0))
    anchor_y = float(anchor.get("y", 0.0))
    label_x = float(label.get("x", anchor_x))
    label_y = float(label.get("y", anchor_y))
    dx = label_x - anchor_x
    dy = label_y - anchor_y
    length = max((dx * dx + dy * dy) ** 0.5, 0.001)
    gap = min(RADIAL_TEXT_GAP_MM, max(length - 0.1, 0.0))
    return {"x": label_x - (dx / length) * gap, "y": label_y - (dy / length) * gap}


def _arrow_path(tip: dict, tail: dict) -> str:
    tip_x = float(tip.get("x", 0.0))
    tip_y = float(tip.get("y", 0.0))
    tail_x = float(tail.get("x", tip_x))
    tail_y = float(tail.get("y", tip_y))
    dx = tail_x - tip_x
    dy = tail_y - tip_y
    length = max((dx * dx + dy * dy) ** 0.5, 0.001)
    ux = dx / length
    uy = dy / length
    px = -uy
    py = ux
    arrow_len = 3.5
    arrow_width = 0.7
    left_x = tip_x + ux * arrow_len + px * arrow_width
    left_y = tip_y + uy * arrow_len + py * arrow_width
    right_x = tip_x + ux * arrow_len - px * arrow_width
    right_y = tip_y + uy * arrow_len - py * arrow_width
    return f"M {tip_x:.2f} {tip_y:.2f} L {left_x:.2f} {left_y:.2f} L {right_x:.2f} {right_y:.2f} Z"
