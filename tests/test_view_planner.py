import unittest

from autodrawing.importers import StepImportService
from autodrawing.projection import ProjectionService
from autodrawing.view_planner import plan_view_pack, select_hidden_line_policy


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

    def test_plate_layout_places_front_below_top(self):
        model = StepImportService().import_file("fixtures/step/hole-pattern.step")
        projection = ProjectionService().build_projection(model, mode="final")

        placements = plan_view_pack(projection, model, "first-angle")

        self.assertEqual(projection.views[0].kind, "top")
        self.assertGreater(placements["front"].y_mm, placements["top"].y_mm)
        self.assertLess(placements["right"].x_mm, placements["top"].x_mm)


if __name__ == "__main__":
    unittest.main()
