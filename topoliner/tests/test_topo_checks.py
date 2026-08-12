# -*- coding: utf-8 -*-
"""
Тесты проверки топологии и конвейера исправления.

Работают на Shapely, который использует тот же GEOS, что и QGIS,
поэтому поведение геометрических операций совпадает с рабочим.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from geom_backend import ShapelyBackend  # noqa: E402
import topo_checks as tc  # noqa: E402
from topo_core import MODE_INSERT  # noqa: E402
tc.MODE_INSERT = MODE_INSERT


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


class Base(unittest.TestCase):

    def setUp(self):
        self.b = ShapelyBackend()

    def poly(self, *rings):
        return self.b.polygon(list(rings))

    def kinds(self, findings, kind=None, severity=None):
        out = findings
        if kind:
            out = [f for f in out if f["type"] == kind]
        if severity:
            out = [f for f in out if f["severity"] == severity]
        return out


class TestCheckOverlaps(Base):

    def test_small_overlap_is_auto(self):
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(9.9, 0, 20, 10)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        ov = self.kinds(f, tc.OVERLAP)
        self.assertEqual(len(ov), 1)
        self.assertEqual(ov[0]["severity"], tc.SEVERITY_AUTO)
        self.assertAlmostEqual(ov[0]["value"], 1.0, places=6)

    def test_large_overlap_is_review(self):
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(5, 0, 20, 10)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        ov = self.kinds(f, tc.OVERLAP)
        self.assertEqual(len(ov), 1)
        self.assertEqual(ov[0]["severity"], tc.SEVERITY_REVIEW)

    def test_duplicate_detected(self):
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(0, 0, 10, 10)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertEqual(len(self.kinds(f, tc.DUPLICATE)), 1)

    def test_nested_detected(self):
        items = [(1, self.poly(rect(0, 0, 100, 100))), (2, self.poly(rect(10, 10, 20, 20)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertEqual(len(self.kinds(f, tc.NESTED)), 1)
        self.assertEqual(len(self.kinds(f, tc.OVERLAP)), 0)


class TestCheckGaps(Base):

    def ring_of_four(self, gap_w):
        """Четыре полигона вокруг замкнутой щели шириной gap_w."""
        return [
            (1, self.poly(rect(0, 0, 10, 10))),
            (2, self.poly(rect(10 + gap_w, 0, 20, 10))),
            (3, self.poly(rect(0, 10, 20 + gap_w, 20))),
            (4, self.poly(rect(0, -10, 20 + gap_w, 0))),
        ]

    def test_gap_detected_and_classified(self):
        items = self.ring_of_four(0.1)
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        gaps = self.kinds(f, tc.GAP)
        self.assertEqual(len(gaps), 1)
        self.assertAlmostEqual(gaps[0]["value"], 1.0, places=6)
        self.assertEqual(gaps[0]["severity"], tc.SEVERITY_AUTO)

    def test_open_gap_is_not_a_hole(self):
        """Зазор, выходящий на край покрытия, дырой в объединении не является.

        Это граница метода: такие зазоры закрывает сшивка вершин,
        а не этап заполнения щелей.
        """
        items = [
            (1, self.poly(rect(0, 0, 20, 9.95))),
            (2, self.poly(rect(0, 10, 20, 20))),
        ]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertEqual(len(self.kinds(f, tc.GAP)), 0)

    def test_open_gap_is_closed_by_snapping(self):
        items = [
            (1, self.poly(rect(0, 0, 20, 9.95))),
            (2, self.poly(rect(0, 10, 20, 20))),
        ]
        out, stats, _left = tc.fix_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        merged = self.b.union_all([g for _fid, g in out if g is not None])
        self.assertEqual(len(self.b.parts(merged)), 1,
                         "После сшивки покрытие должно стать сплошным")

    def test_outer_boundary_is_not_a_gap(self):
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(20, 0, 30, 10)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertEqual(len(self.kinds(f, tc.GAP)), 0)


class TestCheckVertexArtifacts(Base):

    def test_spike_detected(self):
        ring = [(0, 0), (10, 0), (10, 10), (5, 10), (5.0001, 25), (5, 10), (0, 10), (0, 0)]
        items = [(1, self.poly(ring))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=1.0,
                               do_gaps=False, do_overlaps=False)
        self.assertGreaterEqual(len(self.kinds(f, tc.SPIKE)), 1)

    def test_sliver_detected(self):
        items = [(1, self.poly(rect(0, 0, 200, 0.5)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0,
                               do_gaps=False, do_overlaps=False)
        self.assertEqual(len(self.kinds(f, tc.SLIVER)), 1)

    def test_tiny_hole_detected(self):
        items = [(1, self.poly(rect(0, 0, 100, 100), rect(50, 50, 51, 51)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0,
                               do_gaps=False, do_overlaps=False)
        self.assertEqual(len(self.kinds(f, tc.TINY_HOLE)), 1)

    def test_vertex_exactly_on_edge_is_on_edge(self):
        """Вершина лежит точно на ребре соседа: дефект вершинности."""
        a = rect(0, 0, 10, 10)
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)]
        items = [(1, self.poly(a)), (2, self.poly(b))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        on_edge = self.kinds(f, tc.ON_EDGE)
        self.assertEqual(len(on_edge), 1)
        self.assertEqual(on_edge[0]["value"], 0.0)
        self.assertEqual(self.kinds(f, tc.UNSNAPPED), [])

    def test_on_edge_survives_tiny_tolerance(self):
        """Такая находка не зависит от допуска: она есть и при почти нулевом."""
        a = rect(0, 0, 10, 10)
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)]
        items = [(1, self.poly(a)), (2, self.poly(b))]
        f, _s = tc.check_items(self.b, items, tolerance=0.001, area_threshold=0.001)
        self.assertEqual(len(self.kinds(f, tc.ON_EDGE)), 1)

    def test_vertex_near_edge_is_unsnapped(self):
        """Вершина рядом с ребром: находка целиком зависит от допуска."""
        a = rect(0, 0, 10, 10)
        b = [(10.5, 0), (20, 0), (20, 10), (10.5, 10), (10.5, 5), (10.5, 0)]
        items = [(1, self.poly(a)), (2, self.poly(b))]
        wide, _s1 = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        near = self.kinds(wide, tc.UNSNAPPED)
        self.assertGreaterEqual(len(near), 1)
        self.assertGreater(near[0]["value"], 0.0)
        # При допуске меньше расхождения находки нет вовсе.
        tight, _s2 = tc.check_items(self.b, items, tolerance=0.1, area_threshold=10.0)
        self.assertEqual(self.kinds(tight, tc.UNSNAPPED), [])
        self.assertEqual(self.kinds(tight, tc.ON_EDGE), [])

    def test_summary_reports_median(self):
        f = [
            tc.finding(tc.UNSNAPPED, tc.SEVERITY_AUTO, value=0.0),
            tc.finding(tc.UNSNAPPED, tc.SEVERITY_AUTO, value=1.0),
            tc.finding(tc.UNSNAPPED, tc.SEVERITY_AUTO, value=9.0),
        ]
        s = tc.summarize(f)
        self.assertAlmostEqual(s[tc.UNSNAPPED]["value_med"], 1.0)
        self.assertAlmostEqual(s[tc.UNSNAPPED]["value_max"], 9.0)

    def test_clean_layer_gives_no_findings(self):
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(10, 0, 20, 10)))]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=1.0)
        self.assertEqual(f, [], "На чистом покрытии находок быть не должно: %r" % f)


class TestFix(Base):

    def area_sum(self, items):
        return sum(self.b.area(g) for _fid, g in items if g is not None)

    def test_small_overlap_removed(self):
        """Допуск мал, поэтому сшивка перекрытие не убирает и работает шаг вычитания."""
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(9.9, 0, 20, 10)))]
        out, stats, left = tc.fix_items(self.b, items, tolerance=0.05, area_threshold=10.0)
        self.assertEqual(stats["overlaps_fixed"], 1)
        f, _s = tc.check_items(self.b, [(i, g) for i, g in out if g], 0.05, 10.0)
        self.assertEqual(len(self.kinds(f, tc.OVERLAP)), 0)

    def test_small_overlap_absorbed_by_snapping(self):
        """При достаточном допуске то же перекрытие исчезает уже на сшивке."""
        items = [(1, self.poly(rect(0, 0, 10, 10))), (2, self.poly(rect(9.9, 0, 20, 10)))]
        out, stats, _left = tc.fix_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertEqual(stats["overlaps_fixed"], 0)
        f, _s = tc.check_items(self.b, [(i, g) for i, g in out if g], 2.0, 10.0)
        self.assertEqual(len(self.kinds(f, tc.OVERLAP)), 0)

    def test_large_overlap_is_left_alone(self):
        a = self.poly(rect(0, 0, 10, 10))
        b = self.poly(rect(5, 0, 20, 10))
        out, stats, left = tc.fix_items(self.b, [(1, a), (2, b)],
                                        tolerance=0.5, area_threshold=10.0)
        self.assertEqual(stats["overlaps_fixed"], 0)
        self.assertEqual(stats["overlaps_left"], 1)
        self.assertTrue(any(x["type"] == tc.OVERLAP for x in left))
        # Геометрия обоих объектов сохранена по площади.
        self.assertAlmostEqual(self.area_sum(out), self.b.area(a) + self.b.area(b), places=6)

    def test_overlap_winner_is_larger_by_default(self):
        big = self.poly(rect(0, 0, 100, 100))
        small = self.poly(rect(99.9, 0, 120, 5))
        out, stats, _left = tc.fix_items(self.b, [(1, big), (2, small)],
                                         tolerance=0.05, area_threshold=10.0)
        self.assertEqual(stats["overlaps_fixed"], 1)
        self.assertAlmostEqual(self.b.area(out[0][1]), 10000.0, places=6)
        # Мелкий объект отдал полосу перекрытия 0.1 x 5.
        self.assertAlmostEqual(self.b.area(out[1][1]), 20.1 * 5 - 0.5, places=6)

    def test_small_gap_goes_to_longest_shared_border(self):
        """Замкнутая щель 10 x 0.1 достаётся соседу с самой длинной общей границей."""
        left_p = self.poly(rect(0, 0, 10, 10))
        right_p = self.poly(rect(10.1, 0, 20, 10))
        top = self.poly(rect(0, 10, 20, 20))
        bottom = self.poly(rect(0, -10, 20, 0))
        out, stats, _left = tc.fix_items(
            self.b, [(1, left_p), (2, right_p), (3, top), (4, bottom)],
            tolerance=0.01, area_threshold=10.0)
        self.assertEqual(stats["gaps_filled"], 1)
        areas = {fid: self.b.area(g) for fid, g in out}
        # Щель граничит с левым и правым по 10 м, с верхом и низом по 0.1 м.
        # Победитель определяется первым максимумом, площадь щели уходит одному соседу.
        total = sum(areas.values())
        self.assertAlmostEqual(total, 100 + 99 + 200 + 200 + 1.0, places=6)
        self.assertEqual(sum(1 for fid in (1, 2) if areas[fid] > 100.5), 1)

    def test_large_gap_is_left_alone(self):
        top = self.poly(rect(0, 10, 20, 20))
        bottom = self.poly(rect(0, 0, 20, 5))
        side_l = self.poly(rect(-5, 0, 0, 20))
        side_r = self.poly(rect(20, 0, 25, 20))
        out, stats, left = tc.fix_items(
            self.b, [(1, top), (2, bottom), (3, side_l), (4, side_r)],
            tolerance=0.5, area_threshold=10.0)
        self.assertEqual(stats["gaps_filled"], 0)
        self.assertEqual(stats["gaps_left"], 1)
        self.assertTrue(any(x["type"] == tc.GAP for x in left))

    def test_bowtie_is_made_valid(self):
        bowtie = self.poly([(0, 0), (10, 10), (10, 0), (0, 10), (0, 0)])
        self.assertFalse(self.b.is_valid(bowtie))
        out, stats, _left = tc.fix_items(self.b, [(1, bowtie)],
                                         tolerance=0.5, area_threshold=1.0)
        self.assertEqual(stats["made_valid"], 1)
        self.assertTrue(self.b.is_valid(out[0][1]))

    def test_spike_removed_area_kept(self):
        ring = [(0, 0), (10, 0), (10, 10), (5, 10), (5.0001, 40), (5, 10), (0, 10), (0, 0)]
        g = self.poly(ring)
        out, stats, _left = tc.fix_items(self.b, [(1, g)],
                                         tolerance=0.5, area_threshold=1.0)
        self.assertGreaterEqual(stats["spikes"], 1)
        self.assertAlmostEqual(self.b.area(out[0][1]), 100.0, places=3)

    def test_tiny_hole_filled_large_hole_kept(self):
        g = self.poly(rect(0, 0, 100, 100), rect(10, 10, 11, 11), rect(50, 50, 80, 80))
        out, stats, _left = tc.fix_items(self.b, [(1, g)],
                                         tolerance=0.5, area_threshold=10.0)
        self.assertEqual(stats["tiny_holes"], 1)
        rings = self.b.rings(self.b.parts(out[0][1])[0])
        self.assertEqual(len(rings), 2, "Крупная дыра должна остаться")

    def test_unsnapped_becomes_shared_node(self):
        a = rect(0, 0, 10, 10)
        b = [(10.3, 0), (20, 0), (20, 10), (10.3, 10), (10.3, 5), (10.3, 0)]
        out, stats, _left = tc.fix_items(self.b, [(1, self.poly(a)), (2, self.poly(b))],
                                         tolerance=2.0, area_threshold=1.0)
        f, _s = tc.check_items(self.b, [(i, g) for i, g in out if g],
                               tolerance=2.0, area_threshold=1.0)
        self.assertEqual(len(self.kinds(f, tc.UNSNAPPED)), 0)
        self.assertEqual(len(self.kinds(f, tc.GAP)), 0)
        self.assertEqual(len(self.kinds(f, tc.OVERLAP)), 0)

    def test_idempotent(self):
        a = rect(0, 0, 10, 10)
        b = [(10.3, 0), (20, 0), (20, 10), (10.3, 10), (10.3, 5), (10.3, 0)]
        c = self.poly(rect(0, 10.1, 20, 20))
        first, s1, _l1 = tc.fix_items(
            self.b, [(1, self.poly(a)), (2, self.poly(b)), (3, c)],
            tolerance=2.0, area_threshold=10.0)
        second, s2, _l2 = tc.fix_items(
            self.b, [(fid, g) for fid, g in first if g is not None],
            tolerance=2.0, area_threshold=10.0)
        for key in ("overlaps_fixed", "gaps_filled", "spikes", "dup_vertices",
                    "made_valid", "tiny_holes", "tiny_parts"):
            self.assertEqual(s2[key], 0, "Повторный прогон правил %s" % key)
        self.assertAlmostEqual(s2["area_before"], s2["area_after"], places=6)

    def test_no_feature_is_lost_on_normal_data(self):
        items = [
            (1, self.poly(rect(0, 0, 10, 10))),
            (2, self.poly(rect(10.2, 0, 20, 10))),
            (3, self.poly(rect(0, 10.2, 20, 20))),
        ]
        out, stats, _left = tc.fix_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertEqual(stats["features_lost"], 0)
        self.assertTrue(all(g is not None for _fid, g in out))

    def test_tiny_feature_not_dropped_by_default(self):
        items = [(1, self.poly(rect(0, 0, 100, 100))), (2, self.poly(rect(200, 200, 200.5, 200.5)))]
        out, stats, left = tc.fix_items(self.b, items, tolerance=0.1, area_threshold=10.0)
        self.assertEqual(stats["tiny_features_dropped"], 0)
        self.assertIsNotNone(out[1][1])
        self.assertTrue(any(x["type"] == tc.TINY_FEATURE for x in left))

    def test_tiny_feature_dropped_on_request(self):
        items = [(1, self.poly(rect(0, 0, 100, 100))), (2, self.poly(rect(200, 200, 200.5, 200.5)))]
        out, stats, _left = tc.fix_items(self.b, items, tolerance=0.1, area_threshold=10.0,
                                         options={"drop_tiny_features": True})
        self.assertEqual(stats["tiny_features_dropped"], 1)
        self.assertIsNone(out[1][1])

    def test_area_is_broadly_preserved(self):
        items = [
            (1, self.poly(rect(0, 0, 10, 10))),
            (2, self.poly(rect(10.2, 0, 20, 10))),
            (3, self.poly(rect(0, 10.2, 20, 20))),
        ]
        out, stats, _left = tc.fix_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        rel = abs(stats["area_after"] - stats["area_before"]) / stats["area_before"]
        self.assertLess(rel, 0.02, "Площадь изменилась на %.3f %%" % (100 * rel))


class TestFixEndToEnd(Base):

    def test_messy_coverage_becomes_clean(self):
        """Сводный случай: зазоры, лишние вершины, микродыра, мелкое перекрытие."""
        items = [
            (1, self.poly(rect(0, 0, 10, 10), rect(4, 4, 4.5, 4.5))),
            (2, self.poly([(10.3, 0), (20, 0), (20, 10), (10.3, 10), (10.3, 6), (10.3, 0)])),
            (3, self.poly(rect(0, 9.8, 20.1, 20))),
        ]
        before, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        self.assertGreater(len(before), 0)

        out, stats, left = tc.fix_items(self.b, items, tolerance=2.0, area_threshold=10.0)
        clean = [(fid, g) for fid, g in out if g is not None]
        self.assertEqual(len(clean), 3)

        after, _s2 = tc.check_items(self.b, clean, tolerance=2.0, area_threshold=10.0)
        for kind in (tc.OVERLAP, tc.GAP, tc.UNSNAPPED, tc.TINY_HOLE, tc.INVALID):
            self.assertEqual(
                len(self.kinds(after, kind)), 0,
                "Осталось нарушение %s: %r" % (kind, self.kinds(after, kind)))


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestAssembly(Base):
    """Контроль сборки по атрибуту: главный критерий приёмки покрытия."""

    def test_clean_group_assembles_into_one_part(self):
        items = [
            (1, self.poly(rect(0, 0, 10, 10)), "B1"),
            (2, self.poly(rect(10, 0, 20, 10)), "B1"),
            (3, self.poly(rect(0, 10, 20, 20)), "B1"),
        ]
        f, per = tc.check_assembly(self.b, items, area_threshold=1.0)
        self.assertEqual(f, [])
        self.assertEqual(per["B1"]["parts"], 1)
        self.assertEqual(per["B1"]["holes"], 0)

    def test_open_gap_splits_the_group(self):
        """Зазор, невидимый для поиска щелей, разрезает группу при сборке."""
        items = [
            (1, self.poly(rect(0, 0, 20, 9.95)), "B1"),
            (2, self.poly(rect(0, 10, 20, 20)), "B1"),
        ]
        # Поиск щелей по покрытию такой зазор не находит.
        plain, _s = tc.check_items(
            self.b, [(fid, g) for fid, g, _k in items], tolerance=2.0, area_threshold=10.0)
        self.assertEqual(len(self.kinds(plain, tc.GAP)), 0)
        # А сборка группы находит.
        f, per = tc.check_assembly(self.b, items, area_threshold=1.0)
        splits = [x for x in f if x["type"] == tc.GROUP_SPLIT]
        self.assertEqual(len(splits), 1)
        self.assertEqual(per["B1"]["parts"], 2)
        self.assertIn("0.05", splits[0]["note"])

    def test_hole_inside_group_is_found(self):
        items = [
            (1, self.poly(rect(0, 0, 10, 20)), "B1"),
            (2, self.poly(rect(10, 0, 20, 9)), "B1"),
            (3, self.poly(rect(10, 11, 20, 20)), "B1"),
            (4, self.poly(rect(20, 0, 30, 20)), "B1"),
        ]
        f, per = tc.check_assembly(self.b, items, area_threshold=1.0)
        holes = [x for x in f if x["type"] == tc.GROUP_HOLE]
        self.assertEqual(len(holes), 1)
        self.assertAlmostEqual(holes[0]["value"], 20.0, places=6)
        self.assertEqual(per["B1"]["holes"], 1)

    def test_groups_are_independent(self):
        items = [
            (1, self.poly(rect(0, 0, 10, 10)), "B1"),
            (2, self.poly(rect(10, 0, 20, 10)), "B1"),
            (3, self.poly(rect(100, 0, 110, 10)), "B2"),
        ]
        f, per = tc.check_assembly(self.b, items, area_threshold=1.0)
        self.assertEqual(f, [])
        self.assertEqual(per["B1"]["parts"], 1)
        self.assertEqual(per["B2"]["parts"], 1)

    def test_fix_then_assembly_is_clean(self):
        """Полный цикл: грязное покрытие, очистка, сборка группы сходится."""
        raw = [
            (1, self.poly(rect(0, 0, 10.3, 10))),
            (2, self.poly([(10, 0), (20, 0), (20, 10), (10, 10), (10, 6), (10, 0)])),
            (3, self.poly(rect(0, 9.8, 20.1, 20))),
        ]
        out, _stats, _left = tc.fix_items(self.b, raw, tolerance=2.0, area_threshold=10.0)
        items = [(fid, g, "B1") for fid, g in out if g is not None]
        f, per = tc.check_assembly(self.b, items, area_threshold=1.0)
        self.assertEqual(per["B1"]["parts"], 1, "Группа должна собраться в одно тело")
        self.assertEqual(f, [])


class TestAssemblyDistantBodies(Base):
    """Одно значение атрибута может описывать несколько разнесённых тел."""

    def two_distant_bodies(self):
        return [
            (1, self.poly(rect(0, 0, 10, 10)), "-145"),
            (2, self.poly(rect(10, 0, 20, 10)), "-145"),
            (3, self.poly(rect(3000, 0, 3010, 10)), "-145"),
        ]

    def test_distant_body_is_a_finding_in_strict_mode(self):
        f, per = tc.check_assembly(self.b, self.two_distant_bodies(), area_threshold=1.0)
        self.assertEqual(len([x for x in f if x["type"] == tc.GROUP_SPLIT]), 1)
        self.assertEqual(per["-145"]["splits"], 1)

    def test_distant_body_is_not_a_finding_with_max_gap(self):
        f, per = tc.check_assembly(
            self.b, self.two_distant_bodies(), area_threshold=1.0, max_gap=100.0)
        self.assertEqual([x for x in f if x["type"] == tc.GROUP_SPLIT], [])
        self.assertEqual(per["-145"]["separate"], 1)
        self.assertEqual(per["-145"]["splits"], 0)

    def test_real_defect_still_found_with_max_gap(self):
        """Микроразрыв внутри тела остаётся находкой, дальнее тело нет."""
        items = [
            (1, self.poly(rect(0, 0, 10, 9.95)), "-145"),
            (2, self.poly(rect(0, 10, 10, 20)), "-145"),
            (3, self.poly(rect(3000, 0, 3010, 10)), "-145"),
        ]
        f, per = tc.check_assembly(self.b, items, area_threshold=1.0, max_gap=100.0)
        splits = [x for x in f if x["type"] == tc.GROUP_SPLIT]
        self.assertEqual(len(splits), 1)
        self.assertIn("0.05", splits[0]["note"])
        self.assertEqual(per["-145"]["separate"], 1)

    def test_holes_can_be_ignored(self):
        items = [
            (1, self.poly(rect(0, 0, 10, 20)), "A"),
            (2, self.poly(rect(10, 0, 20, 9)), "A"),
            (3, self.poly(rect(10, 11, 20, 20)), "A"),
            (4, self.poly(rect(20, 0, 30, 20)), "A"),
        ]
        f, _per = tc.check_assembly(self.b, items, area_threshold=1.0, ignore_holes=True)
        self.assertEqual([x for x in f if x["type"] == tc.GROUP_HOLE], [])


class TestSnapCanBreakGeometry(Base):
    """Слияние вершин схлопывает объект, который уже допуска."""

    def strip(self, width, n=20, length=40.0):
        """Узкая полоса: противоположные берега ближе допуска друг к другу."""
        top = [(i * length / n, width) for i in range(n + 1)]
        bot = [(i * length / n, 0.0) for i in range(n, -1, -1)]
        return top + bot + [top[0]]

    def test_narrow_strip_is_broken_by_snapping(self):
        from topo_core import clean_topology
        ring = self.strip(0.4)
        self.assertTrue(self.b.is_valid(self.poly(ring)), "Исходная полоса корректна")
        res = clean_topology([ring], tolerance=1.0)
        out = res["rings"][0]
        self.assertIsNotNone(out)
        broken = self.b.polygon([[(p[0], p[1]) for p in out]])
        self.assertGreater(res["stats"]["vertices_moved"], 0)
        self.assertFalse(self.b.is_valid(broken),
                         "Полоса уже допуска должна схлопнуться сама в себя")

    def test_wide_strip_survives(self):
        from topo_core import clean_topology
        ring = self.strip(3.0)
        res = clean_topology([ring], tolerance=1.0)
        out = res["rings"][0]
        self.assertEqual(res["stats"]["vertices_moved"], 0)
        self.assertTrue(self.b.is_valid(self.b.polygon([[(p[0], p[1]) for p in out]])))

    def test_ring_width_predicts_the_damage(self):
        """Эффективная ширина отличает опасный объект от безопасного."""
        from topo_core import ring_width
        narrow = ring_width([(p[0], p[1]) for p in self.strip(0.4)])
        wide = ring_width([(p[0], p[1]) for p in self.strip(3.0)])
        self.assertLess(narrow, 1.0)
        self.assertGreater(wide, 1.0)

    def test_pipeline_keeps_result_valid(self):
        """Конвейер очистки не выдаёт некорректную геометрию."""
        out, _stats, _left = tc.fix_items(
            self.b, [(1, self.poly(self.strip(0.4)))], tolerance=1.0, area_threshold=0.1)
        geom = out[0][1]
        if geom is not None:
            self.assertTrue(self.b.is_valid(geom))


class TestSegmentStats(Base):

    def test_stats_point_at_safe_tolerance(self):
        from topo_core import segment_length_stats
        ring = [(0, 0), (0.2, 0), (0.4, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        median, p05, n = segment_length_stats([ring])
        self.assertEqual(n, 6)
        self.assertAlmostEqual(p05, 0.2, places=9)
        self.assertGreater(median, p05)


class TestProtectNarrow(Base):
    """Объект уже допуска не должен теряться при очистке."""

    def strip(self, y0, width, n=10, length=20.0):
        top = [(i * length / n, y0 + width) for i in range(n + 1)]
        bot = [(i * length / n, y0) for i in range(n, -1, -1)]
        return top + bot + [top[0]]

    def test_narrow_feature_survives_cleanup(self):
        items = [
            (1, self.poly(self.strip(0.0, 0.3))),
            (2, self.poly(self.strip(0.5, 6.0))),
        ]
        out, stats, _left = tc.fix_items(self.b, items, tolerance=1.0, area_threshold=0.1)
        self.assertEqual(stats["features_lost"], 0)
        self.assertIsNotNone(out[0][1], "Узкий объект не должен исчезнуть")
        self.assertGreaterEqual(stats["rings_frozen"], 1)
        self.assertAlmostEqual(self.b.area(out[0][1]), 20 * 0.3, places=6)

    def test_without_protection_object_is_saved_only_by_rollback(self):
        """Без защиты объект спасает лишь откат, и он попадает в список проблем.

        Геометрия при этом возвращается к исходной, то есть границы такого
        объекта остаются несогласованными с соседями. Защита решает ту же
        задачу заранее и без потери согласования.
        """
        items = [
            (1, self.poly(self.strip(0.0, 0.3))),
            (2, self.poly(self.strip(0.5, 6.0))),
        ]
        out, stats, left = tc.fix_items(
            self.b, items, tolerance=1.0, area_threshold=0.1,
            options={"protect_narrow": False})
        self.assertEqual(stats["rings_frozen"], 0)
        self.assertGreater(stats["valid_rejected"], 0)
        self.assertTrue(any(x["type"] == tc.INVALID for x in left))

    def test_protection_avoids_the_rollback(self):
        items = [
            (1, self.poly(self.strip(0.0, 0.3))),
            (2, self.poly(self.strip(0.5, 6.0))),
        ]
        _out, stats, left = tc.fix_items(self.b, items, tolerance=1.0, area_threshold=0.1)
        self.assertEqual(stats["valid_rejected"], 0)
        self.assertEqual([x for x in left if x["type"] == tc.INVALID], [])

    def test_result_stays_valid_with_protection(self):
        items = [
            (1, self.poly(self.strip(0.0, 0.3))),
            (2, self.poly(self.strip(0.5, 6.0))),
        ]
        out, _stats, _left = tc.fix_items(self.b, items, tolerance=1.0, area_threshold=0.1)
        for _fid, g in out:
            if g is not None:
                self.assertTrue(self.b.is_valid(g))


class TestInsertOnlyContract(Base):
    """Контракт инструмента 1.05: только вставка, площадь неприкосновенна."""

    def rings_of(self, geom):
        return [r for part in tc.to_parts(self.b, geom) for r in part]

    def seam_pair(self):
        """Два полигона по общей прямой, вершинность на шве разная."""
        left = [(0, 0), (10, 0), (10, 3), (10, 7), (10, 10), (0, 10), (0, 0)]
        right = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)]
        return left, right

    def test_area_is_exactly_preserved(self):
        from topo_core import clean_topology
        left, right = self.seam_pair()
        before = self.b.area(self.poly(left)) + self.b.area(self.poly(right))
        res = clean_topology([left, right], tolerance=1e-6, mode=tc.MODE_INSERT)
        after = sum(
            self.b.area(self.b.polygon([[(p[0], p[1]) for p in r]]))
            for r in res["rings"])
        self.assertEqual(before, after, "Площадь обязана совпасть точно")
        self.assertGreater(res["stats"]["nodes_inserted"], 0)

    def test_every_original_vertex_survives(self):
        from topo_core import clean_topology
        left, right = self.seam_pair()
        res = clean_topology([left, right], tolerance=1e-6, mode=tc.MODE_INSERT)
        for src, out in zip((left, right), res["rings"]):
            got = {(round(p[0], 9), round(p[1], 9)) for p in out}
            for p in src:
                self.assertIn((round(p[0], 9), round(p[1], 9)), got)

    def test_vertex_count_only_grows(self):
        from topo_core import clean_topology
        left, right = self.seam_pair()
        res = clean_topology([left, right], tolerance=1e-6, mode=tc.MODE_INSERT)
        for src, out in zip((left, right), res["rings"]):
            self.assertGreaterEqual(len(out), len(src))

    def test_missing_nodes_are_actually_added(self):
        from topo_core import clean_topology
        left, right = self.seam_pair()
        res = clean_topology([left, right], tolerance=1e-6, mode=tc.MODE_INSERT)
        left_out = {(round(p[0], 9), round(p[1], 9)) for p in res["rings"][0]}
        right_out = {(round(p[0], 9), round(p[1], 9)) for p in res["rings"][1]}
        self.assertIn((10.0, 5.0), left_out)
        for pt in ((10.0, 3.0), (10.0, 7.0)):
            self.assertIn(pt, right_out)

    def test_audit_is_clean_afterwards(self):
        """После вставки проверка не должна находить вершин на рёбрах."""
        from topo_core import clean_topology
        left, right = self.seam_pair()
        res = clean_topology([left, right], tolerance=1e-6, mode=tc.MODE_INSERT)
        items = [
            (i + 1, self.b.polygon([[(p[0], p[1]) for p in r]]))
            for i, r in enumerate(res["rings"])]
        f, _s = tc.check_items(self.b, items, tolerance=1e-6, area_threshold=1e-6,
                               do_gaps=False, do_overlaps=False)
        self.assertEqual(self.kinds(f, tc.ON_EDGE), [])

    def test_reference_layer_supplies_nodes_and_stays_out(self):
        """Вершины опорного слоя достраивают входной, сам опорный не выводится."""
        from topo_core import clean_topology
        target = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        donor = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 4), (10, 0)]
        res = clean_topology([target], tolerance=1e-6, mode=tc.MODE_INSERT,
                             fixed_rings=[donor])
        self.assertEqual(len(res["rings"]), 1)
        out = {(round(p[0], 9), round(p[1], 9)) for p in res["rings"][0]}
        self.assertIn((10.0, 4.0), out)

    def test_far_vertex_is_not_inserted_with_tiny_epsilon(self):
        """Вершина в стороне от ребра узла не даёт: эпсилон это защита."""
        from topo_core import clean_topology
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        b = [(10.5, 0), (20, 0), (20, 10), (10.5, 10), (10.5, 5), (10.5, 0)]
        res = clean_topology([a, b], tolerance=1e-6, mode=tc.MODE_INSERT)
        self.assertEqual(res["stats"]["nodes_inserted"], 0)
        self.assertEqual(res["stats"]["vertices_moved"], 0)

    def test_nothing_moves_in_insert_mode(self):
        from topo_core import clean_topology
        left, right = self.seam_pair()
        res = clean_topology([left, right], tolerance=1e-6, mode=tc.MODE_INSERT)
        self.assertEqual(res["stats"]["vertices_moved"], 0)
        self.assertEqual(res["stats"]["max_move"], 0.0)
        self.assertEqual(res["stats"]["rings_degenerate"], 0)


class TestProjectionOntoEdge(Base):
    """Узел в проекции на ребро не меняет форму и не рождает самопересечений."""

    def pinch(self, gap=3e-7):
        """Кольцо с перешейком: две части границы почти касаются."""
        return [(0, 0), (10, 0), (10, 4), (1, 4), (1, 4 + gap),
                (10, 4 + gap), (10, 10), (0, 10), (0, 0)]

    def neighbour(self, gap=3e-7):
        """Сосед, чья вершина лежит на ребре перешейка с малым отклонением."""
        return [(10, 0), (20, 0), (20, 10), (10, 10), (10, 4 + gap),
                (5, 4 + 8e-7), (10, 4), (10, 0)]

    def insert(self, project):
        from topo_core import clean_topology
        return clean_topology(
            [self.pinch(), self.neighbour()], tolerance=1e-6,
            mode=tc.MODE_INSERT, project_onto_edge=project)

    def ring_geom(self, ring):
        return self.b.polygon([[(p[0], p[1]) for p in ring]])

    def test_without_projection_ring_self_intersects(self):
        """Так выглядела ошибка: вершина соседа смещала ребро вбок."""
        res = self.insert(project=False)
        self.assertFalse(self.b.is_valid(self.ring_geom(res["rings"][0])))

    def test_projection_keeps_geometry_valid(self):
        res = self.insert(project=True)
        self.assertTrue(self.b.is_valid(self.ring_geom(res["rings"][0])))
        self.assertGreater(res["stats"]["nodes_inserted"], 0)

    def test_projection_preserves_area_exactly(self):
        before = self.b.area(self.ring_geom(self.pinch()))
        res = self.insert(project=True)
        after = self.b.area(self.ring_geom(res["rings"][0]))
        self.assertEqual(before, after, "Проекция обязана сохранить площадь")

    def test_without_projection_area_drifts(self):
        before = self.b.area(self.ring_geom(self.pinch()))
        res = self.insert(project=False)
        after = self.b.area(self.ring_geom(res["rings"][0]))
        self.assertNotEqual(before, after)


class TestSelfTouchingRing(Base):
    """Кольцо, касающееся само себя, не должно ломаться при вставке узлов.

    Случай из данных: одна и та же точка является и вершиной кольца,
    и точкой на другом его ребре, к которому она не примыкает. Вставка узла
    в такое ребро превращала касание в шпильку, а точку пересечения клали
    по параметру чужого ребра, отчего касание становилось пересечением.
    """

    def touching_ring(self):
        """Контур в форме восьмёрки, касающийся себя в одной точке."""
        return [(0, 0), (10, 0), (10, 5), (5, 5), (10, 5.0), (10, 10),
                (0, 10), (0, 5), (5, 5), (0, 5.0), (0, 0)]

    def test_vertex_already_present_gets_no_node(self):
        from topo_core import clean_topology
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        # Вершина соседа совпадает с уже существующей вершиной кольца A
        nb = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 0)]
        res = clean_topology([a, nb], tolerance=1e-6, mode=tc.MODE_INSERT,
                             project_onto_edge=True)
        self.assertEqual(res["stats"]["nodes_inserted"], 0)

    def test_node_is_not_duplicated_into_own_vertex(self):
        """Точка, уже являющаяся вершиной кольца, узлом не становится."""
        from topo_core import clean_topology
        # Кольцо проходит через точку (5, 5) дважды: как вершина и по ребру
        ring = [(0, 0), (10, 0), (10, 10), (5, 10), (5, 5), (0, 5), (0, 0)]
        donor = [(5, 5), (6, 4), (7, 5), (5, 5)]
        res = clean_topology([ring], tolerance=1e-6, mode=tc.MODE_INSERT,
                             fixed_rings=[donor], project_onto_edge=True)
        out = res["rings"][0]
        seen = [p for p in out if abs(p[0] - 5) < 1e-9 and abs(p[1] - 5) < 1e-9]
        self.assertEqual(len(seen), 1, "Вершина (5,5) не должна удваиваться")

    def test_crossing_node_lands_on_its_own_edge(self):
        """Узел пересечения кладётся на то ребро, в которое вставляется."""
        from topo_core import clean_topology
        a = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        c = [(5, -5), (15, -5), (15, 15), (5, 15), (5, -5)]
        res = clean_topology([a, c], tolerance=1e-6, mode=tc.MODE_INSERT,
                             project_onto_edge=True)
        for ring in res["rings"]:
            g = self.b.polygon([[(p[0], p[1]) for p in ring]])
            self.assertTrue(self.b.is_valid(g))
        self.assertEqual(res["stats"]["nodes_crossing"], 4)


class TestInsertUntilStable(Base):
    """Одного прохода мало: вставленный узел ложится на ребро третьего объекта."""

    def three_in_a_row(self):
        """Три полосы: у каждой своя вершинность на общих границах."""
        a = [(0, 0), (10, 0), (10, 4), (10, 10), (0, 10), (0, 0)]
        b = [(10, 0), (20, 0), (20, 10), (10, 10), (10, 6), (10, 0)]
        c = [(0, 10), (10, 10), (20, 10), (20, 20), (0, 20), (0, 10)]
        return [a, b, c]

    def insert_pass(self, rings):
        from topo_core import clean_topology
        return clean_topology(rings, tolerance=1e-6, mode=tc.MODE_INSERT,
                              project_onto_edge=True)

    def test_repeat_until_no_nodes_are_found(self):
        rings = self.three_in_a_row()
        total = 0
        passes = 0
        for _ in range(8):
            res = self.insert_pass(rings)
            added = res["stats"]["nodes_inserted"]
            total += added
            passes += 1
            rings = [r for r in res["rings"] if r]
            if added == 0:
                break
        self.assertGreater(total, 0)
        self.assertEqual(self.insert_pass(rings)["stats"]["nodes_inserted"], 0,
                         "После стабилизации узлов быть не должно")

    def test_stable_result_has_no_findings(self):
        rings = self.three_in_a_row()
        for _ in range(8):
            res = self.insert_pass(rings)
            rings = [r for r in res["rings"] if r]
            if res["stats"]["nodes_inserted"] == 0:
                break
        items = [(i + 1, self.b.polygon([[(p[0], p[1]) for p in r]]))
                 for i, r in enumerate(rings)]
        f, _s = tc.check_items(self.b, items, tolerance=1e-6, area_threshold=1e-6)
        self.assertEqual(self.kinds(f, tc.ON_EDGE), [])

    def test_area_survives_all_passes(self):
        rings = self.three_in_a_row()
        before = sum(self.b.area(self.b.polygon([list(r)])) for r in rings)
        for _ in range(8):
            res = self.insert_pass(rings)
            rings = [r for r in res["rings"] if r]
            if res["stats"]["nodes_inserted"] == 0:
                break
        after = sum(self.b.area(self.b.polygon([[(p[0], p[1]) for p in r]])) for r in rings)
        self.assertAlmostEqual(before, after, places=9)


class TestOverlapWidth(Base):
    """Мусорность перекрытия определяется шириной, а не площадью."""

    def strip_overlap(self, width, length=64.0):
        a = self.poly(rect(0, 0, length, 10))
        b = self.poly(rect(0, 10 - width, length, 30))
        return a, b

    def test_long_thin_overlap_is_debris(self):
        """Полоса шириной с допуск набирает сотню единиц площади, но это мусор."""
        a, c = self.strip_overlap(width=2.0)
        inter = self.b.intersection(a, c)
        self.assertGreater(self.b.area(inter), 100.0)
        self.assertTrue(tc.overlap_is_debris(self.b, inter, area_threshold=1.0,
                                             tolerance=2.5))

    def test_wide_overlap_is_a_dispute(self):
        a, c = self.strip_overlap(width=8.0)
        inter = self.b.intersection(a, c)
        self.assertFalse(tc.overlap_is_debris(self.b, inter, area_threshold=1.0,
                                              tolerance=2.0))

    def test_fix_removes_long_thin_overlap(self):
        a, c = self.strip_overlap(width=2.0)
        out, stats, left = tc.fix_items(
            self.b, [(1, a), (2, c)], tolerance=2.5, area_threshold=1.0,
            options={"snap": False})
        self.assertEqual(stats["overlaps_fixed"], 1)
        self.assertEqual(stats["overlaps_left"], 0)

    def test_fix_keeps_wide_overlap_for_human(self):
        a, c = self.strip_overlap(width=8.0)
        out, stats, left = tc.fix_items(
            self.b, [(1, a), (2, c)], tolerance=2.0, area_threshold=1.0,
            options={"snap": False})
        self.assertEqual(stats["overlaps_fixed"], 0)
        self.assertEqual(stats["overlaps_left"], 1)


class TestLeftoversAreRechecked(Base):
    """В остатки не должно попадать то, чего в результате уже нет."""

    def test_disappeared_overlap_is_not_reported(self):
        a = self.poly(rect(0, 0, 64, 10))
        c = self.poly(rect(0, 8, 64, 30))
        out, stats, left = tc.fix_items(
            self.b, [(1, a), (2, c)], tolerance=2.5, area_threshold=1.0,
            options={"snap": False})
        geoms = {fid: g for fid, g in out if g is not None}
        for item in left:
            if item["type"] == tc.OVERLAP:
                ga, gb = geoms[item["fid"]], geoms[item["fid_b"]]
                self.assertTrue(
                    self.b.intersects(ga, gb)
                    and self.b.area(self.b.intersection(ga, gb)) > 0,
                    "Сообщено о перекрытии, которого в результате нет")

    def test_counter_matches_reported_items(self):
        a = self.poly(rect(0, 0, 64, 10))
        c = self.poly(rect(0, 8, 64, 30))
        _out, stats, left = tc.fix_items(
            self.b, [(1, a), (2, c)], tolerance=2.5, area_threshold=1.0,
            options={"snap": False})
        self.assertEqual(stats["overlaps_left"],
                         sum(1 for x in left if x["type"] == tc.OVERLAP))


class TestGrouping(Base):
    """Слой из нескольких покрытий проверяется по группам."""

    def two_layers(self):
        """Две зоны на двух пластах: геометрия совпадает по замыслу."""
        a = self.poly(rect(0, 0, 10, 10))
        c = self.poly(rect(10, 0, 20, 10))
        return [(1, a, "АБ"), (2, c, "АБ"), (3, a, "Кр.II"), (4, c, "Кр.II")]

    def test_without_grouping_layers_look_like_duplicates(self):
        items = [(fid, g) for fid, g, _k in self.two_layers()]
        f, _s = tc.check_items(self.b, items, tolerance=2.0, area_threshold=1.0)
        self.assertGreaterEqual(len(self.kinds(f, tc.DUPLICATE)), 2)

    def test_grouping_removes_false_findings(self):
        rows = self.two_layers()
        keys = {fid: k for fid, _g, k in rows}
        items = [(fid, g) for fid, g, _k in rows]
        f, _s = tc.check_grouped(self.b, items, lambda fid: keys[fid],
                                 tolerance=2.0, area_threshold=1.0)
        self.assertEqual(f, [], "Внутри пласта нарушений нет: %r" % f)

    def test_group_key_is_recorded(self):
        rows = [(1, self.poly(rect(0, 0, 10, 10)), "АБ"),
                (2, self.poly(rect(9.5, 0, 20, 10)), "АБ")]
        keys = {fid: k for fid, _g, k in rows}
        items = [(fid, g) for fid, g, _k in rows]
        f, _s = tc.check_grouped(self.b, items, lambda fid: keys[fid],
                                 tolerance=0.05, area_threshold=1.0)
        self.assertTrue(f)
        self.assertTrue(all(x["key"] == "АБ" for x in f))

    def test_fix_does_not_snap_across_groups(self):
        """Объекты разных групп не притягиваются друг к другу."""
        rows = [(1, self.poly(rect(0, 0, 10, 10)), "АБ"),
                (2, self.poly(rect(10.5, 0, 20, 10)), "Кр.II")]
        keys = {fid: k for fid, _g, k in rows}
        items = [(fid, g) for fid, g, _k in rows]
        out, stats, _left = tc.fix_grouped(self.b, items, lambda fid: keys[fid],
                                           tolerance=2.0, area_threshold=1.0)
        self.assertEqual(stats["vertices_moved"], 0)
        self.assertEqual(len(out), 2)


class TestAssemblyBodiesColumn(Base):
    """Колонка тел должна показывать реальное число частей."""

    def split_group(self):
        return [
            (1, self.poly(rect(0, 0, 10, 10)), "B"),
            (2, self.poly(rect(500, 0, 510, 10)), "B"),
        ]

    def test_strict_mode_counts_parts(self):
        _f, per = tc.check_assembly(self.b, self.split_group(), area_threshold=1.0)
        self.assertEqual(per["B"]["bodies"], 2)
        self.assertEqual(per["B"]["splits"], 1)

    def test_with_gap_threshold_counts_bodies(self):
        _f, per = tc.check_assembly(self.b, self.split_group(),
                                    area_threshold=1.0, max_gap=10.0)
        self.assertEqual(per["B"]["bodies"], 2)
        self.assertEqual(per["B"]["splits"], 0)
        self.assertEqual(per["B"]["separate"], 1)


class TestCavity(Base):
    """Крупная полость это часть замысла, а не дефект покрытия."""

    def ring_with_hole(self, hole):
        outer = [(0, 0), (100, 0), (100, 100), (0, 100)]
        return [
            (1, self.b.polygon([outer + [outer[0]], hole + [hole[0]]])),
        ]

    def test_large_cavity_is_not_reported(self):
        hole = [(20, 20), (80, 20), (80, 80), (20, 80)]
        items = self.ring_with_hole(hole)
        f, _s = tc.check_items(self.b, items, tolerance=1.0, area_threshold=1.0,
                               cavity_area=1000.0)
        self.assertEqual(self.kinds(f, tc.GAP), [])
        self.assertEqual(self.kinds(f, tc.TINY_HOLE), [])

    def test_without_threshold_it_is_reported(self):
        hole = [(20, 20), (80, 20), (80, 80), (20, 80)]
        items = self.ring_with_hole(hole)
        f, _s = tc.check_items(self.b, items, tolerance=1.0, area_threshold=1.0)
        self.assertGreaterEqual(len(self.kinds(f, tc.GAP)), 1)

    def test_small_gap_still_reported_with_threshold(self):
        a = self.poly(rect(0, 0, 10, 10))
        c = self.poly(rect(10.1, 0, 20, 10))
        top = self.poly(rect(0, 10, 20, 20))
        bottom = self.poly(rect(0, -10, 20, 0))
        f, _s = tc.check_items(self.b, [(1, a), (2, c), (3, top), (4, bottom)],
                               tolerance=2.0, area_threshold=10.0,
                               cavity_area=1000.0)
        self.assertEqual(len(self.kinds(f, tc.GAP)), 1)


class TestAssemblyForLines(Base):
    """Контроль сборки для линий: вопрос в связности цепи."""

    def line(self, *pts):
        return self.b.linestring(list(pts))

    def test_adjacent_segments_form_one_chain(self):
        items = [(1, self.line((0, 0), (50, 0)), "ЮП"),
                 (2, self.line((50, 0), (100, 0)), "ЮП")]
        f, per = tc.check_assembly(self.b, items, is_line=True)
        self.assertEqual(per["ЮП"]["bodies"], 1,
                         "Смежные участки должны склеиться в одну цепь")
        self.assertEqual(f, [])

    def test_detached_segment_is_a_split(self):
        items = [(1, self.line((0, 0), (50, 0)), "ЮП"),
                 (2, self.line((50, 0), (100, 0)), "ЮП"),
                 (3, self.line((500, 0), (550, 0)), "ЮП")]
        f, per = tc.check_assembly(self.b, items, is_line=True)
        self.assertEqual(per["ЮП"]["bodies"], 2)
        self.assertEqual(len(self.kinds(f, tc.GROUP_SPLIT)), 1)

    def test_gap_threshold_accepts_separate_chains(self):
        """Порог разрыва меньше расстояния: цепи считаются разными телами.

        Смысл порога обратный тому, что подсказывает название: он говорит,
        насколько далеко части ещё считаются одним телом. Расстояние больше
        порога означает разные тела, а не разрыв внутри одного.
        """
        items = [(1, self.line((0, 0), (50, 0)), "ЮП"),
                 (2, self.line((500, 0), (550, 0)), "ЮП")]
        f, per = tc.check_assembly(self.b, items, is_line=True, max_gap=10.0)
        self.assertEqual(self.kinds(f, tc.GROUP_SPLIT), [])
        self.assertEqual(per["ЮП"]["separate"], 1)
        self.assertEqual(per["ЮП"]["bodies"], 2)

    def test_gap_threshold_larger_than_distance_reports_a_split(self):
        """Порог больше расстояния: части считаются одним телом с разрывом."""
        items = [(1, self.line((0, 0), (50, 0)), "ЮП"),
                 (2, self.line((500, 0), (550, 0)), "ЮП")]
        f, per = tc.check_assembly(self.b, items, is_line=True, max_gap=1000.0)
        self.assertEqual(per["ЮП"]["bodies"], 1)
        self.assertEqual(len(self.kinds(f, tc.GROUP_SPLIT)), 1)

    def test_measure_is_length_for_lines(self):
        items = [(1, self.line((0, 0), (50, 0)), "ЮП"),
                 (2, self.line((50, 0), (100, 0)), "ЮП")]
        _f, per = tc.check_assembly(self.b, items, is_line=True)
        self.assertAlmostEqual(per["ЮП"]["area"], 100.0, places=6)

    def test_lines_have_no_interior_rings(self):
        """Замкнутая цепь линий полостью не считается."""
        ring = [self.line((0, 0), (10, 0)), self.line((10, 0), (10, 10)),
                self.line((10, 10), (0, 10)), self.line((0, 10), (0, 0))]
        items = [(i + 1, g, "K") for i, g in enumerate(ring)]
        _f, per = tc.check_assembly(self.b, items, is_line=True)
        self.assertEqual(per["K"]["holes"], 0)

    def test_groups_are_independent(self):
        items = [(1, self.line((0, 0), (50, 0)), "A"),
                 (2, self.line((500, 0), (550, 0)), "B")]
        f, per = tc.check_assembly(self.b, items, is_line=True)
        self.assertEqual(f, [])
        self.assertEqual(per["A"]["bodies"], 1)
        self.assertEqual(per["B"]["bodies"], 1)


class TestFindingsHaveNotes(Base):
    """У каждой находки должно быть пояснение.

    Пустое поле note заставляет человека гадать, что именно не так,
    и чем находка отличается от соседней того же типа.
    """

    def messy_scene(self):
        return [
            (1, self.poly(rect(0, 0, 10, 10), rect(4, 4, 4.5, 4.5))),
            (2, self.poly(rect(9.5, 0, 20, 10))),
            (3, self.poly(rect(0, 0, 10, 10))),
            (4, self.poly(rect(2, 2, 3, 3))),
            (5, self.poly(rect(0, 200, 200, 200.4))),
        ]

    def test_every_finding_has_a_note(self):
        f, _s = tc.check_items(self.b, self.messy_scene(),
                               tolerance=2.0, area_threshold=10.0)
        self.assertTrue(f, "Сцена должна давать находки")
        empty = sorted({x["type"] for x in f if not x["note"]})
        self.assertEqual(empty, [], "Находки без пояснения: %r" % empty)

    def test_notes_differ_between_wide_and_narrow_overlap(self):
        narrow = [(1, self.poly(rect(0, 0, 64, 10))),
                  (2, self.poly(rect(0, 9, 64, 30)))]
        wide = [(1, self.poly(rect(0, 0, 20, 10))),
                (2, self.poly(rect(0, 2, 20, 30)))]
        f1, _s1 = tc.check_items(self.b, narrow, tolerance=2.0, area_threshold=1.0)
        f2, _s2 = tc.check_items(self.b, wide, tolerance=2.0, area_threshold=1.0)
        note1 = self.kinds(f1, tc.OVERLAP)[0]["note"]
        note2 = self.kinds(f2, tc.OVERLAP)[0]["note"]
        self.assertNotEqual(note1, note2)
        self.assertTrue(note1 and note2)

    def test_assembly_findings_have_notes(self):
        items = [(1, self.poly(rect(0, 0, 10, 10)), "B"),
                 (2, self.poly(rect(500, 0, 510, 10)), "B")]
        f, _per = tc.check_assembly(self.b, items, area_threshold=1.0)
        self.assertTrue(f)
        for item in f:
            self.assertTrue(item["note"], "Находка сборки без пояснения: %r" % item)
