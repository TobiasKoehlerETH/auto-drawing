from __future__ import annotations

from math import atan2, degrees, hypot
from uuid import uuid4

from .contracts import (
    AnchorRef,
    AnnotationPlacement,
    Bounds2D,
    DimensionObject,
    DrawingDocument,
    DrawingView,
    Point2D,
    ProjectedCircle,
    ProjectedViewGeometry,
    ProjectionBundle,
)
from .view_planner import placed_bounds


DIMENSION_OFFSET_MM = 10.0
LINEAR_LABEL_OFFSET_MM = 8.0
RADIAL_LABEL_OFFSET_MM = 9.0


class DimensionService:
    def generate_defaults(self, document: DrawingDocument, projection: ProjectionBundle) -> list[DimensionObject]:
        if document.dimensions:
            return document.dimensions

        dimensions: list[DimensionObject] = []
        geometry_by_id = {geometry.id: geometry for geometry in projection.views}
        anchor_view = self._anchor_view(document)
        if anchor_view and anchor_view.kind != "isometric":
            geometry = geometry_by_id.get(anchor_view.geometry_id)
            if geometry:
                dimensions.extend(self._extent_dimensions(anchor_view, geometry))

        thickness_dimension = self._plate_thickness_dimension(document, geometry_by_id, anchor_view)
        if thickness_dimension:
            dimensions.append(thickness_dimension)

        for view in document.views:
            if view.kind == "isometric":
                continue
            geometry = geometry_by_id.get(view.geometry_id)
            if not geometry:
                continue
            dimensions.extend(self._diameter_dimensions(view, geometry))

        return dimensions

    def normalize_dimension(self, dimension: DimensionObject) -> DimensionObject:
        normalized = dimension.model_copy(deep=True)
        geometry = normalized.computed_geometry or {}
        if geometry.get("kind") == "angular" and normalized.dimension_type in {"Angle", "Angle3Pt"}:
            vertex = _point_from_mapping(geometry.get("vertex", {}))
            first = _point_from_mapping(geometry.get("first", {}))
            second = _point_from_mapping(geometry.get("second", {}))
            normalized.value = format_angle_from_points(vertex, first, second)
        normalized.formatted_text = normalized.formatted_text or self.format_value(normalized.dimension_type, normalized.value, normalized.units)
        normalized.label = normalized.formatted_text
        normalized.references_2d = normalized.references_2d or normalized.references
        if not normalized.references:
            normalized.references = normalized.references_2d[:]
        return normalized

    def update_text_placement(self, dimension: DimensionObject, x_mm: float, y_mm: float) -> DimensionObject:
        updated = dimension.model_copy(deep=True)
        updated.placement.x_mm = x_mm
        updated.placement.y_mm = y_mm
        updated.placement.user_locked = True
        geometry = dict(updated.computed_geometry)
        geometry["label"] = {"x": x_mm, "y": y_mm}
        updated.computed_geometry = geometry
        return updated

    def translate_dimension(self, dimension: DimensionObject, dx_mm: float, dy_mm: float) -> DimensionObject:
        if dx_mm == 0 and dy_mm == 0:
            return dimension
        updated = dimension.model_copy(deep=True)
        updated.placement.x_mm += dx_mm
        updated.placement.y_mm += dy_mm
        updated.computed_geometry = _translate_geometry(updated.computed_geometry, dx_mm, dy_mm)
        return updated

    def format_dimension(self, dimension: DimensionObject, format_spec: str | None) -> DimensionObject:
        updated = dimension.model_copy(deep=True)
        updated.format_spec = format_spec
        updated.formatted_text = self.format_value(updated.dimension_type, updated.value, updated.units, format_spec)
        return updated

    def format_value(
        self,
        dimension_type: str,
        value: float,
        units: str = "mm",
        format_spec: str | None = None,
    ) -> str:
        decimals = 2
        if format_spec and "." in format_spec:
            after_dot = format_spec.split(".", 1)[1]
            digits = "".join(ch for ch in after_dot if ch.isdigit())
            if digits:
                decimals = max(0, min(int(digits[0]), 6))
        formatted = f"{value:.{decimals}f}".rstrip("0").rstrip(".")
        if dimension_type == "Radius":
            return f"R{formatted}"
        if dimension_type == "Diameter":
            return f"\u2300{formatted}"
        if dimension_type in {"Angle", "Angle3Pt"}:
            return f"{formatted}\u00b0"
        return formatted

    def _anchor_view(self, document: DrawingDocument) -> DrawingView | None:
        anchor_id = document.projection_group.anchor_view_id
        return next((view for view in document.views if view.id == anchor_id), None) or next(
            (view for view in document.views if view.kind != "isometric"),
            None,
        )

    def _extent_dimensions(self, view: DrawingView, geometry: ProjectedViewGeometry) -> list[DimensionObject]:
        bounds = placed_bounds(view.local_bounds, view.placement)
        horizontal_y = bounds.y_max + DIMENSION_OFFSET_MM
        vertical_x = bounds.x_max + DIMENSION_OFFSET_MM
        horizontal_start = Point2D(x=bounds.x_min, y=bounds.y_max)
        horizontal_end = Point2D(x=bounds.x_max, y=bounds.y_max)
        horizontal_line_start = Point2D(x=bounds.x_min, y=horizontal_y)
        horizontal_line_end = Point2D(x=bounds.x_max, y=horizontal_y)
        vertical_start = Point2D(x=bounds.x_max, y=bounds.y_min)
        vertical_end = Point2D(x=bounds.x_max, y=bounds.y_max)
        vertical_line_start = Point2D(x=vertical_x, y=bounds.y_min)
        vertical_line_end = Point2D(x=vertical_x, y=bounds.y_max)
        return [
            self._linear_dimension(
                view=view,
                geometry=geometry,
                dimension_type="DistanceX",
                value=view.local_bounds.width,
                placement=_linear_label_placement("horizontal", horizontal_start, horizontal_end, horizontal_line_start, horizontal_line_end),
                extension_start=horizontal_start,
                extension_end=horizontal_end,
                line_start=horizontal_line_start,
                line_end=horizontal_line_end,
                anchor_a_role="min-x",
                anchor_b_role="max-x",
            ),
            self._linear_dimension(
                view=view,
                geometry=geometry,
                dimension_type="DistanceY",
                value=view.local_bounds.height,
                placement=_linear_label_placement("vertical", vertical_start, vertical_end, vertical_line_start, vertical_line_end),
                extension_start=vertical_start,
                extension_end=vertical_end,
                line_start=vertical_line_start,
                line_end=vertical_line_end,
                anchor_a_role="min-y",
                anchor_b_role="max-y",
            ),
        ]

    def _linear_dimension(
        self,
        *,
        view: DrawingView,
        geometry: ProjectedViewGeometry,
        dimension_type: str,
        value: float,
        placement: AnnotationPlacement,
        extension_start: Point2D,
        extension_end: Point2D,
        line_start: Point2D,
        line_end: Point2D,
        anchor_a_role: str,
        anchor_b_role: str,
    ) -> DimensionObject:
        dim_id = f"dim-{view.kind}-{dimension_type.lower()}-{uuid4().hex[:6]}"
        references = [geometry.source_ref.id]
        return DimensionObject(
            id=dim_id,
            view_id=view.id,
            label=self.format_value(dimension_type, value),
            value=value,
            units="mm",
            anchor_a=AnchorRef(view_id=view.id, primitive_id=geometry.source_ref.id, role=anchor_a_role),
            anchor_b=AnchorRef(view_id=view.id, primitive_id=geometry.source_ref.id, role=anchor_b_role),
            placement=placement,
            dimension_type=dimension_type,  # type: ignore[arg-type]
            measurement_type="Projected",
            references=references,
            references_2d=references,
            computed_geometry={
                "kind": "linear",
                "orientation": "horizontal" if dimension_type == "DistanceX" else "vertical",
                "extension_start": extension_start.model_dump(mode="json"),
                "extension_end": extension_end.model_dump(mode="json"),
                "line_start": line_start.model_dump(mode="json"),
                "line_end": line_end.model_dump(mode="json"),
                "label": {"x": placement.x_mm, "y": placement.y_mm},
            },
            formatted_text=self.format_value(dimension_type, value),
            format_spec="%.2f",
        )

    def _diameter_dimensions(self, view: DrawingView, geometry: ProjectedViewGeometry) -> list[DimensionObject]:
        dimensions: list[DimensionObject] = []
        grouped: dict[float, list[ProjectedCircle]] = {}
        for circle in geometry.circles:
            grouped.setdefault(round(circle.radius, 3), []).append(circle)
        for circles in grouped.values():
            if len(circles) >= 2:
                dimensions.append(self._circle_dimension(view, sorted(circles, key=lambda item: (item.center.y, item.center.x))[0], count=len(circles), through=True))
            else:
                dimensions.append(self._circle_dimension(view, circles[0]))
        return dimensions

    def _circle_dimension(self, view: DrawingView, circle: ProjectedCircle, *, count: int = 1, through: bool = False) -> DimensionObject:
        center = self._local_to_sheet(circle.center, view)
        radius = circle.radius * view.placement.scale
        if count >= 2:
            view_bounds = placed_bounds(view.local_bounds, view.placement)
            label = Point2D(x=max(view_bounds.x_min + 18.0, center.x + radius + RADIAL_LABEL_OFFSET_MM), y=max(view_bounds.y_min - 8.0, 14.0))
        else:
            label = Point2D(x=center.x + radius + RADIAL_LABEL_OFFSET_MM, y=center.y - radius - RADIAL_LABEL_OFFSET_MM)
        anchor = Point2D(x=center.x + radius, y=center.y)
        value = circle.radius * 2.0
        dim_id = f"dim-{view.kind}-diameter-{circle.id}-{uuid4().hex[:6]}"
        references = [circle.source_ref.id]
        formatted_text = self.format_value("Diameter", value)
        if count >= 2:
            formatted_text = f"{count}x {formatted_text}" + (" THRU" if through else "")
        return DimensionObject(
            id=dim_id,
            view_id=view.id,
            label=formatted_text,
            value=value,
            units="mm",
            anchor_a=AnchorRef(view_id=view.id, primitive_id=circle.id, role="center"),
            anchor_b=AnchorRef(view_id=view.id, primitive_id=circle.id, role="circle"),
            placement=AnnotationPlacement(x_mm=label.x, y_mm=label.y),
            dimension_type="Diameter",
            measurement_type="Projected",
            references=references,
            references_2d=references,
            computed_geometry={
                "kind": "radial",
                "center": center.model_dump(mode="json"),
                "radius": radius,
                "anchor": anchor.model_dump(mode="json"),
                "label": label.model_dump(mode="json"),
            },
            formatted_text=formatted_text,
            format_spec="%.2f",
        )

    def _plate_thickness_dimension(
        self,
        document: DrawingDocument,
        geometry_by_id: dict[str, ProjectedViewGeometry],
        anchor_view: DrawingView | None,
    ) -> DimensionObject | None:
        if not anchor_view or anchor_view.kind != "top":
            return None
        candidates = [
            view
            for view in document.views
            if view.kind == "front" and view.local_bounds.height > 0 and view.local_bounds.height < max(anchor_view.local_bounds.width, anchor_view.local_bounds.height) * 0.35
        ]
        if not candidates:
            return None
        view = candidates[0]
        geometry = geometry_by_id.get(view.geometry_id)
        if not geometry:
            return None
        bounds = placed_bounds(view.local_bounds, view.placement)
        vertical_x = bounds.x_max + DIMENSION_OFFSET_MM
        extension_start = Point2D(x=bounds.x_max, y=bounds.y_min)
        extension_end = Point2D(x=bounds.x_max, y=bounds.y_max)
        line_start = Point2D(x=vertical_x, y=bounds.y_min)
        line_end = Point2D(x=vertical_x, y=bounds.y_max)
        return self._linear_dimension(
            view=view,
            geometry=geometry,
            dimension_type="DistanceY",
            value=view.local_bounds.height,
            placement=_linear_label_placement("vertical", extension_start, extension_end, line_start, line_end),
            extension_start=extension_start,
            extension_end=extension_end,
            line_start=line_start,
            line_end=line_end,
            anchor_a_role="min-y",
            anchor_b_role="max-y",
        )

    def _local_to_sheet(self, point: Point2D, view: DrawingView) -> Point2D:
        return Point2D(
            x=view.placement.x_mm + point.x * view.placement.scale,
            y=view.placement.y_mm - point.y * view.placement.scale,
        )


