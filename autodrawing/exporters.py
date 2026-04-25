from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

from .contracts import PipelineBundle, SceneGraph, SceneItem
from .view_planner import placed_bounds


class HtmlExportService:
    def render_html(self, bundle: PipelineBundle) -> str:
        svg = self.render_svg(bundle)
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{bundle.canonical_model.source_name}</title>
  <style>
    @page {{ size: A3 landscape; margin: 8mm; }}
    :root {{ color-scheme: only light; }}
    body {{ margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif; background: white; }}
    svg {{ width: 100%; height: auto; display: block; background: white; }}
    path, rect, circle {{ fill: none; stroke: #111827; stroke-width: 0.35; }}
    .sheet-frame {{ stroke-width: 0.5; }}
    .title-block-grid, .projection-symbol {{ stroke-width: 0.25; }}
    .hidden {{ stroke: #475569; stroke-width: 0.18; stroke-dasharray: 2 1.2; opacity: 0.58; }}
    .centerline {{ stroke-dasharray: 10 3 2 3; }}
    .smooth {{ stroke: #334155; }}
    .dimension-line {{ stroke: #111827; stroke-width: 0.25; }}
    .extension-line {{ stroke-width: 0.18; }}
    .leader-line {{ stroke-width: 0.25; }}
    .arrowhead {{ fill: #111827; stroke: #111827; stroke-width: 0.18; }}
    .dimension-text, .note, .view-label, .title-block-field {{ font-size: 4px; fill: #0f172a; stroke: none; }}
    .view-label {{ font-weight: 600; letter-spacing: 0.02em; }}
  </style>
</head>
<body>
{svg}
</body>
</html>
"""

    def render_svg(self, bundle: PipelineBundle) -> str:
        scene = bundle.scene_graph
        body: list[str] = []
        use_template_background = bool(bundle.document.page_template.source_path and bundle.document.page_template.svg_source.strip())

        if use_template_background:
            body.extend(self._render_template_background(bundle.document.page_template.svg_source))

        for layer_name in (() if use_template_background else ("frame", "titleBlock")):
            for item in scene.layers.get(layer_name, []):
                body.append(self._render_item(item))

        items_by_group = self._group_items(scene)
        views_by_id = {view.id: view for view in bundle.document.views}
        for view_id in bundle.document.view_order:
            view = views_by_id[view_id]
            bounds = placed_bounds(view.local_bounds, view.placement)
            items = items_by_group.get(view_id, [])
            rendered = "".join(self._render_item(item) for item in items)
            body.append(
                "<g "
                f'data-view-id="{self._escape(view.id)}" '
                f'data-view-kind="{self._escape(view.kind)}" '
                f'data-view-label="{self._escape(view.label)}" '
                f'data-view-bounds="{bounds.x_min:.2f},{bounds.y_min:.2f},{bounds.x_max:.2f},{bounds.y_max:.2f}"'
                ">"
                f"{rendered}</g>"
            )

        for layer_name in ("dimensions", "notes", "bom", "selectionOverlay"):
            for item in scene.layers.get(layer_name, []):
                if item.group_id:
                    continue
                body.append(self._render_item(item))

        return (
            f'<svg class="drawing-canvas" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {scene.width_mm:.2f} {scene.height_mm:.2f}">'
            + "".join(body)
            + "</svg>"
        )

    def _render_template_background(self, svg_source: str) -> list[str]:
        try:
            root = ET.fromstring(svg_source)
        except ET.ParseError:
            return [svg_source]
        return [ET.tostring(child, encoding="unicode") for child in list(root)]

    def _group_items(self, scene: SceneGraph) -> dict[str, list[SceneItem]]:
        ordered_layers = ("viewGeometryVisible", "viewGeometryHidden", "sectionHatch", "centerlines", "notes")
        grouped: dict[str, list[SceneItem]] = {}
        for layer_name in ordered_layers:
            for item in scene.layers.get(layer_name, []):
                if not item.group_id:
                    continue
                grouped.setdefault(item.group_id, []).append(item)
        return grouped

    def _render_item(self, item: SceneItem) -> str:
        classes = " ".join(item.classes)
        class_attr = f' class="{classes}"' if classes else ""
        if item.kind == "path":
            return f'<path{class_attr} d="{self._escape(item.path_data or "")}" />'
        if item.kind == "rect":
            return (
                f'<rect{class_attr} x="{item.x:.2f}" y="{item.y:.2f}" width="{item.width:.2f}" '
                f'height="{item.height:.2f}" />'
            )
        if item.kind == "circle":
            return f'<circle{class_attr} cx="{item.x:.2f}" cy="{item.y:.2f}" r="{item.radius:.2f}" />'
        if item.kind == "text":
            return f'<text{class_attr} x="{item.x:.2f}" y="{item.y:.2f}">{self._escape(item.text or "")}</text>'
        raise ValueError(f"Unsupported scene item kind: {item.kind}")

    def _escape(self, text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )


class PdfExportService:
    def export_pdf(self, bundle: PipelineBundle, output_path: str | Path, frontend_dir: str | Path) -> Path:
        html = HtmlExportService().render_html(bundle)
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as temp_dir:
            html_path = Path(temp_dir) / "drawing.html"
            html_path.write_text(html, encoding="utf-8")
            script_path = Path(frontend_dir) / "scripts" / "export-pdf.mjs"
            if not script_path.exists():
                raise RuntimeError("Puppeteer export script is missing")
            command = ["node", str(script_path), str(html_path), str(destination)]
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    check=False,
                    cwd=str(frontend_dir),
                    timeout=30,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Puppeteer PDF export timed out after 30 seconds") from exc
            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip() or "Puppeteer PDF export failed")
        return destination
