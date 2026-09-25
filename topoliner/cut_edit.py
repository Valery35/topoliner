# -*- coding: utf-8 -*-
"""
cut_edit
--------
Ввод нарисованного контура в слой через буфер правок.

Оболочка Processing выдаёт новый слой, а редактор правит тот, что открыт.
Правки идут через буфер редактирования слоя одной командой, поэтому отмена
в QGIS возвращает покрытие целиком, а не по объекту.

Геометрия живёт в cut и покрыта тестами. Здесь чтение соседей, атрибуты
нового объекта, возврат отметок Z и запись в буфер.
"""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsWkbTypes,
)

from .cut import MODE_CLIP, MODE_INSET, MODE_OVERLAY, cut_into_coverage
from .geom_backend import QgisBackend
from .i18n import tr
from .topo_algorithm import assemble, explode
from .z_restore import edges_from, restore_z

__all__ = ["apply_cut", "can_cut", "attributes_for", "inherited_values",
           "key_fields", "MODE_CLIP", "MODE_INSET", "MODE_OVERLAY"]


# ────────────────────────────────────────────────────────────────────────────
# Атрибуты
# ────────────────────────────────────────────────────────────────────────────

def _is_null(value):
    """Пусто ли значение. NULL приходит из QGIS отдельным объектом."""
    if value is None:
        return True
    check = getattr(value, "isNull", None)
    if check is None:
        return False
    return bool(check())


def _same(one, two):
    if _is_null(one) or _is_null(two):
        return _is_null(one) and _is_null(two)
    return one == two


def key_fields(fields, layer=None):
    """
    Номера полей, которые новому объекту не переносятся.

    Ключ слоя обязан быть уникальным. Унаследованный ключ совпал бы
    с ключом соседа, и запись такого объекта отклоняется хранилищем.
    Поле fid служит ключом в GeoPackage, поэтому оно исключается всегда.
    """
    keys = set()
    for i, field in enumerate(fields):
        if field.name().lower() == "fid":
            keys.add(i)
    if layer is not None:
        for i in layer.primaryKeyAttributes():
            if 0 <= i < len(fields):
                keys.add(i)
    return keys


def inherited_values(rows, count, keys=()):
    """
    Атрибуты, унаследованные от соседей.

    Поле, у которого все отдавшие площадь соседи имеют одно значение,
    получает это значение. Поле с разными значениями остаётся пустым,
    потому что выбрать между соседями инструмент не может. Ключ слоя
    остаётся пустым всегда.
    """
    if not rows:
        return [None] * count
    out = []
    first = rows[0]
    for i in range(count):
        if i in keys:
            out.append(None)
            continue
        value = first[i] if i < len(first) else None
        for row in rows[1:]:
            other = row[i] if i < len(row) else None
            if not _same(value, other):
                value = None
                break
        out.append(None if _is_null(value) else value)
    return out


def attributes_for(fields, rows, keys=(), values=None):
    """
    Атрибуты нового объекта.

    Основа это наследование от соседей, поверх неё ложатся значения класса.
    Класс задан человеком, поэтому он старше унаследованного.
    """
    out = inherited_values(rows, len(fields), keys)
    if not values:
        return out
    for i, field in enumerate(fields):
        if i in keys:
            continue
        name = field.name()
        if name in values:
            out[i] = values[name]
    return out


# ────────────────────────────────────────────────────────────────────────────
# Ввод контура в буфер правок
# ────────────────────────────────────────────────────────────────────────────

def can_cut(layer):
    """Готов ли слой к правке. Возвращает пояснение либо пустую строку."""
    if layer is None:
        return tr("Слой не выбран.")
    if layer.geometryType() != QgsWkbTypes.PolygonGeometry:
        return tr("Нужен слой полигонов.")
    if not layer.isEditable():
        return tr("Слой не в режиме редактирования.")
    return ""


def _area_of(backend, parts):
    total = 0.0
    for rings in parts:
        if rings:
            geometry = backend.polygon(list(rings))
            if geometry is not None:
                total += backend.area(geometry)
    return total


