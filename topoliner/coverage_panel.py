# -*- coding: utf-8 -*-
"""
coverage_panel
--------------
Панель ввода контуров в покрытие.

Панель держит всё, что нужно рисованию: слой, класс будущего объекта, режим
наложения и пороги. Карта-инструмент ничего не хранит, он спрашивает панель.

Список классов берётся из обычного слоя-таблицы проекта. Своего хранилища
у панели нет намеренно. Таблица правится таблицей атрибутов QGIS, грузится
откуда угодно и живёт вместе с проектом.
"""

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsEditFormConfig,
    QgsGeometry,
    QgsProject,
    QgsSymbolLayerUtils,
    QgsWkbTypes,
)
from qgis.gui import QgsDockWidget, QgsFieldComboBox, QgsMapLayerComboBox
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .cut import MODE_CLIP, MODE_INSET, MODE_OVERLAY
from .cut_edit import apply_cut, can_cut, key_fields
from .i18n import tr
from .qt_compat import USER_ROLE, layer_filter

__all__ = ["CoveragePanel"]

ON_STYLE = "background-color: #2e7d32; color: white; font-weight: bold;"

# В QGIS 4 перечисление переехало в Qgis.AttributeFormSuppression.
try:
    from qgis.core import Qgis
    FORM_OFF = Qgis.AttributeFormSuppression.On
except AttributeError:
    FORM_OFF = QgsEditFormConfig.SuppressOn


