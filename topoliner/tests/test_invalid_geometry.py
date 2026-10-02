# -*- coding: utf-8 -*-
"""
Сторож порядка вызовов при чтении слоя.

Инструменты топологии обязаны принимать некорректную геометрию, именно её
они и ищут. Источник объектов запоминает настройку проверки геометрии
в момент создания. Поэтому запрет проверки обязан стоять раньше первого
parameterAsSource, иначе он опаздывает, и у человека с настройкой
«Остановить алгоритм» инструмент отказывается читать слой.
"""

import ast
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)


class TestInvalidGeometryOrder(unittest.TestCase):

    def test_check_is_disabled_before_the_source_is_taken(self):
        found = []
        seen = 0
        for name in sorted(os.listdir(PLUGIN)):
            if not name.endswith(".py"):
                continue
            with open(os.path.join(PLUGIN, name), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if not (isinstance(node, ast.FunctionDef)
                        and node.name == "processAlgorithm"):
                    continue
                source = None
                check = None
                for call in ast.walk(node):
                    if not isinstance(call, ast.Call):
                        continue
                    attr = getattr(call.func, "attr", "")
                    if attr == "parameterAsSource":
                        source = min(source or call.lineno, call.lineno)
                    elif attr == "setInvalidGeometryCheck":
                        check = min(check or call.lineno, call.lineno)
                if source is None:
                    continue
                seen += 1
                if check is None or check > source:
                    found.append("%s:%d" % (name, node.lineno))
        self.assertGreater(seen, 0)
        self.assertEqual(found, [], "Запрет проверки опаздывает: %r" % found)


if __name__ == "__main__":
    unittest.main()
