# -*- coding: utf-8 -*-
"""
Поля выходных слоёв создаются без устаревшего вызова.

QgsField(имя, QVariant.Int) с QGIS 3.38 даёт предупреждение Python.
В потоке Processing обработчик предупреждений QGIS роняет программу
с нарушением доступа. Так упал QGIS 3.40.12 на проверке топологии,
3 октября 2026 года. Сторож следит, что поля создаёт только make_field.
"""
import ast
import os
import sys
import unittest

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PLUGIN)

import qgis_helpers  # noqa: E402

HELPER = "qgis_helpers.py"


def direct_fields(source):
    """Строки, где QgsField вызывается напрямую."""
    return [node.lineno for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "QgsField"]


def plugin_sources():
    for folder, dirs, files in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__")]
        for name in files:
            if name.endswith(".py") and name != HELPER:
                with open(os.path.join(folder, name), encoding="utf-8") as fh:
                    yield name, fh.read()


class Meta:
    class Type:
        Int, LongLong, Double, QString = "m-int", "m-long", "m-double", "m-str"


class FlatMeta:
    Int, LongLong, Double, QString = "f-int", "f-long", "f-double", "f-str"


class Variant:
    Int, LongLong, Double, String = "v-int", "v-long", "v-double", "v-str"


class TestFieldTypes(unittest.TestCase):

    def test_no_direct_field(self):
        found = [(name, lines) for name, source in plugin_sources()
                 for lines in [direct_fields(source)] if lines]
        self.assertEqual(found, [])

    def test_guard_sees_old_call(self):
        bad = 'fields.append(QgsField("num", QVariant.Int))\n'
        self.assertEqual(direct_fields(bad), [1])

    def test_new_qgis_takes_meta_type(self):
        for version in (33800, 34012, 40003):
            self.assertEqual(
                qgis_helpers.field_type("int", version, Meta, Variant),
                "m-int")
        self.assertEqual(
            qgis_helpers.field_type("string", 34012, Meta, Variant), "m-str")

    def test_qt5_meta_type_without_scope(self):
        self.assertEqual(
            qgis_helpers.field_type("long", 34012, FlatMeta, Variant),
            "f-long")

    def test_old_qgis_takes_variant(self):
        for version in (31600, 33600, 33799):
            self.assertEqual(
                qgis_helpers.field_type("double", version, Meta, Variant),
                "v-double")
        self.assertEqual(
            qgis_helpers.field_type("string", 31600, Meta, Variant), "v-str")


def bare_runs(source):
    """Строки processAlgorithm без обёртки no_warnings."""
    return [node.lineno for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef)
            and node.name == "processAlgorithm"
            and "no_warnings" not in [getattr(d, "id", "")
                                      for d in node.decorator_list]]


class TestNoWarnings(unittest.TestCase):

    def test_every_run_is_wrapped(self):
        found = [(name, lines) for name, source in plugin_sources()
                 for lines in [bare_runs(source)] if lines]
        self.assertEqual(found, [])

    def test_guard_sees_bare_run(self):
        bad = ("class A:\n"
               "    def processAlgorithm(self, p, c, f):\n"
               "        return {}\n")
        self.assertEqual(bare_runs(bad), [2])

    def test_wrapper_silences_warning(self):
        import warnings

        class Algorithm:
            @qgis_helpers.no_warnings
            def processAlgorithm(self, value):
                warnings.warn("old call", DeprecationWarning)
                return value

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            self.assertEqual(Algorithm().processAlgorithm(7), 7)


if __name__ == "__main__":
    unittest.main()
