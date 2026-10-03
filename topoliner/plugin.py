# -*- coding: utf-8 -*-
"""
Точка входа плагина.

Вся работа идёт в панели Processing, её даёт провайдер. Кроме провайдера
плагин ставит одну кнопку, окно «О модуле».

Панель «Покрытие» лежит в дереве, но к интерфейсу не подключена. Разрез
в ней работает, а окно пока не объясняет человеку, что с ним делать.
Включается одной строкой ниже, PANEL = True.
"""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .i18n import tr
from .provider import TopolinerProvider
from .qt_compat import DOCK_RIGHT, run_dialog
from .ui_dialogs import AboutDialog

MENU = "Topoliner"
PANEL = False


class TopolinerPlugin:
    """Основной класс плагина. Регистрирует провайдер и окно «О модуле»."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.toolbar = None
        self.panel = None
        self.actions = []

    def initGui(self):
        self.provider = TopolinerProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        window = self.iface.mainWindow()
        about = QAction(self.icon("icon.png"), tr("О модуле Topoliner"), window)
        about.triggered.connect(self.open_about)
        self.iface.addPluginToMenu(MENU, about)
        self.actions.append(about)

        if PANEL:
            self.add_panel(window)

    def add_panel(self, window):
        from .coverage_panel import CoveragePanel
        self.toolbar = self.iface.addToolBar(MENU)
        self.toolbar.setObjectName("TopolinerToolbar")
        self.panel = CoveragePanel(self.iface, window)
        self.iface.addDockWidget(DOCK_RIGHT, self.panel)
        self.panel.hide()
        action = QAction(self.icon("cut.svg"), tr("Покрытие"), window)
        action.setCheckable(True)
        action.setToolTip(tr("Панель ввода нарисованных контуров в покрытие"))
        action.toggled.connect(self.panel.setUserVisible)
        self.panel.visibilityChanged.connect(action.setChecked)
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(MENU, action)
        self.actions.append(action)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        if self.panel is not None:
            self.panel.draw_button.setChecked(False)
            self.iface.removeDockWidget(self.panel)
            self.panel.deleteLater()
            self.panel = None
        for action in self.actions:
            self.iface.removePluginMenu(MENU, action)
        self.actions = []
        if self.toolbar is not None:
            self.toolbar.deleteLater()
            self.toolbar = None

    def icon(self, name):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "icons", name)
        return QIcon(path) if os.path.exists(path) else QIcon()

    def open_about(self):
        run_dialog(AboutDialog(self.iface.mainWindow()))
