# -*- coding: utf-8 -*-
"""
Тесты врезки контура в покрытие.

Главная проверка здесь одна. Кромка разреза обязана стать одной дугой
с двумя соседями. Две дуги рядом означают, что границы разошлись, а это
и есть то, что врезка обязана исключить.

Остальное держит контракт двух порогов и сохранение площади.
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN)

from coverage import build_coverage  # noqa: E402
from cut import (MODE_CLIP, MODE_INSET, MODE_OVERLAY,  # noqa: E402
                 cut_into_coverage)
from geom_backend import get_backend  # noqa: E402


def square(x0, y0, x1, y1):
    """Кольцо прямоугольника без повтора первой вершины."""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


class CutCase(unittest.TestCase):

    def setUp(self):
        self.backend = get_backend("shapely")

    def cut(self, items, cut_parts, threshold=0.0, node_eps=1e-6,
            mode=MODE_OVERLAY):
        return cut_into_coverage(self.backend, items, cut_parts,
                                 area_threshold=threshold, node_eps=node_eps,
                                 mode=mode)

    def area(self, parts):
        """Площадь набора частей."""
        total = 0.0
        for rings in parts:
            if rings:
                total += self.backend.area(
                    self.backend.polygon(list(rings)))
        return total

    def result_items(self, items, done, new_fid=900):
        """Покрытие после врезки, годное для build_coverage."""
        out = []
        for fid, parts in items:
            if fid in done["changed"]:
                parts = done["changed"][fid]
            elif fid in done["untouched"]:
                pass
            if parts:
                out.append((fid, parts))
        if done["created"]:
            out.append((new_fid, done["created"]))
        return out

    def arcs_between(self, items, one, two):
        """Дуги, разделяющие два объекта."""
        model = build_coverage(items, grid=1e-7, node_eps=1e-6)
        found = []
        for arc in model["arcs"]:
            pair = {arc["left"], arc["right"]}
            if pair == {one, two}:
                found.append(arc)
        return found

    def shared_length(self, items, one, two):
        """Суммарная длина общей кромки.

        Счёт дуг ненадёжен: при разошедшихся вершинах пара коротких
        случайных совпадений даёт то же количество. Длина говорит прямо,
        сколько границы действительно общее.
        """
        total = 0.0
        for arc in self.arcs_between(items, one, two):
            coords = arc["coords"]
            for i in range(len(coords) - 1):
                total += math.dist(coords[i], coords[i + 1])
        return total


class TestSharedEdge(CutCase):

    def test_cut_edge_is_one_arc(self):
        """Кромка между остатком и новым объектом одна, а не две."""
        items = [(1, [[square(0, 0, 10, 10)]])]
        done = self.cut(items, [[square(4, 0, 6, 10)]])
        self.assertTrue(done["created"])
        after = self.result_items(items, done)
        # Две кромки разреза по десять единиц каждая.
        self.assertAlmostEqual(self.shared_length(after, 1, 900), 20.0,
                               places=6)

    def test_edge_between_two_neighbours(self):
        """Контур поперёк общей границы двух соседей."""
        items = [(1, [[square(0, 0, 10, 10)]]),
                 (2, [[square(10, 0, 20, 10)]])]
        done = self.cut(items, [[square(8, 2, 12, 4)]])
        self.assertEqual(sorted(done["donors"]), [1, 2])
        after = self.result_items(items, done)
        # Контур 8..12 по x и 2..4 по y. С объектом 1 общая кромка это
        # левая сторона и два уса по два, с объектом 2 то же справа.
        for fid in (1, 2):
            self.assertAlmostEqual(self.shared_length(after, fid, 900), 6.0,
                                   places=6,
                                   msg="кромка с объектом %d" % fid)

    def test_no_duplicate_vertices_on_the_cut(self):
        """У обеих сторон кромки один и тот же набор вершин."""
        items = [(1, [[square(0, 0, 10, 10)]]),
                 (2, [[square(10, 0, 20, 10)]])]
        done = self.cut(items, [[square(8, 2, 12, 4)]])
        after = self.result_items(items, done)
        model = build_coverage(after, grid=1e-7, node_eps=1e-6)
        lonely = [a for a in model["arcs"]
                  if a["right"] is None and a["left"] is not None]
        # Одиночные дуги бывают только по внешнему краю покрытия.
        for arc in lonely:
            for x, y in arc["coords"]:
                self.assertTrue(
                    x in (0.0, 20.0) or y in (0.0, 10.0),
                    "внутренняя дуга осталась без второго соседа: %r"
                    % ((x, y),))


class TestArea(CutCase):

    def test_area_is_preserved(self):
        """Врезка внутри покрытия площади не создаёт и не теряет."""
        items = [(1, [[square(0, 0, 10, 10)]]),
                 (2, [[square(10, 0, 20, 10)]])]
        done = self.cut(items, [[square(8, 2, 12, 4)]])
        self.assertAlmostEqual(done["outside"], 0.0, places=9)
        self.assertAlmostEqual(done["area_after"], done["area_before"],
                               places=9)

    def test_growth_equals_the_outside_part(self):
        """Покрытие выросло ровно на ту часть, что легла за его край."""
        items = [(1, [[square(0, 0, 10, 10)]])]
        done = self.cut(items, [[square(8, 2, 14, 4)]])
        self.assertAlmostEqual(done["area_after"] - done["area_before"],
                               done["outside"], places=9)

    def test_outside_part_goes_to_the_new_object(self):
        """Часть контура за краем покрытия достаётся новому объекту."""
        items = [(1, [[square(0, 0, 10, 10)]])]
        done = self.cut(items, [[square(8, 2, 14, 4)]])
        self.assertAlmostEqual(done["outside"], 8.0, places=9)
        after = self.result_items(items, done)
        model = build_coverage(after, grid=1e-7, node_eps=1e-6)
        self.assertEqual(len(model["owners"]), 2)


class TestThreshold(CutCase):

    def test_small_slice_leaves_the_object_alone(self):
        """Отрезаемый кусок мельче порога. Объект не трогается."""
        items = [(1, [[square(0, 0, 10, 10)]]),
                 (2, [[square(10, 0, 20, 10)]])]
        done = self.cut(items, [[square(9.99, 2, 12, 4)]], threshold=1.0)
        self.assertEqual(done["donors"], [2])
        self.assertIn(1, done["untouched"])

    def test_small_remainder_is_swallowed(self):
        """Остаток мельче порога. Объект уходит под контур целиком."""
        # Остаток объекта 2 это полоса шириной 0.05 и площадью 0.5,
        # то есть мельче порога.
        items = [(1, [[square(0, 0, 10, 10)]]),
                 (2, [[square(10, 0, 10.2, 10)]])]
        done = self.cut(items, [[square(5, 0, 10.15, 10)]], threshold=1.0)
        self.assertEqual(done["changed"].get(2), [])
        after = self.result_items(items, done)
        self.assertEqual(sorted(fid for fid, _ in after), [1, 900])

    def test_threshold_zero_cuts_everything(self):
        items = [(1, [[square(0, 0, 10, 10)]]),
                 (2, [[square(10, 0, 20, 10)]])]
        done = self.cut(items, [[square(9.99, 2, 12, 4)]], threshold=0.0)
        self.assertEqual(sorted(done["donors"]), [1, 2])


class TestHoles(CutCase):

    def test_cut_across_a_hole(self):
        """Полость в объекте врезку не ломает."""
        ring = square(0, 0, 20, 20)
        hole = square(8, 8, 12, 12)
        items = [(1, [[ring, hole]])]
        done = self.cut(items, [[square(6, 9, 14, 11)]])
        self.assertTrue(done["created"])
        after = self.result_items(items, done)
        model = build_coverage(after, grid=1e-7, node_eps=1e-6)
        self.assertTrue(model["arcs"])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestMissingNodes(CutCase):
    """Разрез кончается на границе с третьим объектом.

    У того узла в этой точке нет, и без вставки врезка оставляла бы после
    себя нарушение, которое находит инструмент 1.01.
    """

    def neighbours(self):
        return [(1, [[square(0, 0, 10, 10)]]), (2, [[square(10, 0, 20, 10)]])]

    def has_vertex(self, parts, x, y):
        for rings in parts:
            for ring in rings:
                for v in ring:
                    if abs(v[0] - x) < 1e-9 and abs(v[1] - y) < 1e-9:
                        return True
        return False

    def test_neighbour_gets_the_missing_node(self):
        items = self.neighbours()
        done = self.cut(items, [[square(2, 2, 10, 4)]])
        self.assertEqual(done["donors"], [1])
        self.assertIn(2, done["noded"])
        self.assertTrue(self.has_vertex(done["noded"][2], 10.0, 2.0))
        self.assertTrue(self.has_vertex(done["noded"][2], 10.0, 4.0))

    def test_without_insertion_the_node_is_missing(self):
        """Сторож: с нулевым отклонением прежнее поведение возвращается."""
        items = self.neighbours()
        done = self.cut(items, [[square(2, 2, 10, 4)]], node_eps=0.0)
        self.assertEqual(done["noded"], {})
        self.assertEqual(done["nodes"], 0)

    def test_area_survives_the_insertion(self):
        items = self.neighbours()
        done = self.cut(items, [[square(2, 2, 10, 4)]])
        self.assertAlmostEqual(done["area_after"] - done["area_before"],
                               done["outside"], places=6)

    def test_shape_of_the_neighbour_is_the_same(self):
        items = self.neighbours()
        done = self.cut(items, [[square(2, 2, 10, 4)]])
        before = self.backend.polygon([square(10, 0, 20, 10)])
        after = self.backend.polygon(done["noded"][2][0])
        self.assertAlmostEqual(self.backend.area(after),
                               self.backend.area(before), places=9)


class TestModes(CutCase):
    """Три режима наложения.

    Покрытие это квадрат 10 на 10. Контур наполовину лежит на нём,
    наполовину за его краем, поэтому видно, что каждому режиму достаётся.
    """

    def setUp(self):
        CutCase.setUp(self)
        self.items = [(1, [[square(0, 0, 10, 10)]])]
        self.band = [[square(5, 2, 15, 6)]]   # 5 внутри, 10 снаружи, высота 4

    def test_overlay_takes_the_whole_contour(self):
        done = self.cut(self.items, self.band, mode=MODE_OVERLAY)
        self.assertEqual(done["donors"], [1])
        self.assertAlmostEqual(self.area(done["created"]), 40.0, places=6)
        self.assertAlmostEqual(self.area(done["changed"][1]), 80.0, places=6)
        self.assertAlmostEqual(done["outside"], 20.0, places=6)
        self.assertAlmostEqual(done["dropped"], 0.0, places=6)

    def test_clip_leaves_neighbours_alone(self):
        done = self.cut(self.items, self.band, mode=MODE_CLIP)
        self.assertEqual(done["donors"], [])
        self.assertEqual(done["changed"], {})
        self.assertAlmostEqual(self.area(done["created"]), 20.0, places=6)
        self.assertAlmostEqual(done["outside"], 20.0, places=6)

    def test_inset_keeps_the_area_of_the_coverage(self):
        done = self.cut(self.items, self.band, mode=MODE_INSET)
        self.assertEqual(done["donors"], [1])
        self.assertAlmostEqual(self.area(done["created"]), 20.0, places=6)
        self.assertAlmostEqual(self.area(done["changed"][1]), 80.0, places=6)
        self.assertAlmostEqual(done["outside"], 0.0, places=6)
        self.assertAlmostEqual(done["dropped"], 20.0, places=6)
        self.assertAlmostEqual(done["area_after"], done["area_before"], places=6)

    def test_area_holds_in_every_mode(self):
        for mode in (MODE_OVERLAY, MODE_CLIP, MODE_INSET):
            done = self.cut(self.items, self.band, mode=mode)
            self.assertAlmostEqual(done["area_after"] - done["area_before"],
                                   done["outside"], places=6,
                                   msg="режим %s" % mode)

    def test_unknown_mode_is_refused(self):
        with self.assertRaises(ValueError):
            self.cut(self.items, self.band, mode="боком")

    def test_clip_edge_is_shared_with_the_neighbour(self):
        """В отсечении кромка тоже общая, её даёт сам сосед."""
        done = self.cut(self.items, self.band, mode=MODE_CLIP)
        after = self.result_items(self.items, done)
        self.assertAlmostEqual(self.shared_length(after, 1, 900), 4.0, places=6)
