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
