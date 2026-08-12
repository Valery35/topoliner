# -*- coding: utf-8 -*-
"""
Сборка архивов плагина.

Создаёт два файла в dist/:
  topoliner.zip         рабочий архив, включает tests/
  topoliner_upload.zip  архив для plugins.qgis.org, без tests/

Запуск из корня репозитория:
    python tools/build_zip.py
"""

import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = "topoliner"
DIST = os.path.join(ROOT, "dist")

SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_EXT = {".pyc", ".pyo"}


def check_license():
    """LICENSE обязан лежать внутри папки плагина: каталог проверяет архив,
    а не репозиторий. Файл в корне остаётся для GitHub, и оба должны совпадать."""
    root_file = os.path.join(ROOT, "LICENSE")
    plugin_file = os.path.join(ROOT, PLUGIN, "LICENSE")
    if not os.path.exists(plugin_file):
        raise SystemExit("Нет файла %s/LICENSE, каталог отклонит архив" % PLUGIN)
    with open(root_file, encoding="utf-8") as fh:
        a = fh.read()
    with open(plugin_file, encoding="utf-8") as fh:
        b = fh.read()
    if a != b:
        raise SystemExit("LICENSE в корне и в папке плагина различаются")


def read_version():
    path = os.path.join(ROOT, PLUGIN, "metadata.txt")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("version="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("В metadata.txt не найдено поле version")


def collect(with_tests):
    base = os.path.join(ROOT, PLUGIN)
    for folder, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if not with_tests and os.path.basename(folder) == "tests":
            dirs[:] = []
            continue
        for name in files:
            if os.path.splitext(name)[1] in SKIP_EXT:
                continue
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, ROOT)
            yield full, rel


def build(target, with_tests):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for full, rel in collect(with_tests):
            zf.write(full, rel)
            count += 1
    size = os.path.getsize(target) / 1024.0
    print("%s: файлов %d, размер %.1f КБ" % (os.path.basename(target), count, size))


def main():
    check_license()
    version = read_version()
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    print("Версия %s" % version)
    build(os.path.join(DIST, "%s.zip" % PLUGIN), with_tests=True)
    build(os.path.join(DIST, "%s_upload.zip" % PLUGIN), with_tests=False)
    print("Готово. Для каталога загружайте файл с суффиксом _upload.")


if __name__ == "__main__":
    sys.exit(main())
