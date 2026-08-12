# -*- coding: utf-8 -*-
"""
TopologyCleanAlgorithm
----------------------
Топологическая сшивка полигонального или линейного слоя.

Обёртка над topo_core: разбирает геометрии в кольца, вызывает ядро,
собирает результат обратно и печатает отчёт в панель Processing.
Атрибуты объектов сохраняются полностью, меняется только геометрия.
"""

from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsFeatureSink,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsMultiPolygon,
    QgsPoint,
    QgsPolygon,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
)
from qgis.PyQt.QtCore import QVariant

from .help_texts import help_for
from .i18n import tr
from .branding import banner, help_footer
from .topo_core import (
    MODE_BOTH,
    MODE_INSERT,
    ring_width,
    segment_length_stats,
    MODE_INSERT,
    MODE_MERGE,
    Z_FROM_VERTEX,
    Z_INTERPOLATE,
    clean_topology,
)

MODES = [MODE_BOTH, MODE_INSERT, MODE_MERGE]
Z_MODES = [Z_INTERPOLATE, Z_FROM_VERTEX]


# ────────────────────────────────────────────────────────────────────────────
# Разбор и сборка геометрии
# ────────────────────────────────────────────────────────────────────────────

def _curve_to_linestring(curve):
    """Возвращает QgsLineString для любой кривой."""
    if curve is None:
        return None
    if isinstance(curve, QgsLineString):
        return curve
    return curve.curveToLine()


def _ring_coords(line, with_z):
    n = line.numPoints()
    if with_z:
        return [(line.xAt(i), line.yAt(i), line.zAt(i)) for i in range(n)]
    return [(line.xAt(i), line.yAt(i), None) for i in range(n)]


def explode(geom, with_z):
    """
    Разбирает геометрию на части и кольца.
    Возвращает список частей, часть это список колец, кольцо это список вершин.
    Для линий часть содержит ровно одно кольцо.
    """
    if geom is None or geom.isEmpty():
        return []
    g = geom.constGet()
    if g is None:
        return []
    if g.hasCurvedSegments():
        g = g.segmentize()

    gtype = QgsWkbTypes.geometryType(g.wkbType())
    parts = []

    if gtype == QgsWkbTypes.PolygonGeometry:
        polys = []
        if QgsWkbTypes.isMultiType(g.wkbType()):
            polys = [g.geometryN(i) for i in range(g.numGeometries())]
        else:
            polys = [g]
        for poly in polys:
            rings = []
            ext = _curve_to_linestring(poly.exteriorRing())
            if ext is None or ext.numPoints() < 4:
                continue
            rings.append(_ring_coords(ext, with_z))
            for k in range(poly.numInteriorRings()):
                inner = _curve_to_linestring(poly.interiorRing(k))
                if inner is not None and inner.numPoints() >= 4:
                    rings.append(_ring_coords(inner, with_z))
            parts.append(rings)

    elif gtype == QgsWkbTypes.LineGeometry:
        lines = []
        if QgsWkbTypes.isMultiType(g.wkbType()):
            lines = [g.geometryN(i) for i in range(g.numGeometries())]
        else:
            lines = [g]
        for line in lines:
            ls = _curve_to_linestring(line)
            if ls is not None and ls.numPoints() >= 2:
                parts.append([_ring_coords(ls, with_z)])

    return parts


def _build_linestring(coords, with_z):
    if with_z:
        pts = [QgsPoint(c[0], c[1], 0.0 if c[2] is None else c[2]) for c in coords]
    else:
        pts = [QgsPoint(c[0], c[1]) for c in coords]
    return QgsLineString(pts)


def assemble(parts, is_polygon, is_multi, with_z):
    """Собирает геометрию обратно. Возвращает QgsGeometry или None."""
    if is_polygon:
        built = []
        for rings in parts:
            if not rings or rings[0] is None:
                continue
            poly = QgsPolygon()
            poly.setExteriorRing(_build_linestring(rings[0], with_z))
            for inner in rings[1:]:
                if inner is not None:
                    poly.addInteriorRing(_build_linestring(inner, with_z))
            built.append(poly)
        if not built:
            return None
        if is_multi or len(built) > 1:
            mp = QgsMultiPolygon()
            for poly in built:
                mp.addGeometry(poly)
            return QgsGeometry(mp)
        return QgsGeometry(built[0])

    built = []
    for rings in parts:
        if not rings or rings[0] is None:
            continue
        built.append(_build_linestring(rings[0], with_z))
    if not built:
        return None
    if is_multi or len(built) > 1:
        ml = QgsMultiLineString()
        for line in built:
            ml.addGeometry(line)
        return QgsGeometry(ml)
    return QgsGeometry(built[0])


