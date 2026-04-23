import unittest
from pathlib import Path

from autodrawing.importers import StepImportError, StepImportService
from autodrawing.pipeline import AutodrawingPipeline


class ImporterPipelineTests(unittest.TestCase):
    def test_importer_extracts_units_and_bbox(self):
        model = StepImportService().import_file("fixtures/step/simple-block.step")

        self.assertEqual(model.units, "mm")
        self.assertAlmostEqual(model.primary_shape.bounding_box.size.x, 120.0)
        self.assertAlmostEqual(model.primary_shape.bounding_box.size.z, 40.0)

    def test_importer_detects_hole_pattern_and_section_candidate(self):
        model = StepImportService().import_file("fixtures/step/hole-pattern.step")
        kinds = {hint.kind for hint in model.primary_shape.feature_hints}

        self.assertIn("hole-pattern", kinds)
        self.assertIn("section-candidate", kinds)

    def test_importer_extracts_cube_fixture_bbox(self):
        model = StepImportService().import_file("fixtures/step/cube-30.step")

        self.assertEqual(model.primary_shape.name, "Cube 30")
        self.assertAlmostEqual(model.primary_shape.bounding_box.size.x, 30.0)
        self.assertAlmostEqual(model.primary_shape.bounding_box.size.y, 30.0)
        self.assertAlmostEqual(model.primary_shape.bounding_box.size.z, 30.0)
        self.assertEqual(len(model.primary_shape.source_edges), 12)

    def test_importer_extracts_step_edge_topology_from_sample_part(self):
        sample = Path("sample_part/sample.STEP")
        if not sample.exists():
            self.skipTest("sample STEP part is not checked out")

        model = StepImportService().import_file(sample)

        self.assertGreater(len(model.primary_shape.source_edges), 20)
        self.assertTrue(any(edge.curve_kind == "circle" for edge in model.primary_shape.source_edges))

    def test_importer_rejects_non_step_content(self):
        with self.assertRaises(StepImportError):
            StepImportService().import_file("fixtures/step/invalid-missing-header.step")

    def test_pipeline_builds_views_for_fixture(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/hole-pattern.step", mode="final")
        kinds = {view.kind for view in bundle.projection.views}
        isometric = next(view for view in bundle.projection.views if view.kind == "isometric")

        self.assertEqual(bundle.projection.adapter, "occt")
        self.assertTrue({"front", "top", "right", "isometric"} <= kinds)
        self.assertTrue(bundle.scene_graph.layers["centerlines"])
        self.assertFalse(isometric.hidden_edges)

    def test_plate_like_part_uses_broad_face_as_front_view(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/hole-pattern.step", mode="final")
        front = next(view for view in bundle.projection.views if view.kind == "front")
        top = next(view for view in bundle.projection.views if view.kind == "top")

        self.assertGreater(front.bounds.height, 50.0)
        self.assertLess(top.bounds.height, front.bounds.height)
        self.assertGreater(front.bounds.width * front.bounds.height, top.bounds.width * top.bounds.height)

    def test_cube_isometric_shows_only_visible_wireframe_edges(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/cube-30.step", mode="final")
        isometric = next(view for view in bundle.projection.views if view.kind == "isometric")

        self.assertFalse(isometric.hidden_edges)
        self.assertEqual(len(isometric.visible_edges), 9)

    def test_pipeline_projects_sample_part_from_source_edges(self):
        sample = Path("sample_part/sample.STEP")
        if not sample.exists():
            self.skipTest("sample STEP part is not checked out")

        bundle = AutodrawingPipeline().from_step_file(sample, mode="final")
        front = next(view for view in bundle.projection.views if view.kind == "front")
        iso_faces = [
            item
            for item in bundle.scene_graph.layers["viewGeometryVisible"]
            if "view-isometric-shaded-face" in item.classes
        ]

        self.assertTrue(any(edge.id.startswith("front-step-edge-") for edge in front.visible_edges))
        self.assertTrue(iso_faces)


if __name__ == "__main__":
    unittest.main()
