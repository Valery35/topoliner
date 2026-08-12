# -*- coding: utf-8 -*-
"""
Тесты топологического упрощения.

Главное требование: общая граница двух соседей после упрощения остаётся
общей вершина в вершину. Именно этого не даёт упрощение полигонов
по отдельности.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geom_backend import ShapelyBackend  # noqa: E402
from topo_simplify import (  # noqa: E402
    build_arcs,
    douglas_peucker,
    simplify_topology,
)


def wiggly_border(n=9, amp=0.4):
    """Извилистая граница по линии x=10."""
    out = []
    for i in range(n):
        y = i * 10.0 / (n - 1)
        x = 10.0 + (amp if i % 2 else -amp) * (0 if i in (0, n - 1) else 1)
        out.append((x, y))
    return out


class Base(unittest.TestCase):

    def setUp(self):
        self.b = ShapelyBackend()

    def pair(self):
        """Два соседа с общей извилистой границей. Оба обходятся по кругу."""
        border = wiggly_border()
        left = [(0.0, 0.0)] + border + [(0.0, 10.0)]
        right = list(reversed(border)) + [(20.0, 0.0), (20.0, 10.0)]
        return left, right

    def assert_valid_input(self, *rings):
        """Тест не имеет смысла на некорректном входе."""
        for ring in rings:
            self.assertTrue(self.b.is_valid(self.poly(ring)),
                            "Исходное кольцо теста некорректно")

    def poly(self, ring):
        return self.b.polygon([list(ring) + [ring[0]]])

    def shared_points(self, ring, x=10.0, span=1.0):
        return {(round(p[0], 9), round(p[1], 9))
                for p in ring if abs(p[0] - x) <= span}


class TestDouglasPeucker(Base):

    def test_endpoints_are_kept(self):
        pts = [(0, 0), (1, 0.05), (2, -0.05), (3, 0)]
        out = douglas_peucker(pts, 0.5)
        self.assertEqual(out[0], pts[0])
        self.assertEqual(out[-1], pts[-1])

    def test_flat_chain_collapses_to_ends(self):
        pts = [(i, 0.0) for i in range(20)]
        self.assertEqual(douglas_peucker(pts, 0.1), [pts[0], pts[-1]])

    def test_sharp_corner_survives(self):
        pts = [(0, 0), (5, 0), (5, 5)]
        self.assertEqual(len(douglas_peucker(pts, 0.5)), 3)

    def test_zero_tolerance_changes_nothing(self):
        pts = [(0, 0), (1, 0.3), (2, 0)]
        self.assertEqual(douglas_peucker(pts, 0.0), pts)

    def test_long_chain_does_not_recurse(self):
        """Дуга в десятки тысяч вершин не должна упираться в предел рекурсии."""
        pts = [(i * 0.001, math.sin(i * 0.01)) for i in range(30000)]
        out = douglas_peucker(pts, 0.01)
        self.assertLess(len(out), len(pts))
        self.assertGreater(len(out), 2)


class TestArcs(Base):

    def test_shared_border_becomes_one_arc(self):
        left, right = self.pair()
        arcs, paths = build_arcs([left, right])
        self.assertEqual(len(paths), 2)
        used = {}
        for ri, path in enumerate(paths):
            for idx, _rev in path:
                used.setdefault(idx, set()).add(ri)
        shared = [i for i, r in used.items() if len(r) > 1]
        self.assertEqual(len(shared), 1, "Общая граница это ровно одна дуга")
        self.assertEqual(len(arcs[shared[0]]), 9)

    def test_isolated_ring_is_a_single_arc(self):
        ring = [(0, 0), (10, 0), (10, 10), (0, 10)]
        arcs, paths = build_arcs([ring])
        self.assertEqual(len(paths[0]), 1)

    def test_three_way_junction_splits_arcs(self):
        """Там, где сходятся три полигона, дуга обязана обрываться."""
        a = [(0, 0), (10, 0), (10, 5), (0, 5)]
        b = [(10, 0), (20, 0), (20, 5), (10, 5)]
        c = [(0, 5), (10, 5), (20, 5), (20, 10), (0, 10)]
        arcs, paths = build_arcs([a, b, c])
        for path in paths:
            self.assertGreaterEqual(len(path), 2)


class TestSimplifyKeepsTopology(Base):

    def test_input_of_the_pair_is_valid(self):
        self.assert_valid_input(*self.pair())

    def test_shared_border_stays_identical(self):
        left, right = self.pair()
        self.assert_valid_input(left, right)
        res = simplify_topology([left, right], tolerance=0.5)
        l_out, r_out = res["rings"]
        self.assertEqual(self.shared_points(l_out), self.shared_points(r_out),
                         "Общая граница должна совпасть вершина в вершину")

    def test_no_gap_appears_between_neighbours(self):
        left, right = self.pair()
        res = simplify_topology([left, right], tolerance=0.5)
        merged = self.b.union_all([self.poly(r) for r in res["rings"]])
        parts = self.b.parts(merged)
        self.assertEqual(len(parts), 1, "Между соседями появился разрыв")
        rings = self.b.rings(parts[0])
        self.assertEqual(len(rings), 1, "Между соседями появилась щель")

    def test_no_overlap_appears(self):
        left, right = self.pair()
        res = simplify_topology([left, right], tolerance=0.5)
        a, c = (self.poly(r) for r in res["rings"])
        inter = self.b.polygonal_only(self.b.intersection(a, c))
        self.assertLess(self.b.area(inter), 1e-9, "Соседи наехали друг на друга")

    def test_independent_simplification_breaks_it(self):
        """Контрольный случай: упрощение по отдельности разводит границы."""
        left, right = self.pair()
        l_out = douglas_peucker(left, 0.5)
        r_out = douglas_peucker(right, 0.5)
        self.assertNotEqual(self.shared_points(l_out), self.shared_points(r_out))

    def test_vertices_are_reduced(self):
        left, right = self.pair()
        res = simplify_topology([left, right], tolerance=0.5)
        self.assertLess(res["stats"]["vertices_out"], res["stats"]["vertices_in"])

    def test_zero_tolerance_keeps_everything(self):
        left, right = self.pair()
        res = simplify_topology([left, right], tolerance=0.0)
        for src, out in zip((left, right), res["rings"]):
            self.assertEqual(len(out), len(src))

    def test_junction_points_do_not_move(self):
        """Узлы, где сходятся три полигона, остаются на месте."""
        a = [(0, 0), (10, 0), (10.3, 2.5), (10, 5), (0, 5)]
        b = [(10, 0), (20, 0), (20, 5), (10, 5), (10.3, 2.5)]
        c = [(0, 5), (10, 5), (20, 5), (20, 10), (0, 10)]
        res = simplify_topology([a, b, c], tolerance=1.0)
        for ring in res["rings"]:
            pts = {(round(p[0], 9), round(p[1], 9)) for p in ring}
            self.assertIn((10.0, 5.0), pts)

    def test_result_is_valid(self):
        left, right = self.pair()
        self.assert_valid_input(left, right)
        res = simplify_topology([left, right], tolerance=0.5)
        for ring in res["rings"]:
            self.assertTrue(self.b.is_valid(self.poly(ring)))

    def test_idempotent(self):
        left, right = self.pair()
        first = simplify_topology([left, right], tolerance=0.5)
        second = simplify_topology(first["rings"], tolerance=0.5)
        for r1, r2 in zip(first["rings"], second["rings"]):
            self.assertEqual([(round(p[0], 9), round(p[1], 9)) for p in r1],
                             [(round(p[0], 9), round(p[1], 9)) for p in r2])

    def test_min_points_protects_short_arcs(self):
        left, right = self.pair()
        res = simplify_topology([left, right], tolerance=5.0, min_points=100)
        self.assertEqual(res["stats"]["vertices_out"], res["stats"]["vertices_in"])


class TestGrid(Base):

    def test_coordinates_written_with_different_precision_match(self):
        """Соседи, записанные с микронным расхождением, всё равно общие."""
        d = 1e-9
        left = [(0, 0), (10, 0), (10, 5), (10, 10), (0, 10)]
        right = [(10 + d, 0), (20, 0), (20, 10), (10 + d, 10), (10 + d, 5)]
        res = simplify_topology([left, right], tolerance=1.0, grid=1e-6)
        merged = self.b.union_all([self.poly(r) for r in res["rings"]])
        self.assertEqual(len(self.b.parts(merged)), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
