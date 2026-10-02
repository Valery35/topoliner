# -*- coding: utf-8 -*-
"""
Точка входа плагина.

Вся работа идёт в панели Processing, её даёт провайдер. Кроме провайдера
плагин ставит одну кнопку, окно «О модуле».

Панель «Покрытие» лежит в дереве, но к интерфейсу не подключена. Она
переделывается под штатное рисование QGIS и вернётся отдельным выпуском.
"""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .i18n import tr
from .provider import TopolinerProvider
from .qt_compat import run_dialog
from .ui_dialogs import AboutDialog

MENU = "Topoliner"


class TopolinerPlugin:
    """Основной класс плагина. Регистрирует провайдер и окно «О модуле»."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.actions = []

    def initGui(self):
        self.provider = TopolinerProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        about = QAction(self.icon("icon.png"), tr("О модуле Topoliner"),
                        self.iface.mainWindow())
        about.triggered.connect(self.open_about)
        self.iface.addPluginToMenu(MENU, about)
        self.actions.append(about)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        for action in self.actions:
            self.iface.removePluginMenu(MENU, action)
        self.actions = []

    def icon(self, name):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "icons", name)
        return QIcon(path) if os.path.exists(path) else QIcon()

    def open_about(self):
        run_dialog(AboutDialog(self.iface.mainWindow()))
