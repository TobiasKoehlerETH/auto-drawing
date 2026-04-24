import unittest
from xml.etree import ElementTree as ET

from autodrawing.exporters import HtmlExportService
from autodrawing.pipeline import AutodrawingPipeline
from autodrawing.techdraw_exact import DEFAULT_TEMPLATE_PATH
from autodrawing.techdraw_exact.svg_templates import NS, extract_editable_texts, load_svg_template, render_svg_template


class TechDrawExactTests(unittest.TestCase):
    def test_default_template_contains_expected_editable_fields(self):
        template = load_svg_template(DEFAULT_TEMPLATE_PATH)
        editable_names = {item.name for item in extract_editable_texts(DEFAULT_TEMPLATE_PATH)}

        self.assertEqual(template.orientation, "landscape")
        self.assertIn("title", editable_names)
        self.assertIn("drawing_number", editable_names)
        self.assertIn("scale", editable_names)

    def test_pipeline_uses_techdraw_native_adapter(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/simple-block.step", mode="final")
        front = next(view for view in bundle.document.views if view.kind == "front")
        isometric = next(view for view in bundle.document.views if view.kind == "isometric")

        self.assertEqual(bundle.projection.adapter, "techdraw-native")
        self.assertEqual(front.placement.scale, 1.0)
        self.assertEqual(isometric.placement.scale, 0.5)
        self.assertTrue(bundle.document.page_template.source_path)
        self.assertIn("title", bundle.document.page_template.editable_metadata)
        self.assertTrue(bundle.document.techdraw_runtime)
        self.assertEqual(bundle.document.techdraw_runtime["projection_group_id"], "proj-group-001")
        self.assertIn("1 : 1", bundle.document.page_template.svg_source)

    def test_svg_export_uses_processed_template_content(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/simple-block.step", mode="final")
        svg = HtmlExportService().render_svg(bundle)

        self.assertIn("Component Drawing", svg)
        self.assertIn("autodrawing", svg)

    def test_rendered_template_removes_black_corner_trimming_marks(self):
        rendered = render_svg_template(DEFAULT_TEMPLATE_PATH, {"title": "Trimless title"})
        root = ET.fromstring(rendered)

        self.assertIsNone(root.find(".//*[@id='trimming_marks']"))
        self.assertIsNone(root.find(".//*[@id='top_left_trimming']"))
        self.assertIsNone(root.find(".//*[@id='bottom_right_trimming']"))

    def test_rendered_template_constrains_long_text_inside_field_width(self):
        rendered = render_svg_template(DEFAULT_TEMPLATE_PATH, {"title": "Very long title " * 12})
        root = ET.fromstring(rendered)
        title_field = root.find(".//svg:text[@id='title_data_field']", NS)

        self.assertIsNotNone(title_field)
        self.assertEqual(title_field.attrib.get("lengthAdjust"), "spacingAndGlyphs")
        self.assertLessEqual(float(title_field.attrib.get("textLength", "0")), 78.0)


if __name__ == "__main__":
    unittest.main()
