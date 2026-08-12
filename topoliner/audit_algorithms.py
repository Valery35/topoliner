# -*- coding: utf-8 -*-
"""
Два Processing-алгоритма поверх topo_checks:

  TopologyAuditAlgorithm  проверка топологии, ничего не изменяет
  TopologyFixAlgorithm    очистка в один проход, кнопка "всё сделать"

Логика проверок и исправлений живёт в topo_checks и покрыта тестами.
Здесь только чтение слоя, восстановление отметок Z и печать отчёта.
"""

from qgis.core import (
    QgsExpression,
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPoint,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from . import topo_checks as tc
from .help_texts import help_for
from .i18n import tr
from .branding import banner, help_footer
from .geom_backend import QgisBackend
from .topo_algorithm import assemble, explode
from .topo_core import _PointGrid


# ────────────────────────────────────────────────────────────────────────────
# Общее
# ────────────────────────────────────────────────────────────────────────────

def finding_fields():
    fields = QgsFields()
    fields.append(QgsField("type", QVariant.String))
    fields.append(QgsField("label", QVariant.String))
    fields.append(QgsField("severity", QVariant.String))
    fields.append(QgsField("fid_a", QVariant.LongLong))
    fields.append(QgsField("fid_b", QVariant.LongLong))
    fields.append(QgsField("value", QVariant.Double))
    fields.append(QgsField("note", QVariant.String))
    fields.append(QgsField("grp", QVariant.String))
    return fields


def write_findings(sink, fields, findings):
    if sink is None:
        return 0
    n = 0
    for f in findings:
        feat = QgsFeature(fields)
        if f["x"] is not None:
            feat.setGeometry(QgsGeometry(QgsPoint(f["x"], f["y"])))
        feat.setAttributes([
            f["type"],
            tc.label_of(f["type"]),
            f["severity"],
            -1 if f["fid"] is None else int(f["fid"]),
            -1 if f["fid_b"] is None else int(f["fid_b"]),
            float(f["value"]),
            f["note"],
            f.get("key", ""),
        ])
        sink.addFeature(feat, QgsFeatureSink.FastInsert)
        n += 1
    return n


def read_group_keys(source, names, feedback):
    """Ключ группировки для каждого объекта. Пустой список полей означает
    одну общую группу."""
    keys = {}
    if not names:
        return None
    for feat in source.getFeatures():
        keys[feat.id()] = " | ".join(
            "" if feat[n] is None else str(feat[n]) for n in names)
    return keys


def read_items(source, feedback):
    """Читает слой в список (fid, QgsGeometry без Z) и словарь исходных геометрий."""
    items = []
    originals = {}
    total = source.featureCount() or 1
    for i, feat in enumerate(source.getFeatures()):
        if feedback.isCanceled():
            return None, None
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            continue
        flat = QgsGeometry(geom)
        if QgsWkbTypes.hasZ(flat.wkbType()):
            flat.get().dropZValue()
        if QgsWkbTypes.hasM(flat.wkbType()):
            flat.get().dropMValue()
        items.append((feat.id(), flat))
        originals[feat.id()] = feat
        if i % 500 == 0:
            feedback.setProgress(5.0 * i / total)
    return items, originals


def print_summary(feedback, summary):
    if not summary:
        feedback.pushInfo(tr("Нарушений не найдено."))
        return
    feedback.pushInfo("%-40s %8s %8s %12s %12s"
                      % ("нарушение", "чинится", "решать", "медиана", "максимум"))
    order = sorted(summary.items(), key=lambda kv: -(kv[1]["auto"] + kv[1]["review"]))
    for kind, slot in order:
        feedback.pushInfo("%-40s %8d %8d %12.4f %12.4f" % (
            tc.label_of(kind), slot["auto"], slot["review"],
            slot.get("value_med", 0.0), slot["value_max"]))


# ────────────────────────────────────────────────────────────────────────────
# Проверка
# ────────────────────────────────────────────────────────────────────────────

class TopologyAuditAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    TOLERANCE = "TOLERANCE"
    AREA = "AREA"
    DO_OVERLAPS = "DO_OVERLAPS"
    DO_GAPS = "DO_GAPS"
    DO_NODES = "DO_NODES"
    CAVITY = "CAVITY"
    FIELDS = "FIELDS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "topologyaudit"

    def displayName(self):
        return tr("1.01 Проверка топологии")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return TopologyAuditAlgorithm()

    def shortHelpString(self):
        return help_for("topologyaudit") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Проверяемый слой (полигоны)"),
            [QgsProcessing.TypeVectorPolygon]))

        p = QgsProcessingParameterNumber(
            self.TOLERANCE, tr("Допуск (в единицах CRS слоя)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=2.0, minValue=1e-9)
        p.setHelp("Расстояние, ниже которого расхождение считается технической погрешностью.")
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.AREA, tr("Порог площади мусора (в кв. единицах CRS)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.0)
        p.setHelp(
            "Площадь, ниже которой фрагмент считается техническим мусором.\n"
            "Разумная точка отсчёта это квадрат допуска."
        )
        self.addParameter(p)

        p = QgsProcessingParameterField(
            self.FIELDS, tr("Поле или поля группировки (необязательно)"),
            parentLayerParameterName=self.INPUT, allowMultiple=True, optional=True)
        p.setHelp(
            "Нужно, когда слой не является единым покрытием, например когда\n"
            "зоны нескольких пластов лежат в одном слое. Объекты разных групп\n"
            "накладываются друг на друга по замыслу, и без группировки каждое\n"
            "такое наложение попадает в перекрытия, дубликаты и вложения."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.CAVITY, tr("Площадь законной полости (0 - не учитывать)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0)
        p.setHelp(
            "Полость крупнее этой площади считается частью замысла и находкой\n"
            "не является: целик, озеро, незакартированный участок.\n"
            "Мелкая дыра в покрытии это дефект, очень крупная почти всегда нет."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_OVERLAPS, tr("Искать перекрытия, дубликаты и вложения"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_GAPS, tr("Искать щели в покрытии"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_NODES, tr("Искать вершины без узла на соседнем ребре"), defaultValue=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Находки"), QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        area = self.parameterAsDouble(parameters, self.AREA, context)

        # Инструменты топологии обязаны принимать некорректную геометрию:
        # именно её они и ищут. Иначе один плохой объект валит весь прогон.
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        items, _orig = read_items(source, feedback)
        if items is None:
            return {}
        if not items:
            raise QgsProcessingException("Во входном слое нет геометрий.")

        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Объектов: %d, допуск %g, порог площади %g")
                          % (len(items), tolerance, area))

        backend = QgisBackend()
        names = self.parameterAsFields(parameters, self.FIELDS, context)
        keys = read_group_keys(source, names, feedback)
        common = dict(
            tolerance=tolerance, area_threshold=area,
            do_overlaps=self.parameterAsBoolean(parameters, self.DO_OVERLAPS, context),
            do_gaps=self.parameterAsBoolean(parameters, self.DO_GAPS, context),
            do_unsnapped=self.parameterAsBoolean(parameters, self.DO_NODES, context),
            cavity_area=self.parameterAsDouble(parameters, self.CAVITY, context),
        )
        if keys:
            feedback.pushInfo(tr("Группировка по %s: групп %d")
                              % (", ".join(names), len(set(keys.values()))))
            findings, summary = tc.check_grouped(
                backend, items, lambda fid: keys.get(fid),
                progress=lambda f: feedback.setProgress(5.0 + 90.0 * f), **common)
        else:
            findings, summary = tc.check_items(
                backend, items,
                progress=lambda f: feedback.setProgress(5.0 + 90.0 * f), **common)

        fields = finding_fields()
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            QgsWkbTypes.Point, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать слой находок.")
        n = write_findings(sink, fields, findings)

        auto = sum(1 for f in findings if f["severity"] == tc.SEVERITY_AUTO)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Топология ──"))
        print_summary(feedback, summary)
        feedback.pushInfo("")
        feedback.pushInfo(tr("Всего находок: %d, из них чинится автоматически: %d, решать человеку: %d")
                          % (n, auto, n - auto))
        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}


# ────────────────────────────────────────────────────────────────────────────
# Очистка
# ────────────────────────────────────────────────────────────────────────────

class TopologyFixAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    TOLERANCE = "TOLERANCE"
    AREA = "AREA"
    SPIKE = "SPIKE"
    DO_SNAP = "DO_SNAP"
    DO_VALID = "DO_VALID"
    DO_OVERLAPS = "DO_OVERLAPS"
    DO_GAPS = "DO_GAPS"
    DROP_TINY = "DROP_TINY"
    CAVITY = "CAVITY"
    WINNER = "WINNER"
    KEEP_Z = "KEEP_Z"
    FIELDS = "FIELDS"
    OUTPUT = "OUTPUT"
    REMAINS = "REMAINS"

    def name(self):
        return "topologyfix"

    def displayName(self):
        return tr("1.02 Топологическая очистка (всё сразу)")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return TopologyFixAlgorithm()

    def shortHelpString(self):
        return help_for("topologyfix") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Входной слой (полигоны)"), [QgsProcessing.TypeVectorPolygon]))

        p = QgsProcessingParameterNumber(
            self.TOLERANCE, tr("Допуск (в единицах CRS слоя)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=2.0, minValue=1e-9)
        p.setHelp("Предельное смещение вершины и радиус поиска соседних рёбер.")
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.AREA, tr("Порог площади мусора (в кв. единицах CRS)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.0)
        p.setHelp(
            "Фрагменты мельче этого порога считаются мусором и убираются молча.\n"
            "Перекрытия и щели крупнее порога не изменяются."
        )
        self.addParameter(p)

        p = QgsProcessingParameterField(
            self.FIELDS, tr("Поле или поля группировки (необязательно)"),
            parentLayerParameterName=self.INPUT, allowMultiple=True, optional=True)
        p.setHelp(
            "Объекты разных групп не сшиваются между собой и не спорят\n"
            "за площадь. Нужно, когда в одном слое лежат несколько покрытий,\n"
            "например зоны разных пластов."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_SNAP, tr("Сшивать вершины и узлы"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_VALID, tr("Исправлять некорректную геометрию"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_OVERLAPS, tr("Убирать мелкие перекрытия"), defaultValue=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.DO_GAPS, tr("Заполнять мелкие щели"), defaultValue=True))

        p = QgsProcessingParameterEnum(
            self.WINNER, tr("При перекрытии площадь сохраняет"),
            options=["Более крупный объект", "Объект с меньшим идентификатором"],
            defaultValue=0)
        p.setHelp("Проигравший объект отдаёт полосу перекрытия.")
        self.addParameter(p)

        p = QgsProcessingParameterBoolean(
            self.DROP_TINY, tr("Удалять объекты мельче порога площади"), defaultValue=False)
        p.setHelp(
            "По умолчанию выключено: удаление объекта уничтожает и его атрибуты.\n"
            "Без этой галочки такие объекты только попадают в слой оставшихся проблем."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.CAVITY, tr("Площадь законной полости (0 - не учитывать)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0)
        p.setHelp(
            "Полость крупнее этой площади считается частью замысла и находкой\n"
            "не является: целик, озеро, незакартированный участок.\n"
            "Мелкая дыра в покрытии это дефект, очень крупная почти всегда нет."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.SPIKE, tr("Порог угла иглы, градусы"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0,
            minValue=0.0, maxValue=45.0)
        p.setHelp(
            "Вершина снимается, если линия разворачивается в ней назад\n"
            "с углом меньше указанного. Значение около одного градуса\n"
            "убирает только явные артефакты оцифровки."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterBoolean(
            self.KEEP_Z, tr("Восстанавливать отметки Z"), defaultValue=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Очищенный слой")))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.REMAINS, tr("Оставшиеся проблемы"), QgsProcessing.TypeVectorPoint,
            optional=True, createByDefault=True))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        area = self.parameterAsDouble(parameters, self.AREA, context)
        keep_z = self.parameterAsBoolean(parameters, self.KEEP_Z, context)
        with_z = QgsWkbTypes.hasZ(source.wkbType()) and keep_z

        options = {
            "snap": self.parameterAsBoolean(parameters, self.DO_SNAP, context),
            "fix_invalid": self.parameterAsBoolean(parameters, self.DO_VALID, context),
            "resolve_overlaps": self.parameterAsBoolean(parameters, self.DO_OVERLAPS, context),
            "fill_gaps": self.parameterAsBoolean(parameters, self.DO_GAPS, context),
            "drop_tiny_features": self.parameterAsBoolean(parameters, self.DROP_TINY, context),
            "spike_angle": self.parameterAsDouble(parameters, self.SPIKE, context),
            "cavity_area": self.parameterAsDouble(parameters, self.CAVITY, context),
            "overlap_winner": ["larger", "first"][
                self.parameterAsEnum(parameters, self.WINNER, context)],
        }

        # Инструменты топологии обязаны принимать некорректную геометрию:
        # именно её они и ищут. Иначе один плохой объект валит весь прогон.
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        items, originals = read_items(source, feedback)
        if items is None:
            return {}
        if not items:
            raise QgsProcessingException("Во входном слое нет геометрий.")

        # Исходные вершины для восстановления Z.
        z_grid = None
        z_vals = []
        if with_z:
            z_grid = _PointGrid(max(tolerance, 1e-6))
            for feat in source.getFeatures():
                g = feat.geometry()
                if g is None or g.isEmpty():
                    continue
                for part in explode(g, True):
                    for ring in part:
                        for x, y, z in ring:
                            z_grid.add(x, y)
                            z_vals.append(z)

        backend = QgisBackend()
        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Объектов: %d, допуск %g, порог площади %g")
                          % (len(items), tolerance, area))

        names = self.parameterAsFields(parameters, self.FIELDS, context)
        keys = read_group_keys(source, names, feedback)
        if keys:
            feedback.pushInfo(tr("Группировка по %s: групп %d")
                              % (", ".join(names), len(set(keys.values()))))
            new_items, stats, left = tc.fix_grouped(
                backend, items, lambda fid: keys.get(fid),
                tolerance=tolerance, area_threshold=area, options=options,
                progress=lambda f: feedback.setProgress(5.0 + 80.0 * f))
        else:
            new_items, stats, left = tc.fix_items(
                backend, items, tolerance=tolerance, area_threshold=area,
                options=options,
                progress=lambda f: feedback.setProgress(5.0 + 80.0 * f))

        # ── Запись ────────────────────────────────────────────────────────
        out_wkb = QgsWkbTypes.multiType(
            QgsWkbTypes.zmType(QgsWkbTypes.Polygon, with_z, False))
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(),
            out_wkb, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        written = 0
        for fid, geom in new_items:
            if feedback.isCanceled():
                return {}
            if geom is None or geom.isEmpty():
                continue
            if with_z:
                geom = self._restore_z(geom, z_grid, z_vals, tolerance)
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

        # ── Отчёт ─────────────────────────────────────────────────────────
        feedback.setProgress(95)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Исправлено молча ──"))
        feedback.pushInfo(tr("Повторяющихся вершин снято:  %d") % stats["dup_vertices"])
        feedback.pushInfo(tr("Игл снято:                   %d") % stats["spikes"])
        feedback.pushInfo(tr("Вершин сведено:              %d (макс. смещение %.4f)")
                          % (stats["vertices_moved"], stats["max_move"]))
        feedback.pushInfo(tr("Узлов вставлено:             %d") % stats["nodes_inserted"])
        feedback.pushInfo(tr("Микрочастей удалено:         %d") % stats["tiny_parts"])
        feedback.pushInfo(tr("Микродыр залито:             %d") % stats["tiny_holes"])
        if stats.get("rings_frozen"):
            feedback.pushInfo(tr("Колец не изменялось:         %d (уже допуска)")
                              % stats["rings_frozen"])
        feedback.pushInfo(tr("Геометрий исправлено:        %d") % stats["made_valid"])
        feedback.pushInfo(tr("Перекрытий убрано:           %d") % stats["overlaps_fixed"])
        feedback.pushInfo(tr("Щелей заполнено:             %d") % stats["gaps_filled"])
        if stats["tiny_features_dropped"]:
            feedback.pushInfo(tr("Микрообъектов удалено:       %d") % stats["tiny_features_dropped"])

        touch = 0
        for _fid, geom in new_items:
            if geom is None or geom.isEmpty():
                continue
            for part in tc.to_parts(backend, geom):
                for ring in part:
                    if tc.self_touch_points(ring, True):
                        touch += 1
                        break
        if touch:
            feedback.pushWarning(
                tr("Объектов с самокасанием колец: %d. GEOS считает такую геометрию "
                "корректной, а SQL Server может её отклонить. При заливке в MSSQL "
                "применяйте MakeValid на стороне сервера.") % touch)

        feedback.pushInfo("")
        feedback.pushInfo(tr("── Оставлено человеку ──"))
        print_summary(feedback, tc.summarize(left))

        before = stats["area_before"]
        after = stats["area_after"]
        rel = (100.0 * (after - before) / before) if before else 0.0
        feedback.pushInfo("")
        feedback.pushInfo(tr("Площадь до/после: %.3f / %.3f (%+.6f %%)") % (before, after, rel))
        feedback.pushInfo(tr("Объектов на входе/выходе: %d / %d") % (len(items), written))
        if stats["features_lost"]:
            feedback.pushWarning(tr("Объектов исчезло: %d, см. слой оставшихся проблем")
                                 % stats["features_lost"])
        if stats["valid_rejected"]:
            feedback.pushWarning(tr("Исправлений отменено из-за потери площади: %d")
                                 % stats["valid_rejected"])
        if abs(rel) > 1.0:
            feedback.pushWarning(
                tr("Суммарная площадь изменилась более чем на процент. "
                "Проверьте пороги: скорее всего порог площади завышен."))
        feedback.setProgress(100)

        out = {self.OUTPUT: dest_id}
        if remains_id is not None:
            out[self.REMAINS] = remains_id
        return out

    # ── Восстановление Z ─────────────────────────────────────────────────
    @staticmethod
    def _restore_z(geom, grid, z_vals, tolerance):
        """Отметка каждой вершины берётся у ближайшей исходной вершины."""
        parts = explode(geom, False)
        if not parts:
            return geom
        new_parts = []
        for rings in parts:
            new_rings = []
            for ring in rings:
                new_ring = []
                for x, y, _z in ring:
                    z = 0.0
                    radius = max(tolerance, 1e-6)
                    for _attempt in range(6):
                        idx, _d = grid.nearest(x, y, radius)
                        if idx is not None:
                            z = z_vals[idx]
                            break
                        radius *= 4.0
                    new_ring.append((x, y, z))
                new_rings.append(new_ring)
            new_parts.append(new_rings)
        rebuilt = assemble(new_parts, True, True, True)
        return rebuilt if rebuilt is not None else geom


# ────────────────────────────────────────────────────────────────────────────
# Контроль сборки
# ────────────────────────────────────────────────────────────────────────────

class AssemblyCheckAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    FIELDS = "FIELDS"
    AREA = "AREA"
    MAX_GAP = "MAX_GAP"
    IGNORE_HOLES = "IGNORE_HOLES"
    OUTPUT = "OUTPUT"

    def name(self):
        return "assemblycheck"

    def displayName(self):
        return tr("1.04 Контроль сборки по атрибуту")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return AssemblyCheckAlgorithm()

    def shortHelpString(self):
        return help_for("assemblycheck") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Слой (полигоны)"), [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterField(
            self.FIELDS, tr("Поле или поля группировки"), parentLayerParameterName=self.INPUT,
            allowMultiple=True))

        p = QgsProcessingParameterNumber(
            self.AREA, tr("Порог площади мусора (в кв. единицах CRS)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=1.0, minValue=0.0)
        p.setHelp("Внутренние кольца мельче порога помечаются как технический мусор.")
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.MAX_GAP, tr("Максимальный разрыв внутри тела (в единицах CRS)"),
            type=QgsProcessingParameterNumber.Double, defaultValue=0.0, minValue=0.0)
        p.setHelp(
            "Части, отстоящие друг от друга дальше этого расстояния, считаются\n"
            "законно отдельными телами и находкой не являются.\n"
            "Ноль означает, что группа обязана собираться в одно целое.\n"
            "Ноль подходит для зон, блоков и панелей. Для полигонов изолиний\n"
            "и подобных данных задавайте величину порядка нескольких допусков."
        )
        self.addParameter(p)

        p = QgsProcessingParameterBoolean(
            self.IGNORE_HOLES, tr("Внутренние кольца допустимы"), defaultValue=False)
        p.setHelp(
            "Отключает поиск полостей внутри тел. Нужно там, где полость\n"
            "законна по смыслу, например у полигонов изолиний."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Находки сборки"), QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")
        names = self.parameterAsFields(parameters, self.FIELDS, context)
        if not names:
            raise QgsProcessingException("Укажите хотя бы одно поле группировки.")
        area = self.parameterAsDouble(parameters, self.AREA, context)

        # Инструменты топологии обязаны принимать некорректную геометрию:
        # именно её они и ищут. Иначе один плохой объект валит весь прогон.
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        items = []
        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                return {}
            geom = feat.geometry()
            if geom is None or geom.isEmpty():
                continue
            flat = QgsGeometry(geom)
            if QgsWkbTypes.hasZ(flat.wkbType()):
                flat.get().dropZValue()
            key = " | ".join(
                "" if feat[n] is None else str(feat[n]) for n in names)
            items.append((feat.id(), flat, key))
            if i % 500 == 0:
                feedback.setProgress(10.0 * i / total)

        if not items:
            raise QgsProcessingException("Во входном слое нет геометрий.")

        feedback.pushInfo(banner())
        backend = QgisBackend()
        findings, per_group = tc.check_assembly(
            backend, items, area_threshold=area,
            max_gap=self.parameterAsDouble(parameters, self.MAX_GAP, context),
            ignore_holes=self.parameterAsBoolean(parameters, self.IGNORE_HOLES, context),
            progress=lambda f: feedback.setProgress(10.0 + 80.0 * f))

        fields = finding_fields()
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            QgsWkbTypes.Point, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать слой находок.")
        write_findings(sink, fields, findings)

        bad = [(k, v) for k, v in per_group.items() if v["splits"] or v["holes"]]
        separate = sum(1 for v in per_group.values() if v["separate"])
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Сборка по %s ──") % ", ".join(names))
        feedback.pushInfo(tr("Групп: %d, без дефектов сборки: %d")
                          % (len(per_group), len(per_group) - len(bad)))
        if separate:
            feedback.pushInfo(
                tr("Групп из нескольких законно отдельных тел: %d "
                "(разрыв больше заданного порога, нарушением не считается)") % separate)
        if bad:
            feedback.pushInfo("")
            feedback.pushInfo("%-24s %6s %7s %7s %14s"
                              % ("группа", "тел", "разрыв", "колец", "площадь"))
            for k, v in sorted(bad, key=lambda kv: -(kv[1]["splits"] + kv[1]["holes"]))[:40]:
                feedback.pushInfo("%-24s %6d %7d %7d %14.2f"
                                  % (str(k)[:24], v["bodies"], v["splits"],
                                     v["holes"], v["area"]))
            if len(bad) > 40:
                feedback.pushInfo(tr("... и ещё %d групп, см. слой находок") % (len(bad) - 40))
            feedback.pushWarning(
                tr("Групп с дефектами сборки: %d. Смотрите поле note: там расстояние, "
                "которого не хватило допуску. Если разрывы измеряются сотнями метров, "
                "значит группы не обязаны быть цельными и нужно задать "
                "максимальный разрыв.") % len(bad))
        else:
            feedback.pushInfo(tr("Дефектов сборки не найдено."))
        feedback.setProgress(100)
        return {self.OUTPUT: dest_id}
