from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SchemaVersion = Literal["1.0"]
Units = Literal["mm", "cm", "m", "in"]
ProjectionType = Literal["first-angle", "third-angle"]
ViewKind = Literal["front", "top", "right", "left", "rear", "bottom", "isometric", "section", "detail"]
ModeKind = Literal["preview", "final"]
Severity = Literal["info", "warning", "error"]
ValidationStatus = Literal["pass", "warning", "needs_review", "fail"]
LayerName = Literal[
    "frame",
    "titleBlock",
    "viewGeometryVisible",
    "viewGeometryHidden",
    "sectionHatch",
    "centerlines",
    "dimensions",
    "notes",
    "bom",
    "selectionOverlay",
]
CommandKind = Literal[
    "CreateDimension",
    "DeleteDimension",
    "MoveDimensionText",
    "MoveNote",
    "MoveView",
    "SetDimensionFormat",
    "SetDimensionMeasurementType",
    "SetTitleBlockField",
    "ReorderBomRow",
    "ChangeViewScale",
    "SetDisplayTransform",
]
PrimitiveKind = Literal["rect", "circle", "text", "path"]
DimensionType = Literal["Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle", "Angle3Pt"]


class Point2D(BaseModel):
    x: float
    y: float


class Point3D(BaseModel):
    x: float
    y: float
    z: float


class ImportedFloatArray(BaseModel):
    array: list[float]


class ImportedIndexArray(BaseModel):
    array: list[int]


class ImportedMeshAttributes(BaseModel):
    position: ImportedFloatArray
    normal: ImportedFloatArray | None = None


class ImportedMeshPayload(BaseModel):
    color: list[float] | None = None
    index: ImportedIndexArray
    name: str | None = None
    attributes: ImportedMeshAttributes


class OcctDrawingPreviewRequest(BaseModel):
    source_name: str
    meshes: list[ImportedMeshPayload]
    units: Units = "mm"
    mode: ModeKind = "preview"


