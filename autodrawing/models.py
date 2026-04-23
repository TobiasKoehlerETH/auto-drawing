from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SourceType = Literal["sldprt", "step"]
FamilyType = Literal["prismatic", "plate", "turned", "imported", "unsupported"]
Complexity = Literal["low", "medium", "high"]
DisplayModeName = Literal["hidden-lines-visible", "shaded-with-edges"]
ProjectionType = Literal["first-angle", "third-angle"]
ValidationStatus = Literal["pass", "warning", "needs_review", "fail"]


@dataclass
class BoundingBox:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @property
    def longest(self) -> float:
        return max(self.x, self.y, self.z)

    @property
    def shortest(self) -> float:
        return min(self.x, self.y, self.z)

    @property
    def middle(self) -> float:
        values = sorted((self.x, self.y, self.z))
        return values[1]

    @property
    def thickness_ratio(self) -> float:
        if self.longest <= 0:
            return 0.0
        return self.shortest / self.longest

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass
class PartProfile:
    source_type: SourceType
    family: FamilyType
    complexity: Complexity
    bounding_box: BoundingBox
    has_hole_pattern: bool
    needs_section: bool
    needs_detail: bool
    preferred_main_axis: str
    feature_types: list[str] = field(default_factory=list)
    feature_names: list[str] = field(default_factory=list)
    imported: bool = False
    unsupported_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "family": self.family,
            "complexity": self.complexity,
            "bounding_box": self.bounding_box.to_dict(),
            "has_hole_pattern": self.has_hole_pattern,
            "needs_section": self.needs_section,
            "needs_detail": self.needs_detail,
            "preferred_main_axis": self.preferred_main_axis,
            "feature_types": self.feature_types,
            "feature_names": self.feature_names,
            "imported": self.imported,
            "unsupported_reasons": self.unsupported_reasons,
        }


@dataclass
class ViewSpec:
    model_view: str
    role: str
    position: tuple[float, float]
    scale: float
    display_mode: DisplayModeName

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_view": self.model_view,
            "role": self.role,
            "position": [self.position[0], self.position[1]],
            "scale": self.scale,
            "display_mode": self.display_mode,
        }


@dataclass
class DrawingPlan:
    sheet_size: str
    projection: ProjectionType
    view_specs: list[ViewSpec]
    dimension_strategy: str
    metadata: dict[str, str]
    review_level: ValidationStatus
    required_dimension_roles: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sheet_size": self.sheet_size,
            "projection": self.projection,
            "view_specs": [view.to_dict() for view in self.view_specs],
            "dimension_strategy": self.dimension_strategy,
            "metadata": self.metadata,
            "review_level": self.review_level,
            "required_dimension_roles": self.required_dimension_roles,
        }


@dataclass
class OutputPaths:
    drawing: Path
    pdf: Path
    preview_png: Path
    trace_log: Path
    validation_json: Path
    working_source: Path | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "drawing": str(self.drawing),
            "pdf": str(self.pdf),
            "preview_png": str(self.preview_png),
            "trace_log": str(self.trace_log),
            "validation_json": str(self.validation_json),
            "working_source": str(self.working_source) if self.working_source else None,
        }


@dataclass
class GenerationRequest:
    input_path: Path
    out_dir: Path
    family: str = "auto"
    sheet: str = "A3"
    projection: ProjectionType = "first-angle"
    base_name: str | None = None


@dataclass
class ValidationReport:
    status: ValidationStatus
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    check_results: dict[str, bool] = field(default_factory=dict)
    input_path: str = ""
    output_paths: dict[str, str | None] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    plan: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "errors": self.errors,
            "warnings": self.warnings,
            "check_results": self.check_results,
            "input_path": self.input_path,
            "output_paths": self.output_paths,
            "profile": self.profile,
            "plan": self.plan,
            "metrics": self.metrics,
        }
