from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module


@dataclass(frozen=True)
class TechDrawRuntimeStatus:
    exact_kernel_available: bool
    kernel_name: str | None
    detail: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def detect_runtime_status() -> TechDrawRuntimeStatus:
    try:
        import_module("OCP")
    except Exception as exc:  # pragma: no cover - environment dependent
        return TechDrawRuntimeStatus(
            exact_kernel_available=False,
            kernel_name=None,
            detail=f"OCP runtime unavailable: {type(exc).__name__}: {exc}",
        )
    return TechDrawRuntimeStatus(
        exact_kernel_available=True,
        kernel_name="OCP",
        detail="OCP runtime import succeeded.",
    )
