# -*- coding: utf-8 -*-
"""
TopologySimplifyAlgorithm
-------------------------
Упрощение полигонального слоя с сохранением общих границ.
"""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsGeometry,
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
from .branding import banner, help_footer
from .topo_algorithm import assemble, explode
from .topo_simplify import simplify_topology


class TopologySimplifyAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    TOLERANCE = "TOLERANCE"
    GRID = "GRID"
    MIN_POINTS = "MIN_POINTS"
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

    def shortHelpString(self):
        return help_for("topologysimplify") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Входной слой (полигоны)"),
            [QgsProcessing.TypeVectorPolygon]))

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
        names = self.parameterAsFields(parameters, self.FIELDS, context)
        keep_z = self.parameterAsBoolean(parameters, self.KEEP_Z, context)

        wkb = source.wkbType()
        is_multi = QgsWkbTypes.isMultiType(wkb)
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
            area_before += geom.area()
            key = " | ".join("" if feat[n] is None else str(feat[n]) for n in names) \
                if names else ""
            idx_parts = []
            bucket = groups.setdefault(key, {"rings": [], "addr": []})
            for part in parts:
                idx_ring = []
                for ring in part:
                    idx_ring.append((key, len(bucket["rings"])))
                    bucket["rings"].append([(p[0], p[1]) for p in ring])
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
                                    grid=grid, min_points=min_points)
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
            geom = assemble(parts, True, is_multi, False)
            if geom is None or geom.isEmpty():
                dropped += 1
                continue
            if not geom.isGeosValid():
                invalid += 1
            area_after += geom.area()
            out = QgsFeature(feat)
            out.setGeometry(geom)
            sink.addFeature(out, QgsFeatureSink.FastInsert)
            written += 1
            if k % 500 == 0:
                feedback.setProgress(80.0 + 18.0 * k / len(records))

        # ── Отчёт ─────────────────────────────────────────────────────────
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Результат ──"))
        feedback.pushInfo(tr("Дуг: %d, из них общих для соседей: %d")
                          % (arcs_total, shared_total))
        feedback.pushInfo(tr("Вершин было/стало: %d / %d (%.1f %%)")
                          % (v_in, v_out, 100.0 * v_out / v_in if v_in else 0.0))
        delta = area_after - area_before
        rel = (100.0 * delta / area_before) if area_before else 0.0
        feedback.pushInfo(tr("Площадь до/после: %.3f / %.3f (%+.6f %%)")
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
