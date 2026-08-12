# -*- coding: utf-8 -*-
from qgis.core import QgsApplication
from .provider import TopolinerProvider


class TopolinerPlugin:
    """Основной класс плагина. Регистрирует Processing-провайдер."""

    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initGui(self):
        self.provider = TopolinerProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):
        if self.provider:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
