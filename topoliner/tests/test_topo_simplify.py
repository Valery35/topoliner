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


class TestSmoothing(Base):
    """Сглаживание идёт по дугам, поэтому общая граница остаётся общей."""

    def geoms(self, res):
        return [self.poly(r) for r in res["rings"]]

    def simplify(self, smooth, tolerance=0.2):
        left, right = self.pair()
        return simplify_topology([left, right], tolerance=tolerance, smooth=smooth)

    def test_no_gap_or_overlap_appears(self):
        for passes in (1, 2, 3):
            res = self.simplify(passes)
            geoms = self.geoms(res)
            merged = self.b.union_all(geoms)
            parts = self.b.parts(merged)
            self.assertEqual(len(parts), 1,
                             "Разрыв при сглаживании в %d прохода" % passes)
            self.assertEqual(len(self.b.rings(parts[0])), 1,
                             "Щель при сглаживании в %d прохода" % passes)
            inter = self.b.polygonal_only(
                self.b.intersection(geoms[0], geoms[1]))
            self.assertLess(self.b.area(inter), 1e-9,
                            "Перекрытие при сглаживании в %d прохода" % passes)

    def test_result_stays_valid(self):
        for passes in (1, 2, 3):
            for geom in self.geoms(self.simplify(passes)):
                self.assertTrue(self.b.is_valid(geom))

    def test_vertices_grow_with_passes(self):
        counts = [self.simplify(p)["stats"]["vertices_out"] for p in (0, 1, 2)]
        self.assertLess(counts[0], counts[1])
        self.assertLess(counts[1], counts[2])

    def test_zero_passes_change_nothing(self):
        plain = simplify_topology(list(self.pair()), tolerance=0.2)
        smoothed = simplify_topology(list(self.pair()), tolerance=0.2, smooth=0)
        for a, c in zip(plain["rings"], smoothed["rings"]):
            self.assertEqual(a, c)

    def test_junction_points_do_not_move(self):
        """Узлы ветвления это концы дуг, они обязаны остаться на месте."""
        a = [(0, 0), (10, 0), (10.3, 2.5), (10, 5), (0, 5)]
        b = [(10, 0), (20, 0), (20, 5), (10, 5), (10.3, 2.5)]
        c = [(0, 5), (10, 5), (20, 5), (20, 10), (0, 10)]
        res = simplify_topology([a, b, c], tolerance=0.5, smooth=2)
        for ring in res["rings"]:
            pts = {(round(p[0], 9), round(p[1], 9)) for p in ring}
            self.assertIn((10.0, 5.0), pts)

    def test_smoothing_stays_within_hull(self):
        """Схема Чайкина не выходит за исходную линию, выбросов быть не может."""
        from topo_simplify import chaikin
        pts = [(0, 0), (5, 10), (10, 0)]
        out = chaikin(pts, 3)
        self.assertLessEqual(max(p[1] for p in out), 10.0 + 1e-9)
        self.assertGreaterEqual(min(p[1] for p in out), 0.0 - 1e-9)

    def test_open_line_endpoints_are_fixed(self):
        from topo_simplify import chaikin
        pts = [(0, 0), (5, 5), (10, 0)]
        out = chaikin(pts, 2)
        self.assertEqual(out[0], pts[0])
        self.assertEqual(out[-1], pts[-1])

    def test_closed_ring_is_smoothed_round(self):
        """Кольцо без узлов ветвления сглаживается по кругу, без излома на стыке."""
        square = [(0, 0), (10, 0), (10, 10), (0, 10)]
        res = simplify_topology([square], tolerance=0.0, smooth=2)
        ring = res["rings"][0]
        self.assertNotIn((0.0, 0.0), [(round(p[0], 9), round(p[1], 9)) for p in ring])
        self.assertTrue(self.b.is_valid(self.poly(ring)))


