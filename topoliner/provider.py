# -*- coding: utf-8 -*-
from qgis.core import QgsProcessingProvider

from .i18n import tr
from qgis.PyQt.QtGui import QIcon
import os

from .audit_algorithms import (
    AssemblyCheckAlgorithm,
    TopologyAuditAlgorithm,
    TopologyFixAlgorithm,
)
from .line_algorithms import LineAuditAlgorithm, LineFixAlgorithm
from .simplify_algorithm import BoundariesAlgorithm, TopologySimplifyAlgorithm
from .topo_algorithm import InsertNodesAlgorithm, TopologyCleanAlgorithm


class TopolinerProvider(QgsProcessingProvider):

    def loadAlgorithms(self):
        # Порядок соответствует нумерации: пары проверка и очистка стоят
        # рядом, полигоны перед линиями.
        self.addAlgorithm(TopologyAuditAlgorithm())       # 1.01
        self.addAlgorithm(LineAuditAlgorithm())           # 1.02
        self.addAlgorithm(TopologyFixAlgorithm())         # 1.03
        self.addAlgorithm(LineFixAlgorithm())             # 1.04
        self.addAlgorithm(TopologyCleanAlgorithm())       # 1.05
        self.addAlgorithm(InsertNodesAlgorithm())         # 1.06
        self.addAlgorithm(AssemblyCheckAlgorithm())       # 1.07
        self.addAlgorithm(TopologySimplifyAlgorithm())    # 2.01
        self.addAlgorithm(BoundariesAlgorithm())          # 2.02

    def id(self):
        return "topoliner"

    def name(self):
        return "Topoliner"

    def longName(self):
        return tr("Topoliner - топология и обработка геометрии")

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icons", "icon.png")
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return super().icon()
