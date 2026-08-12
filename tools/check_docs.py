# -*- coding: utf-8 -*-
"""
Проверка согласованности документации.

Следит за тем, что легко упустить при правках: битые внутренние ссылки,
отсутствие английской пары у русского файла, кириллица в английских текстах
за пределами подписи к ссылке на русскую версию.

    python tools/check_docs.py
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAIRS = [("README.md", "README.en.md"),
         ("MANUAL.md", "MANUAL.en.md"),
         ("DETAILS.md", "DETAILS.en.md")]

# Подпись ссылки на русскую версию в английском файле кириллицей допустима.
ALLOWED_CYRILLIC = ("Русская версия",)


def main():
    problems = []

    for ru, en in PAIRS:
        for name in (ru, en):
            if not os.path.exists(os.path.join(ROOT, name)):
                problems.append("нет файла %s" % name)

    for name in os.listdir(ROOT):
        if not name.endswith(".md"):
            continue
        path = os.path.join(ROOT, name)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()

        for link in re.findall(r"\[[^\]]*\]\(([^)#:]+\.md)\)", text):
            if not os.path.exists(os.path.join(ROOT, link)):
                problems.append("%s ссылается на несуществующий %s" % (name, link))

        if name.endswith(".en.md"):
            cleaned = text
            for allowed in ALLOWED_CYRILLIC:
                cleaned = cleaned.replace(allowed, "")
            found = re.findall(r"[А-Яа-яЁё]+", cleaned)
            if found:
                problems.append("%s: кириллица в английском тексте: %r"
                                % (name, found[:5]))

    for ru, en in PAIRS:
        ru_path, en_path = os.path.join(ROOT, ru), os.path.join(ROOT, en)
        if not (os.path.exists(ru_path) and os.path.exists(en_path)):
            continue
        with open(ru_path, encoding="utf-8") as fh:
            ru_text = fh.read()
        with open(en_path, encoding="utf-8") as fh:
            en_text = fh.read()
        if en not in ru_text:
            problems.append("%s не ссылается на %s" % (ru, en))
        if ru not in en_text:
            problems.append("%s не ссылается на %s" % (en, ru))

    if problems:
        print("Проблемы в документации:")
        for line in problems:
            print("  " + line)
        return 1
    print("Документация согласована.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
