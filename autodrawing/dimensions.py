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
        kind = geometry.get("kind")
        geometry["label"] = {"x": x_mm, "y": y_mm}
        if kind == "linear":
            orientation = geometry.get("orientation")
            start = geometry.get("extension_start", {})
            end = geometry.get("extension_end", {})
            if orientation == "horizontal":
                geometry["line_start"] = {"x": start.get("x", x_mm), "y": y_mm}
                geometry["line_end"] = {"x": end.get("x", x_mm), "y": y_mm}
            elif orientation == "vertical":
                geometry["line_start"] = {"x": x_mm, "y": start.get("y", y_mm)}
                geometry["line_end"] = {"x": x_mm, "y": end.get("y", y_mm)}
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
        return f"{formatted} {units}"

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
        return [
            self._linear_dimension(
                view=view,
                geometry=geometry,
                dimension_type="DistanceX",
                value=view.local_bounds.width,
                placement=AnnotationPlacement(x_mm=(bounds.x_min + bounds.x_max) / 2.0, y_mm=horizontal_y),
                extension_start=Point2D(x=bounds.x_min, y=bounds.y_max),
                extension_end=Point2D(x=bounds.x_max, y=bounds.y_max),
                line_start=Point2D(x=bounds.x_min, y=horizontal_y),
                line_end=Point2D(x=bounds.x_max, y=horizontal_y),
                anchor_a_role="min-x",
                anchor_b_role="max-x",
            ),
            self._linear_dimension(
                view=view,
                geometry=geometry,
                dimension_type="DistanceY",
                value=view.local_bounds.height,
                placement=AnnotationPlacement(x_mm=vertical_x, y_mm=(bounds.y_min + bounds.y_max) / 2.0),
                extension_start=Point2D(x=bounds.x_max, y=bounds.y_min),
                extension_end=Point2D(x=bounds.x_max, y=bounds.y_max),
                line_start=Point2D(x=vertical_x, y=bounds.y_min),
                line_end=Point2D(x=vertical_x, y=bounds.y_max),
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
        for circle in geometry.circles:
            dimensions.append(self._circle_dimension(view, circle))
        return dimensions

    def _circle_dimension(self, view: DrawingView, circle: ProjectedCircle) -> DimensionObject:
        center = self._local_to_sheet(circle.center, view)
        radius = circle.radius * view.placement.scale
        label = Point2D(x=center.x + radius + RADIAL_LABEL_OFFSET_MM, y=center.y - radius - RADIAL_LABEL_OFFSET_MM)
        anchor = Point2D(x=center.x + radius, y=center.y)
        value = circle.radius * 2.0
        dim_id = f"dim-{view.kind}-diameter-{circle.id}-{uuid4().hex[:6]}"
        references = [circle.source_ref.id]
        return DimensionObject(
            id=dim_id,
            view_id=view.id,
            label=self.format_value("Diameter", value),
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
            formatted_text=self.format_value("Diameter", value),
            format_spec="%.2f",
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
