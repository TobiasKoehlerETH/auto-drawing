from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import DrawingEngine
from .models import GenerationRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a general single-part SolidWorks drawing")
    parser.add_argument("--input", required=True, type=Path, help="Input SLDPRT or STEP file")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--family", default="auto", choices=["auto", "prismatic", "plate", "turned"])
    parser.add_argument("--sheet", default="A3", choices=["A3"])
    parser.add_argument("--projection", default="first-angle", choices=["first-angle", "third-angle"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = DrawingEngine(root=Path.cwd())
    report = engine.generate(
        GenerationRequest(
            input_path=args.input,
            out_dir=args.out_dir,
            family=args.family,
            sheet=args.sheet,
            projection=args.projection,
        )
    )
    print(json.dumps(report.to_dict(), indent=2))
    if report.status == "fail":
        return 1
    if report.status == "needs_review":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
