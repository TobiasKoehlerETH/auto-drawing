import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from autodrawing.api import app, preview_store


class PreviewApiTests(unittest.TestCase):
    def setUp(self):
        preview_store._bundles.clear()  # noqa: SLF001 - isolated in-memory test fixture
        self.client = TestClient(app)
        self.fixture_path = Path("fixtures/step/cube-30.step")

    def test_drawing_preview_returns_preview_payload(self):
        response = self.client.post(
            "/api/studio/drawing-preview?mode=final",
            files={"file": (self.fixture_path.name, self.fixture_path.read_bytes(), "application/step")},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("preview_id", payload)
        self.assertIn("svg", payload)
        self.assertTrue(payload["views"])
        orthographic_scales = {view["scale"] for view in payload["views"] if view["kind"] != "isometric"}
        self.assertEqual(len(orthographic_scales), 1)
        self.assertEqual(next(iter(orthographic_scales)), 1.0)
        self.assertEqual(next(view["scale"] for view in payload["views"] if view["kind"] == "isometric"), 0.5)
        self.assertEqual(payload["document"]["page_template"]["id"], "iso-a3-landscape")
        self.assertTrue(payload["document"]["page_template"]["source_path"])
        self.assertFalse(payload["scene_graph"]["layers"]["frame"])
        self.assertFalse(payload["scene_graph"]["layers"]["titleBlock"])
        self.assertTrue(payload["tracked_draw_bridge_available"])
        self.assertTrue(payload["dimension_editing_available"])
        self.assertTrue(payload["document"]["dimensions"])
        self.assertTrue(payload["scene_graph"]["layers"]["dimensions"])

    def test_preview_command_updates_selected_view(self):
        create = self.client.post(
            "/api/studio/drawing-preview?mode=final",
            files={"file": (self.fixture_path.name, self.fixture_path.read_bytes(), "application/step")},
        )
        payload = create.json()
        front = next(view for view in payload["views"] if view["id"] == "view-front")

        response = self.client.post(
            f"/api/studio/drawing-previews/{payload['preview_id']}/command",
            json={
                "command": {
                    "id": "cmd-move-front",
                    "kind": "MoveView",
                    "target_id": "view-front",
                    "before": {"x_mm": front["x_mm"], "y_mm": front["y_mm"]},
                    "after": {"x_mm": front["x_mm"] + 12, "y_mm": front["y_mm"] + 6},
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        updated = response.json()
        moved_front = next(view for view in updated["views"] if view["id"] == "view-front")
        self.assertAlmostEqual(moved_front["x_mm"], front["x_mm"] + 12)
        self.assertAlmostEqual(moved_front["y_mm"], front["y_mm"] + 6)
        linked_dimension = next(dimension for dimension in payload["document"]["dimensions"] if dimension["view_id"] == "view-front")
        moved_dimension = next(dimension for dimension in updated["document"]["dimensions"] if dimension["id"] == linked_dimension["id"])
        self.assertAlmostEqual(moved_dimension["placement"]["x_mm"], linked_dimension["placement"]["x_mm"] + 12)
        self.assertAlmostEqual(moved_dimension["placement"]["y_mm"], linked_dimension["placement"]["y_mm"] + 6)

    def test_drawing_preview_from_occt_mesh_payload(self):
        response = self.client.post(
            "/api/studio/drawing-preview-from-occt",
            json={
                "source_name": "cube-from-occt.step",
                "units": "mm",
                "mode": "final",
                "meshes": [
                    {
                        "index": {
                            "array": [
                                0, 1, 2, 0, 2, 3,
                                4, 6, 5, 4, 7, 6,
                                0, 4, 5, 0, 5, 1,
                                1, 5, 6, 1, 6, 2,
                                2, 6, 7, 2, 7, 3,
                                3, 7, 4, 3, 4, 0,
                            ]
                        },
                        "attributes": {
                            "position": {
                                "array": [
                                    0, 0, 0,
                                    30, 0, 0,
                                    30, 30, 0,
                                    0, 30, 0,
                                    0, 0, 30,
                                    30, 0, 30,
                                    30, 30, 30,
                                    0, 30, 30,
                                ]
                            }
                        },
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["document"]["canonical_model_name"], "cube-from-occt.step")
        self.assertTrue(any(item["id"].startswith("front-mesh-") for item in payload["projection"]["views"][0]["visible_edges"]))
        isometric = next(view for view in payload["projection"]["views"] if view["kind"] == "isometric")
        self.assertEqual(len(isometric["visible_edges"]), 6)
        self.assertTrue(any(len(edge["points"]) > 2 for edge in isometric["visible_edges"]))
        self.assertFalse(isometric["hidden_edges"])
        self.assertTrue(payload["dimension_editing_available"])
        self.assertTrue(payload["document"]["dimensions"])


if __name__ == "__main__":
    unittest.main()
