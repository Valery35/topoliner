# -*- coding: utf-8 -*-
"""
Инструменты для линейных слоёв: проверка и очистка.

Вынесены в отдельные алгоритмы, а не добавлены в полигональные. У линий свой
набор нарушений: щели, перекрытия и волосяные полигоны к ним не применимы,
зато появляются висячие концы, недоводы, перелёты и псевдоузлы. Смешивать
это в одном инструменте значило бы половину параметров держать
неприменимыми.
"""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsPoint,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)

from . import line_checks as lc
from .audit_algorithms import finding_fields, write_findings
from .branding import banner, help_footer, help_url
from .help_texts import help_for
from .i18n import tr


def read_lines(source, feedback):
    """Читает линейный слой. Мультилиния разбирается на части."""
    items = []
    originals = {}
    parts_of = {}
    total = source.featureCount() or 1
    for i, feat in enumerate(source.getFeatures()):
        if feedback.isCanceled():
            return None, None, None
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            continue
        inner = geom.constGet()
        if inner is None:
            continue
        if inner.hasCurvedSegments():
            inner = inner.segmentize()
        pieces = []
        if QgsWkbTypes.isMultiType(inner.wkbType()):
            for k in range(inner.numGeometries()):
                pieces.append(inner.geometryN(k))
        else:
            pieces.append(inner)
        indices = []
        for piece in pieces:
            line = piece if isinstance(piece, QgsLineString) else piece.curveToLine()
            if line is None or line.numPoints() < 2:
                continue
            coords = [(line.xAt(k), line.yAt(k)) for k in range(line.numPoints())]
            indices.append(len(items))
            items.append((feat.id(), coords))
        if indices:
            originals[feat.id()] = feat
            parts_of[feat.id()] = indices
        if i % 500 == 0:
            feedback.setProgress(5.0 * i / total)
    return items, originals, parts_of


def build_line_geometry(parts, is_multi):
    """Собирает геометрию из списка списков координат."""
    built = []
    for coords in parts:
        if coords and len(coords) >= 2:
            built.append(QgsLineString([QgsPoint(p[0], p[1]) for p in coords]))
    if not built:
        return None
    if is_multi or len(built) > 1:
        multi = QgsMultiLineString()
        for line in built:
            multi.addGeometry(line)
        return QgsGeometry(multi)
    return QgsGeometry(built[0])


def print_line_summary(feedback, summary):
    if not summary:
        feedback.pushInfo(tr("Нарушений не найдено."))
        return
    # У линий свои нарушения, но встречаются и общие с полигонами:
    # повторяющиеся вершины, иглы, дубликаты. Их названия берутся оттуда.
    from . import topo_checks as tc

    labels = dict(lc.LINE_TYPE_LABELS)
    labels.update(tc.TYPE_LABELS)
    feedback.pushInfo("%-40s %8s %8s %12s %12s"
                      % (tr("нарушение"), tr("чинится"), tr("решать"),
                         tr("медиана"), tr("максимум")))
    order = sorted(summary.items(), key=lambda kv: -(kv[1]["auto"] + kv[1]["review"]))
    for kind, slot in order:
        feedback.pushInfo("%-40s %8d %8d %12.4f %12.4f" % (
            tr(labels.get(kind, kind)), slot["auto"], slot["review"],
            slot.get("value_med", 0.0), slot["value_max"]))


# ────────────────────────────────────────────────────────────────────────────
# 1.02 Проверка топологии линий
# ────────────────────────────────────────────────────────────────────────────

class LineAuditAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    TOLERANCE = "TOLERANCE"
    MIN_LENGTH = "MIN_LENGTH"
    DO_DANGLES = "DO_DANGLES"
    DO_CROSSINGS = "DO_CROSSINGS"
    DO_PSEUDO = "DO_PSEUDO"
    OUTPUT = "OUTPUT"

    def name(self):
        return "lineaudit"

    def displayName(self):
        return tr("1.02 Проверка топологии линий")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return LineAuditAlgorithm()

    def helpUrl(self):
        return help_url()

    def shortHelpString(self):
        return help_for("lineaudit") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Проверяемый слой (линии)"),
            [QgsProcessing.TypeVectorLine]))

        p = QgsProcessingParameterNumber(
            self.TOLERANCE, tr("Допуск (в единицах CRS слоя)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=2.0,
            minValue=1e-9)
        p.setHelp(
            "Расстояние, ниже которого расхождение считается погрешностью.\n"
            "Недовод и перелёт короче допуска относятся к мусору."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.MIN_LENGTH, tr("Порог длины линии (0 - не учитывать)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0,
            minValue=0.0)
        p.setHelp("Линии короче этой длины попадают в находки.")
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_DANGLES, tr("Искать висячие концы, недоводы и перелёты"),
            defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_CROSSINGS, tr("Искать пересечения без узла"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_PSEUDO, tr("Искать псевдоузлы"), defaultValue=False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Находки"), QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        min_length = self.parameterAsDouble(parameters, self.MIN_LENGTH, context)

        feedback.pushInfo(banner())
        items, _orig, _parts = read_lines(source, feedback)
        if items is None:
            return {}
        if not items:
            raise QgsProcessingException("Во входном слое нет линий.")

        feedback.pushInfo(tr("Линий: %d, допуск %g") % (len(items), tolerance))

        findings, summary = lc.check_lines(
            items, tolerance=tolerance, min_length=min_length,
            do_dangles=self.parameterAsBoolean(parameters, self.DO_DANGLES, context),
            do_crossings=self.parameterAsBoolean(parameters, self.DO_CROSSINGS, context),
            do_pseudo=self.parameterAsBoolean(parameters, self.DO_PSEUDO, context),
            progress=lambda f: feedback.setProgress(5.0 + 90.0 * f),
        )

        fields = finding_fields()
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            QgsWkbTypes.Point, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать слой находок.")
        written = write_findings(sink, fields, findings)

        auto = sum(1 for f in findings if f["severity"] == lc.SEVERITY_AUTO)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Топология линий ──"))
        print_line_summary(feedback, summary)
        feedback.pushInfo("")
        feedback.pushInfo(
            tr("Всего находок: %d, из них чинится автоматически: %d, решать человеку: %d")
            % (written, auto, written - auto))
        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}


# ────────────────────────────────────────────────────────────────────────────
# 1.04 Очистка линий
# ────────────────────────────────────────────────────────────────────────────

class LineFixAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    TOLERANCE = "TOLERANCE"
    MIN_LENGTH = "MIN_LENGTH"
    DO_TRIM = "DO_TRIM"
    DO_CLOSE = "DO_CLOSE"
    DO_SNAP = "DO_SNAP"
    DROP_SHORT = "DROP_SHORT"
    SPIKE = "SPIKE"
    OUTPUT = "OUTPUT"
    REMAINS = "REMAINS"

    def name(self):
        return "linefix"

    def displayName(self):
        return tr("1.04 Очистка топологии линий")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return LineFixAlgorithm()

    def helpUrl(self):
        return help_url()

    def shortHelpString(self):
        return help_for("linefix") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Входной слой (линии)"),
            [QgsProcessing.TypeVectorLine]))

        p = QgsProcessingParameterNumber(
            self.TOLERANCE, tr("Допуск (в единицах CRS слоя)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=2.0,
            minValue=1e-9)
        p.setHelp(
            "Предельное смещение конца линии и предельная длина\n"
            "обрезаемого хвоста."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.MIN_LENGTH, tr("Порог длины линии (0 - не учитывать)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0,
            minValue=0.0)
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_TRIM, tr("Обрезать перелёты за узел"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_CLOSE, tr("Дотягивать недоводы до соседней линии"),
            defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_SNAP, tr("Вставлять недостающие узлы"), defaultValue=True))

        p = QgsProcessingParameterBoolean(
            self.DROP_SHORT, tr("Удалять линии короче порога длины"),
            defaultValue=False)
        p.setHelp(
            "По умолчанию выключено: удаление объекта уничтожает и его атрибуты.\n"
            "Без этой галочки такие линии только попадают в оставшиеся проблемы."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.SPIKE, tr("Порог угла иглы, градусы"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0,
            minValue=0.0, maxValue=45.0)
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Очищенный слой")))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.REMAINS, tr("Оставшиеся проблемы"), QgsProcessing.TypeVectorPoint,
            optional=True, createByDefault=True))

    def processAlgorithm(self, parameters, context, feedback):
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        min_length = self.parameterAsDouble(parameters, self.MIN_LENGTH, context)
        options = {
            "trim_overshoots": self.parameterAsBoolean(parameters, self.DO_TRIM, context),
            "close_undershoots": self.parameterAsBoolean(parameters, self.DO_CLOSE, context),
            "snap": self.parameterAsBoolean(parameters, self.DO_SNAP, context),
            "drop_short": self.parameterAsBoolean(parameters, self.DROP_SHORT, context),
            "spike_angle": self.parameterAsDouble(parameters, self.SPIKE, context),
        }

        feedback.pushInfo(banner())
        items, originals, parts_of = read_lines(source, feedback)
        if items is None:
            return {}
        if not items:
            raise QgsProcessingException("Во входном слое нет линий.")

        feedback.pushInfo(tr("Линий: %d, допуск %g") % (len(items), tolerance))

        new_items, stats, left = lc.fix_lines(
            items, tolerance=tolerance, min_length=min_length, options=options,
            progress=lambda f: feedback.setProgress(5.0 + 80.0 * f))

        wkb = QgsWkbTypes.multiType(QgsWkbTypes.LineString)
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(), wkb,
            source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        written = 0
        lost = 0
        for fid, indices in parts_of.items():
            if feedback.isCanceled():
                return {}
            parts = [new_items[k][1] for k in indices]
            geom = build_line_geometry(parts, True)
            if geom is None or geom.isEmpty():
                lost += 1
                continue
            feat = QgsFeature(originals[fid])
            feat.setGeometry(geom)
            sink.addFeature(feat, QgsFeatureSink.FastInsert)
            written += 1

        remains_id = None
        if parameters.get(self.REMAINS) not in (None, ""):
            fields = finding_fields()
            (rsink, remains_id) = self.parameterAsSink(
                parameters, self.REMAINS, context, fields,
                QgsWkbTypes.Point, source.sourceCrs())
            write_findings(rsink, fields, left)

        feedback.setProgress(95)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Исправлено молча ──"))
        feedback.pushInfo(tr("Повторяющихся вершин снято:  %d") % stats["dup_vertices"])
        feedback.pushInfo(tr("Игл снято:                   %d") % stats["spikes"])
        feedback.pushInfo(tr("Перелётов обрезано:          %d") % stats["overshoots_trimmed"])
        feedback.pushInfo(tr("Недоводов закрыто:           %d (макс. смещение %.4f)")
                          % (stats["undershoots_closed"], stats["max_move"]))
        feedback.pushInfo(tr("Узлов вставлено:             %d") % stats["nodes_inserted"])
        if stats["zero_dropped"]:
            feedback.pushInfo(tr("Линий нулевой длины удалено: %d") % stats["zero_dropped"])
        if stats["short_dropped"]:
            feedback.pushInfo(tr("Коротких линий удалено:      %d") % stats["short_dropped"])

        before, after = stats["length_before"], stats["length_after"]
        rel = (100.0 * (after - before) / before) if before else 0.0
        feedback.pushInfo("")
        feedback.pushInfo(tr("Длина до/после: %.3f / %.3f (%+.6f %%)")
                          % (before, after, rel))
        feedback.pushInfo(tr("Объектов на входе/выходе: %d / %d")
                          % (len(parts_of), written))
        if lost:
            feedback.pushWarning(tr("Объектов потеряно: %d") % lost)
        feedback.setProgress(100)

        out = {self.OUTPUT: dest_id}
        if remains_id is not None:
            out[self.REMAINS] = remains_id
        return out