def format_angle_from_points(vertex: Point2D, first: Point2D, second: Point2D) -> float:
    a0 = atan2(first.y - vertex.y, first.x - vertex.x)
    a1 = atan2(second.y - vertex.y, second.x - vertex.x)
    angle = abs(degrees(a1 - a0)) % 360.0
    return 360.0 - angle if angle > 180.0 else angle


def distance_between(a: Point2D, b: Point2D) -> float:
    return hypot(a.x - b.x, a.y - b.y)


def _linear_label_placement(
    orientation: str,
    extension_start: Point2D,
    extension_end: Point2D,
    line_start: Point2D,
    line_end: Point2D,
) -> AnnotationPlacement:
    if orientation == "horizontal":
        direction = 1.0 if (line_start.y + line_end.y) >= (extension_start.y + extension_end.y) else -1.0
        return AnnotationPlacement(
            x_mm=(line_start.x + line_end.x) / 2.0,
            y_mm=(line_start.y + line_end.y) / 2.0 + direction * LINEAR_LABEL_OFFSET_MM,
        )
    direction = 1.0 if (line_start.x + line_end.x) >= (extension_start.x + extension_end.x) else -1.0
    return AnnotationPlacement(
        x_mm=(line_start.x + line_end.x) / 2.0 + direction * LINEAR_LABEL_OFFSET_MM,
        y_mm=(line_start.y + line_end.y) / 2.0,
    )


def _point_from_mapping(value: dict) -> Point2D:
    return Point2D(x=float(value.get("x", 0.0)), y=float(value.get("y", 0.0)))


def _translate_geometry(value, dx_mm: float, dy_mm: float):
    if isinstance(value, dict):
        translated = {key: _translate_geometry(item, dx_mm, dy_mm) for key, item in value.items()}
        x = translated.get("x")
        y = translated.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            translated["x"] = float(x) + dx_mm
            translated["y"] = float(y) + dy_mm
        return translated
    if isinstance(value, list):
        return [_translate_geometry(item, dx_mm, dy_mm) for item in value]
    return value
