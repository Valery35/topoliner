# -*- coding: utf-8 -*-
"""
Тесты проверки и очистки линейных слоёв.

У линий свой набор нарушений, поэтому и тесты отдельные. Главное, что
проверяется: недовод, перелёт и висячий конец различаются между собой,
а не сваливаются в одну кучу.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from line_checks import (  # noqa: E402
    CROSSING,
    DANGLE,
    OVERSHOOT,
    PSEUDO_NODE,
    SHORT_LINE,
    UNDERSHOOT,
    ZERO_LENGTH,
    check_lines,
    fix_lines,
)
from topo_checks import DUPLICATE, DUP_VERTEX, SPIKE  # noqa: E402


class Base(unittest.TestCase):

    def kinds(self, findings, kind):
        return [f for f in findings if f["type"] == kind]

    def main_line(self):
        return [(0, 0), (100, 0)]


class TestEndpointClassification(Base):
    """Недовод, перелёт и висячий конец это три разных случая."""

    def test_undershoot_is_found(self):
        items = [(1, self.main_line()), (2, [(50, 20), (50, 0.5)])]
        f, _s = check_lines(items, tolerance=2.0)
        found = self.kinds(f, UNDERSHOOT)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0]["value"], 0.5, places=6)

    def test_overshoot_is_found(self):
        items = [(1, self.main_line()), (2, [(30, -20), (30, 1.5)])]
        f, _s = check_lines(items, tolerance=2.0)
        found = self.kinds(f, OVERSHOOT)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0]["value"], 1.5, places=6)
        self.assertEqual(self.kinds(f, UNDERSHOOT), [],
                         "Перелёт не должен попадать в недоводы")

    def test_dangle_stays_for_the_operator(self):
        """Висячий конец у гидросети это устье или тупик, решает человек."""
        items = [(1, self.main_line()), (2, [(70, 20), (70, 10)])]
        f, _s = check_lines(items, tolerance=2.0)
        dangles = self.kinds(f, DANGLE)
        self.assertGreaterEqual(len(dangles), 1)
        self.assertTrue(all(d["severity"] == "review" for d in dangles))

    def test_undershoot_and_overshoot_are_auto(self):
        items = [(1, self.main_line()),
                 (2, [(50, 20), (50, 0.5)]),
                 (3, [(30, -20), (30, 1.5)])]
        f, _s = check_lines(items, tolerance=2.0)
        for kind in (UNDERSHOOT, OVERSHOOT):
            for item in self.kinds(f, kind):
                self.assertEqual(item["severity"], "auto")

    def test_connected_ends_are_not_reported(self):
        items = [(1, [(0, 0), (50, 0)]), (2, [(50, 0), (100, 0)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(self.kinds(f, UNDERSHOOT), [])
        self.assertEqual(self.kinds(f, OVERSHOOT), [])

    def test_gap_beyond_tolerance_is_a_dangle(self):
        """Расхождение больше допуска это не недовод, а разрыв сети."""
        items = [(1, self.main_line()), (2, [(50, 20), (50, 8.0)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(self.kinds(f, UNDERSHOOT), [])
        self.assertGreaterEqual(len(self.kinds(f, DANGLE)), 1)


class TestOtherViolations(Base):

    def test_pseudo_node(self):
        items = [(1, [(0, 0), (50, 0)]), (2, [(50, 0), (100, 0)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(len(self.kinds(f, PSEUDO_NODE)), 1)

    def test_three_way_junction_is_not_a_pseudo_node(self):
        items = [(1, [(0, 0), (50, 0)]), (2, [(50, 0), (100, 0)]),
                 (3, [(50, 0), (50, 50)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(self.kinds(f, PSEUDO_NODE), [])

    def test_crossing_without_node(self):
        items = [(1, self.main_line()), (2, [(10, -10), (10, 10)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(len(self.kinds(f, CROSSING)), 1)

    def test_crossing_with_node_is_clean(self):
        items = [(1, [(0, 0), (10, 0), (100, 0)]),
                 (2, [(10, -10), (10, 0), (10, 10)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(self.kinds(f, CROSSING), [])

    def test_duplicate_line(self):
        items = [(1, self.main_line()), (2, list(reversed(self.main_line())))]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(len(self.kinds(f, DUPLICATE)), 1)

    def test_zero_length(self):
        items = [(1, [(5, 5), (5, 5)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertEqual(len(self.kinds(f, ZERO_LENGTH)), 1)

    def test_short_line(self):
        items = [(1, self.main_line()), (2, [(200, 0), (200.4, 0)])]
        f, _s = check_lines(items, tolerance=2.0, min_length=1.0)
        self.assertEqual(len(self.kinds(f, SHORT_LINE)), 1)

    def test_duplicate_vertices_and_spikes(self):
        items = [(1, [(0, 0), (10, 0), (10, 0), (20, 0)]),
                 (2, [(0, 50), (10, 50), (10.0001, 60), (10, 50), (20, 50)])]
        f, _s = check_lines(items, tolerance=2.0)
        self.assertGreaterEqual(len(self.kinds(f, DUP_VERTEX)), 1)
        self.assertGreaterEqual(len(self.kinds(f, SPIKE)), 1)

    def test_clean_network_gives_only_dangles(self):
        """У аккуратной сети остаются только концы, и это не дефект."""
        items = [(1, [(0, 0), (50, 0)]), (2, [(50, 0), (100, 0)]),
                 (3, [(50, 0), (50, 50)])]
        f, _s = check_lines(items, tolerance=2.0, do_pseudo=False)
        for item in f:
            self.assertEqual(item["type"], DANGLE, "Лишняя находка: %r" % item)


class TestFix(Base):

    def scene(self):
        return [(1, self.main_line()),
                (2, [(50, 20), (50, 0.5)]),     # недовод
                (3, [(30, -20), (30, 1.5)]),    # перелёт
                (4, [(70, 20), (70, 10)])]      # висячий конец

    def test_overshoot_is_trimmed_to_the_node(self):
        out, stats, _left = fix_lines(self.scene(), tolerance=2.0)
        self.assertEqual(stats["overshoots_trimmed"], 1)
        line = dict(out)[3]
        self.assertAlmostEqual(line[-1][1], 0.0, places=6)

    def test_undershoot_is_closed(self):
        out, stats, _left = fix_lines(self.scene(), tolerance=2.0)
        self.assertEqual(stats["undershoots_closed"], 1)
        line = dict(out)[2]
        self.assertAlmostEqual(line[-1][1], 0.0, places=6)
        self.assertLessEqual(stats["max_move"], 2.0 + 1e-9)

    def test_nodes_are_inserted_into_the_main_line(self):
        out, stats, _left = fix_lines(self.scene(), tolerance=2.0)
        main = dict(out)[1]
        xs = [round(p[0], 6) for p in main]
        self.assertIn(30.0, xs)
        self.assertIn(50.0, xs)

    def test_dangle_is_left_alone(self):
        out, _stats, _left = fix_lines(self.scene(), tolerance=2.0)
        self.assertEqual([(round(p[0], 6), round(p[1], 6)) for p in dict(out)[4]],
                         [(70.0, 20.0), (70.0, 10.0)])

    def test_only_dangles_remain_after_cleanup(self):
        out, _stats, _left = fix_lines(self.scene(), tolerance=2.0)
        clean = [(fid, c) for fid, c in out if c]
        f, _s = check_lines(clean, tolerance=2.0)
        for item in f:
            self.assertEqual(item["type"], DANGLE,
                             "После очистки осталось: %r" % item)

    def test_zero_length_is_dropped(self):
        items = [(1, self.main_line()), (2, [(5, 5), (5, 5)])]
        out, stats, _left = fix_lines(items, tolerance=2.0)
        self.assertEqual(stats["zero_dropped"], 1)
        self.assertIsNone(dict(out)[2])

    def test_short_line_is_kept_by_default(self):
        items = [(1, self.main_line()), (2, [(200, 0), (200.4, 0)])]
        out, stats, left = fix_lines(items, tolerance=2.0, min_length=1.0)
        self.assertEqual(stats["short_dropped"], 0)
        self.assertIsNotNone(dict(out)[2])
        self.assertTrue(any(x["type"] == SHORT_LINE for x in left))

    def test_short_line_dropped_on_request(self):
        items = [(1, self.main_line()), (2, [(200, 0), (200.4, 0)])]
        out, stats, _left = fix_lines(items, tolerance=2.0, min_length=1.0,
                                      options={"drop_short": True})
        self.assertEqual(stats["short_dropped"], 1)
        self.assertIsNone(dict(out)[2])

    def test_idempotent(self):
        first, stats1, _l1 = fix_lines(self.scene(), tolerance=2.0)
        second, stats2, _l2 = fix_lines(
            [(fid, c) for fid, c in first if c], tolerance=2.0)
        self.assertEqual(stats2["overshoots_trimmed"], 0)
        self.assertEqual(stats2["undershoots_closed"], 0)
        self.assertEqual(stats2["nodes_inserted"], 0)

    def test_clean_network_is_untouched(self):
        items = [(1, [(0, 0), (50, 0)]), (2, [(50, 0), (100, 0)]),
                 (3, [(50, 0), (50, 50)])]
        out, stats, _left = fix_lines(items, tolerance=2.0)
        for (fid, src), (_fid2, dst) in zip(items, out):
            self.assertEqual([(round(p[0], 9), round(p[1], 9)) for p in src],
                             [(round(p[0], 9), round(p[1], 9)) for p in dst])
        self.assertEqual(stats["vertices_moved"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestLineNotes(Base):
    """У каждой линейной находки должно быть пояснение."""

    def messy(self):
        return [(1, self.main_line()),
                (2, [(50, 20), (50, 0.5)]),
                (3, [(30, -20), (30, 1.5)]),
                (4, [(70, 20), (70, 10)]),
                (5, [(10, -10), (10, 10)]),
                (6, [(5, 5), (5, 5)]),
                (7, [(0, 80), (10, 80), (10, 80), (20, 80)]),
                (8, self.main_line())]

    def test_every_finding_has_a_note(self):
        f, _s = check_lines(self.messy(), tolerance=2.0, min_length=1.0,
                            do_pseudo=True)
        self.assertTrue(f)
        empty = sorted({x["type"] for x in f if not x["note"]})
        self.assertEqual(empty, [], "Находки без пояснения: %r" % empty)

    def test_notes_carry_the_measured_value(self):
        """В пояснении к недоводу и перелёту стоит измеренное расстояние."""
        f, _s = check_lines(self.messy(), tolerance=2.0)
        under = self.kinds(f, UNDERSHOOT)[0]
        over = self.kinds(f, OVERSHOOT)[0]
        self.assertIn("0.5000", under["note"])
        self.assertIn("1.5000", over["note"])
