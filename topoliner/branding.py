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
    except Exception:
        pass
    return _version


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
