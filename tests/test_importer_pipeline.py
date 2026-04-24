import unittest
from math import cos, pi, sin
from pathlib import Path

from autodrawing.contracts import ImportedFloatArray, ImportedIndexArray, ImportedMeshAttributes, ImportedMeshPayload
from autodrawing.importers import StepImportError, StepImportService
from autodrawing.pipeline import AutodrawingPipeline


class ImporterPipelineTests(unittest.TestCase):
    def _has_vertical_outline(self, view, x_value: float) -> bool:
        target = round(x_value, 2)
        intervals: list[tuple[float, float]] = []
        for edge in view.visible_edges:
            xs = {round(point.x, 2) for point in edge.points}
            if xs != {target}:
                continue
            ys = [round(point.y, 2) for point in edge.points]
            intervals.append((min(ys), max(ys)))
        if not intervals:
            return False
        intervals.sort()
        merged_lo, merged_hi = intervals[0]
        for lo, hi in intervals[1:]:
            if lo <= merged_hi + 1e-3:
                merged_hi = max(merged_hi, hi)
            else:
                merged_lo, merged_hi = lo, hi
                break
        return merged_lo <= 0.01 and merged_hi >= round(view.bounds.height, 2) - 0.01

    def _visible_verticals(self, view) -> set[float]:
        verticals: set[float] = set()
        for edge in view.visible_edges:
            xs = {round(point.x, 2) for point in edge.points}
            if len(xs) == 1:
                verticals.add(next(iter(xs)))
        return verticals

    def _cylinder_mesh(self, radius: float = 10.0, height: float = 24.0, segments: int = 24) -> ImportedMeshPayload:
        positions: list[float] = []
        indices: list[int] = []

        for index in range(segments):
            angle = (2 * pi * index) / segments
            positions.extend([radius * cos(angle), radius * sin(angle), 0.0])
        for index in range(segments):
            angle = (2 * pi * index) / segments
            positions.extend([radius * cos(angle), radius * sin(angle), height])

        bottom_center_index = len(positions) // 3
        positions.extend([0.0, 0.0, 0.0])
        top_center_index = len(positions) // 3
        positions.extend([0.0, 0.0, height])

        for index in range(segments):
            next_index = (index + 1) % segments
            bottom_a = index
            bottom_b = next_index
            top_a = index + segments
            top_b = next_index + segments

            indices.extend([bottom_a, bottom_b, top_b])
            indices.extend([bottom_a, top_b, top_a])

            indices.extend([bottom_center_index, bottom_b, bottom_a])
            indices.extend([top_center_index, top_a, top_b])

        return ImportedMeshPayload(
            name="synthetic-cylinder",
            index=ImportedIndexArray(array=indices),
            attributes=ImportedMeshAttributes(position=ImportedFloatArray(array=positions)),
        )

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

        self.assertEqual(bundle.projection.adapter, "techdraw-native")
        self.assertTrue({"front", "top", "right", "isometric"} <= kinds)
        self.assertTrue(bundle.scene_graph.layers["centerlines"])
        self.assertFalse(isometric.hidden_edges)

    def test_plate_like_part_uses_broad_face_as_top_view(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/hole-pattern.step", mode="final")
        front = next(view for view in bundle.projection.views if view.kind == "front")
        top = next(view for view in bundle.projection.views if view.kind == "top")

        self.assertEqual(bundle.projection.views[0].kind, "top")
        self.assertGreater(top.bounds.height, 50.0)
        self.assertLess(front.bounds.height, top.bounds.height)
        self.assertGreater(top.bounds.width * top.bounds.height, front.bounds.width * front.bounds.height)

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
        top = next(view for view in bundle.projection.views if view.kind == "top")
        right = next(view for view in bundle.projection.views if view.kind == "right")
        iso_faces = [
            item
            for item in bundle.scene_graph.layers["viewGeometryVisible"]
            if "view-isometric-shaded-face" in item.classes
        ]

        self.assertTrue(any(edge.id.startswith("front-step-edge-") for edge in front.visible_edges))
        self.assertTrue(self._has_vertical_outline(front, 0.0))
        self.assertTrue(self._has_vertical_outline(front, front.bounds.width))
        self.assertTrue(self._has_vertical_outline(right, 0.0))
        self.assertTrue(self._has_vertical_outline(right, right.bounds.width))
        self.assertEqual(self._visible_verticals(front), {0.0, round(front.bounds.width, 2)})
        self.assertEqual(self._visible_verticals(right), {0.0, round(right.bounds.width, 2)})
        self.assertGreaterEqual(len(front.hidden_edges), 4)
        self.assertGreaterEqual(len(top.centerlines), 8)
        self.assertGreaterEqual(len(bundle.scene_graph.layers["centerlines"]), 8)
        self.assertTrue(iso_faces)

    def test_occt_mesh_projection_adds_orthographic_silhouettes(self):
        bundle = AutodrawingPipeline().from_occt_meshes([self._cylinder_mesh()], source_name="cylinder.step", mode="final")
        front = next(view for view in bundle.projection.views if view.kind == "front")

        self.assertTrue(any(edge.id.startswith("front-silhouette-") for edge in front.visible_edges))
        self.assertTrue(self._has_vertical_outline(front, 0.0))
        self.assertTrue(self._has_vertical_outline(front, front.bounds.width))

    def test_occt_mesh_projection_adds_isometric_silhouettes(self):
        bundle = AutodrawingPipeline().from_occt_meshes([self._cylinder_mesh()], source_name="cylinder.step", mode="final")
        isometric = next(view for view in bundle.projection.views if view.kind == "isometric")

        self.assertTrue(any(len(edge.points) > 2 for edge in isometric.visible_edges))


if __name__ == "__main__":
    unittest.main()
