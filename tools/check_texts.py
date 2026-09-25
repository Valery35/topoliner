# -*- coding: utf-8 -*-
"""
Проверка текстов по требованиям из AGENTS.md.

Смотрит на всё, что читает человек: файлы markdown, справки инструментов
и подсказки полей в вызовах setHelp.

    python tools/check_texts.py
    python tools/check_texts.py --new      только изменённое относительно HEAD
    python tools/check_texts.py --strict   ненулевой код возврата при находках

Проверка машинная и находок не исправляет. Каждая находка это файл, строка,
цитата и суть расхождения.

Сам AGENTS.md из лексической проверки исключён. В нём стоит список стоп-слов,
и каждое слово этого списка обернулось бы находкой на себя же.
"""

import ast
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "topoliner")

STOP_WORDS = (
    "честный", "честнее", "честно", "врать", "врёт", "главные грабли", "софт",
    "кучка", "гладь", "скучный", "лаг", "членение", "наблюдённый",
    "предъявить", "соблазн", "лесенка", "сходит с рук", "деваться некуда",
    "вперемешку", "крутить параметры", "руками", "кучу", "под рукой",
    "мелочь",
)

# Двоеточие допустимо перед списком, в ссылках, во времени и в названиях.
COLON_OK = re.compile(r"(https?:|file:|mailto:|\d:\d|::|:\s*$|:\s*\*\*|:`)")

LONG_DASH = re.compile(r"[\u2013\u2014]")
SENTENCE = re.compile(r"[^.!?]+[.!?]")


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
            try:
                text = ast.literal_eval(node.args[0])
            except ValueError:
                continue
            if isinstance(text, str):
                out.append((name, "setHelp", node.lineno, text))
    return out


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


def check_prose(where, text, problems, russian=True):
    """Пунктуация и лексика в одном куске текста."""
    plain = re.sub(r"<[^>]+>", " ", text)
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
        for word in STOP_WORDS:
            if re.search(r"\b%s" % re.escape(word), low):
                problems.append((place, word, "стоп-слово"))
        for match in re.finditer(r"\bчисл[оа]\b", low):
            near = low[max(0, match.start() - 1):match.end() + 1]
            if near.startswith("\u00ab") or near.endswith("\u00bb"):
                continue
            quote = line[max(0, match.start() - 18):match.end() + 18]
            problems.append((place, quote.strip(),
                             "«число» вместо «количества»"))


def sentence_stats(text):
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = re.sub(r"\s+", " ", plain)
    lengths = [len(s.split()) for s in SENTENCE.findall(plain) if s.strip()]
    if not lengths:
        return 0.0, 0, 0, 0
    mean = sum(lengths) / len(lengths)
    return mean, len(lengths), sum(1 for n in lengths if n > 28), \
        sum(1 for n in lengths if n > 34)


def git_path():
    """Путь к git. В среде QGIS его нет в PATH, поэтому ищем и по местам."""
    found = shutil.which("git")
    if found:
        return found
    for path in (r"C:\Program Files\Git\cmd\git.exe",
                 r"C:\Program Files (x86)\Git\cmd\git.exe"):
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
        russian = not name.endswith(".en.md") and name != "AGENTS.md"
        check_prose(name, body, problems, russian=russian)
        texts.append((name, body))

    for name, key, line, text in help_strings():
        where = "%s (%s, строка %d)" % (name, key, line)
        russian = not re.search(r"[A-Za-z]{4,}\s+[A-Za-z]{4,}", text[:80]) \
            or bool(re.search(r"[А-Яа-я]", text))
        check_prose(where, text, problems, russian=russian)
        texts.append((where, text))

    print("Проверка текстов")
    print("")
    if problems:
        print("Находок: %d" % len(problems))
        for place, quote, reason in problems:
            print("  %-40s %-40s %s" % (place, quote[:40], reason))
    else:
        print("Находок нет.")

    print("")
    print("Длина предложений")
    worst = []
    for name, text in texts:
        mean, total, over28, over34 = sentence_stats(text)
        if total:
            worst.append((over34, over28, mean, total, name))
    worst.sort(reverse=True)
    for over34, over28, mean, total, name in worst[:12]:
        print("  %-46s средняя %4.1f, предложений %4d, длиннее 28: %d, "
              "длиннее 34: %d" % (name, mean, total, over28, over34))
    return 1 if (problems and strict) else 0


if __name__ == "__main__":
    sys.exit(main())
