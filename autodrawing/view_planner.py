from __future__ import annotations

from collections.abc import Iterable

from .contracts import Bounds2D, CanonicalCadModel, FeatureHint, ProjectionBundle, ProjectionType, ViewPlacement
from .standards import DEFAULT_VIEW_GAP_MM, ISOMETRIC_AREA_MM, MAIN_VIEW_AREA_MM


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

    front = geometry_by_kind.get("front")
    top = geometry_by_kind.get("top")
    right = geometry_by_kind.get("right")
    iso = geometry_by_kind.get("isometric")

    if not front:
        return {}

    main_w = MAIN_VIEW_AREA_MM["width"]
    main_h = MAIN_VIEW_AREA_MM["height"]

    horizontal_units = front.bounds.width
    vertical_units = front.bounds.height
    if right:
        horizontal_units += gap + right.bounds.width
    if top:
        vertical_units += gap + top.bounds.height

    scale = min(
        1.85,
        main_w / max(horizontal_units, 1.0),
        main_h / max(vertical_units, 1.0),
    )
    scale = max(scale, 0.45)

    scaled_front_w = front.bounds.width * scale
    scaled_front_h = front.bounds.height * scale
    scaled_right_w = right.bounds.width * scale if right else 0.0
    scaled_top_h = top.bounds.height * scale if top else 0.0

    total_w = scaled_front_w + (gap + scaled_right_w if right else 0.0)
    total_h = scaled_front_h + (gap + scaled_top_h if top else 0.0)

    left = MAIN_VIEW_AREA_MM["x"] + max((main_w - total_w) / 2.0, 0.0)
    top_y = MAIN_VIEW_AREA_MM["y"] + max((main_h - total_h) / 2.0, 0.0)

    placements: dict[str, ViewPlacement] = {}

    if projection_type == "first-angle":
        front_left = left + (scaled_right_w + gap if right else 0.0)
        front_top = top_y
        right_left = left
        top_top = front_top + scaled_front_h + gap
    else:
        front_left = left
        front_top = top_y + (scaled_top_h + gap if top else 0.0)
        right_left = front_left + scaled_front_w + gap
        top_top = top_y

    front_bottom = front_top + scaled_front_h
    placements["front"] = ViewPlacement(x_mm=front_left, y_mm=front_bottom, scale=scale)

    if top:
        top_bottom = top_top + scaled_top_h
        placements["top"] = ViewPlacement(x_mm=front_left, y_mm=top_bottom, scale=scale)

    if right:
        placements["right"] = ViewPlacement(x_mm=right_left, y_mm=front_bottom, scale=scale)

    if iso:
        iso_scale = min(
            max(scale * 0.72, 0.42),
            ISOMETRIC_AREA_MM["width"] / max(iso.bounds.width, 1.0),
            ISOMETRIC_AREA_MM["height"] / max(iso.bounds.height, 1.0),
        )
        iso_left = ISOMETRIC_AREA_MM["x"] + max((ISOMETRIC_AREA_MM["width"] - iso.bounds.width * iso_scale) / 2.0, 0.0)
        iso_top = ISOMETRIC_AREA_MM["y"] + max((ISOMETRIC_AREA_MM["height"] - iso.bounds.height * iso_scale) / 2.0, 0.0)
        placements["isometric"] = ViewPlacement(
            x_mm=iso_left,
            y_mm=iso_top + iso.bounds.height * iso_scale,
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
