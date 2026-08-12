# -*- coding: utf-8 -*-
"""
Проверка готовности к публикации.

Смотрит на то, что обычно возвращает модератор каталога: заполненность
метаданных, структуру архива, лицензию, отсутствие внешних зависимостей.
Запуск из корня репозитория:

    python tools/preflight.py
"""

import ast
import configparser
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = "topoliner"

REQUIRED = ("name", "qgisMinimumVersion", "description", "version",
            "author", "email", "about", "repository", "tracker")


def module_level_imports(path):
    """Имена модулей, импортируемых на верхнем уровне файла."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    names = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def main():
    errors, warnings = [], []

    meta_path = os.path.join(ROOT, PLUGIN, "metadata.txt")
    cp = configparser.ConfigParser()
    cp.read(meta_path, encoding="utf-8")
    general = cp["general"]

    for field in REQUIRED:
        if not general.get(field, "").strip():
            errors.append("metadata.txt: не заполнено поле %s" % field)
    raw = open(meta_path, encoding="utf-8").read()
    if "ЗАПОЛНИТЬ" in raw:
        errors.append("metadata.txt: осталась заглушка ЗАПОЛНИТЬ")
    if re.search(r"[А-Яа-яЁё]", general.get("description", "")):
        warnings.append("description на русском, каталог международный")
    if len(general.get("description", "")) > 500:
        warnings.append("description длиннее 500 символов")
    if general.get("experimental", "").lower() not in ("false", ""):
        warnings.append("плагин помечен как experimental")

    for name in ("__init__.py", "metadata.txt", "icons/icon.png"):
        if not os.path.exists(os.path.join(ROOT, PLUGIN, name)):
            errors.append("нет файла %s/%s" % (PLUGIN, name))
    if not os.path.exists(os.path.join(ROOT, "LICENSE")):
        errors.append("нет файла LICENSE")
    else:
        text = open(os.path.join(ROOT, "LICENSE"), encoding="utf-8").read()
        if "GNU GENERAL PUBLIC LICENSE" not in text:
            errors.append("LICENSE не является текстом GPL")

    # Внешние зависимости. Ленивый импорт внутри функции допустим:
    # ShapelyBackend нужен только тестам и в QGIS не создаётся.
    allowed = {"qgis", "PyQt5", "math", "os", "sys", "re", "json", "ast",
               "collections", "zipfile", "shutil", "configparser"}
    for folder, dirs, files in os.walk(os.path.join(ROOT, PLUGIN)):
        dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            for module in module_level_imports(path) - allowed:
                if not module.startswith("_"):
                    errors.append("%s: обязательный импорт %s" % (name, module))

    print("Проверка готовности Topoliner %s" % general.get("version", "?"))
    if errors:
        print("\nОшибки:")
        for line in errors:
            print("  " + line)
    if warnings:
        print("\nЗамечания:")
        for line in warnings:
            print("  " + line)
    if not errors and not warnings:
        print("\nВсё в порядке.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
