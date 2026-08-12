# -*- coding: utf-8 -*-
"""
Сборка руководства в PDF.

Источник это doc/MANUAL.md и doc/MANUAL.en.md, картинки берутся
из doc/figures. Результат кладётся внутрь плагина, в topoliner/doc,
чтобы кнопка справки открывала его у любого, кто поставил плагин из ZIP.

    python tools/build_manual.py

Нужны pandoc и xelatex. Если их нет, скрипт скажет об этом и выйдет,
не роняя остальную сборку.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = "topoliner"
DOC_SRC = os.path.join(ROOT, "doc")
DOC_OUT = os.path.join(ROOT, PLUGIN, "doc")

# Шрифт с кириллицей и полным набором знаков. Заголовок документа не задаём:
# в нём кириллица иногда выходит квадратами.
HEADER_COMMON = r"""
\usepackage{float}
\floatplacement{figure}{H}
\usepackage{microtype}
\setlength{\emergencystretch}{3em}
"""

# Русское оглавление и переносы. Без этого заголовок содержания
# остаётся английским, а слова переносятся по английским правилам.
HEADER_RU = r"""
\usepackage{polyglossia}
\setmainlanguage{russian}
\setotherlanguage{english}
"""

BOOKS = [
    ("MANUAL.md", "Topoliner.pdf", "russian"),
    ("MANUAL.en.md", "Topoliner_en.pdf", "english"),
]


def have(tool):
    return shutil.which(tool) is not None


def build(source, target, language):
    """
    Собирает один PDF.

    Используется свой шаблон: в стандартном шаблоне pandoc жёстко прописан
    пакет lmodern, которого может не быть в урезанной установке TeX,
    а шрифты мы всё равно задаём явно.
    """
    header_path = os.path.join(DOC_SRC, "_header.tex")
    with open(header_path, "w", encoding="utf-8") as fh:
        fh.write(HEADER_COMMON)
        if language == "russian":
            fh.write(HEADER_RU)

    command = [
        "pandoc", source,
        "-o", target,
        "--pdf-engine=xelatex",
        "--toc", "--toc-depth=3",
        "-V", "mainfont=DejaVu Serif",
        "-V", "sansfont=DejaVu Sans",
        "-V", "monofont=DejaVu Sans Mono",
        "-V", "geometry:margin=2.2cm",
        "-V", "colorlinks=true",
        # Шаблон pandoc по умолчанию тянет lmodern, которого может не быть.
        # Шрифты у нас заданы явно, поэтому пакет не нужен.
        "-V", "linkcolor=NavyBlue",
        "--template=_template.tex",
        "-H", header_path,
        "--resource-path=" + DOC_SRC,
    ]
    result = subprocess.run(command, cwd=DOC_SRC, capture_output=True, text=True)
    os.remove(header_path)
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit("pandoc вернул ошибку на %s" % source)


def main():
    for tool in ("pandoc", "xelatex"):
        if not have(tool):
            print("Нет %s, руководство не собрано." % tool)
            return 0

    figures = os.path.join(DOC_SRC, "figures")
    if not os.path.isdir(figures):
        print("Нет папки doc/figures, сначала запустите tools/make_figures.py")
        return 1

    os.makedirs(DOC_OUT, exist_ok=True)
    for source, target, language in BOOKS:
        source_path = os.path.join(DOC_SRC, source)
        if not os.path.exists(source_path):
            print("Пропущено: нет %s" % source)
            continue
        out_path = os.path.join(DOC_OUT, target)
        build(source, out_path, language)
        size = os.path.getsize(out_path) / 1024.0
        print("%-18s %7.1f КБ" % (target, size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
