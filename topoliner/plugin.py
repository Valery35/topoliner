# -*- coding: utf-8 -*-
"""
Точка входа плагина.

Основная работа идёт в панели Processing, её даёт провайдер. Отдельно стоит
панель «Покрытие»: она вводит нарисованный контур в открытый слой, и нужна
там, где окно Processing неудобно, то есть в режиме редактирования.
"""

import os

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .coverage_panel import CoveragePanel
from .cut_tool import CutMapTool
from .i18n import tr
from .provider import TopolinerProvider
from .qt_compat import DOCK_RIGHT, run_dialog
from .ui_dialogs import AboutDialog

MENU = "Topoliner"


class TopolinerPlugin:
    """Основной класс плагина. Регистрирует провайдер, панель и кнопки."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.toolbar = None
        self.panel = None
        self.tool = None
        self.actions = []

    # ── Запуск и остановка ────────────────────────────────────────────────

    def initGui(self):
        self.provider = TopolinerProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

        window = self.iface.mainWindow()
        self.toolbar = self.iface.addToolBar(MENU)
        self.toolbar.setObjectName("TopolinerToolbar")

        self.panel = CoveragePanel(self.iface, window)
        self.iface.addDockWidget(DOCK_RIGHT, self.panel)
        self.panel.hide()

        self.tool = CutMapTool(self.iface, self.panel)
        self.panel.set_tool(self.tool)

        panel_action = QAction(self.icon("cut.svg"), tr("Покрытие"), window)
        panel_action.setCheckable(True)
        panel_action.setToolTip(
            tr("Панель ввода нарисованных контуров в покрытие"))
        panel_action.toggled.connect(self.panel.setUserVisible)
        self.panel.visibilityChanged.connect(panel_action.setChecked)

        about = QAction(self.icon("icon.png"), tr("О модуле"), window)
        about.triggered.connect(self.open_about)

        for action in (panel_action, about):
            self.toolbar.addAction(action)
            self.iface.addPluginToMenu(MENU, action)
            self.actions.append(action)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        if self.tool is not None:
            if self.iface.mapCanvas().mapTool() is self.tool:
                self.iface.mapCanvas().unsetMapTool(self.tool)
            self.tool = None
        if self.panel is not None:
            self.iface.removeDockWidget(self.panel)
            self.panel.deleteLater()
            self.panel = None
        for action in self.actions:
            self.iface.removePluginMenu(MENU, action)
        self.actions = []
        if self.toolbar is not None:
            self.toolbar.deleteLater()
            self.toolbar = None

    # ── Действия ──────────────────────────────────────────────────────────

    def icon(self, name):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "icons", name)
        return QIcon(path) if os.path.exists(path) else QIcon()

    def open_about(self):
        run_dialog(AboutDialog(self.iface.mainWindow()))