class CoveragePanel(QgsDockWidget):
    """Панель «Покрытие». Настройки ввода контуров и список классов."""

    def __init__(self, iface, parent=None):
        QgsDockWidget.__init__(self, tr("Покрытие"), parent)
        self.setObjectName("TopolinerCoveragePanel")
        self.iface = iface
        self.watched = None
        self.busy = False
        self.pending = []
        self.form_before = None

        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # ── Слой покрытия ─────────────────────────────────────────────────
        layout.addWidget(QLabel(tr("Слой покрытия")))
        self.layer_box = QgsMapLayerComboBox(body)
        self.layer_box.setFilters(layer_filter("PolygonLayer"))
        self.layer_box.layerChanged.connect(self.layer_changed)
        layout.addWidget(self.layer_box)

        # ── Таблица классов ───────────────────────────────────────────────
        layout.addWidget(QLabel(tr("Таблица классов")))
        self.table_box = QgsMapLayerComboBox(body)
        # Таблица классов обычно без геометрии, а фильтр VectorLayer
        # такие слои не показывает.
        self.table_box.setFilters(layer_filter("VectorLayer")
                                  | layer_filter("NoGeometry"))
        self.table_box.setAllowEmptyLayer(True, tr("нет таблицы"))
        # Пока человек не выбрал таблицу, панель не должна подставлять
        # первый попавшийся слой проекта.
        self.table_box.setLayer(None)
        self.table_box.layerChanged.connect(self.table_changed)
        layout.addWidget(self.table_box)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Поле")))
        self.key_box = QgsFieldComboBox(body)
        self.key_box.fieldChanged.connect(self.reload_classes)
        row.addWidget(self.key_box, 1)
        row.addWidget(QLabel(tr("Подпись")))
        self.label_box = QgsFieldComboBox(body)
        self.label_box.setAllowEmptyFieldName(True)
        self.label_box.fieldChanged.connect(self.reload_classes)
        row.addWidget(self.label_box, 1)
        layout.addLayout(row)

        self.classes = QListWidget(body)
        self.classes.setMinimumHeight(120)
        layout.addWidget(self.classes, 1)

        self.match = QLabel("", body)
        self.match.setWordWrap(True)
        layout.addWidget(self.match)

        self.autofill = QCheckBox(tr("Автозаполнять при создании"), body)
        self.autofill.setChecked(True)
        self.autofill.setToolTip(tr(
            "Флажок снят, и после отрисовки открывается обычная форма "
            "атрибутов слоя."))
        layout.addWidget(self.autofill)

        self.apply_button = QPushButton(
            tr("Применить к выделенным объектам"), body)
        self.apply_button.clicked.connect(self.apply_to_selection)
        layout.addWidget(self.apply_button)

        # ── Режим наложения ───────────────────────────────────────────────
        layout.addWidget(QLabel(tr("Режим наложения")))
        self.modes = QButtonGroup(body)
        self.modes.setExclusive(True)
        for mode, name, hint in (
                (MODE_OVERLAY, tr("Наложение"),
                 tr("Новый объект получает весь контур, соседи урезаются.")),
                (MODE_CLIP, tr("Отсечение"),
                 tr("Новый объект ложится только в свободное место, "
                    "соседи площади не теряют.")),
                (MODE_INSET, tr("Врезка"),
                 tr("Новый объект получает только то, что лежит внутри "
                    "покрытия. Площадь покрытия не меняется."))):
            button = QPushButton(name, body)
            button.setCheckable(True)
            button.setToolTip(hint)
            button.setProperty("topoliner_mode", mode)
            self.modes.addButton(button)
            layout.addWidget(button)
        self.modes.buttons()[0].setChecked(True)

        # ── Рисование ─────────────────────────────────────────────────────
        self.draw_button = QPushButton(tr("Режим рисования: ВЫКЛ"), body)
        self.draw_button.setCheckable(True)
        self.draw_button.setToolTip(tr(
            "Включает правку слоя и штатное добавление полигона. Каждый "
            "добавленный полигон сразу обрабатывается по выбранному режиму."))
        self.draw_button.toggled.connect(self.drawing_toggled)
        layout.addWidget(self.draw_button)

        # ── Пороги ────────────────────────────────────────────────────────
        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Порог площади")))
        self.area_box = QDoubleSpinBox(body)
        self.area_box.setDecimals(4)
        self.area_box.setRange(0.0, 1e12)
        self.area_box.setValue(1.0)
        self.area_box.setToolTip(tr(
            "Остаток соседа мельче этой площади отходит контуру целиком. "
            "Кусок соседа мельче этой площади контуру не достаётся."))
        row.addWidget(self.area_box, 1)
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel(tr("Отклонение вершины от ребра")))
        self.eps_box = QDoubleSpinBox(body)
        self.eps_box.setDecimals(12)
        self.eps_box.setRange(0.0, 1.0)
        self.eps_box.setValue(1e-6)
        self.eps_box.setToolTip(tr(
            "Разрез кладёт вершину на границу соседа с третьим объектом. "
            "Узел в этой точке достраивается. Ноль отключает вставку."))
        row.addWidget(self.eps_box, 1)
        layout.addLayout(row)

        self.setWidget(body)
        self.layer_changed(self.layer_box.currentLayer())

    # ── Состояние ─────────────────────────────────────────────────────────

    def layer(self):
        return self.layer_box.currentLayer()

    def mode(self):
        button = self.modes.checkedButton()
        if button is None:
            return MODE_OVERLAY
        return button.property("topoliner_mode")

    def settings(self):
        """Пороги и способ заполнения атрибутов для карты-инструмента."""
        return {"area": self.area_box.value(),
                "node_eps": self.eps_box.value(),
                "mode": self.mode(),
                "values": self.values() if self.autofill.isChecked() else None,
                "fill": self.autofill.isChecked()}

    def values(self):
        """Значения полей выбранного класса, либо пустой словарь."""
        item = self.classes.currentItem()
        if item is None:
            return {}
        return dict(item.data(USER_ROLE) or {})

    # ── Список классов ────────────────────────────────────────────────────

    def layer_changed(self, layer):
        self.reload_classes()
        if self.draw_button.isChecked():
            self._watch(layer)

    def table_changed(self, layer):
        self._follow_table(layer)
        self.reload_classes()

    def _follow_table(self, table):
        """
        Связывает списки полей с таблицей классов.

        Вызывается и из сигнала, и перед чтением таблицы. Сигнал о смене
        слоя приходит не при всяком способе выбора, а поля обязаны отвечать
        выбранной таблице всегда.
        """
        for box in (self.key_box, self.label_box):
            if box.layer() is not table:
                box.setLayer(table)
        if table is None:
            return
        fields = table.fields()
        if len(fields) and not self.key_box.currentField():
            self.key_box.setField(fields[0].name())

    def _colors(self):
        """Цвет класса берётся из стиля слоя покрытия, по значению."""
        out = {}
        layer = self.layer()
        if layer is None:
            return out
        renderer = layer.renderer()
        if not isinstance(renderer, QgsCategorizedSymbolRenderer):
            return out
        for category in renderer.categories():
            symbol = category.symbol()
            if symbol is None:
                continue
            key = "" if category.value() is None else str(category.value())
            out[key] = QIcon(QgsSymbolLayerUtils.symbolPreviewPixmap(
                symbol, QSize(16, 16)))
        return out

    def _plain_icon(self):
        pixmap = QPixmap(16, 16)
        pixmap.fill(QColor(210, 210, 210))
        return QIcon(pixmap)

    def reload_classes(self):
        """Перечитывает таблицу классов и показывает, что будет заполнено."""
        self.classes.clear()
        table = self.table_box.currentLayer()
        self._follow_table(table)
        key = self.key_box.currentField()
        if table is None:
            self.match.setText(tr("Таблица классов не выбрана. Новый объект "
                                  "возьмёт атрибуты у соседей."))
            return
        if not key:
            self.match.setText(tr("Поле класса не выбрано."))
            return

        label_field = self.label_box.currentField()
        colors = self._colors()
        plain = self._plain_icon()
        filled = self._filled_names(table)

        seen = set()
        for feature in table.getFeatures():
            value = feature.attribute(key)
            if value is None:
                continue
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            title = text
            if label_field:
                other = feature.attribute(label_field)
                if other is not None and str(other) != text:
                    title = "%s   %s" % (text, other)
            item = QListWidgetItem(colors.get(text, plain), title)
            item.setData(USER_ROLE, self._row_values(feature, filled))
            self.classes.addItem(item)

        if self.classes.count():
            self.classes.setCurrentRow(0)
        if filled:
            self.match.setText(tr("Заполняются поля: %s") % ", ".join(filled))
        else:
            self.match.setText(tr("Совпадающих полей у таблицы и слоя нет. "
                                  "Класс записать некуда."))

    def _filled_names(self, table):
        """Поля таблицы, имена которых есть и в слое покрытия."""
        layer = self.layer()
        if layer is None:
            return []
        keys = key_fields(layer.fields(), layer)
        target = {layer.fields()[i].name() for i in range(len(layer.fields()))
                  if i not in keys}
        return [f.name() for f in table.fields() if f.name() in target]

    def _row_values(self, feature, filled):
        out = {}
        for name in filled:
            value = feature.attribute(name)
            if value is not None:
                out[name] = value
        return out

    # ── Действия ──────────────────────────────────────────────────────────

    def drawing_toggled(self, on):
        self.draw_button.setText(
            tr("Режим рисования: ВКЛ") if on else tr("Режим рисования: ВЫКЛ"))
        self.draw_button.setStyleSheet(ON_STYLE if on else "")
        if on:
            self._watch(self.layer())
        else:
            self._unwatch()

    def _watch(self, layer):
        """Начинает следить за слоем и включает штатное рисование."""
        self._unwatch()
        if layer is None or layer.geometryType() != QgsWkbTypes.PolygonGeometry:
            self.iface.messageBar().pushWarning(
                tr("Покрытие"), tr("Нужен слой полигонов."))
            self.draw_button.setChecked(False)
            return
        if not layer.isEditable():
            layer.startEditing()
        self.watched = layer
        layer.featureAdded.connect(self.feature_added)
        layer.editCommandEnded.connect(self.command_ended)
        self.pending = []
        self._set_form_hidden(layer, self.autofill.isChecked())
        self.iface.setActiveLayer(layer)
        self.iface.actionAddFeature().trigger()

    def _unwatch(self):
        layer = self.watched
        self.watched = None
        if layer is None:
            return
        try:
            layer.featureAdded.disconnect(self.feature_added)
            layer.editCommandEnded.disconnect(self.command_ended)
            self._set_form_hidden(layer, None)
        except (RuntimeError, TypeError):
            # Слой уже удалён из проекта либо подключения не было.
            self.form_before = None

    def _set_form_hidden(self, layer, hidden):
        """
        Прячет форму атрибутов на время автозаполнения.

        Значение None возвращает слою настройку, которая была до панели.
        """
        config = layer.editFormConfig()
        if hidden is None:
            if self.form_before is None:
                return
            config.setSuppress(self.form_before)
            self.form_before = None
        else:
            if self.form_before is None:
                self.form_before = config.suppress()
            config.setSuppress(FORM_OFF if hidden else self.form_before)
        layer.setEditFormConfig(config)

    def feature_added(self, fid):
        """
        Полигон добавлен штатным инструментом. Запоминает его до конца команды.

        Править слой прямо отсюда нельзя. Сигнал приходит изнутри команды
        правки QGIS, и вложенные в неё изменения ломают стек отмены: отмена
        такого шага роняет программу с нарушением доступа.
        """
        layer = self.watched
        if self.busy or layer is None:
            return
        feature = layer.getFeature(fid)
        self.pending.append((QgsGeometry(feature.geometry()),
                             feature.attributes()))

    def command_ended(self):
        """
        Команда QGIS закончилась. Заменяет её одной своей.

        Добавление полигона отменяется, и тот же контур вводится заново уже
        вместе с обрезкой соседей. В стеке отмены остаётся один шаг.
        """
        layer = self.watched
        if self.busy or layer is None or not self.pending:
            return
        pending, self.pending = self.pending, []
        if len(pending) != 1:
            # Вставка из буфера и подобное. Это не рисование, не трогаем.
            return
        geometry, row = pending[0]
        self.busy = True
        try:
            layer.undoStack().undo()
            fill = self.autofill.isChecked()
            report = apply_cut(
                layer, geometry,
                area_threshold=self.area_box.value(),
                node_eps=self.eps_box.value(), mode=self.mode(),
                values=self.values() if fill else None,
                row=None if fill else row)
        finally:
            self.busy = False
        layer.triggerRepaint()
        if report["error"]:
            self.iface.messageBar().pushWarning(tr("Покрытие"), report["error"])

    def tool_deactivated(self):
        """Оставлено для совместимости со старым инструментом рисования."""
        if self.draw_button.isChecked():
            self.draw_button.setChecked(False)

    def apply_to_selection(self):
        """Записывает выбранный класс в выделенные объекты."""
        layer = self.layer()
        problem = can_cut(layer)
        if problem:
            self.iface.messageBar().pushWarning(tr("Покрытие"), problem)
            return
        values = self.values()
        if not values:
            self.iface.messageBar().pushWarning(
                tr("Покрытие"), tr("Класс не выбран."))
            return
        ids = layer.selectedFeatureIds()
        if not ids:
            self.iface.messageBar().pushWarning(
                tr("Покрытие"), tr("Не выделено ни одного объекта."))
            return

        fields = layer.fields()
        layer.beginEditCommand(tr("Класс выделенным объектам"))
        done = 0
        for fid in ids:
            for name, value in values.items():
                index = fields.indexOf(name)
                if index >= 0:
                    layer.changeAttributeValue(fid, index, value)
            done += 1
        layer.endEditCommand()
        layer.triggerRepaint()
        self.iface.messageBar().pushInfo(
            tr("Покрытие"), tr("Класс записан объектам: %d") % done)
