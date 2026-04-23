from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Code\auto-drawing")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autodrawing.engine import DrawingEngine
from autodrawing.models import GenerationRequest

SAMPLE_PART = ROOT / "sample_part" / "sample.SLDPRT"
OUT_DIR = ROOT / ".generated" / "guideline_drawing"
BASE_NAME = "sample_guideline_attempt"


def main() -> int:
    engine = DrawingEngine(root=ROOT)
    report = engine.generate(
        GenerationRequest(
            input_path=SAMPLE_PART,
            out_dir=OUT_DIR,
            family="auto",
            sheet="A3",
            projection="first-angle",
            base_name=BASE_NAME,
        )
    )
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.status in {"pass", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
