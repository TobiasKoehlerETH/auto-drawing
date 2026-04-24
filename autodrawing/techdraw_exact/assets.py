from __future__ import annotations

from pathlib import Path

TECHDRAW_ASSET_ROOT = Path(__file__).resolve().parent / "assets"
TEMPLATES_ROOT = TECHDRAW_ASSET_ROOT / "Templates"
PATTERNS_ROOT = TECHDRAW_ASSET_ROOT / "PAT"
LINE_GROUP_ROOT = TECHDRAW_ASSET_ROOT / "LineGroup"
SYMBOLS_ROOT = TECHDRAW_ASSET_ROOT / "Symbols"

DEFAULT_TEMPLATE_PATH = TEMPLATES_ROOT / "ISO" / "A3_Landscape_ISO5457_minimal.svg"
