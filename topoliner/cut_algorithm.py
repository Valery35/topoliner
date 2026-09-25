# -*- coding: utf-8 -*-
"""
Processing-алгоритм врезки контуров в покрытие.

  CutIntoCoverageAlgorithm   1.08, оболочка над cut.cut_into_coverage

Геометрия врезки живёт в cut и покрыта тестами. Здесь чтение слоёв,
последовательное применение контуров, наследование атрибутов, возврат
отметок Z и печать отчёта.

Контуры применяются по одному. Результат каждой врезки входит в покрытие
до начала следующей, поэтому два перекрывающихся контура не накладываются
друг на друга.
"""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)

from .cut import cut_into_coverage
from .cut_edit import inherited_values, key_fields
from .help_texts import help_for
from .i18n import tr
from .rounding import fmt
from .branding import banner, help_footer, help_url
from .geom_backend import QgisBackend
from .topo_algorithm import assemble, explode
from .z_restore import edges_from, restore_z


# ────────────────────────────────────────────────────────────────────────────
# Общее
# ────────────────────────────────────────────────────────────────────────────

def _bbox(parts):
    """Габариты набора частей. Внешнего кольца достаточно."""
    x_min = y_min = x_max = y_max = None
    for rings in parts:
        if not rings:
            continue
        for x, y in ((v[0], v[1]) for v in rings[0]):
            if x_min is None or x < x_min:
                x_min = x
            if x_max is None or x > x_max:
                x_max = x
            if y_min is None or y < y_min:
                y_min = y
            if y_max is None or y > y_max:
                y_max = y
    if x_min is None:
        return None
    return (x_min, y_min, x_max, y_max)


def _overlap(one, two):
    """Пересекаются ли габариты. Отбор перед врезкой идёт по ним."""
    if one is None or two is None:
        return False
    return not (one[2] < two[0] or two[2] < one[0]
                or one[3] < two[1] or two[3] < one[1])


def _read(source, feedback, start, span):
    """Слой в список (fid, parts), объекты по идентификатору и площадь."""
    items = []
    originals = {}
    total_area = 0.0
    total = source.featureCount() or 1
    for i, feat in enumerate(source.getFeatures()):
        if feedback.isCanceled():
            return None, None, 0.0
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            continue
        parts = explode(geom, True)
        if not parts:
            continue
        items.append((feat.id(), parts))
        originals[feat.id()] = feat
        total_area += geom.area()
        if i % 500 == 0:
            feedback.setProgress(start + span * i / total)
    return items, originals, total_area


# ────────────────────────────────────────────────────────────────────────────
# Врезка
# ────────────────────────────────────────────────────────────────────────────

