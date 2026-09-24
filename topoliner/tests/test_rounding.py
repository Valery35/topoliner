# -*- coding: utf-8 -*-
"""
Тесты округления величин и псевдонимов полей.

Округление проверяется на величинах, ради которых оно и заведено: на хвосте
двоичного представления, на площади в микроны и на количестве, которое трогать
нельзя.

Псевдонимы проверяются на полноту. Каждое поле выходного слоя обязано иметь
подпись, иначе в таблице атрибутов останется латинское имя без объяснения.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN)

import field_aliases  # noqa: E402
import i18n  # noqa: E402
from rounding import DIGITS, fmt, nice  # noqa: E402


class TestNice(unittest.TestCase):

    def test_binary_tail_is_cut(self):
        self.assertEqual(nice(0.0300000000000011), 0.03)

    def test_small_value_keeps_significant_digits(self):
        """Площадь в микроны не должна превращаться в ноль."""
        self.assertEqual(nice(3.8234567890123e-06), 3.823e-06)
        self.assertNotEqual(nice(3.8234567890123e-06), 0.0)

    def test_large_value_loses_meaningless_digits(self):
        self.assertEqual(nice(1234.5678), 1235.0)

    def test_integer_is_untouched(self):
        """В поле value попадает количество, и его округлять нельзя."""
        self.assertEqual(nice(12345), 12345.0)
        self.assertEqual(nice(1234567), 1234567.0)

    def test_negative_value(self):
        self.assertEqual(nice(-0.0300000000000011), -0.03)

    def test_zero_and_none(self):
        self.assertEqual(nice(0.0), 0.0)
        self.assertIsNone(nice(None))

    def test_text_passes_through(self):
        self.assertEqual(nice("не число"), "не число")

    def test_significant_digits_are_kept(self):
        """Лишних цифр не добавляется, целая часть не теряется."""
        for value in (0.001234567, 12.345678, 8.123456789, 98765.4321):
            text = fmt(value).replace("-", "").replace(".", "").lstrip("0")
            whole = len("%d" % abs(int(value)))
            self.assertLessEqual(len(text), max(DIGITS, whole),
                                 "%r дало %r" % (value, fmt(value)))


class TestFmt(unittest.TestCase):

    def test_no_trailing_zeros(self):
        self.assertEqual(fmt(0.5), "0.5")
        self.assertEqual(fmt(2.0), "2")

    def test_small_value_is_readable(self):
        self.assertEqual(fmt(3.8234567890123e-06), "0.000003823")

    def test_no_exponent_form(self):
        """Показатель степени в подписи на карте читать неудобно."""
        self.assertNotIn("e", fmt(3.8e-09))

    def test_none_gives_empty_string(self):
        self.assertEqual(fmt(None), "")


class TestAliases(unittest.TestCase):

    def tearDown(self):
        i18n.set_language("ru")

    def fields_of(self, name):
        """Имена полей выходного слоя, взятые из кода алгоритмов."""
        pattern = re.compile(r'(?<![\w])%s\.append\(QgsField\("(\w+)"' % name)
        found = []
        for fname in os.listdir(PLUGIN):
            if not fname.endswith(".py"):
                continue
            with open(os.path.join(PLUGIN, fname), encoding="utf-8") as fh:
                found += pattern.findall(fh.read())
        return found

    def test_findings_alias_for_every_field(self):
        names = set(self.fields_of("fields"))
        aliases = set(field_aliases.findings())
        self.assertTrue(names)
        self.assertEqual(sorted(names - aliases - set(field_aliases.borders())
                                - {"dist", "ring"}), [])

    def test_coverage_aliases_cover_their_layers(self):
        nodes = set(self.fields_of("node_fields"))
        arcs = set(self.fields_of("arc_fields"))
        self.assertEqual(sorted(nodes - set(field_aliases.coverage_nodes())), [])
        self.assertEqual(sorted(arcs - set(field_aliases.coverage_arcs())), [])

    def test_no_empty_alias(self):
        for maker in (field_aliases.findings, field_aliases.edits,
                      field_aliases.inserted_nodes, field_aliases.coverage_nodes,
                      field_aliases.coverage_arcs, field_aliases.borders):
            for name, alias in maker().items():
                self.assertTrue(alias.strip(), "%s без подписи" % name)

    def test_aliases_follow_the_interface_language(self):
        i18n.set_language("ru")
        russian = field_aliases.coverage_arcs()
        i18n.set_language("en")
        english = field_aliases.coverage_arcs()
        self.assertNotEqual(russian, english)
        self.assertEqual(sorted(russian), sorted(english))

    def test_every_alias_has_a_translation(self):
        i18n.set_language("ru")
        for maker in (field_aliases.findings, field_aliases.edits,
                      field_aliases.inserted_nodes, field_aliases.coverage_nodes,
                      field_aliases.coverage_arcs, field_aliases.borders):
            for name, alias in maker().items():
                self.assertIn(alias, i18n.EN, "%s без перевода" % name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
