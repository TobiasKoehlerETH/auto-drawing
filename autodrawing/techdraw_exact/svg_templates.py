from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from xml.etree import ElementTree as ET

from .assets import DEFAULT_TEMPLATE_PATH
from .model import DrawSVGTemplate

SVG_NS = "http://www.w3.org/2000/svg"
FREECAD_NS = "https://www.freecad.org/wiki/index.php?title=Svg_Namespace"
NS = {"svg": SVG_NS, "freecad": FREECAD_NS}
TEXT_WIDTH_FACTOR = 0.62
TEXT_PADDING_MM = 1.0
TITLE_BLOCK_FONT_FAMILY = "Segoe UI"
TITLE_BLOCK_TEXT_GROUP_IDS = {"title_block_labels", "title_block_data_fields"}


@dataclass(frozen=True)
class RectBounds:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width


@dataclass(frozen=True)
class EditableText:
    name: str
    x_mm: float
    y_mm: float
    default_value: str
    autofill_key: str | None
    width_mm: float | None
    font_size_mm: float
    text_anchor: str


def _parse_length_mm(raw: str) -> float:
    value = raw.strip().lower().replace("mm", "")
    return float(value or 0.0)


def _orientation(width_mm: float, height_mm: float) -> str:
    return "landscape" if width_mm >= height_mm else "portrait"


def load_svg_template(path: Path = DEFAULT_TEMPLATE_PATH) -> DrawSVGTemplate:
    root = ET.parse(path).getroot()
    width_mm = _parse_length_mm(root.attrib.get("width", "0"))
    height_mm = _parse_length_mm(root.attrib.get("height", "0"))
    editable_texts = {
        item.name: {
            "x_mm": item.x_mm,
            "y_mm": item.y_mm,
            "default_value": item.default_value,
            "autofill_key": item.autofill_key,
            "width_mm": item.width_mm,
            "font_size_mm": item.font_size_mm,
            "text_anchor": item.text_anchor,
        }
        for item in extract_editable_texts(path)
    }
    return DrawSVGTemplate(
        width_mm=width_mm,
        height_mm=height_mm,
        orientation=_orientation(width_mm, height_mm),
        source_path=path,
        editable_texts=editable_texts,
        page_result=str(path),
    )


def extract_editable_texts(path: Path = DEFAULT_TEMPLATE_PATH) -> list[EditableText]:
    root = ET.parse(path).getroot()
    parent_map = {child: parent for parent in root.iter() for child in parent}
    rects_by_id = _extract_rectangles_by_id(root)
    drawing_frame = rects_by_id.get("drawing_space_frame")
    items: list[EditableText] = []
    for element in root.findall(".//svg:text", NS):
        editable_name = element.attrib.get(f"{{{FREECAD_NS}}}editable")
        if not editable_name:
            continue
        tspan = element.find("svg:tspan", NS)
        default_value = ""
        if tspan is not None and tspan.text:
            default_value = tspan.text
        items.append(
            EditableText(
                name=editable_name,
                x_mm=float(element.attrib.get("x", "0")),
                y_mm=float(element.attrib.get("y", "0")),
                default_value=default_value,
                autofill_key=element.attrib.get(f"{{{FREECAD_NS}}}autofill"),
                width_mm=_max_text_width_mm(element, editable_name, parent_map, rects_by_id, drawing_frame),
                font_size_mm=_effective_font_size_mm(element, parent_map),
                text_anchor=_effective_style_value(element, parent_map, "text-anchor", "start"),
            )
        )
    return items


def render_svg_template(path: Path, substitutions: dict[str, str]) -> str:
    tree = ET.parse(path)
    root = tree.getroot()
    parent_map = {child: parent for parent in root.iter() for child in parent}
    rects_by_id = _extract_rectangles_by_id(root)
    drawing_frame = rects_by_id.get("drawing_space_frame")
    _remove_elements_by_id(root, {"trimming_marks"})
    for element in root.findall(".//svg:text", NS):
        editable_name = element.attrib.get(f"{{{FREECAD_NS}}}editable")
        if not editable_name:
            continue
        tspan = element.find("svg:tspan", NS)
        if tspan is None:
            tspan = ET.SubElement(element, f"{{{SVG_NS}}}tspan")
        replacement = substitutions.get(editable_name)
        if replacement is not None:
            tspan.text = replacement
        _constrain_editable_text(element, editable_name, tspan.text or "", parent_map, rects_by_id, drawing_frame)
    _apply_title_block_font(root)
    return ET.tostring(root, encoding="unicode")


