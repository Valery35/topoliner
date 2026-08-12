# -*- coding: utf-8 -*-
"""
TopologySimplifyAlgorithm
-------------------------
Упрощение полигонального слоя с сохранением общих границ.
"""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsPoint,
    QgsLineString,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsFeatureSink,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)

from .help_texts import help_for
from .i18n import tr
from qgis.PyQt.QtCore import QVariant

from . import boundaries
from .branding import banner, help_footer, help_url
from .topo_algorithm import assemble, explode
from .topo_simplify import simplify_topology


class TopologySimplifyAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    TOLERANCE = "TOLERANCE"
    GRID = "GRID"
    MIN_POINTS = "MIN_POINTS"
    SMOOTH = "SMOOTH"
    FIELDS = "FIELDS"
    KEEP_Z = "KEEP_Z"
    OUTPUT = "OUTPUT"

    def name(self):
        return "topologysimplify"

    def displayName(self):
        return tr("2.01 Топологическое упрощение")

    def group(self):
        return tr("2. Генерализация")

    def groupId(self):
        return "generalization"

    def createInstance(self):
        return TopologySimplifyAlgorithm()

    def helpUrl(self):
        return help_url()

    def shortHelpString(self):
        return help_for("topologysimplify") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Входной слой (полигоны или линии)"),
            [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine]))

        p = QgsProcessingParameterNumber(
            self.TOLERANCE, tr("Допуск упрощения (в единицах CRS слоя)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.0)
        p.setHelp(
            "Предельное отклонение упрощённой линии от исходной.\n"
            "Ноль означает, что ничего не прореживается."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.MIN_POINTS, tr("Не упрощать дуги короче, вершин"),
            type=QgsProcessingParameterNumber.Integer, defaultValue=0, minValue=0)
        p.setHelp(
            "Защита коротких участков границы. Ноль отключает её."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.SMOOTH, tr("Сглаживание, число проходов (0 - без сглаживания)"),
            type=QgsProcessingParameterNumber.Integer, defaultValue=0,
            minValue=0, maxValue=5)
        p.setHelp(
            "Срезание углов по схеме Чайкина после прореживания.\n"
            "Линия остаётся внутри исходной, поэтому выбросов и новых\n"
            "самопересечений не возникает. Сглаживание идёт по тем же дугам,\n"
            "поэтому общая граница соседей остаётся общей.\n"
            "Каждый проход примерно удваивает число вершин, обычно хватает\n"
            "одного или двух."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.GRID, tr("Точность опознания общих вершин"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=1e-6, minValue=1e-12)
        p.setHelp(
            "Вершины, отстоящие меньше этой величины, считаются одной.\n"
            "Нужно, когда соседи записаны с разной точностью координат.\n"
            "Это не допуск упрощения, задавать метры здесь не следует."
        )
        self.addParameter(p)

        p = QgsProcessingParameterField(
            self.FIELDS, tr("Поле или поля группировки (необязательно)"),
            parentLayerParameterName=self.INPUT, allowMultiple=True, optional=True)
        p.setHelp(
            "Границы объектов разных групп общими не считаются.\n"
            "Нужно, когда в одном слое лежат несколько покрытий."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterBoolean(
            self.KEEP_Z, tr("Сохранять отметки Z"), defaultValue=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Упрощённый слой")))

    def processAlgorithm(self, parameters, context, feedback):
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        grid = self.parameterAsDouble(parameters, self.GRID, context)
        min_points = self.parameterAsInt(parameters, self.MIN_POINTS, context) or None
        smooth = self.parameterAsInt(parameters, self.SMOOTH, context)
        names = self.parameterAsFields(parameters, self.FIELDS, context)
        keep_z = self.parameterAsBoolean(parameters, self.KEEP_Z, context)

        wkb = source.wkbType()
        is_multi = QgsWkbTypes.isMultiType(wkb)
        is_polygon = (QgsWkbTypes.geometryType(wkb)
                      == QgsWkbTypes.PolygonGeometry)
        with_z = QgsWkbTypes.hasZ(wkb) and keep_z

        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Чтение слоя..."))

        records = []
        groups = {}
        area_before = 0.0
        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                return {}
            geom = feat.geometry()
            parts = explode(geom, with_z)
            if not parts:
                records.append((feat, None, None))
                continue
            area_before += geom.area() if is_polygon else geom.length()
            key = " | ".join("" if feat[n] is None else str(feat[n]) for n in names) \
                if names else ""
            idx_parts = []
            bucket = groups.setdefault(key, {"rings": [], "closed": []})
            for part in parts:
                idx_ring = []
                for ring in part:
                    idx_ring.append((key, len(bucket["rings"])))
                    coords = [(p[0], p[1]) for p in ring]
                    # Кольцо полигона приходит замкнутым, повтор первой вершины
                    # ядру не нужен. Линия остаётся как есть.
                    if is_polygon and len(coords) > 1 and coords[0] == coords[-1]:
                        coords = coords[:-1]
                    bucket["rings"].append(coords)
                    bucket["closed"].append(is_polygon)
                idx_parts.append(idx_ring)
            records.append((feat, idx_parts, key))
            if i % 500 == 0:
                feedback.setProgress(10.0 * i / total)

        if not groups:
            raise QgsProcessingException("Во входном слое нет пригодных геометрий.")

        if names:
            feedback.pushInfo(tr("Группировка по %s: групп %d")
                              % (", ".join(names), len(groups)))

        # ── Упрощение по группам ──────────────────────────────────────────
        results = {}
        arcs_total = shared_total = 0
        v_in = v_out = 0
        for n, (key, bucket) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0]))):
            if feedback.isCanceled():
                return {}
            res = simplify_topology(bucket["rings"], tolerance=tolerance,
                                    grid=grid, min_points=min_points,
                                    smooth=smooth, closed=bucket["closed"])
            results[key] = res["rings"]
            st = res["stats"]
            arcs_total += st["arcs"]
            shared_total += st["arcs_shared"]
            v_in += st["vertices_in"]
            v_out += st["vertices_out"]
            feedback.setProgress(10.0 + 70.0 * (n + 1) / max(1, len(groups)))

        # ── Запись ────────────────────────────────────────────────────────
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(),
            QgsWkbTypes.multiType(wkb), source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        area_after = 0.0
        written = 0
        dropped = 0
        invalid = 0
        for k, (feat, idx_parts, key) in enumerate(records):
            if feedback.isCanceled():
                return {}
            if idx_parts is None:
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                written += 1
                continue
            parts = []
            for part in idx_parts:
                rings = []
                for gkey, ri in part:
                    ring = results[gkey][ri]
                    rings.append([(p[0], p[1], None) for p in ring] if ring else None)
                parts.append(rings)
            geom = assemble(parts, is_polygon, is_multi, False)
            if geom is None or geom.isEmpty():
                dropped += 1
                continue
            if not geom.isGeosValid():
                invalid += 1
            area_after += geom.area() if is_polygon else geom.length()
            out = QgsFeature(feat)
            out.setGeometry(geom)
            sink.addFeature(out, QgsFeatureSink.FastInsert)
            written += 1
            if k % 500 == 0:
                feedback.setProgress(80.0 + 18.0 * k / len(records))

        # ── Отчёт ─────────────────────────────────────────────────────────
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Результат ──"))
        if smooth:
            feedback.pushInfo(tr("Сглаживание: проходов %d") % smooth)
        feedback.pushInfo(tr("Дуг: %d, из них общих для соседей: %d")
                          % (arcs_total, shared_total))
        feedback.pushInfo(tr("Вершин было/стало: %d / %d (%.1f %%)")
                          % (v_in, v_out, 100.0 * v_out / v_in if v_in else 0.0))
        delta = area_after - area_before
        rel = (100.0 * delta / area_before) if area_before else 0.0
        if is_polygon:
            feedback.pushInfo(tr("Площадь до/после: %.3f / %.3f (%+.6f %%)")
                              % (area_before, area_after, rel))
        else:
            feedback.pushInfo(tr("Длина до/после: %.3f / %.3f (%+.6f %%)")
                              % (area_before, area_after, rel))
        feedback.pushInfo(tr("Объектов на входе/выходе: %d / %d") % (len(records), written))
        if dropped:
            feedback.pushWarning(
                tr("Объектов потеряно: %d. Допуск больше размера объекта.") % dropped)
        if invalid:
            feedback.pushWarning(
                tr("Некорректных геометрий: %d. Уменьшите допуск.") % invalid)
        if shared_total == 0 and arcs_total:
            feedback.pushInfo(
                tr("Общих границ не найдено. Если объекты соприкасаются, "
                "увеличьте точность опознания общих вершин."))
        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}