class CutIntoCoverageAlgorithm(QgsProcessingAlgorithm):
    """
    Врезает контуры в полигональное покрытие.

    Обычная врезка средствами редактора режет соседей и новый объект двумя
    независимыми действиями, и кромка разреза у них расходится. Здесь кромка
    приходит из одного наложения и достаётся обеим сторонам одинаковой.
    """

    INPUT = "INPUT"
    CUT = "CUT"
    AREA = "AREA"
    NODE_EPS = "NODE_EPS"
    KEEP_Z = "KEEP_Z"
    OUTPUT = "OUTPUT"

    def name(self):
        return "cutintocoverage"

    def displayName(self):
        return tr("1.08 Врезка контуров в покрытие")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return CutIntoCoverageAlgorithm()

    def helpUrl(self):
        return help_url()

    def shortHelpString(self):
        return help_for("cutintocoverage") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Покрытие (полигоны)"),
            [QgsProcessing.TypeVectorPolygon]))

        p = QgsProcessingParameterFeatureSource(
            self.CUT, tr("Врезаемые контуры (полигоны)"),
            [QgsProcessing.TypeVectorPolygon])
        p.setHelp(
            "Каждый объект слоя это отдельный контур. Контуры применяются\n"
            "по одному, в порядке слоя, и результат каждого входит в покрытие\n"
            "до начала следующего. Линию перед врезкой превращают в полигон\n"
            "построением буфера."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.AREA, tr("Порог площади (в кв. единицах CRS)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0,
            minValue=0.0)
        p.setHelp(
            "Остаток соседа мельче этой площади не оставляется отдельным\n"
            "объектом, а отходит контуру целиком. Кусок соседа мельче этой\n"
            "площади контуру не достаётся, и сосед остаётся как был.\n"
            "Ноль режет всё, что пересеклось, вплоть до осколков в микроны."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.NODE_EPS, tr("Допустимое отклонение вершины от ребра"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1e-6,
            minValue=0.0)
        p.setHelp(
            "Разрез кладёт вершину на границу соседа с третьим объектом,\n"
            "и у этого третьего узла в той точке нет. Инструмент достраивает\n"
            "такие узлы, как это делает инструмент 1.06. Узел ставится\n"
            "в проекцию точки на ребро, поэтому форма и площадь не меняются.\n"
            "Ноль отключает вставку, и врезка оставит нарушение после себя."
        )
        self.addParameter(p)

        p = QgsProcessingParameterBoolean(
            self.KEEP_Z, tr("Восстанавливать отметки Z"), defaultValue=True)
        p.setHelp(
            "Наложение работает в плане, поэтому отметка вершины берётся\n"
            "с ближайшего исходного ребра. Вершина на середине ребра получает\n"
            "отметку, посчитанную вдоль этого ребра. Объекты, которых врезка\n"
            "не коснулась, переносятся без изменения."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Покрытие с врезкой")))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать покрытие.")
        cutter = self.parameterAsSource(parameters, self.CUT, context)
        if cutter is None:
            raise QgsProcessingException("Не удалось прочитать слой контуров.")

        area = self.parameterAsDouble(parameters, self.AREA, context)
        node_eps = self.parameterAsDouble(parameters, self.NODE_EPS, context)
        keep_z = self.parameterAsBoolean(parameters, self.KEEP_Z, context)
        with_z = QgsWkbTypes.hasZ(source.wkbType()) and keep_z

        # Инструменты топологии обязаны принимать некорректную геометрию:
        # именно её они и встречают в покрытиях.
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)

        items, originals, area_before = _read(source, feedback, 0.0, 5.0)
        if items is None:
            return {}
        if not items:
            raise QgsProcessingException("В покрытии нет геометрий.")

        cuts, _cut_originals, _cut_area = _read(cutter, feedback, 5.0, 5.0)
        if cuts is None:
            return {}
        if not cuts:
            raise QgsProcessingException("В слое контуров нет геометрий.")

        backend = QgisBackend()
        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Объектов %d, контуров %d, порог площади %g")
                          % (len(items), len(cuts), area))

        # ── Состояние покрытия ────────────────────────────────────────────
        objects = {}
        order = []
        for fid, parts in items:
            objects[fid] = {
                "parts": parts,
                "values": originals[fid].attributes(),
                "bbox": _bbox(parts),
                "fresh": False,
            }
            order.append(fid)

        field_count = len(source.fields())
        keys = key_fields(
            source.fields(),
            self.parameterAsVectorLayer(parameters, self.INPUT, context))
        next_key = -1
        outside_total = 0.0
        added = 0
        swallowed = 0
        changed_count = 0
        nodes_total = 0

        for number, (_cut_fid, cut_parts) in enumerate(cuts, 1):
            if feedback.isCanceled():
                return {}
            box = _bbox(cut_parts)
            near = [key for key in order
                    if key in objects and _overlap(objects[key]["bbox"], box)]
            done = cut_into_coverage(
                backend, [(key, objects[key]["parts"]) for key in near],
                cut_parts, area_threshold=area, node_eps=node_eps)

            # Атрибуты снимаются до правки: поглощённый сосед исчезает.
            rows = []
            for key in done["donors"]:
                record = objects.get(key)
                if record is not None:
                    rows.append(record["values"])

            for key, parts in done["changed"].items():
                if parts:
                    objects[key]["parts"] = parts
                    objects[key]["bbox"] = _bbox(parts)
                    objects[key]["fresh"] = True
                    changed_count += 1
                else:
                    del objects[key]
                    swallowed += 1

            for key, parts in done["noded"].items():
                if key in objects and parts:
                    objects[key]["parts"] = parts
                    objects[key]["fresh"] = True
            nodes_total += done["nodes"]

            if done["created"]:
                key = next_key
                next_key -= 1
                objects[key] = {
                    "parts": done["created"],
                    "values": inherited_values(rows, field_count, keys),
                    "bbox": _bbox(done["created"]),
                    "fresh": True,
                }
                order.append(key)
                added += 1

            outside_total += done["outside"]
            if len(cuts) <= 20:
                feedback.pushInfo(
                    tr("Контур %d: соседей затронуто %d, вне покрытия %s")
                    % (number, len(done["donors"]), fmt(done["outside"])))
            feedback.setProgress(10.0 + 70.0 * number / len(cuts))

        # ── Отметки Z ─────────────────────────────────────────────────────
        index = None
        if with_z:
            sources = [parts for _fid, parts in items]
            # Контур без отметок дал бы рёбра с нулём, и они перебили бы
            # исходные отметки покрытия вдоль всей кромки разреза.
            if QgsWkbTypes.hasZ(cutter.wkbType()):
                sources.extend(parts for _fid, parts in cuts)
            index = edges_from(sources)

        # ── Запись ────────────────────────────────────────────────────────
        out_wkb = QgsWkbTypes.multiType(
            QgsWkbTypes.zmType(QgsWkbTypes.Polygon, with_z, False))
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(),
            out_wkb, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        written = 0
        area_after = 0.0
        for key in order:
            if feedback.isCanceled():
                return {}
            record = objects.get(key)
            if record is None or not record["parts"]:
                continue
            parts = record["parts"]
            if index is not None and record["fresh"]:
                parts = restore_z(parts, index)
            geom = assemble(parts, True, True, with_z)
            if geom is None or geom.isEmpty():
                continue
            feat = QgsFeature(source.fields())
            feat.setAttributes(list(record["values"]))
            feat.setGeometry(geom)
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            written += 1
            area_after += geom.area()

        # ── Отчёт ─────────────────────────────────────────────────────────
        feedback.setProgress(95)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Результат ──"))
        feedback.pushInfo(tr("Контуров врезано:            %d") % len(cuts))
        feedback.pushInfo(tr("Объектов изменено:           %d") % changed_count)
        feedback.pushInfo(tr("Объектов поглощено целиком:  %d") % swallowed)
        feedback.pushInfo(tr("Объектов добавлено:          %d") % added)
        feedback.pushInfo(tr("Узлов вставлено соседям:     %d") % nodes_total)
        feedback.pushInfo("")
        feedback.pushInfo(tr("Площадь до/после: %s / %s")
                          % (fmt(area_before), fmt(area_after)))
        feedback.pushInfo(tr("Легло вне покрытия: %s") % fmt(outside_total))
        feedback.pushInfo(tr("Объектов на входе/выходе: %d / %d")
                          % (len(items), written))

        gap = area_after - area_before - outside_total
        if abs(gap) > max(1e-6, 1e-9 * max(area_before, 1.0)):
            feedback.pushWarning(
                tr("Расхождение площади: %s. Врезка обязана площадь только "
                   "перераспределять.") % fmt(gap))

        return {self.OUTPUT: dest_id}