class Bounds2D(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    @classmethod
    def from_extents(cls, x_min: float, y_min: float, x_max: float, y_max: float) -> "Bounds2D":
        return cls(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)

    @classmethod
    def from_points(cls, points: list[Point2D]) -> "Bounds2D":
        xs = [point.x for point in points]
        ys = [point.y for point in points]
        return cls.from_extents(min(xs), min(ys), max(xs), max(ys))

    @property
    def width(self) -> float:
        return self.x_max - self.x_min

    @property
    def height(self) -> float:
        return self.y_max - self.y_min

    def translated(self, dx: float, dy: float) -> "Bounds2D":
        return Bounds2D(
            x_min=self.x_min + dx,
            y_min=self.y_min + dy,
            x_max=self.x_max + dx,
            y_max=self.y_max + dy,
        )

    def scaled(self, scale: float) -> "Bounds2D":
        return Bounds2D(
            x_min=self.x_min * scale,
            y_min=self.y_min * scale,
            x_max=self.x_max * scale,
            y_max=self.y_max * scale,
        )


class Diagnostic(BaseModel):
    severity: Severity
    code: str
    message: str


class BoundingBox3D(BaseModel):
    min: Point3D
    max: Point3D
    size: Point3D

    @classmethod
    def from_extents(
        cls,
        min_x: float,
        min_y: float,
        min_z: float,
        max_x: float,
        max_y: float,
        max_z: float,
    ) -> "BoundingBox3D":
        return cls(
            min=Point3D(x=min_x, y=min_y, z=min_z),
            max=Point3D(x=max_x, y=max_y, z=max_z),
            size=Point3D(x=max_x - min_x, y=max_y - min_y, z=max_z - min_z),
        )

    @property
    def longest_axis(self) -> str:
        sizes = {"x": self.size.x, "y": self.size.y, "z": self.size.z}
        return max(sizes, key=sizes.get)


class FeatureHint(BaseModel):
    id: str
    kind: Literal["circular-hole", "hole-pattern", "cylindrical-axis", "section-candidate"]
    axis: Literal["x", "y", "z"] | None = None
    center: Point3D | None = None
    radius: float | None = None
    count: int = 1
    note: str | None = None


class SourceEdge3D(BaseModel):
    id: str
    start: Point3D
    end: Point3D
    curve_kind: Literal["line", "circle", "curve"] = "line"
    adjacent_normals: list[Point3D] = Field(default_factory=list)


class SourceTriangle3D(BaseModel):
    id: str
    a: Point3D
    b: Point3D
    c: Point3D


class ShapeSummary(BaseModel):
    id: str
    name: str
    kind: Literal["part", "assembly", "body"]
    bounding_box: BoundingBox3D
    principal_axes: list[Literal["x", "y", "z"]]
    feature_hints: list[FeatureHint] = Field(default_factory=list)
    source_edges: list[SourceEdge3D] = Field(default_factory=list)
    source_triangles: list[SourceTriangle3D] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class ComponentNode(BaseModel):
    id: str
    name: str
    shape_id: str | None = None
    quantity: int = 1
    repeated_group_id: str | None = None
    children: list["ComponentNode"] = Field(default_factory=list)


class CanonicalCadModel(BaseModel):
    schema_version: SchemaVersion = "1.0"
    source_format: Literal["step"] = "step"
    standards_profile: Literal["iso"] = "iso"
    source_name: str
    units: Units = "mm"
    metadata: dict[str, str] = Field(default_factory=dict)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    shapes: list[ShapeSummary]
    root_component: ComponentNode
    gdandt_notes: list[str] = Field(default_factory=list)

    @property
    def primary_shape(self) -> ShapeSummary:
        return self.shapes[0]


class ProjectionSourceRef(BaseModel):
    id: str
    shape_id: str
    role: str
    entity_kind: Literal["view", "edge", "circle", "arc"] = "view"


class ProjectedEdge(BaseModel):
    id: str
    points: list[Point2D]
    source_ref: ProjectionSourceRef
    style_role: Literal["visible", "hidden", "smooth", "centerline", "hatch"] = "visible"

    @model_validator(mode="after")
    def _validate_points(self) -> "ProjectedEdge":
        if len(self.points) < 2:
            raise ValueError("ProjectedEdge requires at least two points")
        return self


class ProjectedCircle(BaseModel):
    id: str
    center: Point2D
    radius: float
    source_ref: ProjectionSourceRef


class ProjectedArc(BaseModel):
    id: str
    center: Point2D
    radius: float
    start: Point2D
    end: Point2D
    source_ref: ProjectionSourceRef


class ProjectedViewGeometry(BaseModel):
    id: str
    kind: ViewKind
    label: str
    source_ref: ProjectionSourceRef
    bounds: Bounds2D
    visible_edges: list[ProjectedEdge] = Field(default_factory=list)
    hidden_edges: list[ProjectedEdge] = Field(default_factory=list)
    smooth_edges: list[ProjectedEdge] = Field(default_factory=list)
    circles: list[ProjectedCircle] = Field(default_factory=list)
    arcs: list[ProjectedArc] = Field(default_factory=list)
    centerlines: list[ProjectedEdge] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectionBundle(BaseModel):
    schema_version: SchemaVersion = "1.0"
    model_name: str
    mode: ModeKind
    adapter: Literal["occt", "techdraw-native", "techdraw-oracle"] = "occt"
    views: list[ProjectedViewGeometry]


class SheetDefinition(BaseModel):
    size: Literal["A3"] = "A3"
    orientation: Literal["landscape"] = "landscape"
    width_mm: float
    height_mm: float
    standards_profile: Literal["iso"] = "iso"
    projection: ProjectionType = "first-angle"


class ViewPlacement(BaseModel):
    x_mm: float
    y_mm: float
    scale: float = 1.0
    user_locked: bool = False


class DrawingView(BaseModel):
    id: str
    kind: ViewKind
    label: str
    geometry_id: str
    source_ref: ProjectionSourceRef
    placement: ViewPlacement
    local_bounds: Bounds2D
    parent_view_id: str | None = None
    projection_role: str | None = None
    techdraw_type: str | None = None


class AnchorRef(BaseModel):
    view_id: str
    primitive_id: str
    role: str


class AnnotationPlacement(BaseModel):
    x_mm: float
    y_mm: float
    user_locked: bool = False


class DimensionObject(BaseModel):
    id: str
    view_id: str
    label: str
    value: float
    units: Units = "mm"
    anchor_a: AnchorRef
    anchor_b: AnchorRef
    placement: AnnotationPlacement
    dimension_type: DimensionType = "Distance"
    style_profile: Literal["iso"] = "iso"
    measurement_type: Literal["True", "Projected"] = "Projected"
    references: list[str] = Field(default_factory=list)
    references_2d: list[str] = Field(default_factory=list)
    references_3d: list[str] = Field(default_factory=list)
    computed_geometry: dict[str, Any] = Field(default_factory=dict)
    formatted_text: str | None = None
    format_spec: str | None = None


class NoteObject(BaseModel):
    id: str
    view_id: str | None = None
    text: str
    placement: AnnotationPlacement


class BomRow(BaseModel):
    id: str
    item_number: int
    component_id: str
    name: str
    quantity: int


class BalloonObject(BaseModel):
    id: str
    bom_row_id: str
    view_id: str
    text: str
    placement: AnnotationPlacement
    leader_points: list[Point2D] = Field(default_factory=list)


class TitleBlockField(BaseModel):
    id: str
    label: str
    value: str
    placement: AnnotationPlacement
    width_mm: float = 28.0
    editable: bool = True
    autofill_key: str | None = None


class PageTemplateDefinition(BaseModel):
    id: str
    name: str
    svg_source: str
    field_ids: list[str] = Field(default_factory=list)
    source_path: str | None = None
    editable_metadata: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ProjectionGroupLayout(BaseModel):
    anchor_view_id: str
    ordered_view_ids: list[str] = Field(default_factory=list)
    projection: ProjectionType = "first-angle"


class ExportSettings(BaseModel):
    html_filename: str = "drawing.html"
    pdf_filename: str = "drawing.pdf"
    include_hidden_lines: bool = True


class DrawingCommand(BaseModel):
    id: str
    kind: CommandKind
    target_id: str
    before: dict[str, Any]
    after: dict[str, Any]


class DrawingDocument(BaseModel):
    schema_version: SchemaVersion = "1.0"
    canonical_model_name: str
    sheet: SheetDefinition
    page_template: PageTemplateDefinition
    projection_group: ProjectionGroupLayout
    view_order: list[str] = Field(default_factory=list)
    views: list[DrawingView]
    dimensions: list[DimensionObject] = Field(default_factory=list)
    notes: list[NoteObject] = Field(default_factory=list)
    bom_rows: list[BomRow] = Field(default_factory=list)
    balloons: list[BalloonObject] = Field(default_factory=list)
    title_block_fields: list[TitleBlockField] = Field(default_factory=list)
    export_settings: ExportSettings = Field(default_factory=ExportSettings)
    display_transforms: dict[str, str] = Field(default_factory=dict)
    commands: list[DrawingCommand] = Field(default_factory=list)
    redo_commands: list[DrawingCommand] = Field(default_factory=list)
    techdraw_runtime: dict[str, Any] = Field(default_factory=dict)


class SceneItem(BaseModel):
    id: str
    layer: LayerName
    kind: PrimitiveKind
    group_id: str | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    radius: float | None = None
    path_data: str | None = None
    text: str | None = None
    classes: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_geometry(self) -> "SceneItem":
        if self.kind == "rect":
            if self.x is None or self.y is None or self.width is None or self.height is None:
                raise ValueError("rect requires x, y, width, and height")
        elif self.kind == "circle":
            if self.x is None or self.y is None or self.radius is None:
                raise ValueError("circle requires x, y, and radius")
        elif self.kind == "text":
            if self.x is None or self.y is None or self.text is None:
                raise ValueError("text requires x, y, and text")
        elif self.kind == "path":
            if not self.path_data:
                raise ValueError("path requires path_data")
        return self


class SceneGraph(BaseModel):
    schema_version: SchemaVersion = "1.0"
    width_mm: float
    height_mm: float
    layers: dict[LayerName, list[SceneItem]]


class PipelineBundle(BaseModel):
    canonical_model: CanonicalCadModel
    projection: ProjectionBundle
    document: DrawingDocument
    scene_graph: SceneGraph


class PreviewValidation(BaseModel):
    status: ValidationStatus = "pass"
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class PreviewQaSummary(BaseModel):
    status: ValidationStatus = "pass"
    view_count: int = 0
    visible_edge_count: int = 0
    hidden_edge_count: int = 0
    smooth_edge_count: int = 0
    circle_count: int = 0
    arc_count: int = 0


class PreviewViewState(BaseModel):
    id: str
    kind: ViewKind
    label: str
    x_mm: float
    y_mm: float
    scale: float
    width_mm: float
    height_mm: float
    selection_bounds_mm: Bounds2D
    source_ref: ProjectionSourceRef


class DrawingPreview(BaseModel):
    preview_id: str
    mode: ModeKind
    svg: str
    document: DrawingDocument
    projection: ProjectionBundle
    scene_graph: SceneGraph
    views: list[PreviewViewState]
    validation: PreviewValidation
    qa_summary: PreviewQaSummary
    editable_plan_available: bool = True
    dimension_editing_available: bool = False
    tracked_draw_bridge_available: bool = False


ComponentNode.model_rebuild()
