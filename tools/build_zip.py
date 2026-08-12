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


def check_manual():
    """
    Руководство обязано лежать внутри папки плагина: кнопка справки
    открывает его у того, кто поставил плагин из ZIP, а не из репозитория.
    """
    doc = os.path.join(ROOT, PLUGIN, "doc")
    missing = [name for name in ("Topoliner.pdf", "Topoliner_en.pdf")
               if not os.path.exists(os.path.join(doc, name))]
    if missing:
        raise SystemExit(
            "Нет руководства: %s. Запустите tools/make_figures.py "
            "и tools/build_manual.py" % ", ".join(missing))


def read_version():
    path = os.path.join(ROOT, PLUGIN, "metadata.txt")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("version="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("В metadata.txt не найдено поле version")


def collect_plugin(with_tests):
    """Файлы папки плагина."""
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
            yield full, os.path.relpath(full, ROOT)


def collect_repo():
    """
    Файлы репозитория вне папки плагина.

    Разделение строгое: этот архив и архив плагина не пересекаются, поэтому
    оба распаковываются целиком в одно место и выбирать при копировании
    ничего не нужно.
    """
    top_files = ("README.md", "README.en.md", "CHANGELOG.md", "LICENSE",
                 ".gitignore", ".gitattributes")
    for name in top_files:
        path = os.path.join(ROOT, name)
        if os.path.exists(path):
            yield path, name

    for folder_name in ("doc", "tools", "site", ".github"):
        base = os.path.join(ROOT, folder_name)
        if not os.path.isdir(base):
            continue
        for folder, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                if os.path.splitext(name)[1] in SKIP_EXT:
                    continue
                if name in ("_header.tex", "README-DELTA.txt"):
                    continue
                full = os.path.join(folder, name)
                yield full, os.path.relpath(full, ROOT)


def build(target, entries):
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        count = 0
        for full, rel in entries:
            zf.write(full, rel)
            count += 1
    size = os.path.getsize(target) / 1024.0
    print("%-24s файлов %3d, %7.1f КБ"
          % (os.path.basename(target), count, size))


def main():
    check_license()
    check_manual()
    version = read_version()
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    print("Версия %s" % version)

    # Папка плагина: рабочий архив с тестами и архив для каталога без них.
    build(os.path.join(DIST, "%s.zip" % PLUGIN), collect_plugin(True))
    build(os.path.join(DIST, "%s_upload.zip" % PLUGIN), collect_plugin(False))
    # Всё, что вне папки плагина.
    build(os.path.join(DIST, "%s-repo.zip" % PLUGIN), collect_repo())

    print("")
    print("В репозиторий: %s.zip и %s-repo.zip, оба поверх, целиком."
          % (PLUGIN, PLUGIN))
    print("В каталог:     %s_upload.zip" % PLUGIN)
    return 0


if __name__ == "__main__":
    sys.exit(main())