def apply_cut(layer, cut_geometry, area_threshold=1.0, node_eps=1e-6,
              keep_z=True, label=None, mode=MODE_OVERLAY, values=None,
              confirm=None):
    """
    Вводит нарисованный контур в слой.

    layer          QgsVectorLayer в режиме редактирования
    cut_geometry   QgsGeometry нарисованного контура
    area_threshold остаток мельче этой площади молча отходит соседу
    node_eps       отклонение при вставке недостающих узлов
    keep_z         возвращать ли отметки Z
    label          название команды правки для отмены
    mode           режим наложения из cut
    values         {имя поля: значение} для нового объекта, либо None
    confirm        вызываемый объект feature -> bool. Вызывается до правки,
                   ответ False отменяет её целиком. Через него открывают
                   обычную форму атрибутов слоя

    Возвращает словарь отчёта. Ключ error непустой, если правка
    не выполнялась.
    """
    report = {"error": "", "changed": 0, "deleted": 0, "added": 0,
              "noded": 0, "nodes": 0, "pieces": 0, "outside": 0.0,
              "dropped": 0.0, "area_before": 0.0, "area_after": 0.0,
              "donors": 0, "mode": mode}

    problem = can_cut(layer)
    if problem:
        report["error"] = problem
        return report
    if cut_geometry is None or cut_geometry.isEmpty():
        report["error"] = tr("Контур пуст.")
        return report

    with_z = QgsWkbTypes.hasZ(layer.wkbType()) and keep_z
    is_multi = QgsWkbTypes.isMultiType(layer.wkbType())

    cut_parts = explode(cut_geometry, True)
    if not cut_parts:
        report["error"] = tr("Контур не даёт ни одного кольца.")
        return report

    # Соседи берутся по габаритам контура. Вершина разреза ложится на границу
    # внутри этих габаритов, поэтому объект, которому нужен узел, сюда попадает.
    rect = cut_geometry.boundingBox()
    rect.grow(max(node_eps * 10.0, 1e-6))
    request = QgsFeatureRequest(rect)
    request.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)

    items = []
    originals = {}
    for feat in layer.getFeatures(request):
        geometry = feat.geometry()
        if geometry is None or geometry.isEmpty():
            continue
        parts = explode(geometry, True)
        if not parts:
            continue
        items.append((feat.id(), parts))
        originals[feat.id()] = feat

    backend = QgisBackend()
    done = cut_into_coverage(backend, items, cut_parts,
                             area_threshold=area_threshold,
                             node_eps=node_eps, mode=mode)
    if not done["created"] and not done["changed"]:
        report["error"] = tr("Контур ничего не изменил.")
        return report

    index = None
    if with_z:
        sources = [parts for _fid, parts in items]
        if QgsWkbTypes.hasZ(cut_geometry.wkbType()):
            sources.append(cut_parts)
        index = edges_from(sources)

    def build(parts, multi):
        if index is not None:
            parts = restore_z(parts, index)
        return assemble(parts, True, multi, with_z)

    fields = layer.fields()
    keys = key_fields(fields, layer)
    rows = [originals[fid].attributes() for fid in done["donors"]
            if fid in originals]

    # ── Новый объект готовится до правки ──────────────────────────────────
    # Форма атрибутов может быть отменена, и тогда соседи обязаны остаться
    # нетронутыми.
    new_feature = None
    if done["created"]:
        geometry = build(done["created"], is_multi)
        if geometry is not None:
            new_feature = QgsFeature(fields)
            new_feature.setAttributes(attributes_for(fields, rows, keys, values))
            new_feature.setGeometry(geometry)

    if new_feature is not None and confirm is not None:
        if not confirm(new_feature):
            report["error"] = tr("Отменено.")
            return report

    layer.beginEditCommand(label or tr("Ввод контура"))

    for fid, parts in done["changed"].items():
        if not parts:
            layer.deleteFeature(fid)
            report["deleted"] += 1
            continue
        pieces = parts if (is_multi or len(parts) == 1) else \
            sorted(parts, key=lambda p: _area_of(backend, [p]), reverse=True)
        if is_multi or len(pieces) == 1:
            geometry = build(pieces, is_multi)
            if geometry is not None:
                layer.changeGeometry(fid, geometry)
                report["changed"] += 1
            continue
        # Слой однокомпонентный, а остаток распался. Первый кусок остаётся
        # за объектом, остальные становятся отдельными объектами с теми же
        # атрибутами. Так же поступает разрезание объектов в QGIS.
        geometry = build([pieces[0]], False)
        if geometry is not None:
            layer.changeGeometry(fid, geometry)
            report["changed"] += 1
        source = originals.get(fid)
        for piece in pieces[1:]:
            extra = build([piece], False)
            if extra is None:
                continue
            feat = QgsFeature(fields)
            row = list(source.attributes()) if source is not None \
                else [None] * len(fields)
            for i in keys:
                if i < len(row):
                    row[i] = None
            feat.setAttributes(row)
            feat.setGeometry(extra)
            layer.addFeature(feat)
            report["pieces"] += 1

    for fid, parts in done["noded"].items():
        geometry = build(parts, is_multi)
        if geometry is not None:
            layer.changeGeometry(fid, geometry)
            report["noded"] += 1

    if new_feature is not None:
        layer.addFeature(new_feature)
        report["added"] += 1

    layer.endEditCommand()

    report["nodes"] = done["nodes"]
    report["donors"] = len(done["donors"])
    report["outside"] = done["outside"]
    report["dropped"] = done["dropped"]
    report["area_before"] = done["area_before"]
    report["area_after"] = done["area_after"]
    return report
