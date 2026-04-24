from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DrawTemplate:
    width_mm: float
    height_mm: float
    orientation: str


@dataclass
class DrawSVGTemplate(DrawTemplate):
    source_path: Path
    editable_texts: dict[str, dict[str, object]] = field(default_factory=dict)
    page_result: str = ""

    def process_template(self, substitutions: dict[str, str]) -> str:
        from .svg_templates import render_svg_template

        return render_svg_template(self.source_path, substitutions)


@dataclass
class DrawView:
    id: str
    label: str
    x_mm: float = 0.0
    y_mm: float = 0.0
    scale: float = 1.0
    scale_type: str = "Page"
    rotation: float = 0.0
    lock_position: bool = False
    caption: str = ""

    def get_scale(self, page_scale: float) -> float:
        return page_scale if self.scale_type == "Page" else self.scale


@dataclass
class DrawViewCollection(DrawView):
    views: list[DrawView] = field(default_factory=list)

    def add_view(self, view: DrawView) -> None:
        if view.id not in {candidate.id for candidate in self.views}:
            self.views.append(view)

    def remove_view(self, view_id: str) -> None:
        self.views = [candidate for candidate in self.views if candidate.id != view_id]


@dataclass
class DrawProjGroup(DrawViewCollection):
    source_ids: list[str] = field(default_factory=list)
    anchor_view_id: str | None = None
    projection_type: str = "First angle"
    auto_distribute: bool = True
    spacing_x: float = 15.0
    spacing_y: float = 15.0


@dataclass
class DrawProjGroupItem(DrawView):
    projection_type: str = "Front"
    parent_group_id: str | None = None


@dataclass
class DrawViewPart(DrawView):
    source_ids: list[str] = field(default_factory=list)
    direction: tuple[float, float, float] = (0.0, -1.0, 0.0)
    x_direction: tuple[float, float, float] = (1.0, 0.0, 0.0)
    hard_hidden: bool = False
    smooth_hidden: bool = False
    seam_hidden: bool = False
    iso_hidden: bool = False


@dataclass
class DrawViewSection(DrawViewPart):
    base_view_id: str | None = None
    section_normal: tuple[float, float, float] = (0.0, 1.0, 0.0)
    section_origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    section_symbol: str = "A-A"


@dataclass
class DrawViewDetail(DrawViewPart):
    base_view_id: str | None = None
    anchor_point: tuple[float, float, float] = (0.0, 0.0, 0.0)
    radius: float = 0.0
    reference: str = ""


@dataclass
class DrawViewDimension(DrawView):
    measurement_type: str = "Projected"
    references_2d: list[str] = field(default_factory=list)
    references_3d: list[str] = field(default_factory=list)
    dimension_type: str = "Distance"
    format_spec: str = ""
    over_tolerance: float = 0.0
    under_tolerance: float = 0.0
    show_units: bool = True

    def get_text(self, value: float, units: str) -> str:
        suffix = f" {units}" if self.show_units else ""
        return f"{value:g}{suffix}"


@dataclass
class DrawViewBalloon(DrawView):
    source_view_id: str | None = None
    text: str = ""
    origin_x: float = 0.0
    origin_y: float = 0.0


@dataclass
class DrawPage:
    id: str
    label: str
    template: DrawSVGTemplate
    page_scale: float = 1.0
    projection_type: str = "First angle"
    next_balloon_index: int = 1
    views: list[DrawView] = field(default_factory=list)

    def add_view(self, view: DrawView) -> None:
        if view.id not in {candidate.id for candidate in self.views}:
            self.views.append(view)

    def remove_view(self, view_id: str) -> None:
        self.views = [candidate for candidate in self.views if candidate.id != view_id]

    def get_views(self) -> list[DrawView]:
        return list(self.views)
