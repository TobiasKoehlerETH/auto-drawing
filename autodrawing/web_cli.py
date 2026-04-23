from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import AutodrawingPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate an OSS-first drawing bundle from a STEP file")
    parser.add_argument("--input", required=True, type=Path, help="Input STEP file")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output directory")
    parser.add_argument("--mode", choices=["preview", "final"], default="preview")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bundle = AutodrawingPipeline().from_step_file(args.input, mode=args.mode)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    bundle_json = args.out_dir / "bundle.json"
    html_path = args.out_dir / bundle.document.export_settings.html_filename
    bundle_json.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2), encoding="utf-8")
    html_path.write_text(AutodrawingPipeline().render_html(bundle), encoding="utf-8")
    print(json.dumps({"bundle": str(bundle_json), "html": str(html_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
