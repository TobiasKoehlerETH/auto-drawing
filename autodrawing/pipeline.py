from __future__ import annotations

from pathlib import Path

from .contracts import DrawingCommand, ImportedMeshPayload, PipelineBundle
from .documents import DrawingDocumentService
from .exporters import HtmlExportService
from .importers import StepImportService
from .projection import ProjectionService
from .scene import SceneGraphService


class AutodrawingPipeline:
    def __init__(self) -> None:
        self.importer = StepImportService()
        self.projection = ProjectionService()
        self.documents = DrawingDocumentService()
        self.scene = SceneGraphService()
        self.html = HtmlExportService()

    def from_step_file(self, path: str | Path, mode: str = "preview") -> PipelineBundle:
        model = self.importer.import_file(path)
        projection = self.projection.build_projection(model, mode=mode)
        document = self.documents.create_document(model, projection)
        scene_graph = self.scene.build_scene(document, projection)
        return PipelineBundle(canonical_model=model, projection=projection, document=document, scene_graph=scene_graph)

    def from_step_text(self, text: str, source_name: str = "uploaded.step", mode: str = "preview") -> PipelineBundle:
        model = self.importer.import_text(text, source_name=source_name)
        projection = self.projection.build_projection(model, mode=mode)
        document = self.documents.create_document(model, projection)
        scene_graph = self.scene.build_scene(document, projection)
        return PipelineBundle(canonical_model=model, projection=projection, document=document, scene_graph=scene_graph)

    def from_occt_meshes(
        self,
        meshes: list[ImportedMeshPayload],
        *,
        source_name: str = "uploaded.step",
        units: str = "mm",
        mode: str = "preview",
    ) -> PipelineBundle:
        model = self.importer.import_occt_meshes(meshes, source_name=source_name, units=units)
        projection = self.projection.build_projection(model, mode=mode)
        document = self.documents.create_document(model, projection)
        scene_graph = self.scene.build_scene(document, projection)
        return PipelineBundle(canonical_model=model, projection=projection, document=document, scene_graph=scene_graph)

    def apply_command(self, bundle: PipelineBundle, command: DrawingCommand) -> PipelineBundle:
        document = self.documents.apply_command(bundle.document, command)
        scene_graph = self.scene.build_scene(document, bundle.projection)
        return PipelineBundle(
            canonical_model=bundle.canonical_model,
            projection=bundle.projection,
            document=document,
            scene_graph=scene_graph,
        )

    def apply_commands(self, bundle: PipelineBundle, commands: list[DrawingCommand]) -> PipelineBundle:
        next_bundle = bundle
        for command in commands:
            next_bundle = self.apply_command(next_bundle, command)
        return next_bundle

    def undo(self, bundle: PipelineBundle) -> PipelineBundle:
        document = self.documents.undo_last(bundle.document)
        scene_graph = self.scene.build_scene(document, bundle.projection)
        return PipelineBundle(
            canonical_model=bundle.canonical_model,
            projection=bundle.projection,
            document=document,
            scene_graph=scene_graph,
        )

    def redo(self, bundle: PipelineBundle) -> PipelineBundle:
        document = self.documents.redo_last(bundle.document)
        scene_graph = self.scene.build_scene(document, bundle.projection)
        return PipelineBundle(
            canonical_model=bundle.canonical_model,
            projection=bundle.projection,
            document=document,
            scene_graph=scene_graph,
        )

    def regenerate(self, bundle: PipelineBundle, mode: str | None = None) -> PipelineBundle:
        projection = self.projection.build_projection(bundle.canonical_model, mode=mode or bundle.projection.mode)
        document = self.documents.regenerate_for_projection(bundle.document, projection, bundle.canonical_model)
        scene_graph = self.scene.build_scene(document, projection)
        return PipelineBundle(
            canonical_model=bundle.canonical_model,
            projection=projection,
            document=document,
            scene_graph=scene_graph,
        )

    def render_html(self, bundle: PipelineBundle) -> str:
        return self.html.render_html(bundle)
