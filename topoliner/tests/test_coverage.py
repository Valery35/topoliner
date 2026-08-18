# -*- coding: utf-8 -*-
"""
Тесты топологической модели покрытия.

Смысл модели в том, что дуга хранится один раз и знает обоих соседей.
Поэтому главный тест здесь не про числа, а про свойство: правка дуги
меняет обоих соседей сразу, и границы разойтись не могут.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coverage import assemble_from_arcs, build_coverage  # noqa: E402


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class Base(unittest.TestCase):

    def two_neighbours(self):
        return [(1, [[rect(0, 0, 10, 10)]]), (2, [[rect(10, 0, 20, 10)]])]

    def three_polygons(self):
        return [(1, [[rect(0, 0, 10, 10)]]),
                (2, [[rect(10, 0, 20, 10)]]),
                (3, [[rect(0, 10, 20, 20)]])]

    def rounded(self, points):
        return [(round(p[0], 6), round(p[1], 6)) for p in points]


class TestNodes(Base):

    def test_nodes_are_shared(self):
        """Одна точка стыка это один узел, а не три."""
        coverage = build_coverage(self.three_polygons())
        places = {(round(n["x"], 6), round(n["y"], 6))
                  for n in coverage["nodes"]}
        self.assertEqual(len(places), len(coverage["nodes"]))

    def test_degree_counts_arcs(self):
        coverage = build_coverage(self.three_polygons())
        for node in coverage["nodes"]:
            self.assertEqual(node["degree"], len(node["arcs"]))
            self.assertGreaterEqual(node["degree"], 3,
                                    "В этой сцене все узлы тройные")

    def test_two_neighbours_have_two_nodes(self):
        coverage = build_coverage(self.two_neighbours())
        self.assertEqual(len(coverage["nodes"]), 2)


class TestArcs(Base):

    def test_shared_arc_knows_both_sides(self):
        coverage = build_coverage(self.two_neighbours())
        shared = [a for a in coverage["arcs"] if a["right"] is not None]
        self.assertEqual(len(shared), 1)
        self.assertEqual({shared[0]["left"], shared[0]["right"]}, {1, 2})

    def test_outer_arc_has_one_side(self):
        coverage = build_coverage(self.two_neighbours())
        for arc in coverage["arcs"]:
            if arc["right"] is None:
                self.assertIsNotNone(arc["left"])

    def test_arc_ends_are_nodes(self):
        coverage = build_coverage(self.three_polygons())
        node_ids = {n["id"] for n in coverage["nodes"]}
        for arc in coverage["arcs"]:
            self.assertIn(arc["from_node"], node_ids)
            self.assertIn(arc["to_node"], node_ids)

    def test_arc_endpoints_match_node_coordinates(self):
        coverage = build_coverage(self.three_polygons())
        nodes = {n["id"]: n for n in coverage["nodes"]}
        for arc in coverage["arcs"]:
            start = nodes[arc["from_node"]]
            end = nodes[arc["to_node"]]
            self.assertAlmostEqual(arc["coords"][0][0], start["x"], places=6)
            self.assertAlmostEqual(arc["coords"][-1][1], end["y"], places=6)

    def test_each_border_stored_once(self):
        """Общая граница хранится одной дугой, а не двумя."""
        coverage = build_coverage(self.three_polygons())
        shared = [a for a in coverage["arcs"] if a["right"] is not None]
        pairs = {frozenset((a["left"], a["right"])) for a in shared}
        self.assertEqual(len(pairs), len(shared))


class TestAssembly(Base):

    def test_rings_are_restored(self):
        items = self.three_polygons()
        coverage = build_coverage(items)
        back = assemble_from_arcs(coverage)
        self.assertEqual(len(back), 3)
        for _fid, _ring, points in back:
            self.assertIsNotNone(points)
            self.assertGreaterEqual(len(points), 3)

    def test_geometry_survives_the_round_trip(self):
        """Разобрали и собрали: множество вершин то же."""
        items = self.two_neighbours()
        coverage = build_coverage(items)
        back = assemble_from_arcs(coverage)
        for fid, _ring, points in back:
            source = dict(items)[fid][0][0]
            self.assertEqual(set(self.rounded(points)),
                             set(self.rounded(source)))

    def test_editing_an_arc_changes_both_neighbours(self):
        """Ради этого модель и нужна."""
        coverage = build_coverage(self.two_neighbours())
        shared = [a for a in coverage["arcs"] if a["right"] is not None][0]
        bent = [(10.0, 0.0), (11.5, 5.0), (10.0, 10.0)]

        back = assemble_from_arcs(coverage, {shared["id"]: bent})
        for _fid, _ring, points in back:
            self.assertIn((11.5, 5.0), self.rounded(points),
                          "Излом обязан появиться у обоих соседей")

    def test_editing_an_outer_arc_touches_one(self):
        coverage = build_coverage(self.two_neighbours())
        outer = [a for a in coverage["arcs"] if a["right"] is None][0]
        owner = outer["left"]
        moved = list(outer["coords"])
        moved.insert(1, (moved[0][0] - 3.0, moved[0][1] + 1.0))

        back = assemble_from_arcs(coverage, {outer["id"]: moved})
        changed = [fid for fid, _r, points in back
                   if (round(moved[1][0], 6), round(moved[1][1], 6))
                   in self.rounded(points)]
        self.assertEqual(changed, [owner])


class TestGeneral(Base):

    def test_empty_input(self):
        coverage = build_coverage([])
        self.assertEqual(coverage["arcs"], [])
        self.assertEqual(coverage["nodes"], [])

    def test_single_polygon(self):
        coverage = build_coverage([(1, [[rect(0, 0, 10, 10)]])])
        self.assertEqual(len(coverage["arcs"]), 1)
        arc = coverage["arcs"][0]
        self.assertIsNone(arc["right"])
        self.assertEqual(arc["from_node"], arc["to_node"],
                         "Кольцо без ветвлений замыкается само на себя")

    def test_hole_is_a_separate_ring(self):
        items = [(1, [[rect(0, 0, 100, 100), rect(40, 40, 60, 60)]])]
        coverage = build_coverage(items)
        self.assertEqual(len(coverage["rings"]), 2)
        numbers = {coverage["owners"][i][1] for i in range(2)}
        self.assertEqual(numbers, {0, 1})

    def test_unnoded_input_is_noded_first(self):
        """У верхнего полигона нет вершины в точке стыка двух нижних."""
        coverage = build_coverage(self.three_polygons())
        shared = [a for a in coverage["arcs"] if a["right"] is not None]
        self.assertEqual(len(shared), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
