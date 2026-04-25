from __future__ import annotations

from collections.abc import Iterable

from .contracts import Bounds2D, CanonicalCadModel, FeatureHint, ProjectionBundle, ProjectionType, ViewPlacement
from .standards import (
    DEFAULT_VIEW_GAP_MM,
    ISOMETRIC_VIEW_SCALE,
    MAIN_VIEW_AREA_MM,
    ORTHOGRAPHIC_VIEW_SCALE,
    TITLE_BLOCK_BOUNDS_MM,
)


def is_plate_like(model: CanonicalCadModel) -> bool:
    size = model.primary_shape.bounding_box.size
    longest = max(size.x, size.y, size.z, 1.0)
    shortest = min(size.x, size.y, size.z)
    return shortest / longest <= 0.18


def primary_orthographic_view_kind(model: CanonicalCadModel) -> str:
    return "top" if is_plate_like(model) else "front"


def default_view_scale(view_kind: str) -> float:
    return ISOMETRIC_VIEW_SCALE if view_kind == "isometric" else ORTHOGRAPHIC_VIEW_SCALE


def select_hidden_line_policy(model: CanonicalCadModel, view_name: str, default: bool = True) -> bool:
    if view_name == "isometric":
        return False

    hints = {hint.kind for hint in model.primary_shape.feature_hints}
    if "section-candidate" in hints and view_name in {"front", "right"}:
        return True
    if {"circular-hole", "hole-pattern"} & hints and view_name in {"front", "right"}:
        return True
    return default


def select_centerline_circles(hints: Iterable[FeatureHint], view_name: str) -> bool:
    kinds = {hint.kind for hint in hints}
    if view_name == "isometric":
        return False
    return bool({"circular-hole", "hole-pattern"} & kinds)


def plan_view_pack(
    projection: ProjectionBundle,
    model: CanonicalCadModel,
    projection_type: ProjectionType = "first-angle",
) -> dict[str, ViewPlacement]:
    geometry_by_kind = {view.kind: view for view in projection.views}
    gap = DEFAULT_VIEW_GAP_MM

    primary_kind = primary_orthographic_view_kind(model)
    secondary_vertical_kind = "front" if primary_kind == "top" else "top"

    right = geometry_by_kind.get("right")
    iso = geometry_by_kind.get("isometric")
    primary = geometry_by_kind.get(primary_kind)
    secondary_vertical = geometry_by_kind.get(secondary_vertical_kind)

    if not primary:
        return {}

    main_w = MAIN_VIEW_AREA_MM["width"]
    main_h = MAIN_VIEW_AREA_MM["height"]
    scale = ORTHOGRAPHIC_VIEW_SCALE

    scaled_primary_w = primary.bounds.width * scale
    scaled_primary_h = primary.bounds.height * scale
    scaled_right_w = right.bounds.width * scale if right else 0.0
    scaled_right_h = right.bounds.height * scale if right else 0.0
    scaled_secondary_w = secondary_vertical.bounds.width * scale if secondary_vertical else 0.0
    scaled_secondary_h = secondary_vertical.bounds.height * scale if secondary_vertical else 0.0

    if projection_type == "first-angle" and primary_kind == "top":
        orthographic_w = max(scaled_primary_w, scaled_secondary_w)
        total_w = orthographic_w + (gap + scaled_right_w if right else 0.0)
        total_h = scaled_secondary_h + gap + scaled_primary_h if secondary_vertical else scaled_primary_h
    else:
        total_w = scaled_primary_w + (gap + scaled_right_w if right else 0.0)
        total_h = scaled_primary_h + (gap + scaled_secondary_h if secondary_vertical else 0.0)

    left = MAIN_VIEW_AREA_MM["x"] + max((main_w - total_w) / 2.0, 0.0)
    top_y = MAIN_VIEW_AREA_MM["y"] + max((main_h - total_h) / 2.0, 0.0)

    placements: dict[str, ViewPlacement] = {}

    if projection_type == "first-angle" and primary_kind == "top":
        secondary_vertical_top = top_y
        primary_top = secondary_vertical_top + scaled_secondary_h + gap if secondary_vertical else top_y
        primary_left = left + (scaled_right_w + gap if right else 0.0)
        right_left = left
        right_top = secondary_vertical_top
    elif projection_type == "first-angle":
        primary_left = left + (scaled_right_w + gap if right else 0.0)
        primary_top = top_y
        right_left = left
        right_top = primary_top
        secondary_vertical_top = primary_top + scaled_primary_h + gap
    else:
        primary_left = left
        primary_top = top_y + (scaled_secondary_h + gap if secondary_vertical else 0.0)
        right_left = primary_left + scaled_primary_w + gap
        right_top = primary_top
        secondary_vertical_top = top_y

    primary_bottom = primary_top + scaled_primary_h
    placements[primary_kind] = ViewPlacement(x_mm=primary_left, y_mm=primary_bottom, scale=default_view_scale(primary_kind))

    if secondary_vertical:
        secondary_vertical_bottom = secondary_vertical_top + scaled_secondary_h
        placements[secondary_vertical_kind] = ViewPlacement(
            x_mm=primary_left,
            y_mm=secondary_vertical_bottom,
            scale=default_view_scale(secondary_vertical_kind),
        )

    if right:
        right_bottom = right_top + scaled_right_h
        placements["right"] = ViewPlacement(x_mm=right_left, y_mm=right_bottom, scale=default_view_scale("right"))

    if iso:
        iso_scale = default_view_scale("isometric")
        iso_width = iso.bounds.width * iso_scale
        title_right = TITLE_BLOCK_BOUNDS_MM["x"] + TITLE_BLOCK_BOUNDS_MM["width"]
        title_top = TITLE_BLOCK_BOUNDS_MM["y"]
        iso_left = title_right - iso_width
        if iso_width > TITLE_BLOCK_BOUNDS_MM["width"]:
            iso_left = TITLE_BLOCK_BOUNDS_MM["x"]
        iso_bottom = title_top - DEFAULT_VIEW_GAP_MM / 2.0
        placements["isometric"] = ViewPlacement(
            x_mm=iso_left - iso.bounds.x_min * iso_scale,
            y_mm=iso_bottom + iso.bounds.y_min * iso_scale,
            scale=iso_scale,
        )

    return placements


def placed_bounds(bounds: Bounds2D, placement: ViewPlacement) -> Bounds2D:
    return Bounds2D.from_extents(
        x_min=placement.x_mm + bounds.x_min * placement.scale,
        y_min=placement.y_mm - bounds.y_max * placement.scale,
        x_max=placement.x_mm + bounds.x_max * placement.scale,
        y_max=placement.y_mm - bounds.y_min * placement.scale,
    )
