# -*- coding: utf-8 -*-
"""
qt_compat
---------
Одинаковые имена для Qt 5 и Qt 6.

В Qt 6 перечисления стали областными. Qt.CrossCursor превратился
в Qt.CursorShape.CrossCursor, и обращение по старому имени падает. Плагин
работает и в QGIS 3.16, где стоит Qt 5, поэтому имя берётся тем способом,
который есть в этой сборке.

Здесь собрано только то, что нужно окнам и карте.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialogButtonBox

__all__ = ["CROSS_CURSOR", "LEFT_BUTTON", "RIGHT_BUTTON", "KEY_ESCAPE",
           "KEY_BACKSPACE", "KEY_DELETE", "KEY_S", "USER_ROLE",
           "DOCK_RIGHT", "BUTTON_CLOSE", "BUTTON_OK", "BUTTON_CANCEL",
           "BUTTON_DEFAULTS", "ROLE_ACTION", "run_dialog", "layer_filter"]


def _pick(owner, group, name):
    """Значение из области перечисления, а при её отсутствии из класса."""
    scope = getattr(owner, group, None)
    if scope is not None:
        found = getattr(scope, name, None)
        if found is not None:
            return found
    return getattr(owner, name)


CROSS_CURSOR = _pick(Qt, "CursorShape", "CrossCursor")
LEFT_BUTTON = _pick(Qt, "MouseButton", "LeftButton")
RIGHT_BUTTON = _pick(Qt, "MouseButton", "RightButton")
KEY_ESCAPE = _pick(Qt, "Key", "Key_Escape")
KEY_BACKSPACE = _pick(Qt, "Key", "Key_Backspace")
KEY_DELETE = _pick(Qt, "Key", "Key_Delete")
KEY_S = _pick(Qt, "Key", "Key_S")
USER_ROLE = _pick(Qt, "ItemDataRole", "UserRole")
DOCK_RIGHT = _pick(Qt, "DockWidgetArea", "RightDockWidgetArea")

BUTTON_CLOSE = _pick(QDialogButtonBox, "StandardButton", "Close")
BUTTON_OK = _pick(QDialogButtonBox, "StandardButton", "Ok")
BUTTON_CANCEL = _pick(QDialogButtonBox, "StandardButton", "Cancel")
BUTTON_DEFAULTS = _pick(QDialogButtonBox, "StandardButton", "RestoreDefaults")
ROLE_ACTION = _pick(QDialogButtonBox, "ButtonRole", "ActionRole")


def layer_filter(name):
    """
    Фильтр списка слоёв по виду геометрии.

    В QGIS 4 фильтры переехали в Qgis.LayerFilter, в QGIS 3 они лежали
    в QgsMapLayerProxyModel. Имя у них одно и то же.
    """
    from qgis.core import Qgis, QgsMapLayerProxyModel
    group = getattr(Qgis, "LayerFilter", None)
    if group is not None and hasattr(group, name):
        return getattr(group, name)
    return getattr(QgsMapLayerProxyModel, name)


def run_dialog(dialog):
    """Показывает окно и ждёт ответа. В Qt 5 метод назывался иначе."""
    runner = getattr(dialog, "exec", None)
    if runner is None:
        runner = dialog.exec_
    return runner()
