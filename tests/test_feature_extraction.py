import unittest
from types import SimpleNamespace
from unittest.mock import patch

import autodrawing.engine as engine


class Feature:
    def __init__(self, name: str, feature_type: str, next_feature=None):
        self.Name = name
        self._feature_type = feature_type
        self._next = next_feature

    def GetTypeName2(self):
        return self._feature_type

    def GetNextFeature(self):
        return self._next


class FeatureExtractionTests(unittest.TestCase):
    def setUp(self):
        self.swmod = SimpleNamespace(IFeature=SimpleNamespace(CLSID=None))
        self.dispatch_patch = patch.object(engine, "wrap_dispatch", lambda obj, *_args: obj)
        self.swmod_patch = patch.object(engine, "SWMOD", self.swmod)
        self.dispatch_patch.start()
        self.swmod_patch.start()

    def tearDown(self):
        self.swmod_patch.stop()
        self.dispatch_patch.stop()

    def test_prefers_tree_traversal(self):
        f3 = Feature("Cut-Extrude1", "Cut")
        f2 = Feature("Boss-Extrude1", "Boss", f3)
        f1 = Feature("Front Plane", "RefPlane", f2)
        model = SimpleNamespace(
            FirstFeature=lambda: f1,
            FeatureManager=SimpleNamespace(GetFeatureCount=lambda include_hidden=True: 3),
        )

        records = engine.DrawingEngine()._extract_feature_records(model)

        self.assertEqual(
            [record["name"] for record in records],
            ["Front Plane", "Boss-Extrude1", "Cut-Extrude1"],
        )

    def test_falls_back_to_reverse_positions(self):
        reverse = {
            1: Feature("Boss-Extrude1", "Boss"),
            2: Feature("Sketch1", "ProfileFeature"),
        }
        model = SimpleNamespace(
            FirstFeature=lambda: None,
            FeatureByPositionReverse=lambda pos: reverse.get(pos),
            FeatureManager=SimpleNamespace(GetFeatureCount=lambda include_hidden=True: 2),
        )

        records = engine.DrawingEngine()._extract_feature_records(model)

        self.assertEqual(
            [record["name"] for record in records],
            ["Boss-Extrude1", "Sketch1"],
        )

    def test_tries_zero_based_reverse_positions(self):
        reverse = {
            0: Feature("Sketch1", "ProfileFeature"),
            1: Feature("Boss-Extrude1", "Boss"),
        }
        model = SimpleNamespace(
            FirstFeature=lambda: None,
            FeatureByPositionReverse=lambda pos: reverse.get(pos),
            FeatureManager=SimpleNamespace(GetFeatureCount=lambda include_hidden=True: 2),
        )

        records = engine.DrawingEngine()._extract_feature_records(model)

        self.assertEqual(
            [record["name"] for record in records],
            ["Boss-Extrude1", "Sketch1"],
        )


if __name__ == "__main__":
    unittest.main()