# ────────────────────────────────────────────────────────────────────────────
# Алгоритм
# ────────────────────────────────────────────────────────────────────────────

class TopologyCleanAlgorithm(QgsProcessingAlgorithm):

    INPUT = "INPUT"
    REFERENCE = "REFERENCE"
    TOLERANCE = "TOLERANCE"
    MODE = "MODE"
    PRIORITY = "PRIORITY"
    Z_MODE = "Z_MODE"
    CROSSINGS = "CROSSINGS"
    REPAIR = "REPAIR"
    PROTECT = "PROTECT"
    VALIDATE = "VALIDATE"
    OUTPUT = "OUTPUT"
    REPORT = "REPORT"

    def name(self):
        return "topologyclean"

    def displayName(self):
        return tr("1.03 Топологическая сшивка (узлы и вершины)")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return TopologyCleanAlgorithm()

    def shortHelpString(self):
        return help_for("topologyclean") + help_footer()

    # ── Параметры ─────────────────────────────────────────────────────────
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                tr("Входной слой (полигоны или линии)"),
                [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine],
            )
        )

        p_tol = QgsProcessingParameterNumber(
            self.TOLERANCE,
            tr("Допуск (в единицах CRS слоя)"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=2.0,
            minValue=1e-9,
        )
        p_tol.setHelp(
            "Максимальное расстояние, на которое разрешено сдвинуть вершину.\n"
            "Он же радиус поиска соседних рёбер для вставки узлов.\n"
            "Берите чуть больше реальной величины расхождений и заметно меньше\n"
            "длины самого короткого осмысленного ребра."
        )
        self.addParameter(p_tol)

        p_mode = QgsProcessingParameterEnum(
            self.MODE,
            tr("Режим"),
            options=[
                "Слияние вершин и вставка узлов (полная сшивка)",
                "Только вставка узлов (вершины не двигаются)",
                "Только слияние вершин",
            ],
            defaultValue=0,
        )
        p_mode.setHelp(
            "Полная сшивка закрывает зазоры и согласует узлы.\n"
            "Только вставка узлов не меняет ни одной существующей координаты,\n"
            "это безопасный первый проход для контроля объёма правок."
        )
        self.addParameter(p_mode)

        p_ref = QgsProcessingParameterFeatureSource(
            self.REFERENCE,
            tr("Эталонный слой (необязательно)"),
            [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine],
            optional=True,
        )
        p_ref.setHelp(
            "Слой, который трогать нельзя. Его вершины становятся опорными,\n"
            "входной слой подтягивается к ним. Сам эталон не изменяется."
        )
        self.addParameter(p_ref)

        p_prio = QgsProcessingParameterEnum(
            self.PRIORITY,
            tr("Кто кого притягивает"),
            options=[
                "По порядку объектов в слое",
                "Крупные объекты притягивают мелкие",
            ],
            defaultValue=1,
        )
        p_prio.setHelp(
            "Определяет, чьи вершины остаются на месте при слиянии.\n"
            "Обычно правильнее оставить на месте крупный объект,\n"
            "а мелкий подтянуть к нему."
        )
        self.addParameter(p_prio)

        p_z = QgsProcessingParameterEnum(
            self.Z_MODE,
            tr("Отметка Z вставленного узла"),
            options=[
                "Интерполировать вдоль ребра",
                "Взять у притянутой вершины",
            ],
            defaultValue=0,
        )
        p_z.setHelp(
            "Интерполяция сохраняет форму ребра в разрезе.\n"
            "Второй вариант нужен, когда узлы должны совпасть и по высоте."
        )
        self.addParameter(p_z)

        p_cross = QgsProcessingParameterBoolean(
            self.CROSSINGS,
            tr("Ставить узлы в точках пересечения рёбер"),
            defaultValue=True,
        )
        p_cross.setHelp(
            "Нужно для перехлёстов, где рёбра пересекаются крест-накрест,\n"
            "а общих вершин нет. Вставка узлов по вершинам такой случай\n"
            "не закрывает, потому что вставлять там нечего."
        )
        self.addParameter(p_cross)

        p_prot = QgsProcessingParameterBoolean(
            self.PROTECT,
            tr("Не изменять объекты уже допуска"),
            defaultValue=True,
        )
        p_prot.setHelp(
            "У объекта, чья ширина меньше допуска, противоположные берега\n"
            "слиплись бы, и он схлопнулся бы сам в себя. С этой галочкой он\n"
            "остаётся нетронутым и служит опорой: соседи подтягиваются к нему.\n"
            "Без неё такие объекты теряются целиком."
        )
        self.addParameter(p_prot)

        p_rep = QgsProcessingParameterEnum(
            self.REPAIR,
            tr("Если сшивка испортила геометрию"),
            options=[
                "Исправить, а если не выходит, вернуть исходную геометрию",
                "Вернуть исходную геометрию объекта",
                "Оставить как есть",
            ],
            defaultValue=0,
        )
        p_rep.setHelp(
            "Слияние вершин выворачивает форму, если объект уже допуска:\n"
            "противоположные берега слипаются. Первый вариант пробует исправить,\n"
            "а если правка съедает больше четверти площади, возвращает объект\n"
            "в исходный вид. Второй сразу возвращает исходный, тогда границы\n"
            "такого объекта останутся несогласованными. Третий пишет как вышло."
        )
        self.addParameter(p_rep)

        p_val = QgsProcessingParameterBoolean(
            self.VALIDATE,
            tr("Проверять корректность геометрии до и после"),
            defaultValue=True,
        )
        p_val.setHelp(
            "Считает число некорректных геометрий на входе и на выходе.\n"
            "На больших слоях проверка занимает заметное время."
        )
        self.addParameter(p_val)

        self.addParameter(
            QgsProcessingParameterFeatureSink(self.OUTPUT, tr("Сшитый слой"))
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.REPORT,
                tr("Точки правок (необязательно)"),
                QgsProcessing.TypeVectorPoint,
                optional=True,
                createByDefault=False,
            )
        )

    # ── Выполнение ────────────────────────────────────────────────────────
    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        mode = MODES[self.parameterAsEnum(parameters, self.MODE, context)]
        priority = self.parameterAsEnum(parameters, self.PRIORITY, context)
        z_mode = Z_MODES[self.parameterAsEnum(parameters, self.Z_MODE, context)]
        do_validate = self.parameterAsBoolean(parameters, self.VALIDATE, context)
        do_cross = self.parameterAsBoolean(parameters, self.CROSSINGS, context)
        repair = self.parameterAsEnum(parameters, self.REPAIR, context)
        protect = self.parameterAsBoolean(parameters, self.PROTECT, context)
        reference = self.parameterAsSource(parameters, self.REFERENCE, context)

        if tolerance <= 0:
            raise QgsProcessingException("Допуск должен быть больше нуля.")

        wkb = source.wkbType()
        is_polygon = QgsWkbTypes.geometryType(wkb) == QgsWkbTypes.PolygonGeometry
        is_multi = QgsWkbTypes.isMultiType(wkb)
        with_z = QgsWkbTypes.hasZ(wkb)

        # ── Чтение и разбор ───────────────────────────────────────────────
        # Инструменты топологии обязаны принимать некорректную геометрию:
        # именно её они и ищут. Иначе один плохой объект валит весь прогон.
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Чтение слоя..."))
        records = []          # (feature, parts as index lists)
        rings = []            # плоский список колец для ядра
        ring_owner = []       # индекс записи для каждого кольца
        area_before = 0.0
        invalid_before = 0
        skipped = 0

        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                return {}
            geom = feat.geometry()
            parts = explode(geom, with_z)
            if not parts:
                skipped += 1
                records.append((feat, None))
                continue
            if is_polygon:
                area_before += geom.area()
            if do_validate and not geom.isGeosValid():
                invalid_before += 1
            idx_parts = []
            for part in parts:
                idx_ring = []
                for ring in part:
                    idx_ring.append(len(rings))
                    rings.append(ring)
                    ring_owner.append(len(records))
                idx_parts.append(idx_ring)
            records.append((feat, idx_parts))
            if i % 500 == 0:
                feedback.setProgress(10.0 * i / total)

        if not rings:
            raise QgsProcessingException("Во входном слое нет пригодных геометрий.")

        # ── Приоритет ─────────────────────────────────────────────────────
        order = list(range(len(rings)))
        if priority == 1:
            def ring_size(idx):
                xs = [p[0] for p in rings[idx]]
                ys = [p[1] for p in rings[idx]]
                return -((max(xs) - min(xs)) * (max(ys) - min(ys)))
            order.sort(key=ring_size)
        ordered_rings = [rings[i] for i in order]

        frozen = set()
        if protect and is_polygon:
            for pos, src_idx in enumerate(order):
                if ring_width([(p[0], p[1]) for p in rings[src_idx]]) < tolerance:
                    frozen.add(pos)

        # ── Эталон ────────────────────────────────────────────────────────
        fixed = []
        if reference is not None:
            ref_z = QgsWkbTypes.hasZ(reference.wkbType())
            for feat in reference.getFeatures():
                if feedback.isCanceled():
                    return {}
                for part in explode(feat.geometry(), ref_z):
                    fixed.extend(part)
            feedback.pushInfo(tr("Эталон: колец %d") % len(fixed))

        # ── Ядро ──────────────────────────────────────────────────────────
        median, p05, n_seg = segment_length_stats(rings)
        feedback.pushInfo(
            tr("Сшивка: колец %d, вершин %d, допуск %g")
            % (len(rings), sum(len(r) for r in rings), tolerance)
        )
        feedback.pushInfo(
            tr("Длина ребра: медиана %.4f, пятый процентиль %.4f (рёбер %d)")
            % (median, p05, n_seg)
        )
        if is_polygon:
            narrow = 0
            widths = []
            for ring in rings:
                w = ring_width([(p[0], p[1]) for p in ring])
                if w > 0:
                    widths.append(w)
                    if w < tolerance:
                        narrow += 1
            if widths:
                widths.sort()
                feedback.pushInfo(
                    tr("Ширина колец: минимум %.4f, медиана %.4f")
                    % (widths[0], widths[len(widths) // 2]))
            if narrow and protect:
                feedback.pushInfo(
                    tr("Колец уже допуска: %d. Они оставлены без изменений и служат "
                    "опорой для соседей.") % narrow)
            elif narrow:
                feedback.pushWarning(
                    tr("Колец уже допуска: %d. У такого кольца противоположные берега "
                    "слипнутся, и оно схлопнется само в себя. Включите защиту "
                    "узких объектов либо возьмите допуск меньше %.4f.")
                    % (narrow, widths[0] if widths else tolerance))
        if p05 > 0 and tolerance > p05:
            feedback.pushInfo(
                tr("Допуск больше пяти процентов самых коротких рёбер (%.4f), "
                "мелкие изгибы будут сглажены.") % p05)

        def progress(fraction):
            feedback.setProgress(10.0 + 70.0 * fraction)

        result = clean_topology(
            ordered_rings,
            tolerance=tolerance,
            mode=mode,
            fixed_rings=fixed or None,
            z_insert=z_mode,
            node_crossings=do_cross,
            frozen=frozen,
            progress=progress,
        )

        new_rings = [None] * len(rings)
        for pos, src_idx in enumerate(order):
            new_rings[src_idx] = result["rings"][pos]
        stats = result["stats"]

        # ── Сборка и запись ───────────────────────────────────────────────
        out_wkb = QgsWkbTypes.multiType(wkb) if repair == 0 else wkb
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(), out_wkb, source.sourceCrs()
        )
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        area_after = 0.0
        invalid_after = 0
        broken = []
        repaired = 0
        reverted = 0
        dropped = 0
        written = 0
        for k, (feat, idx_parts) in enumerate(records):
            if feedback.isCanceled():
                return {}
            if idx_parts is None:
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                written += 1
                continue
            parts = [[new_rings[i] for i in part] for part in idx_parts]
            geom = assemble(parts, is_polygon, is_multi, with_z)
            if geom is None or geom.isEmpty():
                dropped += 1
                continue
            if is_polygon and repair != 2 and not geom.isGeosValid():
                src_geom = feat.geometry()
                if src_geom is not None and src_geom.isGeosValid():
                    broken.append(feat.id())
                    if repair == 0:
                        fixed = geom.makeValid()
                        keep = [p for p in fixed.asGeometryCollection()
                                if QgsWkbTypes.geometryType(p.wkbType())
                                == QgsWkbTypes.PolygonGeometry]
                        if keep:
                            fixed = QgsGeometry.collectGeometry(keep)
                            before = geom.area()
                            if before > 0 and abs(before - fixed.area()) / before <= 0.25:
                                geom = fixed
                                repaired += 1
                            else:
                                geom = QgsGeometry(src_geom)
                                reverted += 1
                        else:
                            geom = QgsGeometry(src_geom)
                            reverted += 1
                    else:
                        geom = QgsGeometry(src_geom)
                        reverted += 1
            if is_polygon:
                area_after += geom.area()
            if do_validate and not geom.isGeosValid():
                invalid_after += 1
            out = QgsFeature(feat)
            out.setGeometry(geom)
            sink.addFeature(out, QgsFeatureSink.FastInsert)
            written += 1
            if k % 500 == 0:
                feedback.setProgress(80.0 + 15.0 * k / len(records))

        # ── Слой точек правок ─────────────────────────────────────────────
        report_id = None
        want_report = parameters.get(self.REPORT) not in (None, "")
        if want_report:
            fields = QgsFields()
            fields.append(QgsField("kind", QVariant.String))
            fields.append(QgsField("dist", QVariant.Double))
            fields.append(QgsField("ring", QVariant.Int))
            (rsink, report_id) = self.parameterAsSink(
                parameters, self.REPORT, context, fields,
                QgsWkbTypes.Point, source.sourceCrs(),
            )
            if rsink is not None:
                for x, y, kind, dist, ring_pos in result["events"]:
                    f = QgsFeature(fields)
                    f.setGeometry(QgsGeometry(QgsPoint(x, y)))
                    src_idx = order[ring_pos] if ring_pos < len(order) else -1
                    f.setAttributes([kind, float(dist), int(src_idx)])
                    rsink.addFeature(f, QgsFeatureSink.FastInsert)

        # ── Отчёт ─────────────────────────────────────────────────────────
        feedback.setProgress(98)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Результат ──"))
        feedback.pushInfo(tr("Вершин сдвинуто:      %d") % stats["vertices_moved"])
        feedback.pushInfo(
            tr("Смещение макс/сред:   %.4f / %.4f") % (stats["max_move"], stats["mean_move"])
        )
        if stats.get("rings_frozen"):
            feedback.pushInfo(tr("Колец не изменялось:  %d (уже допуска)")
                              % stats["rings_frozen"])
        feedback.pushInfo(tr("Узлов вставлено:      %d (из них в пересечениях рёбер: %d)")
                          % (stats["nodes_inserted"], stats["nodes_crossing"]))
        feedback.pushInfo(
            tr("Вершин было/стало:    %d / %d") % (stats["vertices_in"], stats["vertices_out"])
        )
        if is_polygon:
            delta = area_after - area_before
            rel = (100.0 * delta / area_before) if area_before else 0.0
            feedback.pushInfo(
                tr("Площадь до/после:     %.3f / %.3f (%+.5f, %+.6f %%)")
                % (area_before, area_after, delta, rel)
            )
        if stats["rings_degenerate"]:
            feedback.pushWarning(
                tr("Вырожденных колец удалено: %d (допуск больше размера объекта)")
                % stats["rings_degenerate"]
            )
        if dropped:
            feedback.pushWarning(tr("Объектов потеряно целиком: %d") % dropped)
        if skipped:
            feedback.pushInfo(tr("Объектов без геометрии пропущено: %d") % skipped)
        if broken:
            feedback.pushInfo("")
            feedback.pushInfo(tr("Объектов испорчено сшивкой: %d") % len(broken))
            if repaired:
                feedback.pushInfo(tr("  из них исправлено:        %d") % repaired)
            if reverted:
                feedback.pushInfo(tr("  возвращено к исходным:    %d") % reverted)

            feedback.pushInfo(tr("  идентификаторы: %s%s") % (
                ", ".join(str(i) for i in broken[:10]),
                " и ещё %d" % (len(broken) - 10) if len(broken) > 10 else ""))
        if do_validate:
            feedback.pushInfo(
                tr("Некорректных геометрий до/после: %d / %d") % (invalid_before, invalid_after)
            )
            if invalid_after > invalid_before:
                feedback.pushWarning(
                    tr("Некорректных стало больше. Уменьшите допуск: ориентир это "
                    "пятый процентиль длины ребра, он напечатан выше.")
                )
        feedback.pushInfo(tr("Объектов записано:    %d") % written)
        feedback.setProgress(100)

        out = {self.OUTPUT: dest_id}
        if report_id is not None:
            out[self.REPORT] = report_id
        return out


# ────────────────────────────────────────────────────────────────────────────
# Вставка недостающих узлов
# ────────────────────────────────────────────────────────────────────────────


def _invalid_reason(geom):
    """
    Причина некорректности от того же движка, который её обнаружил.

    Спрашивать надо именно GEOS: встроенный валидатор QGIS пользуется другими
    правилами и на этих же данных возвращает пустой список, отчего причина
    выглядит неопределённой.
    """
    try:
        message = geom.lastError()
        if message:
            return message
    except Exception:
        pass
    try:
        from qgis.core import Qgis
        errors = geom.validateGeometry(Qgis.GeometryValidationEngine.Geos)
    except Exception:
        try:
            errors = geom.validateGeometry(1)
        except Exception:
            errors = []
    if errors:
        try:
            where = errors[0].where()
            return "%s в точке %.4f %.4f" % (errors[0].what(), where.x(), where.y())
        except Exception:
            return errors[0].what()
    return "GEOS считает геометрию некорректной, подробностей нет"



class InsertNodesAlgorithm(QgsProcessingAlgorithm):
    """
    Только вставка узлов. Ни одна существующая вершина не двигается
    и не удаляется, поэтому суммарная площадь обязана остаться прежней
    до последнего знака. Отчёт это подтверждает числом.
    """

    INPUT = "INPUT"
    REFERENCE = "REFERENCE"
    EPS = "EPS"
    CROSSINGS = "CROSSINGS"
    OUTPUT = "OUTPUT"
    REPORT = "REPORT"

    def name(self):
        return "insertnodes"

    def displayName(self):
        return tr("1.05 Вставить недостающие узлы")

    def group(self):
        return tr("1. Топология")

    def groupId(self):
        return "topology"

    def createInstance(self):
        return InsertNodesAlgorithm()

    def shortHelpString(self):
        return help_for("insertnodes") + help_footer()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, tr("Входной слой (полигоны или линии)"),
            [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine]))

        p = QgsProcessingParameterFeatureSource(
            self.REFERENCE, tr("Опорный слой (необязательно)"),
            [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine],
            optional=True)
        p.setHelp(
            "Источник узлов для входного слоя. Не изменяется и в результат\n"
            "не попадает. Нужен, когда вершины одного слоя лежат на рёбрах другого."
        )
        self.addParameter(p)

        p = QgsProcessingParameterNumber(
            self.EPS, tr("Допустимое отклонение вершины от ребра"),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=1e-6, minValue=1e-12)
        p.setHelp(
            "Защита от ложных срабатываний, а не допуск поиска.\n"
            "Узел ставится, только если вершина лежит на ребре ближе\n"
            "этой величины. Значение отвечает точности координат.\n"
            "Задавать метры здесь не следует."
        )
        self.addParameter(p)

        p = QgsProcessingParameterBoolean(
            self.CROSSINGS, tr("Ставить узлы в точках пересечения рёбер"),
            defaultValue=True)
        p.setHelp(
            "Точка пересечения лежит на обоих рёбрах, поэтому такая вставка\n"
            "тоже не меняет ни формы, ни площади."
        )
        self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, tr("Слой с узлами")))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.REPORT, tr("Вставленные узлы (необязательно)"),
            QgsProcessing.TypeVectorPoint, optional=True, createByDefault=False))

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException("Не удалось прочитать входной слой.")
        eps = self.parameterAsDouble(parameters, self.EPS, context)
        do_cross = self.parameterAsBoolean(parameters, self.CROSSINGS, context)
        reference = self.parameterAsSource(parameters, self.REFERENCE, context)

        wkb = source.wkbType()
        is_polygon = QgsWkbTypes.geometryType(wkb) == QgsWkbTypes.PolygonGeometry
        is_multi = QgsWkbTypes.isMultiType(wkb)
        with_z = QgsWkbTypes.hasZ(wkb)

        # Инструменты топологии обязаны принимать некорректную геометрию:
        # именно её они и ищут. Иначе один плохой объект валит весь прогон.
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        feedback.pushInfo(banner())
        feedback.pushInfo(tr("Чтение слоя..."))

        records = []
        rings = []
        area_before = 0.0
        vertices_before = 0
        total = source.featureCount() or 1
        for i, feat in enumerate(source.getFeatures()):
            if feedback.isCanceled():
                return {}
            geom = feat.geometry()
            parts = explode(geom, with_z)
            if not parts:
                records.append((feat, None))
                continue
            if is_polygon:
                area_before += geom.area()
            idx_parts = []
            for part in parts:
                idx_ring = []
                for ring in part:
                    idx_ring.append(len(rings))
                    vertices_before += len(ring)
                    rings.append(ring)
                idx_parts.append(idx_ring)
            records.append((feat, idx_parts))
            if i % 500 == 0:
                feedback.setProgress(10.0 * i / total)

        if not rings:
            raise QgsProcessingException("Во входном слое нет пригодных геометрий.")

        fixed = []
        if reference is not None:
            ref_z = QgsWkbTypes.hasZ(reference.wkbType())
            for feat in reference.getFeatures():
                if feedback.isCanceled():
                    return {}
                for part in explode(feat.geometry(), ref_z):
                    fixed.extend(part)
            feedback.pushInfo(tr("Опорный слой: колец %d") % len(fixed))

        feedback.pushInfo(tr("Колец %d, вершин %d, отклонение %g")
                          % (len(rings), vertices_before, eps))

        # Вставленный узел сам может лечь на ребро третьего объекта, поэтому
        # одного прохода мало. Повторяем, пока узлы находятся.
        MAX_PASSES = 8
        current = rings
        inserted_total = 0
        crossing_total = 0
        events = []
        passes = 0
        for step in range(MAX_PASSES):
            if feedback.isCanceled():
                return {}
            result = clean_topology(
                current, tolerance=eps, mode=MODE_INSERT,
                fixed_rings=fixed or None, z_insert=Z_INTERPOLATE,
                node_crossings=do_cross, project_onto_edge=True,
            )
            added = result["stats"]["nodes_inserted"]
            passes = step + 1
            inserted_total += added
            crossing_total += result["stats"]["nodes_crossing"]
            events.extend(result["events"])
            current = [r if r is not None else [] for r in result["rings"]]
            feedback.setProgress(10.0 + 70.0 * (step + 1) / MAX_PASSES)
            if added == 0:
                break
            feedback.pushInfo(tr("Проход %d: узлов %d") % (passes, added))

        result["events"] = events
        stats = dict(result["stats"])
        stats["nodes_inserted"] = inserted_total
        stats["nodes_crossing"] = crossing_total
        stats["passes"] = passes
        new_rings = [r if r else None for r in current]

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context, source.fields(), wkb, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException("Не удалось создать выходной слой.")

        area_after = 0.0
        vertices_after = 0
        written = 0
        touched = 0
        dropped = 0
        reverted = []
        reasons = []
        for k, (feat, idx_parts) in enumerate(records):
            if feedback.isCanceled():
                return {}
            if idx_parts is None:
                sink.addFeature(feat, QgsFeatureSink.FastInsert)
                written += 1
                continue
            parts = [[new_rings[i] for i in part] for part in idx_parts]
            before = sum(len(rings[i]) for part in idx_parts for i in part)
            after = sum(len(r) for part in parts for r in part if r is not None)
            geom = assemble(parts, is_polygon, is_multi, with_z)
            if geom is None or geom.isEmpty():
                dropped += 1
                continue
            # Вставка узла обязана оставлять геометрию не хуже, чем была.
            # Вершина лежит на ребре лишь в пределах точности координат,
            # поэтому в очень узком месте ребро может вывернуться.
            # Такой объект возвращается к исходному виду без узлов.
            if is_polygon and not geom.isGeosValid():
                src_geom = feat.geometry()
                if src_geom is not None and src_geom.isGeosValid():
                    if len(reasons) < 3:
                        reasons.append("%d: %s" % (feat.id(), _invalid_reason(geom)))
                    geom = QgsGeometry(src_geom)
                    reverted.append(feat.id())
                    after = before
            if after != before:
                touched += 1
            vertices_after += after
            if is_polygon:
                area_after += geom.area()
            out = QgsFeature(feat)
            out.setGeometry(geom)
            sink.addFeature(out, QgsFeatureSink.FastInsert)
            written += 1
            if k % 500 == 0:
                feedback.setProgress(80.0 + 15.0 * k / len(records))

        report_id = None
        if parameters.get(self.REPORT) not in (None, ""):
            fields = QgsFields()
            fields.append(QgsField("kind", QVariant.String))
            fields.append(QgsField("dist", QVariant.Double))
            (rsink, report_id) = self.parameterAsSink(
                parameters, self.REPORT, context, fields,
                QgsWkbTypes.Point, source.sourceCrs())
            if rsink is not None:
                for x, y, kind, dist, _ring in result["events"]:
                    f = QgsFeature(fields)
                    f.setGeometry(QgsGeometry(QgsPoint(x, y)))
                    f.setAttributes([kind, float(dist)])
                    rsink.addFeature(f, QgsFeatureSink.FastInsert)

        # ── Отчёт ─────────────────────────────────────────────────────────
        feedback.setProgress(98)
        feedback.pushInfo("")
        feedback.pushInfo(tr("── Результат ──"))
        feedback.pushInfo(tr("Узлов вставлено:      %d (из них в пересечениях рёбер: %d)")
                          % (stats["nodes_inserted"], stats["nodes_crossing"]))
        feedback.pushInfo(tr("Проходов до полного согласования: %d") % stats["passes"])
        if stats["passes"] >= 8:
            feedback.pushWarning(
                tr("Достигнут предел числа проходов. Возможно, узлы ещё нужны: "
                "запустите инструмент повторно по результату."))
        feedback.pushInfo(tr("Объектов изменено:    %d") % touched)
        feedback.pushInfo(tr("Вершин было/стало:    %d / %d") % (vertices_before, vertices_after))

        lost_vertices = vertices_before + stats["nodes_inserted"] - vertices_after
        if lost_vertices > 0:
            feedback.pushInfo(
                tr("Совпадающих вершин снято: %d (точные дубликаты, на форму не влияют)")
                % lost_vertices)

        if is_polygon:
            delta = area_after - area_before
            feedback.pushInfo(tr("Площадь до/после:     %.6f / %.6f") % (area_before, area_after))
            if delta == 0.0:
                feedback.pushInfo(tr("Площадь не изменилась ни на единицу."))
            else:
                rel = abs(delta) / area_before if area_before else 0.0
                if rel < 1e-12:
                    feedback.pushInfo(
                        tr("Расхождение площади %.3e, это ошибка округления.") % abs(delta))
                else:
                    feedback.pushWarning(
                        tr("Площадь изменилась на %.6f. Инструмент обещает не менять её "
                        "вовсе, поэтому проверьте отклонение от ребра: скорее всего "
                        "оно завышено.") % delta)

        if reverted:
            feedback.pushWarning(
                tr("Объектов возвращено к исходному виду: %d. Вставка узла вывернула "
                "их геометрию, узлы для них не добавлены. Идентификаторы: %s%s")
                % (len(reverted), ", ".join(str(i) for i in reverted[:10]),
                   " и ещё %d" % (len(reverted) - 10) if len(reverted) > 10 else ""))
            for line in reasons:
                feedback.pushInfo("  " + line)
            feedback.pushInfo(
                tr("Чтобы понять природу, запустите ещё раз со снятой галочкой "
                "об узлах в пересечениях рёбер. Если откаты исчезнут, дело "
                "в пересечениях, если останутся, в самих вершинах на рёбрах."))
        feedback.pushInfo(tr("Объектов на входе/выходе: %d / %d") % (len(records), written))
        if dropped:
            feedback.pushWarning(tr("Объектов потеряно: %d. Этого быть не должно.") % dropped)
        if stats["rings_degenerate"]:
            feedback.pushWarning(tr("Вырожденных колец: %d") % stats["rings_degenerate"])
        feedback.setProgress(100)

        out = {self.OUTPUT: dest_id}
        if report_id is not None:
            out[self.REPORT] = report_id
        return out
