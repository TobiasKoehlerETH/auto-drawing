from math import hypot
import unittest

from autodrawing.contracts import DrawingCommand
from autodrawing.pipeline import AutodrawingPipeline


class DocumentCommandTests(unittest.TestCase):
    def _bundle(self):
        return AutodrawingPipeline().from_step_file("fixtures/step/hole-pattern.step")

    def _assert_arrowhead_proportions(self, path_data, expected_tip):
        tokens = path_data.split()
        self.assertEqual(tokens[0], "M")
        self.assertEqual(tokens[3], "L")
        self.assertEqual(tokens[6], "L")
        self.assertEqual(tokens[9], "Z")
        tip = (float(tokens[1]), float(tokens[2]))
        left = (float(tokens[4]), float(tokens[5]))
        right = (float(tokens[7]), float(tokens[8]))
        base_midpoint = ((left[0] + right[0]) / 2.0, (left[1] + right[1]) / 2.0)

        self.assertAlmostEqual(tip[0], expected_tip["x"], places=2)
        self.assertAlmostEqual(tip[1], expected_tip["y"], places=2)
        self.assertAlmostEqual(hypot(base_midpoint[0] - tip[0], base_midpoint[1] - tip[1]), 3.5, places=2)
        self.assertAlmostEqual(hypot(left[0] - base_midpoint[0], left[1] - base_midpoint[1]), 0.7, places=2)
        self.assertAlmostEqual(hypot(right[0] - base_midpoint[0], right[1] - base_midpoint[1]), 0.7, places=2)

    def _path_endpoint(self, path_data):
        tokens = path_data.split()
        self.assertEqual(tokens[0], "M")
        self.assertEqual(tokens[3], "L")
        return {"x": float(tokens[4]), "y": float(tokens[5])}

    def _assert_linear_label_clears_dimension_line(self, dimension):
        geometry = dimension.computed_geometry
        line_start = geometry["line_start"]
        line_end = geometry["line_end"]
        label = geometry["label"]
        orientation = geometry["orientation"]

        if orientation == "horizontal":
            self.assertGreaterEqual(abs(label["y"] - line_start["y"]), 7.5)
            return
        if orientation == "vertical":
            self.assertGreaterEqual(abs(label["x"] - line_start["x"]), 7.5)
            return

        dx = line_end["x"] - line_start["x"]
        dy = line_end["y"] - line_start["y"]
        length = max(hypot(dx, dy), 0.001)
        distance = abs(dy * label["x"] - dx * label["y"] + line_end["x"] * line_start["y"] - line_end["y"] * line_start["x"]) / length
        self.assertGreaterEqual(distance, 7.5)

    def test_bundle_starts_with_default_dimensions(self):
        bundle = self._bundle()
        self.assertTrue(bundle.document.dimensions)
        dimension_types = {dimension.dimension_type for dimension in bundle.document.dimensions}
        self.assertIn("DistanceX", dimension_types)
        self.assertIn("DistanceY", dimension_types)
        self.assertIn("Diameter", dimension_types)
        self.assertTrue(bundle.scene_graph.layers["dimensions"])

    def test_dimension_arrowheads_use_narrow_drafting_proportions(self):
        bundle = self._bundle()
        dimensions = bundle.document.dimensions
        scene_items = {item.id: item for item in bundle.scene_graph.layers["dimensions"]}

        linear = next(dimension for dimension in dimensions if dimension.computed_geometry.get("kind") == "linear")
        linear_arrow = scene_items[f"{linear.id}-arrow-a"]
        self._assert_arrowhead_proportions(linear_arrow.path_data, linear.computed_geometry["line_start"])

        radial = next(dimension for dimension in dimensions if dimension.computed_geometry.get("kind") == "radial")
        radial_arrow = scene_items[f"{radial.id}-arrow"]
        self._assert_arrowhead_proportions(radial_arrow.path_data, radial.computed_geometry["anchor"])

    def test_dimension_text_is_offset_from_dimension_and_leader_lines(self):
        bundle = self._bundle()
        scene_items = {item.id: item for item in bundle.scene_graph.layers["dimensions"]}

        horizontal = next(dimension for dimension in bundle.document.dimensions if dimension.dimension_type == "DistanceX")
        horizontal_text = scene_items[f"{horizontal.id}-text"]
        horizontal_label = horizontal.computed_geometry["label"]
        self.assertAlmostEqual(horizontal_text.x, horizontal_label["x"], places=2)
        self.assertAlmostEqual(horizontal_text.y, horizontal_label["y"] - 3.0, places=2)

        vertical = next(dimension for dimension in bundle.document.dimensions if dimension.dimension_type == "DistanceY")
        vertical_text = scene_items[f"{vertical.id}-text"]
        vertical_label = vertical.computed_geometry["label"]
        self.assertAlmostEqual(vertical_text.x, vertical_label["x"] + 3.0, places=2)
        self.assertAlmostEqual(vertical_text.y, vertical_label["y"], places=2)

        radial = next(dimension for dimension in bundle.document.dimensions if dimension.computed_geometry.get("kind") == "radial")
        radial_label = radial.computed_geometry["label"]
        leader_endpoint = self._path_endpoint(scene_items[f"{radial.id}-leader"].path_data)
        self.assertGreater(hypot(leader_endpoint["x"] - radial_label["x"], leader_endpoint["y"] - radial_label["y"]), 2.9)

    def test_move_dimension_text_keeps_dimension_line_fixed(self):
        pipeline = AutodrawingPipeline()
        bundle = self._bundle()
        dimension = next(dimension for dimension in bundle.document.dimensions if dimension.computed_geometry.get("kind") == "linear")
        original_geometry = dimension.computed_geometry
        next_x = dimension.placement.x_mm + 11
        next_y = dimension.placement.y_mm - 7

        moved = pipeline.apply_command(
            bundle,
            DrawingCommand(
                id="cmd-move-dim-text",
                kind="MoveDimensionText",
                target_id=dimension.id,
                before={"x_mm": dimension.placement.x_mm, "y_mm": dimension.placement.y_mm},
                after={"x_mm": next_x, "y_mm": next_y},
            ),
        )

        updated = next(candidate for candidate in moved.document.dimensions if candidate.id == dimension.id)
        self.assertEqual(updated.computed_geometry["line_start"], original_geometry["line_start"])
        self.assertEqual(updated.computed_geometry["line_end"], original_geometry["line_end"])
        self.assertEqual(updated.computed_geometry["label"], {"x": next_x, "y": next_y})

    def test_sample_plate_gets_thickness_and_grouped_hole_callout(self):
        bundle = AutodrawingPipeline().from_step_file("fixtures/step/sample.step", mode="final")

        front = next(view for view in bundle.document.views if view.kind == "front")
        top = next(view for view in bundle.document.views if view.kind == "top")
        right = next(view for view in bundle.document.views if view.kind == "right")
        labels = {dimension.formatted_text for dimension in bundle.document.dimensions}

        self.assertGreater(top.placement.y_mm, front.placement.y_mm)
        self.assertLess(right.placement.x_mm, front.placement.x_mm)
        self.assertIn("10", labels)
        self.assertFalse(any(label and label.endswith(" mm") for label in labels))
        self.assertTrue(any(label and label.startswith("4x ") and "THRU" in label for label in labels))

        general_tolerances = next(field for field in bundle.document.title_block_fields if field.id == "tb-general_tolerances")
        self.assertIn("MMGS", general_tolerances.value)
        self.assertIn("MMGS", bundle.document.page_template.svg_source)
        for dimension in bundle.document.dimensions:
            if dimension.computed_geometry.get("kind") == "linear":
                self._assert_linear_label_clears_dimension_line(dimension)

    def test_move_view_and_undo_redo(self):
        pipeline = AutodrawingPipeline()
        bundle = self._bundle()
        original = bundle.document.views[0]
        command = DrawingCommand(
            id="cmd-view",
            kind="MoveView",
            target_id=original.id,
            before={"x_mm": original.placement.x_mm, "y_mm": original.placement.y_mm},
            after={"x_mm": original.placement.x_mm + 20, "y_mm": original.placement.y_mm + 10},
        )

        moved = pipeline.apply_command(bundle, command)
        self.assertEqual(moved.document.views[0].placement.x_mm, original.placement.x_mm + 20)
        self.assertEqual(moved.document.views[0].placement.y_mm, original.placement.y_mm + 10)

        undone = pipeline.undo(moved)
        self.assertEqual(undone.document.views[0].placement.x_mm, original.placement.x_mm)
        self.assertEqual(undone.document.views[0].placement.y_mm, original.placement.y_mm)

    def test_move_view_translates_linked_dimensions_and_undo_redo(self):
        pipeline = AutodrawingPipeline()
        bundle = self._bundle()
        linked_view_id = bundle.document.dimensions[0].view_id
        linked_view = next(view for view in bundle.document.views if view.id == linked_view_id)
        linked_before = [dimension for dimension in bundle.document.dimensions if dimension.view_id == linked_view.id]
        self.assertTrue(linked_before)

        before_positions = {
            dimension.id: (
                dimension.placement.x_mm,
                dimension.placement.y_mm,
                dict(dimension.computed_geometry.get("label", {})),
            )
            for dimension in linked_before
        }

        moved = pipeline.apply_command(
            bundle,
            DrawingCommand(
                id="cmd-move-front-linked-dims",
                kind="MoveView",
                target_id=linked_view.id,
                before={"x_mm": linked_view.placement.x_mm, "y_mm": linked_view.placement.y_mm},
                after={"x_mm": linked_view.placement.x_mm + 12, "y_mm": linked_view.placement.y_mm + 6},
            ),
        )

        for dimension in moved.document.dimensions:
            if dimension.view_id != linked_view.id:
                continue
            before_x, before_y, before_label = before_positions[dimension.id]
            self.assertEqual(dimension.placement.x_mm, before_x + 12)
            self.assertEqual(dimension.placement.y_mm, before_y + 6)
            if before_label:
                self.assertEqual(dimension.computed_geometry.get("label", {}).get("x"), before_label.get("x", 0) + 12)
                self.assertEqual(dimension.computed_geometry.get("label", {}).get("y"), before_label.get("y", 0) + 6)

        undone = pipeline.undo(moved)
        for dimension in undone.document.dimensions:
            if dimension.view_id != linked_view.id:
                continue
            before_x, before_y, before_label = before_positions[dimension.id]
            self.assertEqual(dimension.placement.x_mm, before_x)
            self.assertEqual(dimension.placement.y_mm, before_y)
            if before_label:
                self.assertEqual(dimension.computed_geometry.get("label", {}).get("x"), before_label.get("x", 0))
                self.assertEqual(dimension.computed_geometry.get("label", {}).get("y"), before_label.get("y", 0))

        redone = pipeline.redo(undone)
        for dimension in redone.document.dimensions:
            if dimension.view_id != linked_view.id:
                continue
            before_x, before_y, before_label = before_positions[dimension.id]
            self.assertEqual(dimension.placement.x_mm, before_x + 12)
            self.assertEqual(dimension.placement.y_mm, before_y + 6)
            if before_label:
                self.assertEqual(dimension.computed_geometry.get("label", {}).get("x"), before_label.get("x", 0) + 12)
                self.assertEqual(dimension.computed_geometry.get("label", {}).get("y"), before_label.get("y", 0) + 6)

    def test_reorder_bom_updates_item_numbers(self):
        pipeline = AutodrawingPipeline()
        bundle = self._bundle()
        if len(bundle.document.bom_rows) == 1:
            document = bundle.document.model_copy(deep=True)
            document.bom_rows.append(
                document.bom_rows[0].model_copy(
                    update={
                        "id": "bom-extra",
                        "item_number": 2,
                        "component_id": "component-extra",
                        "name": "Extra",
                        "quantity": 2,
                    }
                )
            )
            bundle = bundle.model_copy(update={"document": document})

        target = bundle.document.bom_rows[-1]
        command = DrawingCommand(
            id="cmd-bom",
            kind="ReorderBomRow",
            target_id=target.id,
            before={"index": len(bundle.document.bom_rows) - 1},
            after={"index": 0},
        )

        updated = pipeline.apply_command(bundle, command)
        self.assertEqual(updated.document.bom_rows[0].id, target.id)
        self.assertEqual(
            [row.item_number for row in updated.document.bom_rows],
            list(range(1, len(updated.document.bom_rows) + 1)),
        )

    def test_set_display_transform_and_undo_redo(self):
        pipeline = AutodrawingPipeline()
        bundle = self._bundle()
        target_id = bundle.document.views[0].id
        command = DrawingCommand(
            id="cmd-transform",
            kind="SetDisplayTransform",
            target_id=target_id,
            before={"transform": ""},
            after={"transform": "translate(12 8) scale(1.25 1.25)"},
        )

        moved = pipeline.apply_command(bundle, command)
        self.assertEqual(moved.document.display_transforms[target_id], "translate(12 8) scale(1.25 1.25)")

        undone = pipeline.undo(moved)
        self.assertNotIn(target_id, undone.document.display_transforms)

        redone = pipeline.redo(undone)
        self.assertEqual(redone.document.display_transforms[target_id], "translate(12 8) scale(1.25 1.25)")

    def test_dimension_commands_create_delete_format_measurement_and_undo(self):
        pipeline = AutodrawingPipeline()
        bundle = self._bundle()
        target_view = bundle.document.views[0]
        dimension_payload = {
            "id": "dim-angle-manual",
            "view_id": target_view.id,
            "label": "90 deg",
            "value": 0,
            "units": "mm",
            "anchor_a": {"view_id": target_view.id, "primitive_id": target_view.geometry_id, "role": "angle-a"},
            "anchor_b": {"view_id": target_view.id, "primitive_id": target_view.geometry_id, "role": "angle-b"},
            "placement": {"x_mm": target_view.placement.x_mm + 20, "y_mm": target_view.placement.y_mm + 20},
            "dimension_type": "Angle3Pt",
            "measurement_type": "Projected",
            "references_2d": [target_view.geometry_id],
            "computed_geometry": {
                "kind": "angular",
                "vertex": {"x": 0, "y": 0},
                "first": {"x": 10, "y": 0},
                "second": {"x": 0, "y": 10},
                "label": {"x": target_view.placement.x_mm + 20, "y": target_view.placement.y_mm + 20},
            },
        }

        created = pipeline.apply_command(
            bundle,
            DrawingCommand(
                id="cmd-create-dim",
                kind="CreateDimension",
                target_id="dim-angle-manual",
                before={},
                after={"dimension": dimension_payload},
            ),
        )
        manual = next(dimension for dimension in created.document.dimensions if dimension.id == "dim-angle-manual")
        self.assertEqual(manual.dimension_type, "Angle3Pt")
        self.assertAlmostEqual(manual.value, 90.0)
        self.assertEqual(manual.formatted_text, "90\u00b0")

        formatted = pipeline.apply_command(
            created,
            DrawingCommand(
                id="cmd-format-dim",
                kind="SetDimensionFormat",
                target_id=manual.id,
                before={"format_spec": manual.format_spec},
                after={"format_spec": "%.1f"},
            ),
        )
        self.assertEqual(next(d for d in formatted.document.dimensions if d.id == manual.id).formatted_text, "90\u00b0")

        measured = pipeline.apply_command(
            formatted,
            DrawingCommand(
                id="cmd-measure-dim",
                kind="SetDimensionMeasurementType",
                target_id=manual.id,
                before={"measurement_type": "Projected"},
                after={"measurement_type": "True"},
            ),
        )
        self.assertEqual(next(d for d in measured.document.dimensions if d.id == manual.id).measurement_type, "True")

        deleted = pipeline.apply_command(
            measured,
            DrawingCommand(
                id="cmd-delete-dim",
                kind="DeleteDimension",
                target_id=manual.id,
                before={"dimension": manual.model_dump(mode="json")},
                after={},
            ),
        )
        self.assertFalse(any(dimension.id == manual.id for dimension in deleted.document.dimensions))

        restored = pipeline.undo(deleted)
        self.assertTrue(any(dimension.id == manual.id for dimension in restored.document.dimensions))

    def test_set_title_block_field_updates_exact_template_and_undo_redo(self):
        pipeline = AutodrawingPipeline()
        bundle = pipeline.from_step_file("fixtures/step/cube-30.step", mode="final")
        title_field = next(field for field in bundle.document.title_block_fields if field.id == "tb-title")
        updated_title = "Edited Cube Title"
        command = DrawingCommand(
            id="cmd-title",
            kind="SetTitleBlockField",
            target_id=title_field.id,
            before={"value": title_field.value},
            after={"value": updated_title},
        )

        updated = pipeline.apply_command(bundle, command)
        updated_field = next(field for field in updated.document.title_block_fields if field.id == title_field.id)
        self.assertEqual(updated_field.value, updated_title)
        self.assertIn(updated_title, updated.document.page_template.svg_source)

        undone = pipeline.undo(updated)
        undone_field = next(field for field in undone.document.title_block_fields if field.id == title_field.id)
        self.assertEqual(undone_field.value, title_field.value)
        self.assertIn(title_field.value, undone.document.page_template.svg_source)

        redone = pipeline.redo(undone)
        redone_field = next(field for field in redone.document.title_block_fields if field.id == title_field.id)
        self.assertEqual(redone_field.value, updated_title)
        self.assertIn(updated_title, redone.document.page_template.svg_source)

    def test_apply_commands_can_scale_all_non_isometric_views_together(self):
        pipeline = AutodrawingPipeline()
        bundle = pipeline.from_step_file("fixtures/step/cube-30.step", mode="final")
        orthographic_views = [view for view in bundle.document.views if view.kind != "isometric"]
        isometric_view = next(view for view in bundle.document.views if view.kind == "isometric")
        target_scale = 1.35

        updated = pipeline.apply_commands(
            bundle,
            [
                DrawingCommand(
                    id=f"cmd-scale-{view.id}",
                    kind="ChangeViewScale",
                    target_id=view.id,
                    before={"scale": view.placement.scale},
                    after={"scale": target_scale},
                )
                for view in orthographic_views
            ],
        )

        for view in updated.document.views:
            if view.kind == "isometric":
                self.assertEqual(view.placement.scale, isometric_view.placement.scale)
            else:
                self.assertEqual(view.placement.scale, target_scale)

    def test_move_and_scale_view_rebuilds_scene(self):
        pipeline = AutodrawingPipeline()
        bundle = pipeline.from_step_file("fixtures/step/cube-30.step", mode="final")
        original_view = next(view for view in bundle.document.views if view.id == "view-front")
        next_scale = round(original_view.placement.scale * 1.25, 4)
        original_outline = next(
            item for item in bundle.scene_graph.layers["selectionOverlay"] if item.id == "view-front-selection" and item.meta.get("view_id") == "view-front"
        )

        moved = pipeline.apply_command(
            bundle,
            DrawingCommand(
                id="cmd-move-front",
                kind="MoveView",
                target_id=original_view.id,
                before={"x_mm": original_view.placement.x_mm, "y_mm": original_view.placement.y_mm},
                after={"x_mm": original_view.placement.x_mm + 18, "y_mm": original_view.placement.y_mm - 12},
            ),
        )
        scaled = pipeline.apply_command(
            moved,
            DrawingCommand(
                id="cmd-scale-front",
                kind="ChangeViewScale",
                target_id=original_view.id,
                before={"scale": original_view.placement.scale},
                after={"scale": next_scale},
            ),
        )
        updated_view = next(view for view in scaled.document.views if view.id == "view-front")
        updated_outline = next(
            item for item in scaled.scene_graph.layers["selectionOverlay"] if item.id == "view-front-selection" and item.meta.get("view_id") == "view-front"
        )

        self.assertEqual(updated_view.placement.x_mm, original_view.placement.x_mm + 18)
        self.assertEqual(updated_view.placement.y_mm, original_view.placement.y_mm - 12)
        self.assertEqual(updated_view.placement.scale, next_scale)
        self.assertGreater(updated_outline.width, original_outline.width)
        self.assertGreater(updated_outline.x, original_outline.x)
        self.assertLess(updated_outline.y, original_outline.y)


if __name__ == "__main__":
    unittest.main()