class TestLines(Base):
    """Разомкнутые линии: концы и точки ветвления неподвижны."""

    def network(self):
        """Магистраль и приток, соединённые в узле."""
        main = [(0, 0), (5, 0.3), (10, -0.2), (15, 0.1), (20, 0)]
        branch = [(10, -0.2), (12, 5), (14, 10)]
        return [main, branch]

    def simplify(self, rings, tolerance=0.5, smooth=0):
        return simplify_topology(rings, tolerance=tolerance, smooth=smooth,
                                 closed=[False] * len(rings))

    def test_junction_splits_the_line_into_arcs(self):
        arcs, paths = build_arcs(self.network(), closed=[False, False])
        self.assertEqual(len(paths[0]), 2, "Магистраль режется в узле надвое")
        self.assertEqual(len(paths[1]), 1)

    def test_junction_point_stays(self):
        res = self.simplify(self.network())
        for ring in res["rings"]:
            pts = [(round(p[0], 9), round(p[1], 9)) for p in ring]
            self.assertIn((10.0, -0.2), pts, "Узел ветвления сдвинулся")

    def test_line_endpoints_stay(self):
        rings = self.network()
        res = self.simplify(rings)
        for src, out in zip(rings, res["rings"]):
            self.assertEqual((round(out[0][0], 9), round(out[0][1], 9)),
                             (round(src[0][0], 9), round(src[0][1], 9)))
            self.assertEqual((round(out[-1][0], 9), round(out[-1][1], 9)),
                             (round(src[-1][0], 9), round(src[-1][1], 9)))

    def test_line_is_not_closed_into_a_ring(self):
        res = self.simplify(self.network())
        for ring in res["rings"]:
            self.assertNotEqual((ring[0][0], ring[0][1]),
                                (ring[-1][0], ring[-1][1]))

    def test_two_point_line_survives(self):
        """Линия из двух вершин не должна отбраковаться как вырожденная."""
        res = self.simplify([[(0, 0), (10, 0)]])
        self.assertIsNotNone(res["rings"][0])
        self.assertEqual(len(res["rings"][0]), 2)

    def test_shared_segment_stays_shared(self):
        """Общий участок двух линий прореживается один раз."""
        shared = [(0, 0), (2, 0.4), (4, -0.3), (6, 0.2), (8, 0)]
        first = shared + [(10, 3)]
        second = shared + [(10, -3)]
        res = self.simplify([first, second], tolerance=0.5)
        a = [(round(p[0], 9), round(p[1], 9)) for p in res["rings"][0] if p[0] <= 8]
        b = [(round(p[0], 9), round(p[1], 9)) for p in res["rings"][1] if p[0] <= 8]
        self.assertEqual(a, b, "Общий участок разошёлся")

    def test_smoothing_keeps_endpoints_and_junction(self):
        res = self.simplify(self.network(), smooth=2)
        for ring in res["rings"]:
            pts = [(round(p[0], 9), round(p[1], 9)) for p in ring]
            self.assertIn((10.0, -0.2), pts)
        self.assertEqual((round(res["rings"][1][-1][0], 9),
                          round(res["rings"][1][-1][1], 9)), (14.0, 10.0))

    def test_vertices_are_reduced_on_lines(self):
        rings = self.network()
        res = self.simplify(rings, tolerance=1.0)
        self.assertLess(res["stats"]["vertices_out"],
                        res["stats"]["vertices_in"])

    def test_rings_and_lines_can_be_mixed(self):
        """В одном вызове могут идти и кольца, и линии."""
        ring = [(0, 0), (10, 0), (10, 10), (0, 10)]
        line = [(20, 0), (25, 0.4), (30, 0)]
        res = simplify_topology([ring, line], tolerance=0.5,
                                closed=[True, False])
        self.assertGreaterEqual(len(res["rings"][0]), 3)
        self.assertEqual((res["rings"][1][0][0], res["rings"][1][0][1]), (20, 0))
        self.assertEqual((res["rings"][1][-1][0], res["rings"][1][-1][1]), (30, 0))
