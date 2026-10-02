# -*- coding: utf-8 -*-
"""
Дыра, лежащая на границе своей же оболочки.

Образец прислал пользователь. Оба кольца по отдельности годные, но внутреннее
идёт по внешнему, и объект в целом некорректен. Исправление без потери площади
существует. Очистка обязана до него дойти, а не ломать кольца сшивкой раньше.
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN)

import topo_checks as tc  # noqa: E402
from geom_backend import get_backend  # noqa: E402


class TestHoleOnShell(unittest.TestCase):

    def setUp(self):
        self.backend = get_backend("shapely")
        with open(os.path.join(HERE, "data_hole_on_shell.json"),
                  encoding="utf-8") as fh:
            rings = json.load(fh)["rings"]
        rings = [[tuple(p) for p in ring[:-1]] for ring in rings]
        self.geometry = tc.from_parts(self.backend, [rings])

    def test_sample_is_invalid(self):
        self.assertFalse(self.backend.is_valid(self.geometry))

    def test_cleanup_repairs_it_without_losing_area(self):
        before = self.backend.area(self.geometry)
        items, stats, left = tc.fix_items(
            self.backend, [(1, self.geometry)], 2.0, 1.0)
        fixed = items[0][1]
        self.assertIsNotNone(fixed)
        self.assertTrue(self.backend.is_valid(fixed))
        self.assertAlmostEqual(self.backend.area(fixed) / before, 1.0, places=3)
        self.assertEqual([f for f in left if f["type"] == tc.INVALID], [])
        self.assertEqual(stats["valid_rejected"], 0)

    def test_second_run_changes_nothing(self):
        items, _stats, _left = tc.fix_items(
            self.backend, [(1, self.geometry)], 2.0, 1.0)
        again, stats, left = tc.fix_items(self.backend, items, 2.0, 1.0)
        self.assertAlmostEqual(self.backend.area(again[0][1]),
                               self.backend.area(items[0][1]), places=6)
        for key in ("dup_vertices", "spikes", "tiny_parts", "made_valid",
                    "vertices_moved", "nodes_inserted"):
            self.assertEqual(stats[key], 0, key)
        found, _summary = tc.check_items(self.backend, again, 2.0, 1.0)
        self.assertEqual([f["type"] for f in found
                          if f["severity"] == tc.SEVERITY_AUTO], [])


if __name__ == "__main__":
    unittest.main()