def _extract_rectangles_by_id(root: ET.Element) -> dict[str, RectBounds]:
    rects: dict[str, RectBounds] = {}
    for rect in root.findall(".//svg:rect", NS):
        element_id = rect.attrib.get("id")
        if not element_id:
            continue
        rects[element_id] = RectBounds(
            x=float(rect.attrib.get("x", "0")),
            y=float(rect.attrib.get("y", "0")),
            width=float(rect.attrib.get("width", "0")),
            height=float(rect.attrib.get("height", "0")),
        )
    return rects


def _remove_elements_by_id(root: ET.Element, ids: set[str]) -> None:
    for parent in root.iter():
        for child in list(parent):
            if child.attrib.get("id") in ids:
                parent.remove(child)


def _apply_title_block_font(root: ET.Element) -> None:
    for element in root.iter():
        if element.attrib.get("id") in TITLE_BLOCK_TEXT_GROUP_IDS:
            _set_style_value(element, "font-family", TITLE_BLOCK_FONT_FAMILY)


def _constrain_editable_text(
    element: ET.Element,
    editable_name: str,
    text: str,
    parent_map: dict[ET.Element, ET.Element],
    rects_by_id: dict[str, RectBounds],
    drawing_frame: RectBounds | None,
) -> None:
    if not text.strip():
        element.attrib.pop("textLength", None)
        element.attrib.pop("lengthAdjust", None)
        return

    max_width = _max_text_width_mm(element, editable_name, parent_map, rects_by_id, drawing_frame)
    if max_width is None or max_width <= 0:
        return

    font_size = _effective_font_size_mm(element, parent_map)
    estimated_width = _estimate_text_width_mm(text, font_size)
    if estimated_width <= max_width:
        element.attrib.pop("textLength", None)
        element.attrib.pop("lengthAdjust", None)
        return

    element.set("textLength", f"{max_width:.2f}")
    element.set("lengthAdjust", "spacingAndGlyphs")


def _max_text_width_mm(
    element: ET.Element,
    editable_name: str,
    parent_map: dict[ET.Element, ET.Element],
    rects_by_id: dict[str, RectBounds],
    drawing_frame: RectBounds | None,
) -> float | None:
    border_id = _border_id_for_field(editable_name, rects_by_id)
    if border_id:
        return max(rects_by_id[border_id].width - (TEXT_PADDING_MM * 2), 1.0)

    if not drawing_frame:
        return None

    x = float(element.attrib.get("x", "0"))
    anchor = _effective_style_value(element, parent_map, "text-anchor", "start")
    if anchor == "middle":
        return max((min(x - drawing_frame.x, drawing_frame.right - x) * 2) - (TEXT_PADDING_MM * 2), 1.0)
    if anchor == "end":
        return max((x - drawing_frame.x) - (TEXT_PADDING_MM * 2), 1.0)
    return max((drawing_frame.right - x) - TEXT_PADDING_MM, 1.0)


def _border_id_for_field(editable_name: str, rects_by_id: dict[str, RectBounds]) -> str | None:
    direct = f"{editable_name}_border"
    if direct in rects_by_id:
        return direct

    numbered_owner = re.fullmatch(r"(legal_owner)_\d+", editable_name)
    if numbered_owner:
        border_id = f"{numbered_owner.group(1)}_border"
        if border_id in rects_by_id:
            return border_id

    if editable_name.startswith("supplementary_title_") and "title_border" in rects_by_id:
        return "title_border"

    return None


def _effective_font_size_mm(element: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> float:
    raw = _effective_style_value(element, parent_map, "font-size", "5")
    return float(raw.replace("px", "") or 5)


def _effective_style_value(element: ET.Element, parent_map: dict[ET.Element, ET.Element], key: str, default: str) -> str:
    current: ET.Element | None = element
    resolved = default
    chain: list[ET.Element] = []
    while current is not None:
        chain.append(current)
        current = parent_map.get(current)
    for node in reversed(chain):
        if key in node.attrib:
            resolved = node.attrib[key]
        styles = _parse_style(node.attrib.get("style", ""))
        if key in styles:
            resolved = styles[key]
    return resolved


def _parse_style(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    styles: dict[str, str] = {}
    for entry in raw.split(";"):
        if ":" not in entry:
            continue
        key, value = entry.split(":", 1)
        styles[key.strip()] = value.strip()
    return styles


def _set_style_value(element: ET.Element, key: str, value: str) -> None:
    styles = _parse_style(element.attrib.get("style", ""))
    styles[key] = value
    element.set("style", ";".join(f"{style_key}:{style_value}" for style_key, style_value in styles.items()))


def _estimate_text_width_mm(text: str, font_size_mm: float) -> float:
    width_units = 0.0
    for character in text:
        if character.isspace():
            width_units += 0.35
            continue
        if character in "1ilI.,:;|/":
            width_units += 0.38
            continue
        if character in "MW@%#":
            width_units += 0.95
            continue
        width_units += TEXT_WIDTH_FACTOR
    return width_units * font_size_mm
