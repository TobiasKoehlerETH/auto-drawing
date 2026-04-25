from __future__ import annotations

from dataclasses import asdict
from datetime import date

from .assets import DEFAULT_TEMPLATE_PATH
from .model import DrawPage, DrawProjGroup, DrawProjGroupItem, DrawViewPart
from .runtime import detect_runtime_status
from .svg_templates import extract_editable_texts, load_svg_template
from ..contracts import AnnotationPlacement, CanonicalCadModel, DrawingDocument, DrawingView, PageTemplateDefinition, ProjectionBundle, TitleBlockField
from ..templates import drawing_unit_system


class TechDrawExactService:
    def __init__(self) -> None:
        self.runtime = detect_runtime_status()

    def decorate_projection(self, projection: ProjectionBundle) -> ProjectionBundle:
        return projection.model_copy(update={"adapter": "techdraw-native"})

    def build_page(self, model: CanonicalCadModel, projection: ProjectionBundle, document: DrawingDocument) -> DrawPage:
        template = load_svg_template(DEFAULT_TEMPLATE_PATH)
        page = DrawPage(
            id="page-001",
            label=model.source_name,
            template=template,
            page_scale=document.sheet.width_mm / max(template.width_mm, 1.0),
            projection_type="First angle" if document.sheet.projection == "first-angle" else "Third angle",
        )
        group = DrawProjGroup(
            id="proj-group-001",
            label="Projection Group",
            source_ids=[model.primary_shape.id],
            anchor_view_id=document.projection_group.anchor_view_id,
            projection_type=page.projection_type,
        )
        for view in document.views:
            part_view = DrawViewPart(
                id=view.id,
                label=view.label,
                x_mm=view.placement.x_mm,
                y_mm=view.placement.y_mm,
                scale=view.placement.scale,
                source_ids=[view.source_ref.shape_id],
                hard_hidden=view.kind in {"front", "right", "left", "rear", "bottom"},
            )
            group.add_view(
                DrawProjGroupItem(
                    id=f"{view.id}-item",
                    label=view.label,
                    x_mm=view.placement.x_mm,
                    y_mm=view.placement.y_mm,
                    scale=view.placement.scale,
                    projection_type=view.kind.title(),
                    parent_group_id=group.id,
                )
            )
            page.add_view(part_view)
        return page

    def decorate_document(
        self,
        model: CanonicalCadModel,
        projection: ProjectionBundle,
        document: DrawingDocument,
    ) -> DrawingDocument:
        template = load_svg_template(DEFAULT_TEMPLATE_PATH)
        rendered_svg = template.process_template(self._field_values(model, document))
        page = self.build_page(model, projection, document)
        template_definition = PageTemplateDefinition(
            id=document.page_template.id,
            name="FreeCAD TechDraw ISO 5457 A3 Minimal",
            svg_source=rendered_svg,
            field_ids=list(template.editable_texts.keys()),
            source_path=str(DEFAULT_TEMPLATE_PATH),
            editable_metadata=template.editable_texts,
        )
        title_block_fields = self._build_title_block_fields(model, document)
        return document.model_copy(
            update={
                "page_template": template_definition,
                "title_block_fields": title_block_fields,
                "techdraw_runtime": {
                    **self.runtime.as_dict(),
                    "page_id": page.id,
                    "projection_group_id": "proj-group-001",
                },
            }
        )

    def _build_title_block_fields(self, model: CanonicalCadModel, document: DrawingDocument) -> list[TitleBlockField]:
        values = self._field_values(model, document)
        fields: list[TitleBlockField] = []
        for editable in extract_editable_texts(DEFAULT_TEMPLATE_PATH):
            fields.append(
                TitleBlockField(
                    id=f"tb-{editable.name}",
                    label=editable.name.replace("_", " ").title(),
                    value=values.get(editable.name, editable.default_value),
                    placement=AnnotationPlacement(x_mm=editable.x_mm, y_mm=editable.y_mm, user_locked=True),
                    width_mm=max(editable.width_mm or 28.0, 12.0),
                    editable=True,
                    autofill_key=editable.autofill_key,
                )
            )
        return fields

    def _field_values(self, model: CanonicalCadModel, document: DrawingDocument) -> dict[str, str]:
        front_view = next((view for view in document.views if view.kind == "front"), None)
        scale_value = front_view.placement.scale if front_view else 1.0
        values = {
            "approval_person": "",
            "creator": "autodrawing",
            "date_of_issue": date.today().isoformat(),
            "document_type": "Component Drawing",
            "drawing_number": model.source_name,
            "general_tolerances": f"ISO 2768-m / {drawing_unit_system(model.units)}",
            "language_code": "EN",
            "legal_owner_1": "autodrawing",
            "legal_owner_2": "",
            "legal_owner_3": "",
            "legal_owner_4": "",
            "part_material": model.metadata.get("material", "Not specified"),
            "revision_index": "A",
            "scale": self._format_scale(scale_value),
            "sheet_number": "1 / 1",
            "title": model.primary_shape.name,
        }
        for field in document.title_block_fields:
            editable_name = field.id[3:] if field.id.startswith("tb-") else field.id
            default_value = values.get(editable_name)
            if default_value is None:
                values[editable_name] = field.value
                continue
            if editable_name == "general_tolerances" and field.value == f"ISO 2768-m / {model.units}":
                continue
            if field.value != default_value:
                values[editable_name] = field.value
        return values

    def _format_scale(self, scale: float) -> str:
        rounded = round(scale, 2)
        if rounded <= 0:
            return "1 : 1"
        if rounded < 1:
            return f"1 : {round(1 / rounded, 2):g}"
        return f"{rounded:g} : 1"
