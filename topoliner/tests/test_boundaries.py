# -*- coding: utf-8 -*-
"""
Тесты извлечения границ покрытия.

Главное требование: граница между двумя телами выдаётся один раз, а не
дважды, как при обычном переводе полигонов в линии. Второе по важности:
внешний край, край полости и общая граница различаются.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from boundaries import (  # noqa: E402
    KIND_HOLE,
    KIND_OUTER,
    KIND_SHARED,
    extract_boundaries,
)
from geom_backend import ShapelyBackend  # noqa: E402


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class Base(unittest.TestCase):

    def setUp(self):
        self.b = ShapelyBackend()

    def kinds(self, result, kind):
        return [r for r in result if r["kind"] == kind]

    def total_length(self, result):
        total = 0.0
        for item in result:
            coords = item["coords"]
            for i in range(len(coords) - 1):
                dx = coords[i + 1][0] - coords[i][0]
                dy = coords[i + 1][1] - coords[i][1]
                total += (dx * dx + dy * dy) ** 0.5
        return total


class TestSharedOnce(Base):
    """Общая граница выдаётся одной линией."""

    def two_neighbours(self):
        return [(1, [[rect(0, 0, 10, 10)]]), (2, [[rect(10, 0, 20, 10)]])]

    def test_shared_border_appears_once(self):
        result = extract_boundaries(self.two_neighbours())
        shared = self.kinds(result, KIND_SHARED)
        self.assertEqual(len(shared), 1)
        self.assertEqual({shared[0]["fid_a"], shared[0]["fid_b"]}, {1, 2})

    def test_shared_border_geometry(self):
        result = extract_boundaries(self.two_neighbours())
        coords = [(round(p[0], 9), round(p[1], 9))
                  for p in self.kinds(result, KIND_SHARED)[0]["coords"]]
        self.assertEqual(sorted(coords), [(10.0, 0.0), (10.0, 10.0)])

    def test_outer_border_has_no_second_neighbour(self):
        result = extract_boundaries(self.two_neighbours())
        for item in self.kinds(result, KIND_OUTER):
            self.assertIsNone(item["fid_b"])

    def test_total_length_equals_perimeter_minus_shared(self):
        """Общая граница не дублируется, поэтому суммарная длина меньше
        суммы периметров ровно на её длину."""
        result = extract_boundaries(self.two_neighbours())
        perimeters = 40.0 + 40.0
        self.assertAlmostEqual(self.total_length(result), perimeters - 10.0,
                               places=6)


class TestUnnodedInput(Base):
    """Соседи с разной вершинностью: узлы достраиваются перед разбором."""

    def three_polygons(self):
        # У верхнего полигона нет вершины в точке стыка двух нижних
        return [(1, [[rect(0, 0, 10, 10)]]),
                (2, [[rect(10, 0, 20, 10)]]),
                (3, [[rect(0, 10, 20, 20)]])]

    def test_shared_borders_are_recognised(self):
        result = extract_boundaries(self.three_polygons())
        shared = self.kinds(result, KIND_SHARED)
        pairs = {frozenset((s["fid_a"], s["fid_b"])) for s in shared}
        self.assertEqual(pairs, {frozenset((1, 2)), frozenset((1, 3)),
                                 frozenset((2, 3))})

    def test_without_node_insertion_they_are_not(self):
        """Контрольный случай: без вставки узлов граница распадается."""
        result = extract_boundaries(self.three_polygons(), node_eps=0.0)
        shared = self.kinds(result, KIND_SHARED)
        self.assertLess(len(shared), 3)

    def test_arc_breaks_at_a_three_way_junction(self):
        result = extract_boundaries(self.three_polygons())
        for item in self.kinds(result, KIND_SHARED):
            self.assertEqual(len(item["coords"]), 2,
                             "Дуга обязана обрываться в тройном узле")


class TestHoles(Base):

    def test_empty_hole_is_marked_as_hole(self):
        items = [(1, [[rect(0, 0, 100, 100), rect(40, 40, 60, 60)]])]
        result = extract_boundaries(items)
        self.assertEqual(len(self.kinds(result, KIND_HOLE)), 1)
        self.assertEqual(len(self.kinds(result, KIND_OUTER)), 1)

    def test_enclave_makes_the_hole_a_shared_border(self):
        """Если в полости лежит другой объект, это уже общая граница."""
        items = [(1, [[rect(0, 0, 100, 100), rect(40, 40, 60, 60)]]),
                 (2, [[rect(40, 40, 60, 60)]])]
        result = extract_boundaries(items)
        self.assertEqual(self.kinds(result, KIND_HOLE), [])
        shared = self.kinds(result, KIND_SHARED)
        self.assertEqual(len(shared), 1)
        self.assertEqual({shared[0]["fid_a"], shared[0]["fid_b"]}, {1, 2})

    def test_ring_index_tells_outer_from_hole(self):
        items = [(1, [[rect(0, 0, 100, 100), rect(40, 40, 60, 60)]])]
        result = extract_boundaries(items)
        self.assertEqual(self.kinds(result, KIND_OUTER)[0]["ring_a"], 0)
        self.assertGreater(self.kinds(result, KIND_HOLE)[0]["ring_a"], 0)


class TestGeneral(Base):

    def test_single_polygon_gives_one_outer_ring(self):
        result = extract_boundaries([(1, [[rect(0, 0, 10, 10)]])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["kind"], KIND_OUTER)

    def test_detached_polygons_have_no_shared_borders(self):
        items = [(1, [[rect(0, 0, 10, 10)]]), (2, [[rect(500, 0, 510, 10)]])]
        result = extract_boundaries(items)
        self.assertEqual(self.kinds(result, KIND_SHARED), [])
        self.assertEqual(len(self.kinds(result, KIND_OUTER)), 2)

    def test_multipart_object_is_handled(self):
        items = [(1, [[rect(0, 0, 10, 10)], [rect(50, 0, 60, 10)]])]
        result = extract_boundaries(items)
        self.assertEqual(len(self.kinds(result, KIND_OUTER)), 2)
        for item in result:
            self.assertEqual(item["fid_a"], 1)

    def test_empty_input(self):
        self.assertEqual(extract_boundaries([]), [])

    def test_degenerate_ring_is_skipped(self):
        items = [(1, [[[(0, 0), (1, 1)]]])]
        self.assertEqual(extract_boundaries(items), [])

    def test_every_border_carries_its_owner(self):
        items = [(1, [[rect(0, 0, 10, 10)]]), (2, [[rect(10, 0, 20, 10)]])]
        for item in extract_boundaries(items):
            self.assertIsNotNone(item["fid_a"])
            self.assertIn(item["kind"], (KIND_SHARED, KIND_OUTER, KIND_HOLE))

    def test_result_covers_the_whole_boundary(self):
        """Сумма длин равна длине границы объединения плюс общие участки."""
        items = [(1, [[rect(0, 0, 10, 10)]]), (2, [[rect(10, 0, 20, 10)]])]
        result = extract_boundaries(items)
        merged = self.b.union_all([
            self.b.polygon([rect(0, 0, 10, 10) + [(0, 0)]]),
            self.b.polygon([rect(10, 0, 20, 10) + [(10, 0)]]),
        ])
        outer_length = self.b.length(self.b.boundary(merged))
        shared_length = self.total_length(self.kinds(result, KIND_SHARED))
        self.assertAlmostEqual(self.total_length(result),
                               outer_length + shared_length, places=6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
