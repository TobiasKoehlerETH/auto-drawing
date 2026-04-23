from __future__ import annotations

from .contracts import (
    AnchorRef,
    AnnotationPlacement,
    BomRow,
    CanonicalCadModel,
    DimensionObject,
    DrawingCommand,
    DrawingDocument,
    DrawingView,
    NoteObject,
    ProjectionBundle,
    ProjectionGroupLayout,
    SheetDefinition,
    ViewPlacement,
)
from .standards import DEFAULT_PROJECTION, ISO_A3_LANDSCAPE_MM, STANDARD_PROFILE
from .templates import build_default_template
from .view_planner import plan_view_pack


class DrawingDocumentService:
    def create_document(self, model: CanonicalCadModel, projection: ProjectionBundle) -> DrawingDocument:
        placements = plan_view_pack(projection, model, DEFAULT_PROJECTION)
        template, title_block_fields = build_default_template(model)

        views: list[DrawingView] = []
        for geometry in projection.views:
            placement = placements.get(geometry.kind, ViewPlacement(x_mm=40.0, y_mm=80.0, scale=1.0))
            views.append(
                DrawingView(
                    id=f"view-{geometry.kind}",
                    kind=geometry.kind,
                    label=geometry.label,
                    geometry_id=geometry.id,
                    source_ref=geometry.source_ref,
                    placement=placement,
                    local_bounds=geometry.bounds,
                )
            )

        notes = [
            NoteObject(
                id="note-standards",
                view_id=None,
                text="ISO profile drawing preview generated from STEP input.",
                placement=AnnotationPlacement(x_mm=18.0, y_mm=18.0),
            )
        ]
        for diagnostic in model.diagnostics:
            notes.append(
                NoteObject(
                    id=f"note-{diagnostic.code}",
                    view_id=None,
                    text=diagnostic.message,
                    placement=AnnotationPlacement(x_mm=18.0, y_mm=18.0 + len(notes) * 8.0),
                )
            )

        dimensions: list[DimensionObject] = []
        bom_rows = self._build_bom_rows(model)

        return DrawingDocument(
            canonical_model_name=model.source_name,
            sheet=SheetDefinition(
                width_mm=ISO_A3_LANDSCAPE_MM["width"],
                height_mm=ISO_A3_LANDSCAPE_MM["height"],
                standards_profile=STANDARD_PROFILE,
                projection=DEFAULT_PROJECTION,
            ),
            page_template=template,
            projection_group=ProjectionGroupLayout(
                anchor_view_id="view-front",
                ordered_view_ids=[view.id for view in views],
                projection=DEFAULT_PROJECTION,
            ),
            view_order=[view.id for view in views],
            views=views,
            dimensions=dimensions,
            notes=notes,
            bom_rows=bom_rows,
            title_block_fields=title_block_fields,
        )

    def apply_command(self, document: DrawingDocument, command: DrawingCommand) -> DrawingDocument:
        updated = document.model_copy(deep=True)
        targetless_commands = {"ReorderBomRow", "SetDisplayTransform"}
        target = None if command.kind in targetless_commands else self._find_target(updated, command.target_id)
        if command.kind not in targetless_commands and target is None:
            raise KeyError(f"Unknown command target: {command.target_id}")

        if command.kind in {"MoveDimensionText", "MoveNote"}:
            target.placement.x_mm = float(command.after["x_mm"])
            target.placement.y_mm = float(command.after["y_mm"])
            target.placement.user_locked = True
        elif command.kind == "MoveView":
            target.placement.x_mm = float(command.after["x_mm"])
            target.placement.y_mm = float(command.after["y_mm"])
            target.placement.user_locked = True
        elif command.kind == "SetTitleBlockField":
            target.value = str(command.after["value"])
        elif command.kind == "ReorderBomRow":
            row_id = command.target_id
            new_index = int(command.after["index"])
            row = next(row for row in updated.bom_rows if row.id == row_id)
            updated.bom_rows = [candidate for candidate in updated.bom_rows if candidate.id != row_id]
            updated.bom_rows.insert(max(0, min(new_index, len(updated.bom_rows))), row)
            for idx, bom_row in enumerate(updated.bom_rows, start=1):
                bom_row.item_number = idx
        elif command.kind == "ChangeViewScale":
            target.placement.scale = max(float(command.after["scale"]), 0.1)
            target.placement.user_locked = True
        elif command.kind == "SetDisplayTransform":
            transform = str(command.after.get("transform", "")).strip()
            if transform:
                updated.display_transforms[command.target_id] = transform
            else:
                updated.display_transforms.pop(command.target_id, None)
        else:
            raise ValueError(f"Unsupported command kind: {command.kind}")

        updated.commands.append(command)
        updated.redo_commands.clear()
        return updated

    def undo_last(self, document: DrawingDocument) -> DrawingDocument:
        if not document.commands:
            return document
        updated = document.model_copy(deep=True)
        command = updated.commands.pop()
        targetless_commands = {"ReorderBomRow", "SetDisplayTransform"}
        target = None if command.kind in targetless_commands else self._find_target(updated, command.target_id)
        if command.kind not in targetless_commands and target is None:
            raise KeyError(f"Unknown command target: {command.target_id}")

        if command.kind in {"MoveDimensionText", "MoveNote"}:
            target.placement.x_mm = float(command.before["x_mm"])
            target.placement.y_mm = float(command.before["y_mm"])
        elif command.kind == "MoveView":
            target.placement.x_mm = float(command.before["x_mm"])
            target.placement.y_mm = float(command.before["y_mm"])
        elif command.kind == "SetTitleBlockField":
            target.value = str(command.before["value"])
        elif command.kind == "ReorderBomRow":
            old_index = int(command.before["index"])
            row = next(row for row in updated.bom_rows if row.id == command.target_id)
            updated.bom_rows = [candidate for candidate in updated.bom_rows if candidate.id != command.target_id]
            updated.bom_rows.insert(old_index, row)
            for idx, bom_row in enumerate(updated.bom_rows, start=1):
                bom_row.item_number = idx
        elif command.kind == "ChangeViewScale":
            target.placement.scale = float(command.before["scale"])
        elif command.kind == "SetDisplayTransform":
            transform = str(command.before.get("transform", "")).strip()
            if transform:
                updated.display_transforms[command.target_id] = transform
            else:
                updated.display_transforms.pop(command.target_id, None)
        updated.redo_commands.append(command)
        return updated

    def redo_last(self, document: DrawingDocument) -> DrawingDocument:
        if not document.redo_commands:
            return document
        updated = document.model_copy(deep=True)
        command = updated.redo_commands.pop()
        return self.apply_command(updated, command)

    def regenerate_for_projection(self, document: DrawingDocument, projection: ProjectionBundle, model: CanonicalCadModel) -> DrawingDocument:
        regenerated = document.model_copy(deep=True)
        existing = {view.kind: view.placement.model_copy(deep=True) for view in regenerated.views}
        planned = plan_view_pack(projection, model, regenerated.sheet.projection)
        regenerated.views.clear()
        for geometry in projection.views:
            placement = existing.get(geometry.kind) or planned.get(geometry.kind) or ViewPlacement(x_mm=40.0, y_mm=80.0, scale=1.0)
            regenerated.views.append(
                DrawingView(
                    id=f"view-{geometry.kind}",
                    kind=geometry.kind,
                    label=geometry.label,
                    geometry_id=geometry.id,
                    source_ref=geometry.source_ref,
                    placement=placement,
                    local_bounds=geometry.bounds,
                )
            )
        regenerated.view_order = [view.id for view in regenerated.views]
        regenerated.projection_group.ordered_view_ids = regenerated.view_order[:]
        return regenerated

    def _find_target(self, document: DrawingDocument, target_id: str):
        for collection_name in ("dimensions", "notes", "title_block_fields", "views"):
            collection = getattr(document, collection_name)
            for item in collection:
                if item.id == target_id:
                    return item
        return None

    def _build_bom_rows(self, model: CanonicalCadModel) -> list[BomRow]:
        rows: list[BomRow] = []
        children = model.root_component.children or [model.root_component]
        for index, component in enumerate(children, start=1):
            rows.append(
                BomRow(
                    id=f"bom-{component.id}",
                    item_number=index,
                    component_id=component.id,
                    name=component.name,
                    quantity=component.quantity,
                )
            )
        return rows
