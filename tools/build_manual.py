# -*- coding: utf-8 -*-
"""
Сборка руководства в PDF.

Источник это doc/MANUAL.md и doc/MANUAL.en.md, картинки берутся
из doc/figures. Результат кладётся внутрь плагина, в topoliner/doc,
чтобы кнопка справки открывала его у любого, кто поставил плагин из ZIP.

    python tools/build_manual.py

Порядок сборки. Pandoc превращает markdown в самодостаточную страницу HTML
со встроенными картинками и оглавлением, браузер печатает эту страницу в PDF.
Pandoc берётся из PATH либо из пакета pypandoc_binary, браузером служит Edge
или Chrome. TeX не нужен.

Если pandoc или браузер не найдены, скрипт говорит об этом и выходит,
не роняя остальную сборку.
"""

import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = "topoliner"
DOC_SRC = os.path.join(ROOT, "doc")
DOC_OUT = os.path.join(ROOT, PLUGIN, "doc")

BOOKS = [
    ("MANUAL.md", "Topoliner.pdf", "ru", "Содержание"),
    ("MANUAL.en.md", "Topoliner_en.pdf", "en", "Contents"),
]

# Оформление задаётся здесь, а не в браузере. Поля и размер страницы идут
# через @page, потому что колонтитулы браузера отключены отдельным ключом.
CSS = """
@page { size: A4; margin: 20mm 18mm; }
html { -webkit-print-color-adjust: exact; }
body {
  font-family: "DejaVu Serif", "Georgia", serif;
  font-size: 10.5pt; line-height: 1.45; color: #111; margin: 0;
}
h1, h2, h3, h4 {
  font-family: "DejaVu Sans", "Segoe UI", sans-serif;
  color: #0f2e3d; line-height: 1.25; margin: 1.1em 0 0.4em;
  page-break-after: avoid;
}
h1 { font-size: 19pt; border-bottom: 2px solid #0f766e; padding-bottom: 4px; }
h2 { font-size: 15pt; page-break-before: auto; }
h3 { font-size: 12.5pt; }
h4 { font-size: 11pt; }
p { margin: 0.45em 0; orphans: 3; widows: 3; }
a { color: #0f766e; text-decoration: none; }
code, pre {
  font-family: "DejaVu Sans Mono", Consolas, monospace; font-size: 9pt;
}
code { background: #f2f5f5; padding: 0 2px; border-radius: 2px; }
pre {
  background: #f2f5f5; border-left: 3px solid #0f766e;
  padding: 7px 10px; overflow-x: auto; page-break-inside: avoid;
}
pre code { background: none; padding: 0; }
table {
  border-collapse: collapse; width: 100%; margin: 0.7em 0; font-size: 9pt;
  page-break-inside: auto;
}
th, td { border: 1px solid #c8d2d2; padding: 4px 6px; vertical-align: top; }
th { background: #eef4f4; text-align: left; }
tr { page-break-inside: avoid; }
img { max-width: 100%; height: auto; display: block; margin: 0.6em auto; }
figure { margin: 0.8em 0; page-break-inside: avoid; }
figcaption { font-size: 9pt; font-style: italic; text-align: center; color: #444; }
blockquote {
  border-left: 3px solid #c8d2d2; margin: 0.6em 0; padding: 0 0 0 10px; color: #333;
}
hr { border: 0; border-top: 1px solid #d8e0e0; margin: 1.2em 0; }
#TOC { page-break-after: always; }
#TOC ul { list-style: none; padding-left: 1.1em; margin: 0.2em 0; }
#TOC > ul { padding-left: 0; }
#TOC a { color: #111; }
"""


def find_pandoc():
    """Pandoc из PATH, иначе из пакета pypandoc_binary."""
    found = shutil.which("pandoc")
    if found:
        return found
    try:
        import pypandoc
    except ImportError:
        return None
    path = pypandoc.get_pandoc_path()
    if os.path.isfile(path):
        return path
    exe = path + ".exe"
    return exe if os.path.isfile(exe) else None


def find_browser():
    """Edge или Chrome, они умеют печатать страницу в PDF без окна."""
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    patterns = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for pattern in patterns:
        hit = glob.glob(pattern)
        if hit:
            return hit[0]
    return None


def to_html(pandoc, source, target, language, toc_title):
    """Markdown в самодостаточную страницу со встроенными картинками."""
    css_path = os.path.join(DOC_SRC, "_print.css")
    with open(css_path, "w", encoding="utf-8") as fh:
        fh.write(CSS)
    command = [
        pandoc, source,
        "-f", "gfm",
        "-t", "html5",
        "-o", target,
        "--standalone",
        "--embed-resources",
        "--toc", "--toc-depth=3",
        "--metadata", "lang=" + language,
        "--metadata", "title=Topoliner",
        "--variable", "toc-title=" + toc_title,
        "--css", "_print.css",
        "--resource-path=" + DOC_SRC,
    ]
    result = subprocess.run(command, cwd=DOC_SRC, capture_output=True, text=True)
    os.remove(css_path)
    if result.returncode != 0:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit("pandoc вернул ошибку на %s" % source)


def to_pdf(browser, html_path, pdf_path):
    """Печать готовой страницы в PDF без окна браузера."""
    url = "file:///" + os.path.abspath(html_path).replace("\\", "/")
    command = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=20000",
        "--print-to-pdf=" + os.path.abspath(pdf_path),
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) < 10000:
        print(result.stdout[-2000:])
        print(result.stderr[-2000:])
        raise SystemExit("браузер не напечатал %s" % pdf_path)


def main():
    pandoc = find_pandoc()
    if pandoc is None:
        print("Нет pandoc, руководство не собрано.")
        print("Поставить можно так: python -m pip install --user pypandoc_binary")
        return
    browser = find_browser()
    if browser is None:
        print("Нет браузера для печати, руководство не собрано.")
        return

    if not os.path.isdir(DOC_OUT):
        os.makedirs(DOC_OUT)

    for source, target, language, toc_title in BOOKS:
        source_path = os.path.join(DOC_SRC, source)
        if not os.path.exists(source_path):
            print("Нет файла %s, пропущен." % source)
            continue
        html_path = os.path.join(DOC_SRC, "_" + target.replace(".pdf", ".html"))
        pdf_path = os.path.join(DOC_OUT, target)
        to_html(pandoc, source, html_path, language, toc_title)
        try:
            to_pdf(browser, html_path, pdf_path)
        finally:
            if os.path.exists(html_path):
                os.remove(html_path)
        print("%-18s %8.1f КБ" % (target, os.path.getsize(pdf_path) / 1024.0))


if __name__ == "__main__":
    sys.exit(main())
