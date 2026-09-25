# -*- coding: utf-8 -*-
"""
ui_dialogs
----------
Окно «О модуле».

Инструменты Processing своих окон не имеют, диалог им рисует сама панель.
Настройки ввода контуров живут в панели «Покрытие». Здесь остаётся только
то, что отвечает на вопрос, что это за модуль и куда смотреть дальше.
"""

import os

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from .branding import (COMPANY_URL, ISOLINER3D_URL, ISOLINER_URL, PLUGIN_NAME,
                       PRODUCT_URL, manual_path, plugin_version)
from .i18n import tr
from .qt_compat import BUTTON_CLOSE, ROLE_ACTION

__all__ = ["AboutDialog"]


class AboutDialog(QDialog):
    """Что это за модуль, куда смотреть дальше и на каких условиях."""

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(tr("О модуле Topoliner"))
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>%s %s</b>"
                                % (PLUGIN_NAME, plugin_version())))

        text = QTextBrowser(self)
        text.setOpenExternalLinks(True)
        text.setHtml(self.body())
        layout.addWidget(text)

        buttons = QDialogButtonBox(BUTTON_CLOSE, parent=self)
        manual = manual_path()
        if manual:
            button = QPushButton(tr("Руководство"), self)
            button.clicked.connect(self.open_manual)
            buttons.addButton(button, ROLE_ACTION)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def open_manual(self):
        path = manual_path()
        if path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def body(self):
        link = '<a href="%s">%s</a>'
        return (
            "<p>%s</p><p>%s</p><p>%s</p><p>%s<br>%s<br>%s</p><p>%s</p>"
            % (tr("Топология полигональных и линейных покрытий. Инструменты "
                  "находят нарушения и отделяют технический мусор от того, "
                  "что может нести смысл. Мусор исправляется в новый слой."),
               tr("Одиннадцать инструментов стоят в панели Processing, "
                  "в группах «1. Топология» и «2. Генерализация». Панель "
                  "«Покрытие» вводит нарисованный контур прямо в режиме "
                  "редактирования."),
               tr("Исходный слой не изменяется никогда. Автоматика не решает, "
                  "чья граница верна, она смотрит только на масштаб "
                  "расхождения."),
               link % (PRODUCT_URL, tr("Страница плагина")),
               link % (ISOLINER_URL, tr("Isoliner, кригинг и изолинии")),
               link % (ISOLINER3D_URL,
                       tr("Isoliner3D, просмотр поверхностей и тел")),
               tr("Лицензия GPL 3. Развивается на задачах реальных "
                  "предприятий: %s") % (link % (COMPANY_URL, COMPANY_URL)))
        )
