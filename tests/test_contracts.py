import unittest

from autodrawing.contracts import PipelineBundle, SceneGraph, SceneItem
from autodrawing.pipeline import AutodrawingPipeline


class ContractsTests(unittest.TestCase):
    def test_pipeline_bundle_serializes_fixture(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/simple-block.step")
        payload = PipelineBundle.model_validate(bundle.model_dump(mode="json"))

        self.assertEqual(payload.canonical_model.source_format, "step")
        self.assertEqual(payload.document.sheet.size, "A3")
        self.assertIn("viewGeometryVisible", payload.scene_graph.layers)

    def test_scene_item_requires_geometry_fields(self):
        item = SceneItem(id="note-1", layer="notes", kind="text", x=10, y=20, text="Hello")
        scene = SceneGraph(
            schema_version="1.0",
            width_mm=100,
            height_mm=100,
            layers={
                "frame": [],
                "titleBlock": [],
                "viewGeometryVisible": [],
                "viewGeometryHidden": [],
                "sectionHatch": [],
                "centerlines": [],
                "dimensions": [],
                "notes": [item],
                "bom": [],
                "selectionOverlay": [],
            },
        )

        self.assertEqual(scene.layers["notes"][0].text, "Hello")


if __name__ == "__main__":
    unittest.main()
