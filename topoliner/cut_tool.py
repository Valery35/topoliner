# -*- coding: utf-8 -*-
"""
cut_tool
--------
Рисование контура по карте и ввод его в слой.

Инструмент нужен там, где оболочка Processing неудобна. Человек правит
покрытие в режиме редактирования и вводит контур сразу, не выходя из правки
и не собирая для этого отдельный слой.

Щелчки дают прямые отрезки, удержание кнопки рисует от руки. Сглаживание
переключается клавишей S и флажком в панели. Правая кнопка замыкает контур.

Сама правка живёт в cut_edit, настройки в панели. Здесь только сбор вершин,
прилипание и сообщения.
"""

from qgis.core import QgsGeometry, QgsPointXY, QgsWkbTypes
from qgis.gui import QgsMapTool, QgsRubberBand
from qgis.PyQt.QtGui import QColor

from .cut_edit import apply_cut, can_cut
from .i18n import tr
from .qt_compat import (CROSS_CURSOR, KEY_BACKSPACE, KEY_DELETE, KEY_ESCAPE,
                        KEY_S, LEFT_BUTTON, RIGHT_BUTTON)

__all__ = ["CutMapTool"]

# Порог в точках экрана, начиная с которого движение считается рисованием
# от руки, а не дрожанием руки на щелчке.
DRAG_PIXELS = 4

# Сглаживание. Один проход Чайкина с четвертью отрезка скругляет углы
# и не уводит контур далеко от нарисованного.
SMOOTH_PASSES = 1
SMOOTH_OFFSET = 0.25


class CutMapTool(QgsMapTool):
    """
    Рисует контур и вводит его в слой покрытия.

    Левая кнопка ставит вершину, удержание с движением рисует от руки,
    правая замыкает контур. Backspace снимает последнюю вершину, Esc
    отменяет рисование. Клавиша S переключает сглаживание. Вершина
    прилипает к тому, к чему настроено прилипание в проекте.
    """

    def __init__(self, iface, panel):
        canvas = iface.mapCanvas()
        QgsMapTool.__init__(self, canvas)
        self.iface = iface
        self.canvas = canvas
        self.panel = panel
        self.points = []
        self.dragging = False
        self.press_pos = None
        self.band = QgsRubberBand(canvas, QgsWkbTypes.PolygonGeometry)
        self.band.setColor(QColor(220, 80, 20, 200))
        self.band.setFillColor(QColor(220, 80, 20, 40))
        self.band.setWidth(2)
        self.setCursor(CROSS_CURSOR)

    # ── Сбор вершин ───────────────────────────────────────────────────────

    def _snapped(self, event):
        """Точка щелчка с учётом прилипания."""
        match = self.canvas.snappingUtils().snapToMap(event.pos())
        if match.isValid():
            return QgsPointXY(match.point())
        return self.toMapCoordinates(event.pos())

    def _smoothing(self):
        return bool(self.panel is not None
                    and self.panel.settings().get("smooth"))

    def contour(self, extra=None):
        """Нарисованный контур как геометрия, либо None."""
        points = list(self.points)
        if extra is not None:
            points.append(extra)
        if len(points) < 3:
            return None
        geometry = QgsGeometry.fromPolygonXY([points])
        if geometry is None or geometry.isEmpty():
            return None
        if self._smoothing():
            smoothed = geometry.smooth(SMOOTH_PASSES, SMOOTH_OFFSET)
            if smoothed is not None and not smoothed.isEmpty():
                return smoothed
        return geometry

    def _draw(self, extra=None):
        self.band.reset(QgsWkbTypes.PolygonGeometry)
        geometry = self.contour(extra)
        if geometry is not None:
            self.band.setToGeometry(geometry, None)
            return
        points = list(self.points)
        if extra is not None:
            points.append(extra)
        for point in points:
            self.band.addPoint(point, point is points[-1])

    def canvasPressEvent(self, event):
        if event.button() == LEFT_BUTTON:
            self.press_pos = event.pos()
            self.dragging = False

    def canvasMoveEvent(self, event):
        if event.buttons() & LEFT_BUTTON and self.press_pos is not None:
            moved = (abs(event.pos().x() - self.press_pos.x())
                     + abs(event.pos().y() - self.press_pos.y()))
            if self.dragging or moved >= DRAG_PIXELS:
                self.dragging = True
                self.points.append(self.toMapCoordinates(event.pos()))
                self._draw()
            return
        if self.points:
            self._draw(self.toMapCoordinates(event.pos()))

    def canvasReleaseEvent(self, event):
        if event.button() == RIGHT_BUTTON:
            self.finish()
            return
        if event.button() != LEFT_BUTTON:
            return
        if self.dragging:
            # Рисование от руки уже положило вершины по пути курсора.
            self.dragging = False
            self.press_pos = None
            self._draw()
            return
        self.press_pos = None
        self.points.append(self._snapped(event))
        self._draw()

    def keyPressEvent(self, event):
        if event.key() == KEY_ESCAPE:
            self.reset()
        elif event.key() in (KEY_BACKSPACE, KEY_DELETE):
            if self.points:
                self.points.pop()
                self._draw()
        elif event.key() == KEY_S and self.panel is not None:
            self.panel.smooth.setChecked(not self.panel.smooth.isChecked())
            self._draw()

    def deactivate(self):
        self.reset()
        if self.panel is not None:
            self.panel.tool_deactivated()
        QgsMapTool.deactivate(self)

    def reset(self):
        self.points = []
        self.dragging = False
        self.press_pos = None
        self.band.reset(QgsWkbTypes.PolygonGeometry)

    # ── Ввод контура ──────────────────────────────────────────────────────

    def warn(self, text):
        self.iface.messageBar().pushWarning(tr("Покрытие"), text)

    def _form(self, layer):
        """Обработчик подтверждения через обычную форму атрибутов слоя."""
        def ask(feature):
            return bool(self.iface.openFeatureForm(layer, feature, False))
        return ask

    def finish(self):
        geometry = self.contour()
        if geometry is None:
            self.reset()
            self.warn(tr("Контуру нужно не меньше трёх вершин."))
            return

        layer = self.panel.layer() if self.panel is not None \
            else self.iface.activeLayer()
        problem = can_cut(layer)
        if problem:
            self.reset()
            self.warn(problem)
            return

        settings = self.panel.settings() if self.panel is not None else {}
        confirm = self._form(layer) if settings.get("ask_form") else None
        report = apply_cut(
            layer, geometry,
            area_threshold=settings.get("area", 1.0),
            node_eps=settings.get("node_eps", 1e-6),
            mode=settings.get("mode", "overlay"),
            values=settings.get("values"),
            confirm=confirm)
        self.reset()

        if report["error"]:
            self.warn(report["error"])
            return

        layer.triggerRepaint()
        self.canvas.refresh()
        self.iface.messageBar().pushInfo(
            tr("Покрытие"),
            tr("Изменено %d, добавлено %d, удалено %d, узлов вставлено %d")
            % (report["changed"], report["added"] + report["pieces"],
               report["deleted"], report["nodes"]))
