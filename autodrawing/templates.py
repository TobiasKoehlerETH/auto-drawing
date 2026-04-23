from __future__ import annotations

from .contracts import AnnotationPlacement, CanonicalCadModel, PageTemplateDefinition, TitleBlockField
from .standards import (
    DEFAULT_PROJECTION,
    DEFAULT_TEMPLATE_ID,
    DEFAULT_TEMPLATE_NAME,
    ISO_A3_LANDSCAPE_MM,
    PROJECTION_SYMBOL_BOUNDS_MM,
    TITLE_BLOCK_BOUNDS_MM,
    TITLE_BLOCK_FIELD_LAYOUT_MM,
)


def build_default_template(model: CanonicalCadModel) -> tuple[PageTemplateDefinition, list[TitleBlockField]]:
    fields = [
        TitleBlockField(
            id="tb-title",
            label="Title",
            value=model.primary_shape.name,
            placement=AnnotationPlacement(
                x_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-title"]["x"],
                y_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-title"]["y"],
                user_locked=True,
            ),
            width_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-title"]["width"],
        ),
        TitleBlockField(
            id="tb-units",
            label="Units",
            value=model.units.upper(),
            placement=AnnotationPlacement(
                x_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-units"]["x"],
                y_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-units"]["y"],
                user_locked=True,
            ),
            width_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-units"]["width"],
        ),
        TitleBlockField(
            id="tb-source",
            label="Source",
            value=model.source_name,
            placement=AnnotationPlacement(
                x_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-source"]["x"],
                y_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-source"]["y"],
                user_locked=True,
            ),
            width_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-source"]["width"],
        ),
        TitleBlockField(
            id="tb-projection",
            label="Projection",
            value=DEFAULT_PROJECTION,
            placement=AnnotationPlacement(
                x_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-projection"]["x"],
                y_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-projection"]["y"],
                user_locked=True,
            ),
            width_mm=TITLE_BLOCK_FIELD_LAYOUT_MM["tb-projection"]["width"],
        ),
    ]

    svg_source = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ISO_A3_LANDSCAPE_MM["width"]:.0f} {ISO_A3_LANDSCAPE_MM["height"]:.0f}">
  <rect x="5" y="5" width="{ISO_A3_LANDSCAPE_MM["width"] - 10:.0f}" height="{ISO_A3_LANDSCAPE_MM["height"] - 10:.0f}" fill="none" stroke="#111" stroke-width="0.5" />
  <rect x="{TITLE_BLOCK_BOUNDS_MM["x"]:.0f}" y="{TITLE_BLOCK_BOUNDS_MM["y"]:.0f}" width="{TITLE_BLOCK_BOUNDS_MM["width"]:.0f}" height="{TITLE_BLOCK_BOUNDS_MM["height"]:.0f}" fill="none" stroke="#111" stroke-width="0.35" />
  <line x1="{TITLE_BLOCK_BOUNDS_MM["x"]:.0f}" y1="252" x2="{TITLE_BLOCK_BOUNDS_MM["x"] + TITLE_BLOCK_BOUNDS_MM["width"]:.0f}" y2="252" stroke="#111" stroke-width="0.25" />
  <line x1="{TITLE_BLOCK_BOUNDS_MM["x"]:.0f}" y1="262" x2="{TITLE_BLOCK_BOUNDS_MM["x"] + TITLE_BLOCK_BOUNDS_MM["width"]:.0f}" y2="262" stroke="#111" stroke-width="0.25" />
  <line x1="356" y1="{TITLE_BLOCK_BOUNDS_MM["y"]:.0f}" x2="356" y2="{TITLE_BLOCK_BOUNDS_MM["y"] + TITLE_BLOCK_BOUNDS_MM["height"]:.0f}" stroke="#111" stroke-width="0.25" />
  <rect x="{PROJECTION_SYMBOL_BOUNDS_MM["x"]:.0f}" y="{PROJECTION_SYMBOL_BOUNDS_MM["y"]:.0f}" width="{PROJECTION_SYMBOL_BOUNDS_MM["width"]:.0f}" height="{PROJECTION_SYMBOL_BOUNDS_MM["height"]:.0f}" fill="none" stroke="#111" stroke-width="0.25" />
</svg>"""

    template = PageTemplateDefinition(
        id=DEFAULT_TEMPLATE_ID,
        name=DEFAULT_TEMPLATE_NAME,
        svg_source=svg_source,
        field_ids=[field.id for field in fields],
    )
    return template, fields