# ────────────────────────────────────────────────────────────────────────────
# 2.02 Границы полигонов линиями
# ────────────────────────────────────────────────────────────────────────────

class BoundariesAlgorithm(QgsProcessingAlgorithm):
    """
    Извлекает границы покрытия отдельными линиями.

    Обычный перевод полигонов в линии выдаёт общую границу дважды, по разу
    от каждого соседа. Здесь она выходит одной линией и несёт признак того,
    с чем граничит.
    """

    INPUT = "INPUT"
    FIELD = "FIELD"
    NODE_EPS = "NODE_EPS"
    GRID = "GRID"
    OUTPUT = "OUTPUT"

    def name(self):
        return "boundaries"

    def displayName(self):
        return tr("2.02 Границы полигонов линиями")

    def group(self):
        return tr("2. Генерализация")

    def groupId(self):
        return "generalization"

    def createInstance(self):
        return BoundariesAlgorithm()

    def helpUrl(self):
        return help_url()

    def shortHelpString(self):
        return help_for("boundaries") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Входной слой (полигоны)"),
            [QgsProcessing.TypeVectorPolygon]))

        p = QgsProcessingParameterField(
            self.FIELD, tr("Поле, значения которого записать по обе стороны"),
            parentLayerParameterName=self.INPUT, optional=True)
        p.setHelp(
            "Значение этого поля у обоих соседей попадёт в атрибуты линии.\n"
            "Для геологических границ это пласт слева и пласт справа."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.NODE_EPS, tr("Отклонение при поиске общих вершин"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1e-6,
            minValue=0.0)
        p.setHelp(
            "Вершина, лежащая на ребре соседа ближе этой величины, получает\n"
            "узел перед разбором. Без этого общая граница не опознаётся:\n"
            "у соседей разная вершинность, и участок выходит двумя линиями.\n"
            "Вершины при этом не двигаются. Ноль отключает."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.GRID, tr("Точность опознания общих вершин"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1e-6,
            minValue=1e-12)
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Границы"), QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")

        field_names = self.parameterAsFields(parameters, self.FIELD, context)
        field = field_names[0] if field_names else None
        node_eps = self.parameterAsDouble(parameters, self.NODE_EPS, context)
        grid = self.parameterAsDouble(parameters, self.GRID, context)

        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Чтение слоя..."))

        items = []
        values = {}
        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                return {}
            parts = explode(feat.geometry(), False)
            if not parts:
                continue
            items.append((feat.id(), [[[(p[0], p[1]) for p in ring]
                                       for ring in part] for part in parts]))
            if field:
                values[feat.id()] = feat[field]
            if i % 500 == 0:
                feedback.setProgress(10.0 * i / total)

        if not items:
            raise QgsProcessingException("Во входном слое нет полигонов.")

        feedback.pushInfo(tr("Объектов: %d") % len(items))
        feedback.setProgress(20)

        result = boundaries.extract_boundaries(items, grid=grid,
                                               node_eps=node_eps)
        feedback.setProgress(70)

        fields = QgsFields()
        fields.append(QgsField("kind", QVariant.String))
        fields.append(QgsField("label", QVariant.String))
        fields.append(QgsField("fid_a", QVariant.LongLong))
        fields.append(QgsField("fid_b", QVariant.LongLong))
        fields.append(QgsField("length", QVariant.Double))
        if field:
            fields.append(QgsField("val_a", QVariant.String))
            fields.append(QgsField("val_b", QVariant.String))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            QgsWkbTypes.LineString, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        labels = {
            boundaries.KIND_SHARED: tr("граница между объектами"),
            boundaries.KIND_OUTER: tr("внешний край покрытия"),
            boundaries.KIND_HOLE: tr("край полости"),
        }
        counts = {}
        for item in result:
            if feedback.isCanceled():
                return {}
            coords = item["coords"]
            if len(coords) < 2:
                continue
            line = QgsGeometry(QgsLineString([QgsPoint(p[0], p[1])
                                              for p in coords]))
            feat = QgsFeature(fields)
            feat.setGeometry(line)
            attrs = [item["kind"], labels.get(item["kind"], item["kind"]),
                     int(item["fid_a"]),
                     -1 if item["fid_b"] is None else int(item["fid_b"]),
                     float(line.length())]
            if field:
                a = values.get(item["fid_a"])
                b = values.get(item["fid_b"])
                attrs.append("" if a is None else str(a))
                attrs.append("" if b is None else str(b))
            feat.setAttributes(attrs)
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            counts[item["kind"]] = counts.get(item["kind"], 0) + 1

        feedback.pushInfo("")
        feedback.pushInfo(tr("── Результат ──"))
        feedback.pushInfo(tr("Границ между объектами: %d")
                          % counts.get(boundaries.KIND_SHARED, 0))
        feedback.pushInfo(tr("Внешний край покрытия:  %d")
                          % counts.get(boundaries.KIND_OUTER, 0))
        feedback.pushInfo(tr("Краёв полостей:         %d")
                          % counts.get(boundaries.KIND_HOLE, 0))
        feedback.pushInfo(tr("Всего линий:            %d") % len(result))
        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}
