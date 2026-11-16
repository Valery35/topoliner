# -*- coding: utf-8 -*-
"""
Проверка текстов по своду C:\\Dev\\workplace\\TEXTS.md.

Смотрит на всё, что читает человек: файлы markdown, справки инструментов
и подсказки полей в вызовах setHelp. У подсказки, переведённой в i18n.py,
проверяется и английская пара.

    python tools/check_texts.py
    python tools/check_texts.py --new      только изменённое относительно HEAD
    python tools/check_texts.py --strict   ненулевой код возврата при находках

Проверка машинная и находок не исправляет. Каждая находка это файл, строка,
цитата и суть расхождения.

Деление на предложения, длину предложения, нормы длины по языкам, ритм
и стоп-слова считает ядро tools/measure.py. Это копия measure.py из
хранилища github.com/Valery35/agents-md-document-project (лицензия MIT),
коммит aaf87ab. Один код меряет тексты всей линейки, продукты зовут его
по-своему. Копия не правится. Сторож sha256 в tests/test_check_texts.py
ловит правку копии у нас. Расхождение копии с источником он не ловит,
источник при прогоне тестов недоступен. Новая версия ядра приносится
копированием с новой суммой в стороже.

Своё у плагина: сбор текстов из кода, ключ --new по git diff, английская
пара подсказки, пунктуация по строкам с номерами, «прямо» и «число»
вместо «количества». Этих двух проверок в ядре нет.

Сам AGENTS.md из лексической проверки исключён, как и прежде.

Исключения продукта - TERMS. Сюда вносится стоп-слово ядра, которое
у Topoliner стало именем разряда и стоит в журнале, руководстве
и подсказке поля. Вносится только по решению автора, по своду
C:\\Dev\\workplace\\TEXTS.md термин продукта сильнее стоп-слова, но
исключение заводит автор. Список пуст. «Молча» («исправлено молча»)
ждёт решения автора и не внесено, поэтому до его ответа проверка
комплекта находит «молча» и чистой не считается.
"""

import ast
import glob
import html
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "topoliner")
MEASURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "measure.py")


