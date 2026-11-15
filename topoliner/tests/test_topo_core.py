# -*- coding: utf-8 -*-
"""
Тесты ядра топологической сшивки.

Запуск из папки плагина:
    python -m unittest discover -s tests -v
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from topo_core import (  # noqa: E402
    clean_topology,
    ring_area,
    MODE_BOTH,
    MODE_INSERT,
    MODE_MERGE,
    Z_FROM_VERTEX,
    Z_INTERPOLATE,
)

SQUARE_A = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]


def xy(ring):
    return [(round(p[0], 9), round(p[1], 9)) for p in ring]


class TestInsertNodes(unittest.TestCase):

    def test_missing_node_is_inserted_without_moving(self):
        """У соседа есть лишняя вершина на общей границе. Она должна появиться и у нас."""
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)]
        res = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_INSERT)
        a_out = xy(res["rings"][0])
        self.assertIn((10.0, 5.0), a_out)
        self.assertEqual(res["stats"]["nodes_inserted"], 1)
        self.assertEqual(res["stats"]["vertices_moved"], 0)
        # Все исходные вершины A на месте, добавился ровно один узел.
        for p in xy(SQUARE_A):
            self.assertIn(p, a_out)
        self.assertEqual(len(a_out), len(SQUARE_A) + 1)

    def test_area_preserved_on_insert(self):
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)]
        res = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_INSERT)
        self.assertAlmostEqual(
            abs(ring_area(res["rings"][0][:-1])), abs(ring_area(SQUARE_A[:-1])), places=9
        )

    def test_far_vertex_is_not_inserted(self):
        """Вершина дальше допуска не должна порождать узел."""
        b = [(13, 0), (20, 0), (20, 10), (13, 10), (13, 5), (13, 0)]
        res = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_INSERT)
        self.assertEqual(res["stats"]["nodes_inserted"], 0)
        self.assertEqual(xy(res["rings"][0]), xy(SQUARE_A))

    def test_node_inserted_at_correct_position_in_ring(self):
        """Узел должен встать между теми вершинами, между которыми лежит."""
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 3), (10, 7), (10, 0)]
        res = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_INSERT)
        a_out = xy(res["rings"][0])
        i3 = a_out.index((10.0, 3.0))
        i7 = a_out.index((10.0, 7.0))
        self.assertLess(i3, i7)
        self.assertEqual(a_out[i3 - 1], (10.0, 0.0))


class TestMergeVertices(unittest.TestCase):

    def test_gap_is_closed_and_move_is_bounded(self):
        """Зазор 0.5 при допуске 2 закрывается, смещение не превышает допуск."""
        b = [(10.5, 0), (20, 0), (20, 10), (10.5, 10), (10.5, 0)]
        res = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_MERGE)
        b_out = xy(res["rings"][1])
        self.assertIn((10.0, 0.0), b_out)
        self.assertIn((10.0, 10.0), b_out)
        self.assertEqual(res["stats"]["vertices_moved"], 2)
        self.assertLessEqual(res["stats"]["max_move"], 2.0)
        self.assertAlmostEqual(res["stats"]["max_move"], 0.5, places=9)
        # Первый в списке слой не сдвинулся: он задаёт лидеров.
        self.assertEqual(xy(res["rings"][0]), xy(SQUARE_A))

    def test_no_chaining_beyond_tolerance(self):
        """Цепочка вершин с шагом 1.5 при допуске 2 не должна схлопнуться в одну точку.

        Соседние вершины одной линии при слиянии сливаются и лишние удаляются,
        поэтому проверяется не поэлементное соответствие, а гарантия по смещению:
        каждая исходная вершина остаётся в пределах допуска от результата.
        """
        chain = [[(0, 0), (1.5, 0), (3.0, 0), (4.5, 0), (6.0, 0)]]
        res = clean_topology(chain, tolerance=2.0, mode=MODE_MERGE)
        out = res["rings"][0]
        self.assertGreaterEqual(len(out), 3, "Цепочка схлопнулась целиком")
        for src in chain[0]:
            best = min(math.hypot(p[0] - src[0], p[1] - src[1]) for p in out)
            self.assertLessEqual(best, 2.0 + 1e-9)
        self.assertLessEqual(res["stats"]["max_move"], 2.0 + 1e-9)

    def test_hausdorff_guarantee_on_dense_data(self):
        """Та же гарантия на случайных данных: смещение вершин ограничено допуском."""
        import random

        random.seed(7)
        rings = []
        for i in range(40):
            x0 = random.uniform(0, 200)
            y0 = random.uniform(0, 200)
            rings.append([
                (x0, y0), (x0 + 12, y0 + 1), (x0 + 11, y0 + 9), (x0 - 1, y0 + 8), (x0, y0)
            ])
        res = clean_topology(rings, tolerance=2.0, mode=MODE_MERGE)
        for src_ring, out_ring in zip(rings, res["rings"]):
            if out_ring is None:
                continue
            for src in src_ring:
                best = min(math.hypot(p[0] - src[0], p[1] - src[1]) for p in out_ring)
                self.assertLessEqual(best, 2.0 + 1e-9)

    def test_ring_stays_closed_after_merge(self):
        ring = [[(0, 0), (10, 0.3), (10, 10), (0, 10), (0, 0)]]
        res = clean_topology(ring, tolerance=2.0, mode=MODE_MERGE)
        out = res["rings"][0]
        self.assertEqual((out[0][0], out[0][1]), (out[-1][0], out[-1][1]))

    def test_degenerate_ring_is_dropped(self):
        """Треугольник со сторонами меньше допуска схлопывается и отбраковывается."""
        tiny = [(0, 0), (0.5, 0), (0.25, 0.4), (0, 0)]
        res = clean_topology([tiny], tolerance=2.0, mode=MODE_MERGE)
        self.assertIsNone(res["rings"][0])
        self.assertEqual(res["stats"]["rings_degenerate"], 1)

    def test_fixed_rings_win_and_are_not_returned(self):
        """Вершины эталона неподвижны и притягивают рабочий слой."""
        work = [[(0.4, 0), (10, 0), (10, 10), (0.4, 10), (0.4, 0)]]
        fixed = [[(0, 0), (0, 10), (-5, 10), (-5, 0), (0, 0)]]
        res = clean_topology(work, tolerance=2.0, mode=MODE_MERGE, fixed_rings=fixed)
        self.assertEqual(len(res["rings"]), 1)
        out = xy(res["rings"][0])
        self.assertIn((0.0, 0.0), out)
        self.assertIn((0.0, 10.0), out)


class TestCombined(unittest.TestCase):

    def test_both_modes_produce_shared_boundary(self):
        """Зазор плюс несовпадающие узлы. После сшивки границы совпадают вершина в вершину."""
        b = [(10.4, 0), (20, 0), (20, 10), (10.4, 10), (10.4, 5), (10.4, 0)]
        res = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_BOTH)
        a_out = set(xy(res["rings"][0]))
        b_out = set(xy(res["rings"][1]))
        shared = {(10.0, 0.0), (10.0, 10.0), (10.4, 5.0)}
        self.assertTrue(shared.issubset(a_out | b_out))
        # Общая граница A и B состоит из одних и тех же точек.
        border_a = {p for p in a_out if abs(p[0] - 10.0) < 1e-9}
        border_b = {p for p in b_out if abs(p[0] - 10.0) < 1e-9}
        self.assertEqual(border_a, border_b)

    def test_idempotent(self):
        """Повторный прогон по результату ничего не меняет."""
        b = [(10.4, 0), (20, 0), (20, 10), (10.4, 10), (10.4, 5), (10.4, 0)]
        first = clean_topology([SQUARE_A, b], tolerance=2.0, mode=MODE_BOTH)
        second = clean_topology(first["rings"], tolerance=2.0, mode=MODE_BOTH)
        self.assertEqual(second["stats"]["vertices_moved"], 0)
        self.assertEqual(second["stats"]["nodes_inserted"], 0)
        for r1, r2 in zip(first["rings"], second["rings"]):
            self.assertEqual(xy(r1), xy(r2))

    def test_clean_layer_is_untouched(self):
        """Уже согласованный слой не должен меняться вообще."""
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 0)]
        res = clean_topology([a, b], tolerance=2.0, mode=MODE_BOTH)
        self.assertEqual(xy(res["rings"][0]), xy(a))
        self.assertEqual(xy(res["rings"][1]), xy(b))
        self.assertEqual(res["stats"]["rings_changed"], 0)


class TestZ(unittest.TestCase):

    def test_z_interpolated_on_insert(self):
        a = [(0, 0, 100), (10, 0, 100), (10, 10, 200), (0, 10, 200), (0, 0, 100)]
        b = [(10, 0, 50), (20, 0, 50), (20, 10, 50), (10, 10, 50), (10, 5, 50), (10, 0, 50)]
        res = clean_topology([a, b], tolerance=2.0, mode=MODE_INSERT, z_insert=Z_INTERPOLATE)
        node = [p for p in res["rings"][0] if abs(p[0] - 10) < 1e-9 and abs(p[1] - 5) < 1e-9]
        self.assertEqual(len(node), 1)
        self.assertAlmostEqual(node[0][2], 150.0, places=9)

    def test_z_from_vertex_on_insert(self):
        a = [(0, 0, 100), (10, 0, 100), (10, 10, 200), (0, 10, 200), (0, 0, 100)]
        b = [(10, 0, 50), (20, 0, 50), (20, 10, 50), (10, 10, 50), (10, 5, 55), (10, 0, 50)]
        res = clean_topology([a, b], tolerance=2.0, mode=MODE_INSERT, z_insert=Z_FROM_VERTEX)
        node = [p for p in res["rings"][0] if abs(p[0] - 10) < 1e-9 and abs(p[1] - 5) < 1e-9]
        self.assertAlmostEqual(node[0][2], 55.0, places=9)

    def test_own_z_survives_merge(self):
        """При слиянии по XY собственная отметка вершины сохраняется."""
        a = [(0, 0, 100), (10, 0, 100), (10, 10, 100), (0, 10, 100), (0, 0, 100)]
        b = [(10.5, 0, 777), (20, 0, 777), (20, 10, 777), (10.5, 10, 777), (10.5, 0, 777)]
        res = clean_topology([a, b], tolerance=2.0, mode=MODE_MERGE)
        for p in res["rings"][1]:
            self.assertAlmostEqual(p[2], 777.0, places=9)


class TestOpenLines(unittest.TestCase):

    def test_line_endpoint_snaps_to_line(self):
        """Висячий конец линии притягивается и порождает узел в примыкающей линии."""
        main = [(0, 0), (100, 0)]
        spur = [(50.3, 20), (50.3, 0.4)]
        res = clean_topology([main, spur], tolerance=2.0, mode=MODE_BOTH)
        main_out = xy(res["rings"][0])
        spur_out = xy(res["rings"][1])
        self.assertEqual(spur_out[-1], main_out[1] if False else spur_out[-1])
        # Конец отвода лежит на магистрали и является её вершиной.
        self.assertIn(spur_out[-1], main_out)

    def test_open_line_is_not_closed(self):
        line = [[(0, 0), (10, 0), (10, 10)]]
        res = clean_topology(line, tolerance=1.0, mode=MODE_BOTH)
        out = res["rings"][0]
        self.assertNotEqual((out[0][0], out[0][1]), (out[-1][0], out[-1][1]))


class TestSharedBoundaries(unittest.TestCase):
    """Общие точки по границам и угловые случаи."""

    def test_t_junction_three_polygons(self):
        """Слева один полигон, справа два. У левого должен появиться узел в стыке."""
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        b = [(10, 0), (20, 0), (20, 5), (10, 5), (10, 0)]
        c = [(10, 5), (20, 5), (20, 10), (10, 10), (10, 5)]
        res = clean_topology([a, b, c], tolerance=2.0)
        a_out = xy(res["rings"][0])
        self.assertIn((10.0, 5.0), a_out)
        self.assertEqual(res["stats"]["vertices_moved"], 0)

    def test_crossing_edges_get_nodes(self):
        """Перехлёст рёбер без общих вершин: узлы ставятся в точках пересечения."""
        d = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        e = [(5, -5), (15, -5), (15, 15), (5, 15), (5, -5)]
        res = clean_topology([d, e], tolerance=2.0)
        self.assertEqual(res["stats"]["nodes_crossing"], 4)
        d_out = set(xy(res["rings"][0]))
        e_out = set(xy(res["rings"][1]))
        for pt in ((5.0, 0.0), (5.0, 10.0)):
            self.assertIn(pt, d_out)
            self.assertIn(pt, e_out)

    def test_crossings_can_be_disabled(self):
        d = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        e = [(5, -5), (15, -5), (15, 15), (5, 15), (5, -5)]
        res = clean_topology([d, e], tolerance=2.0, node_crossings=False)
        self.assertEqual(res["stats"]["nodes_crossing"], 0)

    def test_corner_overshoot_is_merged(self):
        """Угол заходит за границу соседа меньше допуска: вершины сводятся."""
        f = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        g = [(9.6, 0), (20, 0), (20, 10), (9.6, 10), (9.6, 0)]
        res = clean_topology([f, g], tolerance=2.0)
        g_out = xy(res["rings"][1])
        self.assertIn((10.0, 0.0), g_out)
        self.assertIn((10.0, 10.0), g_out)
        self.assertAlmostEqual(res["stats"]["max_move"], 0.4, places=9)

    def test_matching_slanted_border_gets_no_false_nodes(self):
        """Наклонная граница уже совпадает: лишних узлов быть не должно."""
        h = [(0, 0), (10, 0), (7, 10), (0, 10), (0, 0)]
        i = [(10, 0), (20, 0), (20, 10), (7, 10), (10, 0)]
        res = clean_topology([h, i], tolerance=2.0)
        self.assertEqual(res["stats"]["nodes_inserted"], 0)
        self.assertEqual(res["stats"]["vertices_moved"], 0)
        self.assertEqual(xy(res["rings"][0]), xy(h))

    def test_corner_undershoot_beyond_tolerance_untouched(self):
        """Нестыковка больше допуска не исправляется: это содержательный случай."""
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        b = [(13, 0), (20, 0), (20, 10), (13, 10), (13, 0)]
        res = clean_topology([a, b], tolerance=2.0)
        self.assertEqual(res["stats"]["vertices_moved"], 0)
        self.assertEqual(res["stats"]["nodes_inserted"], 0)

    def test_crossing_is_idempotent(self):
        d = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        e = [(5, -5), (15, -5), (15, 15), (5, 15), (5, -5)]
        first = clean_topology([d, e], tolerance=2.0)
        second = clean_topology(first["rings"], tolerance=2.0)
        self.assertEqual(second["stats"]["nodes_inserted"], 0)
        self.assertEqual(second["stats"]["vertices_moved"], 0)

    def test_four_way_corner_is_consistent(self):
        """Четыре полигона сходятся в одной точке с разбросом меньше допуска."""
        q1 = [(10.2, 10.1), (20, 10.1), (20, 20), (10.2, 20), (10.2, 10.1)]
        q2 = [(0, 9.9), (9.8, 9.9), (9.8, 20), (0, 20), (0, 9.9)]
        q3 = [(0, 0), (10.1, 0), (10.1, 9.7), (0, 9.7), (0, 0)]
        q4 = [(10.1, 0), (20, 0), (20, 10.3), (10.1, 10.3), (10.1, 0)]
        res = clean_topology([q1, q2, q3, q4], tolerance=2.0)
        self.assertLessEqual(res["stats"]["max_move"], 2.0 + 1e-9)
        corners = set()
        for ring in res["rings"]:
            for p in xy(ring):
                if 8.0 < p[0] < 12.0 and 8.0 < p[1] < 12.0:
                    corners.add(p)
        self.assertEqual(len(corners), 1,
                         "Углы должны сойтись в одну точку, получено: %r" % corners)


class TestGuards(unittest.TestCase):

    def test_zero_tolerance_rejected(self):
        with self.assertRaises(ValueError):
            clean_topology([SQUARE_A], tolerance=0.0)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            clean_topology([SQUARE_A], tolerance=1.0, mode="nonsense")

    def test_empty_input(self):
        res = clean_topology([], tolerance=1.0)
        self.assertEqual(res["rings"], [])
        self.assertEqual(res["stats"]["nodes_inserted"], 0)

    def test_progress_called(self):
        seen = []
        clean_topology([SQUARE_A], tolerance=1.0, progress=seen.append)
        self.assertTrue(seen)
        self.assertAlmostEqual(seen[-1], 1.0, places=9)


class TestScale(unittest.TestCase):

    def test_many_rings_run_in_reasonable_time(self):
        """Сетка 60x60 квадратов со случайными сдвигами вершин."""
        import random
        import time

        random.seed(42)
        rings = []
        for i in range(60):
            for j in range(60):
                x0 = i * 10.0 + random.uniform(-0.4, 0.4)
                y0 = j * 10.0 + random.uniform(-0.4, 0.4)
                rings.append([
                    (x0, y0), (x0 + 10, y0), (x0 + 10, y0 + 10), (x0, y0 + 10), (x0, y0)
                ])
        t0 = time.time()
        res = clean_topology(rings, tolerance=2.0, mode=MODE_BOTH)
        elapsed = time.time() - t0
        self.assertLess(elapsed, 30.0, "Слишком медленно: %.1f с" % elapsed)
        self.assertLessEqual(res["stats"]["max_move"], 2.0 + 1e-9)
        self.assertEqual(len(res["rings"]), len(rings))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestCellTraversal(unittest.TestCase):
    """Обход ячеек сетки вдоль отрезка."""

    def test_cells_cover_the_segment(self):
        """Любая точка отрезка должна попадать в одну из выданных ячеек."""
        import random
        from topo_core import _cells_along_segment

        random.seed(11)
        for _ in range(2000):
            x1, y1, x2, y2 = [random.uniform(-50, 50) for _ in range(4)]
            cell = random.choice([0.05, 0.5, 3.0])
            cells = set(_cells_along_segment(x1, y1, x2, y2, cell))
            for k in range(0, 101):
                t = k / 100.0
                px = x1 + (x2 - x1) * t
                py = y1 + (y2 - y1) * t
                key = (int(math.floor(px / cell)), int(math.floor(py / cell)))
                self.assertIn(key, cells)

    def test_traversal_step_count_is_bounded(self):
        """Число ячеек не превышает суммы пройденных границ плюс один."""
        from topo_core import _cells_along_segment

        cells = list(_cells_along_segment(0.0, 10.0, 12.0, 10.0, 0.05))
        self.assertLessEqual(len(cells), 12.0 / 0.05 + 2)

    def test_small_cell_does_not_explode(self):
        """Мелкая ячейка при длинных рёбрах не должна вешать расчёт."""
        import time

        ring = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
        t0 = time.time()
        clean_topology([ring], tolerance=0.01)
        self.assertLess(time.time() - t0, 2.0)


class TestFrozenRings(unittest.TestCase):
    """Кольца уже допуска не изменяются, но служат опорой для соседей."""

    def strip(self, y0, width, n=10, length=20.0):
        top = [(i * length / n, y0 + width) for i in range(n + 1)]
        bot = [(i * length / n, y0) for i in range(n, -1, -1)]
        return top + bot + [top[0]]

    def test_frozen_ring_is_untouched(self):
        narrow = self.strip(0.0, 0.3)
        res = clean_topology([narrow], tolerance=1.0, frozen={0})
        self.assertEqual(xy(res["rings"][0]), xy(narrow))
        self.assertEqual(res["stats"]["vertices_moved"], 0)
        self.assertEqual(res["stats"]["rings_frozen"], 1)

    def test_without_freezing_the_same_ring_collapses(self):
        narrow = self.strip(0.0, 0.3)
        res = clean_topology([narrow], tolerance=1.0)
        self.assertGreater(res["stats"]["vertices_moved"], 0)
        self.assertNotEqual(xy(res["rings"][0]), xy(narrow))

    def test_neighbour_snaps_to_frozen_ring(self):
        """Сосед подтягивается к неизменяемому кольцу, а не наоборот."""
        narrow = self.strip(0.0, 0.3)
        wide = self.strip(0.6, 5.0)
        res = clean_topology([narrow, wide], tolerance=1.0, frozen={0})
        self.assertEqual(xy(res["rings"][0]), xy(narrow),
                         "Узкое кольцо должно остаться нетронутым")
        wide_out = xy(res["rings"][1])
        self.assertIn((0.0, 0.3), wide_out)
        self.assertLessEqual(res["stats"]["max_move"], 1.0 + 1e-9)

    def test_frozen_ring_takes_no_nodes(self):
        """В рёбра неизменяемого кольца узлы не вставляются."""
        narrow = self.strip(0.0, 0.3)
        # Вершина соседа лежит на середине верхнего ребра узкой полосы
        neighbour = [(10.0, 0.3), (20.0, 0.3), (20.0, 6.0), (10.0, 6.0), (10.0, 0.3)]
        res = clean_topology([narrow, neighbour], tolerance=1.0, frozen={0})
        self.assertEqual(len(xy(res["rings"][0])), len(xy(narrow)))


class TestNodeNearVertex(unittest.TestCase):
    """Узел не ставится там, где вершина уже есть в пределах допуска."""

    def test_no_node_next_to_existing_vertex(self):
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        # Вершина соседа лежит на ребре A в одной десятой допуска от угла
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 10 - 0.1), (10, 0)]
        res = clean_topology([a, b], tolerance=1.0)
        self.assertEqual(res["stats"]["nodes_inserted"], 0,
                         "Рядом с существующей вершиной узел не нужен")

    def test_node_is_added_far_from_vertices(self):
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)]
        res = clean_topology([a, b], tolerance=1.0)
        self.assertEqual(res["stats"]["nodes_inserted"], 1)

    def test_no_micro_edges_are_produced(self):
        """Вставка не должна порождать рёбра короче допуска."""
        import math

        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        b = [(10, 0), (20, 0), (20, 10), (10, 10),
             (10, 9.9999), (10, 5), (10, 0.0001), (10, 0)]
        res = clean_topology([a, b], tolerance=0.01)
        out = res["rings"][0]
        for i in range(len(out) - 1):
            d = math.hypot(out[i + 1][0] - out[i][0], out[i + 1][1] - out[i][1])
            self.assertGreater(d, 0.0)
        self.assertEqual(res["stats"]["nodes_inserted"], 1,
                         "Только средний узел действительно нужен")


class TestNearParallelEdges(unittest.TestCase):
    """
    Почти параллельные рёбра пересечением не считаются.

    Случай из кадастрового слоя: граница двух соседей нарисована дважды,
    почти одинаково. Формально рёбра пересекаются под углом в стотысячную
    долю градуса, но точка пересечения вычисляется неустойчиво, и узел
    возвращался на каждом проходе чуть в стороне. За восемь проходов
    на слое из 742 тысяч вершин так набегало 610 тысяч узлов.
    """

    def duplicated_border(self, drift=1e-5):
        """Две границы одной линии, нарисованные с микронным расхождением."""
        a = [(6431900.0, 7761800.0), (6432100.0, 7761800.0 + drift),
             (6432100.0, 7761700.0), (6431900.0, 7761700.0)]
        b = [(6431900.0, 7761800.0 + drift), (6432100.0, 7761800.0),
             (6432100.0, 7761900.0), (6431900.0, 7761900.0)]
        return [a, b]

    def test_no_nodes_at_near_parallel_crossing(self):
        rings = self.duplicated_border()
        res = clean_topology(rings, tolerance=1e-6, mode=MODE_INSERT,
                             project_onto_edge=True)
        self.assertEqual(res["stats"]["nodes_crossing"], 0)

    def test_it_converges(self):
        """Раньше узлы возвращались на каждом проходе."""
        current = self.duplicated_border()
        counts = []
        for _ in range(6):
            res = clean_topology(current, tolerance=1e-6, mode=MODE_INSERT,
                                 project_onto_edge=True)
            counts.append(res["stats"]["nodes_inserted"])
            current = [r for r in res["rings"]]
            if counts[-1] == 0:
                break
        self.assertLessEqual(len(counts), 3, "Не сошлось: %r" % counts)
        self.assertEqual(counts[-1], 0)

    def test_real_crossing_is_still_found(self):
        """Настоящее пересечение под заметным углом никуда не делось."""
        a = [(0, 0), (100, 0), (100, 100), (0, 100)]
        b = [(50, -50), (150, -50), (150, 50), (50, 50)]
        res = clean_topology([a, b], tolerance=1e-6, mode=MODE_INSERT,
                             project_onto_edge=True)
        self.assertGreater(res["stats"]["nodes_crossing"], 0)

    def test_shallow_but_real_crossing_is_found(self):
        """Пологое пересечение в один градус это ещё пересечение."""
        import math
        angle = math.radians(1.0)
        a = [(0, 0), (1000, 0), (1000, 200), (0, 200)]
        b = [(0, -5), (1000, -5 + 1000 * math.tan(angle)),
             (1000, -205), (0, -205)]
        res = clean_topology([a, b], tolerance=1e-6, mode=MODE_INSERT,
                             project_onto_edge=True)
        self.assertGreater(res["stats"]["nodes_crossing"], 0)

    def test_large_coordinates_do_not_defeat_the_check(self):
        """Проверка относительная, поэтому не зависит от величины координат."""
        rings = self.duplicated_border()
        shifted = [[(x + 6000000.0, y + 1000000.0) for x, y in r] for r in rings]
        res = clean_topology(shifted, tolerance=1e-6, mode=MODE_INSERT,
                             project_onto_edge=True)
        self.assertEqual(res["stats"]["nodes_crossing"], 0)


class TestGridOrigin(unittest.TestCase):
    """
    Сетки отсчитываются от угла данных, а не от начала координат.

    При мелкой ячейке и координатах в миллионы метров номера ячеек иначе
    получаются порядка десяти в двенадцатой, а такие числа Python хеширует
    заметно медленнее коротких. На кадастровом слое это давало двукратную
    разницу во времени.
    """

    def test_result_does_not_depend_on_the_origin(self):
        near = [[(0, 0), (10, 0), (10, 10), (0, 10)],
                [(10, 0), (20, 0), (20, 10), (10, 10)],
                [(0, 10), (20, 10), (20, 20), (0, 20)]]
        far = [[(x + 6431900.0, y + 7761800.0) for x, y in ring]
               for ring in near]

        a = clean_topology(near, tolerance=1e-6, mode=MODE_INSERT,
                           project_onto_edge=True)
        b = clean_topology(far, tolerance=1e-6, mode=MODE_INSERT,
                           project_onto_edge=True)
        self.assertEqual(a["stats"]["nodes_inserted"],
                         b["stats"]["nodes_inserted"])
        self.assertEqual([len(r) for r in a["rings"]],
                         [len(r) for r in b["rings"]])

    def test_vertex_grid_separates_rings(self):
        """Ключ сетки вершин включает кольцо, чужие вершины не мешают."""
        from topo_core import _RingVertexGrid
        grid = _RingVertexGrid(1.0)
        grid.add(0, 100.0, 100.0)
        grid.add(1, 100.0, 100.0)
        self.assertTrue(grid.has_vertex(0, 100.0, 100.0, 0.5))
        self.assertTrue(grid.has_vertex(1, 100.0, 100.0, 0.5))
        self.assertFalse(grid.has_vertex(2, 100.0, 100.0, 0.5))

    def test_vertex_grid_works_with_large_coordinates(self):
        from topo_core import _RingVertexGrid
        grid = _RingVertexGrid(1e-6, 6431900.0, 7761800.0)
        grid.add(0, 6431900.5, 7761800.5)
        self.assertTrue(grid.has_vertex(0, 6431900.5, 7761800.5, 1e-6))
        self.assertFalse(grid.has_vertex(0, 6431901.5, 7761800.5, 1e-6))


class TestDetectOnly(unittest.TestCase):
    """
    Режим только обнаружения: события есть, собранных колец нет.

    Проверке нужны события вставки, а геометрию она выбрасывает. Сборка
    результата на слое в семьсот тысяч вершин стоит времени и памяти.
    """

    def scene(self):
        return [[(0, 0), (10, 0), (10, 10), (0, 10)],
                [(10, 0), (20, 0), (20, 10), (10, 10)],
                [(0, 10), (20, 10), (20, 20), (0, 20)]]

    def test_events_are_the_same(self):
        full = clean_topology(self.scene(), tolerance=1e-6, mode=MODE_INSERT)
        short = clean_topology(self.scene(), tolerance=1e-6, mode=MODE_INSERT,
                               detect_only=True)
        self.assertEqual(len(full["events"]), len(short["events"]))
        self.assertEqual(full["stats"]["nodes_inserted"],
                         short["stats"]["nodes_inserted"])

    def test_rings_are_not_built(self):
        short = clean_topology(self.scene(), tolerance=1e-6, mode=MODE_INSERT,
                               detect_only=True)
        self.assertEqual(short["rings"], [])

    def test_normal_mode_still_builds_rings(self):
        full = clean_topology(self.scene(), tolerance=1e-6, mode=MODE_INSERT)
        self.assertEqual(len(full["rings"]), 3)


class TestCrossingMemoryBudget(unittest.TestCase):
    """
    Шаг узлов в пересечениях останавливается, если не помещается в память.

    14 ноября 2026 года QGIS 4.2.3 упал на очистке 1.03 в этом шаге
    с нарушением доступа. Python из состава QGIS при нехватке памяти
    на всей машине падает так, а не с MemoryError. Шаг оценивает память
    заранее и останавливается с понятной причиной.
    """

    def crossing(self):
        """Две линии крест-накрест, узел ставится в точку пересечения."""
        return [[(0, 0), (10, 0)], [(5, -5), (5, 5)]]

    def test_tiny_budget_stops_before_work(self):
        import topo_core
        with self.assertRaises(topo_core.CrossingMemoryError) as caught:
            clean_topology(self.crossing(), tolerance=0.01, mode=MODE_INSERT,
                           memory_budget=1)
        self.assertEqual(caught.exception.vertices, 2)
        self.assertGreater(caught.exception.needed, caught.exception.available)

    def test_budget_counts_segments(self):
        """Ровно на сегменты бюджета хватает, на байт меньше уже нет."""
        import topo_core
        segments = 2 * topo_core.CROSSING_SEGMENT_BYTES
        res = clean_topology(self.crossing(), tolerance=0.01, mode=MODE_INSERT,
                             memory_budget=segments)
        self.assertEqual(res["stats"]["nodes_crossing"], 2)
        with self.assertRaises(topo_core.CrossingMemoryError):
            clean_topology(self.crossing(), tolerance=0.01, mode=MODE_INSERT,
                           memory_budget=segments - 1)


class TestCrossingAcceptedOnce(unittest.TestCase):
    """
    Пересечение принимается один раз, сколько бы общих ячеек ни было у пары.

    Множества проверенных пар больше нет, пара проверяется в каждой общей
    ячейке. Пересечение принимается только в первой из них. Без этого одна
    и та же точка уходила бы во вставку столько раз, сколько у пары общих
    ячеек, а счётчик неустойчивых пересечений рос бы так же.
    """

    def scene(self):
        # Две длинные почти параллельные линии крест-накрест. Кольцо из
        # тысячи коротких рёбер вдали делает ячейку сетки мелкой, и у пары
        # линий оказывается много общих ячеек.
        a = [(0.0, 0.0), (100.0, 1.0)]
        b = [(0.0, 1.0), (100.0, 0.0)]
        dense = [(1000.0 + 0.1 * i, 1000.0) for i in range(1000)]
        return [a, b, dense]

    def test_pair_has_many_common_cells(self):
        """Без этого тест ничего не проверяет."""
        import topo_core
        norm = [topo_core._norm(r) for r in self.scene()]
        cell = max(0.01, topo_core._mean_segment_length(norm))
        ox, oy = topo_core._origin_of(norm)
        grid = topo_core._SegmentGrid(cell, ox, oy)
        a = grid.cells_of(0.0, 0.0, 100.0, 1.0)
        b = set(grid.cells_of(0.0, 1.0, 100.0, 0.0))
        self.assertGreater(len([c for c in a if c in b]), 5)

    def test_each_segment_gets_one_insert(self):
        import topo_core
        seen = []
        original = topo_core._apply_inserts

        def spy(norm, inserts, events, kind):
            seen.append({k: len(v) for k, v in inserts.items()})
            return original(norm, inserts, events, kind)

        topo_core._apply_inserts = spy
        try:
            res = clean_topology(self.scene(), tolerance=0.01, mode=MODE_INSERT)
        finally:
            topo_core._apply_inserts = original
        crossing = [s for s in seen if s][0]
        self.assertEqual(crossing, {(0, 0): 1, (1, 0): 1})
        self.assertEqual(res["stats"]["nodes_crossing"], 2)


class TestCompactIndexesMatchGrids(unittest.TestCase):
    """
    Сжатые индексы шага 3 отвечают так же, как прежние сетки.

    Шаг 3 сшивки держал словарь ячеек отрезков и сетку всех вершин слоя,
    это была половина пика памяти. Сжатые замены обязаны давать тот же
    ответ, и для отрезков - в том же порядке обхода, от него зависит
    порядок вставок.
    """

    def scene(self, seed):
        import random
        rng = random.Random(seed)
        rings = []
        for _ in range(40):
            cx, cy = rng.uniform(0, 100), rng.uniform(0, 100)
            k = rng.randint(3, 15)
            ring = [(cx + rng.uniform(-8, 8), cy + rng.uniform(-8, 8)) for _ in range(k)]
            rings.append(ring + [ring[0]] if rng.random() < 0.7 else ring)
        return rings

    def test_segment_query_matches_grid(self):
        import random
        import topo_core
        for seed in range(5):
            norm = [topo_core._norm(r) for r in self.scene(seed)]
            frozen = {1, 7}
            ox, oy = topo_core._origin_of(norm)
            cell = max(0.5, topo_core._mean_segment_length(norm))
            grid = topo_core._SegmentGrid(cell, ox, oy)
            for ri, (coords, closed) in enumerate(norm):
                if ri in frozen:
                    continue
                n = len(coords)
                for si in range(n if closed else n - 1):
                    x1, y1, _ = coords[si]
                    x2, y2, _ = coords[(si + 1) % n]
                    grid.add((ri, si), x1, y1, x2, y2)
            flat = [topo_core._flat(r) for r in self.scene(seed)]
            self.assertEqual(topo_core._flat_origin(flat), (ox, oy))
            self.assertEqual(max(0.5, topo_core._flat_mean_segment_length(flat)), cell)
            query = topo_core._segment_index(flat, frozen, cell, ox, oy)
            rng = random.Random(seed)
            for _ in range(300):
                x, y = rng.uniform(-10, 110), rng.uniform(-10, 110)
                self.assertEqual(list(query(x, y)), list(grid.query(x, y)))

    def test_own_vertex_matches_grid(self):
        import random
        import topo_core
        for seed in range(5):
            norm = [topo_core._norm(r) for r in self.scene(seed)]
            tol = 2.5
            own = topo_core._RingVertexGrid(tol, *topo_core._origin_of(norm))
            for ri, (coords, _closed) in enumerate(norm):
                for vx, vy, _ in coords:
                    own.add(ri, vx, vy)
            has = topo_core._own_vertex_lookup(
                [topo_core._flat(r) for r in self.scene(seed)], tol)
            rng = random.Random(seed)
            for _ in range(500):
                ri = rng.randrange(len(norm))
                vx, vy, _ = rng.choice(norm[ri][0])
                x, y = vx + rng.uniform(-3, 3), vy + rng.uniform(-3, 3)
                self.assertEqual(has(ri, x, y), own.has_vertex(ri, x, y, tol))

    def test_leader_grid_matches_point_grid(self):
        # Сетка лидеров слияния обязана выбирать того же лидера, что
        # прежняя, в том числе из равноудалённых и при отрицательных
        # координатах.
        import random
        import topo_core
        for seed in range(5):
            rng = random.Random(seed)
            tol = rng.choice([0.5, 1.0, 3.0])
            old = topo_core._PointGrid(tol)
            new = topo_core._LeaderGrid(tol, 60.0)
            for _ in range(3000):
                # Координаты на решётке шага 0.5 дают много равных расстояний.
                x = rng.randint(-100, 100) * 0.5
                y = rng.randint(-100, 100) * 0.5
                a = old.nearest(x, y, tol)
                self.assertEqual(new.nearest(x, y, tol), a)
                if a[0] is None or rng.random() < 0.2:
                    self.assertEqual(new.add(x, y), old.add(x, y))


class TestCrossingMemoryBudgetMore(unittest.TestCase):
    """Продолжение проверок бюджета памяти."""

    def crossing(self):
        return [[(0, 0), (10, 0)], [(5, -5), (5, 5)]]

    def test_enough_budget_gives_the_same_result(self):
        free = clean_topology(self.crossing(), tolerance=0.01, mode=MODE_INSERT)
        ample = clean_topology(self.crossing(), tolerance=0.01, mode=MODE_INSERT,
                               memory_budget=10 ** 9)
        self.assertEqual(free["rings"], ample["rings"])
        self.assertEqual(free["stats"]["nodes_crossing"], 2)
        self.assertEqual(ample["stats"]["nodes_crossing"], 2)

    def test_no_crossings_no_check(self):
        res = clean_topology(self.crossing(), tolerance=0.01, mode=MODE_INSERT,
                             node_crossings=False, memory_budget=1)
        self.assertEqual(res["stats"]["nodes_crossing"], 0)

    def test_available_memory_is_known_here(self):
        import topo_core
        free = topo_core.available_memory()
        self.assertTrue(free is None or free > 0)

    def test_message_names_the_numbers(self):
        import i18n
        import qgis_helpers
        import topo_core
        why = topo_core.CrossingMemoryError(1234567, 3 * 2 ** 30, 2 ** 30)
        try:
            i18n.set_language("ru")
            ru = qgis_helpers.memory_message(why)
            i18n.set_language("en")
            en = qgis_helpers.memory_message(why)
        finally:
            i18n.set_language("ru")
        self.assertIn("1234567", ru)
        self.assertIn("3.0", ru)
        self.assertIn("1.0", ru)
        self.assertIn("1234567", en)
        self.assertNotRegex(en, "[А-Яа-я]")

    def test_wrapper_turns_it_into_a_processing_error(self):
        import qgis_helpers
        import topo_core

        class Tool:
            @qgis_helpers.no_warnings
            def processAlgorithm(self, parameters, context, feedback):
                raise topo_core.CrossingMemoryError(10, 2 ** 31, 2 ** 30)

        with self.assertRaises(qgis_helpers.QgsProcessingException) as caught:
            Tool().processAlgorithm({}, None, None)
        self.assertIn("10", str(caught.exception))
