# -*- coding: utf-8 -*-
"""
Тесты перевода интерфейса.

Проверяется не качество перевода, а целостность механизма: что русский
возвращается без изменений, что английский находится, и что все строки,
обёрнутые в tr в коде, имеют перевод.
"""

import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN)

import i18n  # noqa: E402


class TestMechanism(unittest.TestCase):

    def tearDown(self):
        i18n.set_language("ru")

    def test_russian_returns_source(self):
        i18n.set_language("ru")
        self.assertEqual(i18n.tr("1. Топология"), "1. Топология")

    def test_english_is_translated(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr("1. Топология"), "1. Topology")

    def test_unknown_string_falls_back_to_source(self):
        i18n.set_language("en")
        self.assertEqual(i18n.tr("строка без перевода"), "строка без перевода")

    def test_locale_with_region_is_accepted(self):
        i18n.set_language("ru_RU")
        self.assertTrue(i18n.is_russian())
        i18n.set_language("en_GB")
        self.assertFalse(i18n.is_russian())


class TestCatalogue(unittest.TestCase):

    def collect_wrapped(self):
        """Строки, обёрнутые в tr в исходниках."""
        pattern = re.compile(r'tr\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
        found = set()
        for name in os.listdir(PLUGIN):
            if not name.endswith(".py") or name == "i18n.py":
                continue
            with open(os.path.join(PLUGIN, name), encoding="utf-8") as fh:
                text = fh.read()
            found.update(pattern.findall(text))
        return found

    def test_every_wrapped_string_has_translation(self):
        missing = sorted(s for s in self.collect_wrapped() if s not in i18n.EN)
        self.assertEqual(missing, [], "Нет перевода: %r" % missing)

    def test_translations_differ_from_source(self):
        same = [k for k, v in i18n.EN.items() if k == v]
        self.assertEqual(same, [], "Перевод совпадает с оригиналом: %r" % same)

    def test_no_empty_translations(self):
        empty = [k for k, v in i18n.EN.items() if not v.strip()]
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestHelpTexts(unittest.TestCase):
    """Справки инструментов на двух языках."""

    def setUp(self):
        import help_texts
        self.h = help_texts

    def tearDown(self):
        i18n.set_language("ru")

    def algorithm_names(self):
        """Имена алгоритмов из кода: то, что возвращает метод name."""
        import ast
        names = set()
        for fname in os.listdir(PLUGIN):
            if not fname.endswith(".py"):
                continue
            with open(os.path.join(PLUGIN, fname), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                # Провайдер тоже имеет метод name, но справки у него нет.
                bases = [b.attr if isinstance(b, ast.Attribute) else
                         getattr(b, "id", "") for b in node.bases]
                if not any("Algorithm" in str(x) for x in bases):
                    continue
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "name":
                        for st in ast.walk(item):
                            if isinstance(st, ast.Constant) and isinstance(st.value, str):
                                names.add(st.value)
        return names

    def test_every_algorithm_has_russian_help(self):
        missing = sorted(self.algorithm_names() - set(self.h.RU))
        self.assertEqual(missing, [], "Нет русской справки: %r" % missing)

    def test_every_algorithm_has_english_help(self):
        missing = sorted(self.algorithm_names() - set(self.h.EN))
        self.assertEqual(missing, [], "Нет английской справки: %r" % missing)

    def test_no_extra_entries(self):
        extra = sorted(set(self.h.RU) - self.algorithm_names())
        self.assertEqual(extra, [], "Справка без инструмента: %r" % extra)

    def test_help_for_switches_language(self):
        i18n.set_language("ru")
        ru = self.h.help_for("topologyaudit")
        i18n.set_language("en")
        en = self.h.help_for("topologyaudit")
        self.assertNotEqual(ru, en)
        self.assertIn("Проверка топологии", ru)
        self.assertIn("Topology check", en)

    def test_english_help_has_no_cyrillic(self):
        import re
        for name, text in self.h.EN.items():
            found = re.findall(r"[А-Яа-яЁё]+", text)
            self.assertEqual(found, [], "Кириллица в английской справке %s: %r"
                             % (name, found[:5]))

    def test_markup_tags_are_balanced(self):
        import re
        for table_name, table in (("RU", self.h.RU), ("EN", self.h.EN)):
            for name, text in table.items():
                for tag in ("b", "ul", "ol", "li"):
                    opened = len(re.findall(r"<%s>" % tag, text))
                    closed = len(re.findall(r"</%s>" % tag, text))
                    self.assertEqual(
                        opened, closed,
                        "Незакрытый тег %s в %s/%s" % (tag, table_name, name))

    def test_unknown_algorithm_gives_empty_help(self):
        self.assertEqual(self.h.help_for("нет такого"), "")


class TestNothingUntranslated(unittest.TestCase):
    """Ни одна строка интерфейса не должна остаться без перевода.

    Тест смотрит не на список обёрнутых строк, а на исходный код: находит
    вызовы, выводящие текст пользователю, и требует, чтобы русский текст
    в них был пропущен через tr. Иначе новая строка молча выпадет
    из перевода и заметить это можно будет только на чужой локали.
    """

    def source_files(self):
        for name in os.listdir(PLUGIN):
            if name.endswith(".py") and name not in ("i18n.py", "help_texts.py"):
                yield os.path.join(PLUGIN, name)

    def unwrapped_calls(self):
        import ast
        import re
        found = []
        for path in self.source_files():
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for node in ast.walk(ast.parse(src)):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                if not (isinstance(fn, ast.Attribute)
                        and fn.attr in ("pushInfo", "pushWarning")):
                    continue
                if not node.args:
                    continue
                arg = node.args[0]
                if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "tr":
                    continue
                target = arg.left if (isinstance(arg, ast.BinOp)
                                      and isinstance(arg.op, ast.Mod)) else arg
                if not (isinstance(target, ast.Constant)
                        and isinstance(target.value, str)):
                    continue
                if re.search(r"[А-Яа-яЁё]", target.value):
                    found.append("%s:%d %s" % (os.path.basename(path),
                                               target.lineno, target.value[:40]))
        return found

    def test_all_report_strings_go_through_tr(self):
        found = self.unwrapped_calls()
        self.assertEqual(found, [], "Строки без tr: %r" % found)

    def test_every_tr_string_is_in_the_catalogue(self):
        import ast
        import re
        missing = set()
        for path in self.source_files():
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            for node in ast.walk(ast.parse(src)):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "tr":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        value = node.args[0].value
                        if isinstance(value, str) and value not in i18n.EN:
                            missing.add(value)
        self.assertEqual(sorted(missing), [], "Нет перевода: %r" % sorted(missing))
