from .contracts import CanonicalCadModel, DrawingDocument, PipelineBundle, ProjectionBundle, SceneGraph
from .pipeline import AutodrawingPipeline

__all__ = [
    "AutodrawingPipeline",
    "CanonicalCadModel",
    "DrawingDocument",
    "PipelineBundle",
    "ProjectionBundle",
    "SceneGraph",
    "DrawingEngine",
    "GenerationRequest",
]


def __getattr__(name: str):
    if name in {"DrawingEngine", "GenerationRequest"}:
        from .engine import DrawingEngine  # type: ignore
        from .models import GenerationRequest  # type: ignore

        exports = {
            "DrawingEngine": DrawingEngine,
            "GenerationRequest": GenerationRequest,
        }
        return exports[name]
    raise AttributeError(name)
