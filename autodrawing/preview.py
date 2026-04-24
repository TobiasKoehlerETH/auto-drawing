from __future__ import annotations

from uuid import uuid4

from .contracts import DrawingPreview, PipelineBundle, PreviewQaSummary, PreviewValidation, PreviewViewState
from .exporters import HtmlExportService
from .view_planner import placed_bounds


class PreviewStore:
    def __init__(self) -> None:
        self._bundles: dict[str, PipelineBundle] = {}

    def create(self, bundle: PipelineBundle) -> str:
        preview_id = uuid4().hex[:12]
        self._bundles[preview_id] = bundle
        return preview_id

    def get(self, preview_id: str) -> PipelineBundle:
        return self._bundles[preview_id]

    def put(self, preview_id: str, bundle: PipelineBundle) -> None:
        self._bundles[preview_id] = bundle


class PreviewService:
    def build_preview(self, preview_id: str, bundle: PipelineBundle) -> DrawingPreview:
        warnings = [diagnostic.message for diagnostic in bundle.canonical_model.diagnostics if diagnostic.severity != "info"]
        errors = [diagnostic.message for diagnostic in bundle.canonical_model.diagnostics if diagnostic.severity == "error"]
        validation = PreviewValidation(
            status="fail" if errors else ("warning" if warnings else "pass"),
            warnings=warnings,
            errors=errors,
        )

        views = [
            PreviewViewState(
                id=view.id,
                kind=view.kind,
                label=view.label,
                x_mm=view.placement.x_mm,
                y_mm=view.placement.y_mm,
                scale=view.placement.scale,
                width_mm=view.local_bounds.width * view.placement.scale,
                height_mm=view.local_bounds.height * view.placement.scale,
                selection_bounds_mm=placed_bounds(view.local_bounds, view.placement),
                source_ref=view.source_ref,
            )
            for view in bundle.document.views
        ]

        qa_summary = PreviewQaSummary(
            status=validation.status,
            view_count=len(bundle.projection.views),
            visible_edge_count=sum(len(view.visible_edges) for view in bundle.projection.views),
            hidden_edge_count=sum(len(view.hidden_edges) for view in bundle.projection.views),
            smooth_edge_count=sum(len(view.smooth_edges) for view in bundle.projection.views),
            circle_count=sum(len(view.circles) for view in bundle.projection.views),
            arc_count=sum(len(view.arcs) for view in bundle.projection.views),
        )

        return DrawingPreview(
            preview_id=preview_id,
            mode=bundle.projection.mode,
            svg=HtmlExportService().render_svg(bundle),
            document=bundle.document,
            projection=bundle.projection,
            scene_graph=bundle.scene_graph,
            views=views,
            validation=validation,
            qa_summary=qa_summary,
            tracked_draw_bridge_available=bundle.projection.adapter == "techdraw-native",
        )
