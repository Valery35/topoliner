# -*- coding: utf-8 -*-
"""
branding
--------
Подпись, которая добавляется в конец справки каждого инструмента.

Версия читается из metadata.txt, поэтому обновляется в одном месте
и не расходится с тем, что показывает менеджер модулей.
"""

import os

PLUGIN_NAME = "Topoliner"
COMPANY_URL = "https://www.informpp.ru/главная-страница/предприятиям"

_version = None


def plugin_version():
    """Версия из metadata.txt. Читается один раз."""
    global _version
    if _version is not None:
        return _version
    _version = ""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.txt")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("version="):
                    _version = line.split("=", 1)[1].strip()
                    break
    except (OSError, UnicodeDecodeError):
        # Версия нужна только для подписи, поэтому её отсутствие не повод
        # ронять инструмент: подпись просто выводится без номера.
        _version = ""
    return _version


def manual_path():
    """Путь к руководству на языке интерфейса, либо пустая строка."""
    from .i18n import is_russian
    name = "Topoliner.pdf" if is_russian() else "Topoliner_en.pdf"
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "doc", name)
    return path if os.path.exists(path) else ""


def help_url():
    """
    Адрес для кнопки справки в диалоге инструмента.

    Кнопка открывает руководство в PDF из комплекта плагина, поэтому
    работает и без сети. Если файла нет, возвращается страница продукта.
    """
    path = manual_path()
    if path:
        return "file:///" + path.replace("\\", "/")
    return COMPANY_URL


def banner():
    """Строка для журнала Processing: по ней видно версию на скриншоте."""
    version = plugin_version()
    return "%s %s" % (PLUGIN_NAME, version) if version else PLUGIN_NAME


def help_footer():
    """Хвост справки: название с версией и обращение к предприятиям."""
    version = plugin_version()
    title = "%s v%s" % (PLUGIN_NAME, version) if version else PLUGIN_NAME
    return (
        "<br><br>%s<br><br>"
        "%s развивается на задачах реальных предприятий. Если вашему "
        "производству не хватает функции, напишите нам: %s"
        % (title, PLUGIN_NAME, COMPANY_URL)
    )
