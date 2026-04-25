import unittest

from autodrawing.importers import StepImportService
from autodrawing.projection import ProjectionService
from autodrawing.standards import DEFAULT_VIEW_GAP_MM, TITLE_BLOCK_BOUNDS_MM
from autodrawing.view_planner import placed_bounds, plan_view_pack, select_hidden_line_policy


class ViewPlannerTests(unittest.TestCase):
    def test_hidden_line_policy_hides_isometric(self):
        model = StepImportService().import_file("fixtures/step/hole-pattern.step")

        self.assertFalse(select_hidden_line_policy(model, "isometric", default=True))
        self.assertTrue(select_hidden_line_policy(model, "front", default=False))

    def test_first_angle_layout_places_top_below_front_and_right_left_of_front(self):
        model = StepImportService().import_file("fixtures/step/cube-30.step")
        projection = ProjectionService().build_projection(model, mode="final")

        placements = plan_view_pack(projection, model, "first-angle")

        self.assertGreater(placements["top"].y_mm, placements["front"].y_mm)
        self.assertLess(placements["right"].x_mm, placements["front"].x_mm)
        self.assertEqual(placements["front"].scale, 1.0)
        self.assertEqual(placements["front"].scale, placements["top"].scale)
        self.assertEqual(placements["right"].scale, placements["top"].scale)
        self.assertEqual(placements["isometric"].scale, 0.5)

    def test_isometric_defaults_above_title_block(self):
        model = StepImportService().import_file("fixtures/step/cube-30.step")
        projection = ProjectionService().build_projection(model, mode="final")

        placements = plan_view_pack(projection, model, "first-angle")
        isometric_geometry = next(view for view in projection.views if view.kind == "isometric")
        bounds = placed_bounds(isometric_geometry.bounds, placements["isometric"])

        self.assertLessEqual(bounds.y_max, TITLE_BLOCK_BOUNDS_MM["y"] - DEFAULT_VIEW_GAP_MM / 2.0 + 1e-6)
        self.assertAlmostEqual(bounds.x_max, TITLE_BLOCK_BOUNDS_MM["x"] + TITLE_BLOCK_BOUNDS_MM["width"])

    def test_plate_layout_keeps_first_angle_front_above_top(self):
        model = StepImportService().import_file("fixtures/step/hole-pattern.step")
        projection = ProjectionService().build_projection(model, mode="final")

        placements = plan_view_pack(projection, model, "first-angle")

        self.assertEqual(projection.views[0].kind, "top")
        self.assertGreater(placements["top"].y_mm, placements["front"].y_mm)
        self.assertLess(placements["right"].x_mm, placements["front"].x_mm)
        self.assertEqual(placements["right"].y_mm, placements["front"].y_mm)


if __name__ == "__main__":
    unittest.main()
