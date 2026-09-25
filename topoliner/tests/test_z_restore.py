# -*- coding: utf-8 -*-
"""
Тесты возврата отметок Z после наложения.

Проверяется главное свойство. Вершина, совпавшая с исходной, получает её
отметку без изменения, а вершина на ребре получает отметку, посчитанную
вдоль ребра.
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN)

from z_restore import ZEdges, edges_from, restore_z  # noqa: E402


def ring(*vertices):
    return list(vertices)


class TestZAt(unittest.TestCase):

    def setUp(self):
        # Квадрат со стороной 10. Отметки растут по часовой стрелке.
        self.parts = [[ring((0.0, 0.0, 100.0), (10.0, 0.0, 110.0),
                            (10.0, 10.0, 120.0), (0.0, 10.0, 130.0))]]
        self.index = edges_from([self.parts])

    def test_vertex_keeps_its_own_height(self):
        self.assertAlmostEqual(self.index.z_at(10.0, 0.0), 110.0, places=9)
        self.assertAlmostEqual(self.index.z_at(0.0, 10.0), 130.0, places=9)

    def test_middle_of_edge_is_interpolated(self):
        self.assertAlmostEqual(self.index.z_at(5.0, 0.0), 105.0, places=9)
        self.assertAlmostEqual(self.index.z_at(10.0, 2.5), 112.5, places=9)

    def test_point_aside_takes_the_nearest_edge(self):
        # Точка вне квадрата проецируется на ближнее ребро.
        self.assertAlmostEqual(self.index.z_at(5.0, -3.0), 105.0, places=9)

    def test_far_point_still_finds_an_edge(self):
        # Расширение поиска обязано дотянуться до единственного ребра.
        index = ZEdges()
        index.add_ring(ring((0.0, 0.0, 7.0), (1.0, 0.0, 9.0)))
        index.build()
        self.assertAlmostEqual(index.z_at(0.5, 300.0), 8.0, places=9)

    def test_empty_index_gives_the_default(self):
        index = edges_from([])
        self.assertEqual(index.z_at(1.0, 1.0), 0.0)
        self.assertEqual(index.z_at(1.0, 1.0, 5.0), 5.0)


class TestRestore(unittest.TestCase):

    def setUp(self):
        self.parts = [[ring((0.0, 0.0, 100.0), (10.0, 0.0, 110.0),
                            (10.0, 10.0, 120.0), (0.0, 10.0, 130.0))]]
        self.index = edges_from([self.parts])

    def test_plan_is_not_moved(self):
        cut = [[ring((0.0, 0.0), (5.0, 0.0), (5.0, 10.0), (0.0, 10.0))]]
        done = restore_z(cut, self.index)
        plan = [(v[0], v[1]) for v in done[0][0]]
        self.assertEqual(plan, [(0.0, 0.0), (5.0, 0.0), (5.0, 10.0), (0.0, 10.0)])

    def test_new_vertex_on_the_edge_gets_the_edge_height(self):
        cut = [[ring((0.0, 0.0), (5.0, 0.0), (5.0, 10.0), (0.0, 10.0))]]
        done = restore_z(cut, self.index)
        heights = [v[2] for v in done[0][0]]
        self.assertAlmostEqual(heights[0], 100.0, places=9)
        self.assertAlmostEqual(heights[1], 105.0, places=9)
        self.assertAlmostEqual(heights[3], 130.0, places=9)

    def test_holes_are_restored_too(self):
        parts = [[ring((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
                  ring((2.0, 0.0), (3.0, 0.0), (3.0, 1.0))]]
        done = restore_z(parts, self.index)
        self.assertAlmostEqual(done[0][1][0][2], 102.0, places=9)
        self.assertAlmostEqual(done[0][1][1][2], 103.0, places=9)


if __name__ == "__main__":
    unittest.main()