def _load_measure():
    """Ядро грузится по пути файла и под своим именем.

    Обычный import measure берёт первый попавшийся модуль с этим именем:
    уже загруженный в общем прогоне или лежащий раньше по sys.path. Тогда
    меряет чужой код, а заметно это только случайно.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location("topoliner_measure", MEASURE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


measure = _load_measure()

# Слова сверх ядра. «Прямо» ловится только целиком: у него есть законные
# родственники (прямой, прямого, напрямую).
STOP_WHOLE = ("прямо",)

# Исключения продукта из стоп-слов ядра, по решению автора. См. шапку.
TERMS = ()

LONG_DASH = re.compile(r"[\u2013\u2014]")


def markdown_files():
    for name in sorted(os.listdir(ROOT)):
        if name.endswith(".md"):
            yield os.path.join(ROOT, name)
    doc = os.path.join(ROOT, "doc")
    if os.path.isdir(doc):
        for name in sorted(os.listdir(doc)):
            if name.endswith(".md"):
                yield os.path.join(doc, name)


def help_strings():
    """Справки инструментов и подсказки полей, парами имя и текст."""
    out = []
    path = os.path.join(PLUGIN, "help_texts.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    try:
                        text = ast.literal_eval(value)
                    except ValueError:
                        continue
                    if isinstance(text, str):
                        out.append(("help_texts.py", key.value, node.lineno, text))

    english = english_catalogue()
    for name in sorted(os.listdir(PLUGIN)):
        if not name.endswith(".py"):
            continue
        with open(os.path.join(PLUGIN, name), encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if getattr(node.func, "attr", "") != "setHelp" or not node.args:
                continue
            arg = node.args[0]
            # Подсказка идёт через tr, текст лежит первым аргументом.
            if (isinstance(arg, ast.Call) and getattr(arg.func, "id", "") == "tr"
                    and arg.args):
                arg = arg.args[0]
            try:
                text = ast.literal_eval(arg)
            except ValueError:
                continue
            if isinstance(text, str):
                out.append((name, "setHelp", node.lineno, text))
                if text in english:
                    out.append((name, "setHelp en", node.lineno, english[text]))
    return out


def english_catalogue():
    """Словарь EN из i18n.py, без импорта модуля плагина."""
    path = os.path.join(PLUGIN, "i18n.py")
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and getattr(node.targets[0], "id", "") == "EN"):
            return ast.literal_eval(node.value)
    return {}


def clean_markdown(text):
    """Текст без кода, таблиц и заголовков. Остаётся проза.

    Блоки кода заменяются пустыми строками, а не вырезаются: иначе номера
    строк в находках уезжают относительно исходного файла.
    """
    text = re.sub(r"```.*?```",
                  lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"`[^`]*`", "", text)
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("|", "#", "![", "[!")):
            lines.append("")
            continue
        lines.append(line)
    return "\n".join(lines)


def html_to_text(text):
    """Справка в разметке HTML - в строки прозы для ядра.

    Блочный тег закрывает абзац, строчный заменяется пробелом, сущность
    становится знаком.
    """
    text = re.sub(r"(?i)<\s*(br|/p|p|/li|li|/ul|ul|/ol|ol|/h\d|h\d)\b[^>]*>",
                  "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return html.unescape(text)


def colon_is_fine(before, after):
    """Двоеточие перед списком, в подписи, в соотношении и в адресе."""
    if not after.strip():
        return True
    if before.rstrip().endswith("**") or after.lstrip().startswith("**"):
        return True
    if re.search(r"\d\s*$", before) and re.match(r"\s*\d", after):
        return True
    if re.search(r"(https?|file|mailto)$", before) or after.startswith("//"):
        return True
    return False


def language(text, default="ru"):
    """Язык куска текста по ядру. Пустой текст - язык по умолчанию."""
    if not re.search(r"[A-Za-zА-Яа-яЁё]", text):
        return default
    return measure.detect_lang(text)


def stop_words(where, text, problems, lang):
    """Стоп-слова ядра с номером строки, где слово стоит."""
    lines = text.split("\n")
    for sentence, _item, _first, at in measure.sentences_at(text):
        body = measure.strip_mentions(sentence)
        for pattern, replacement in measure.STOP_WORDS[lang]:
            for match in re.finditer(r"\b" + pattern + r"\b", body, re.IGNORECASE):
                word = match.group(0)
                if word.lower() in TERMS:
                    continue
                line_no = at
                # Предложение может занимать несколько строк абзаца. Номер
                # берётся у строки, где слово стоит на самом деле.
                for k in range(max(at - 1, 0), len(lines)):
                    if re.search(r"\b" + re.escape(word) + r"\b", lines[k],
                                 re.IGNORECASE):
                        line_no = k + 1
                        break
                problems.append(("%s:%d" % (where, line_no), word,
                                 "стоп-слово -> %s" % replacement))


def check_prose(where, text, problems, russian=True, lang=None):
    """Пунктуация по строкам, стоп-слова ядра и слова плагина."""
    # Сущность HTML («&nbsp;») это знак, а не точка с запятой.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    for number, line in enumerate(plain.split("\n"), 1):
        place = "%s:%d" % (where, number)
        if LONG_DASH.search(line):
            problems.append((place, line.strip(), "длинное тире"))
        if ";" in line:
            problems.append((place, line.strip(), "точка с запятой"))
        for match in re.finditer(r":", line):
            if colon_is_fine(line[:match.start()], line[match.end():]):
                continue
            quote = line[max(0, match.start() - 18):match.start() + 18]
            problems.append((place, quote.strip(), "двоеточие внутри строки"))
        if not russian:
            continue
        low = line.lower()
        for word in STOP_WHOLE:
            if re.search(r"\b%s\b" % re.escape(word), low):
                problems.append((place, word, "стоп-слово"))
        for match in re.finditer(r"\bчисл[оа]\b", low):
            near = low[max(0, match.start() - 1):match.end() + 1]
            if near.startswith("\u00ab") or near.endswith("\u00bb"):
                continue
            quote = line[max(0, match.start() - 18):match.end() + 18]
            problems.append((place, quote.strip(),
                             "«число» вместо «количества»"))
    if lang is not None:
        stop_words(where, plain, problems, lang)


def sentences(text):
    """Предложения текста по ядру."""
    return [s for s, _item, _first in measure.sentences(text)]


def sentence_lengths(text):
    """Длины предложений в словах по ядру."""
    return [measure.word_count(s) for s in sentences(text)]


def sentence_stats(text, lang="ru"):
    """Средняя, количество, длиннее предела warn и длиннее предела error.

    Пределы берутся из ядра по языку: русский 28 и 34, английский 38 и 45.
    """
    lengths = [n for n in sentence_lengths(text) if n]
    if not lengths:
        return 0.0, 0, 0, 0
    limit = measure.LIMITS[lang]
    mean = sum(lengths) / len(lengths)
    return (mean, len(lengths),
            sum(1 for n in lengths if n > limit["warn"]),
            sum(1 for n in lengths if n > limit["error"]))


def git_path():
    """Путь к git. В среде QGIS его нет в PATH, поэтому ищем и по местам.

    На рабочей машине git стоит только в составе GitHub Desktop.
    """
    found = shutil.which("git")
    if found:
        return found
    places = [r"C:\Program Files\Git\cmd\git.exe",
              r"C:\Program Files (x86)\Git\cmd\git.exe"]
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        places += sorted(glob.glob(os.path.join(
            local, "GitHubDesktop", "app-*", "resources", "app", "git", "cmd",
            "git.exe")), reverse=True)
    for path in places:
        if os.path.exists(path):
            return path
    return ""


def changed_files():
    """Файлы, изменённые относительно HEAD. Пустой список означает все."""
    git = git_path()
    if not git:
        return []
    done = subprocess.run([git, "diff", "--name-only", "HEAD"],
                          cwd=ROOT, capture_output=True, text=True)
    if done.returncode != 0:
        return []
    names = [n.strip() for n in done.stdout.split("\n") if n.strip()]
    return [os.path.join(ROOT, n.replace("/", os.sep)) for n in names]


def main():
    only_new = "--new" in sys.argv
    strict = "--strict" in sys.argv
    touched = None
    if only_new:
        touched = set(changed_files())
        if not touched:
            print("Изменённых файлов не видно, проверяются все.")
            touched = None

    problems = []
    texts = []

    for path in markdown_files():
        if touched is not None and path not in touched:
            continue
        name = os.path.relpath(path, ROOT)
        with open(path, encoding="utf-8") as fh:
            raw = fh.read()
        body = clean_markdown(raw)
        # Язык по тексту, а не по имени: README.md написан по-английски.
        lang = language(body)
        russian = lang == "ru" and name != "AGENTS.md"
        check_prose(name, body, problems, russian=russian,
                    lang=None if name == "AGENTS.md" else lang)
        texts.append((name, raw, lang))

    help_files = {os.path.join(PLUGIN, "help_texts.py"), os.path.join(PLUGIN, "i18n.py")}
    code_touched = touched is None or any(
        p.startswith(PLUGIN) and p.endswith(".py") for p in touched) \
        or bool(help_files & touched)
    if code_touched:
        for name, key, line, text in help_strings():
            where = "%s (%s, строка %d)" % (name, key, line)
            plain = html_to_text(text)
            lang = language(plain)
            check_prose(where, text, problems, russian=(lang == "ru"), lang=lang)
            texts.append((where, plain, lang))

    print("Проверка текстов")
    print("")
    if problems:
        print("Находок: %d" % len(problems))
        for place, quote, reason in problems:
            print("  %-40s %-40s %s" % (place, quote[:40], reason))
    else:
        print("Находок нет.")

    print("")
    print("Длина предложений, пределы по языку из measure.py: "
          "ru %d и %d, en %d и %d" % (
              measure.LIMITS["ru"]["warn"], measure.LIMITS["ru"]["error"],
              measure.LIMITS["en"]["warn"], measure.LIMITS["en"]["error"]))
    worst = []
    for name, text, lang in texts:
        mean, total, over_warn, over_error = sentence_stats(text, lang)
        if total:
            worst.append((over_error, over_warn, mean, total, name, lang))
    worst.sort(reverse=True)
    for over_error, over_warn, mean, total, name, lang in worst[:12]:
        limit = measure.LIMITS[lang]
        print("  %-46s %s средняя %4.1f, предложений %4d, длиннее %d: %d, "
              "длиннее %d: %d" % (name, lang, mean, total, limit["warn"],
                                  over_warn, limit["error"], over_error))
    return 1 if (problems and strict) else 0


if __name__ == "__main__":
    sys.exit(main())
