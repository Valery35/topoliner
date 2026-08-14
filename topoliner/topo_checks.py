# -*- coding: utf-8 -*-
"""
topo_checks
-----------
Проверка топологии и конвейер автоматического исправления.

Работает поверх geom_backend, поэтому тестируется headless на Shapely
и выполняется в бою на QGIS. Геометрия здесь плоская: отметки Z
восстанавливаются вызывающей стороной по ближайшей исходной вершине.

Принцип разделения ответственности:

  auto    нарушение заведомо является мусором и чинится молча
  review  нарушение может быть содержательным, поэтому только показывается

Границу между auto и review проводят два порога: допуск в единицах длины
и порог площади. Всё, что мельче порогов, считается мусором. Всё, что крупнее,
является решением человека и не трогается ни при каких настройках.
"""

import math

try:  # внутри плагина QGIS
    from .i18n import tr
except ImportError:  # headless-тесты
    from i18n import tr

try:  # внутри плагина QGIS
    from .topo_core import (
        MODE_BOTH,
        MODE_INSERT,
        clean_topology,
        drop_repeated_vertices,
        remove_spikes,
        ring_area,
        ring_width,
        self_touch_points,
    )
except ImportError:  # headless-тесты
    from topo_core import (
        MODE_BOTH,
        MODE_INSERT,
        clean_topology,
        drop_repeated_vertices,
        remove_spikes,
        ring_area,
        ring_width,
        self_touch_points,
    )

SEVERITY_AUTO = "auto"
SEVERITY_REVIEW = "review"

# Типы нарушений
INVALID = "invalid"
SELF_TOUCH = "self_touch"
DUP_VERTEX = "dup_vertex"
SPIKE = "spike"
UNSNAPPED = "unsnapped"
ON_EDGE = "on_edge"
TINY_HOLE = "tiny_hole"
TINY_PART = "tiny_part"
TINY_FEATURE = "tiny_feature"
SLIVER = "sliver"
OVERLAP = "overlap"
GAP = "gap"
DUPLICATE = "duplicate"
NESTED = "nested"
LOST = "lost"
GROUP_SPLIT = "group_split"
GROUP_HOLE = "group_hole"

TYPE_LABELS = {
    INVALID: "некорректная геометрия",
    SELF_TOUCH: "самокасание кольца",
    DUP_VERTEX: "повторяющиеся вершины",
    SPIKE: "игла",
    UNSNAPPED: "вершина рядом с ребром соседа",
    ON_EDGE: "вершина лежит на ребре соседа без узла",
    TINY_HOLE: "микродыра",
    TINY_PART: "микрочасть",
    TINY_FEATURE: "микрообъект",
    SLIVER: "волосяной полигон",
    OVERLAP: "перекрытие",
    GAP: "щель в покрытии",
    DUPLICATE: "дубликат объекта",
    NESTED: "объект внутри другого",
    LOST: "объект потерян при исправлении",
    GROUP_SPLIT: "группа распалась на части",
    GROUP_HOLE: "внутреннее кольцо в группе",
}

def label_of(kind):
    """Название нарушения на языке интерфейса."""
    try:
        from .i18n import tr
    except ImportError:
        try:
            from i18n import tr
        except ImportError:
            return TYPE_LABELS.get(kind, kind)
    return tr(TYPE_LABELS.get(kind, kind))


DEFAULT_SPIKE_ANGLE = 1.0
AREA_EPS = 1e-9


def overlap_is_debris(backend, inter, area_threshold, tolerance):
    """
    Мусорное ли перекрытие.

    Площадь здесь не работает: полоса шириной с допуск и длиной в десятки метров
    наберёт сотню квадратных единиц, оставаясь при этом следствием смещения
    вершин, а не спором двух объектов за площадь. Решает эффективная ширина,
    удвоенная площадь на периметр. Узкая полоса это мусор при любой длине,
    а перекрытие шире допуска содержательно даже при малой площади.
    """
    # Пересечение бывает смесью полигонов, линий и точек. Меры снимаем
    # только с полигональных частей, иначе граница выходит пустой,
    # а ширина неопределённой.
    inter = backend.polygonal_only(inter)
    area = backend.area(inter)
    if area < area_threshold:
        return True
    perimeter = backend.length(backend.boundary(inter))
    if perimeter <= 0:
        return False
    return (2.0 * area / perimeter) < tolerance


def finding(kind, severity, fid=None, fid_b=None, value=0.0, xy=None, note="", key=""):
    x, y = (xy if xy else (None, None))
    return {
        "type": kind,
        "severity": severity,
        "fid": fid,
        "fid_b": fid_b,
        "value": float(value),
        "x": x,
        "y": y,
        "note": note,
        "key": "" if key is None else str(key),
    }


# ────────────────────────────────────────────────────────────────────────────
# Индекс по охватам
# ────────────────────────────────────────────────────────────────────────────

class BBoxIndex:
    """Сеточный индекс по охватам. Чистый Python, одинаков для обоих backend."""

    def __init__(self, cell):
        self.cell = cell if cell and cell > 0 else 1.0
        self.cells = {}

    @staticmethod
    def _keys(bounds, cell):
        x0, y0, x1, y1 = bounds
        i0 = int(math.floor(x0 / cell))
        j0 = int(math.floor(y0 / cell))
        i1 = int(math.floor(x1 / cell))
        j1 = int(math.floor(y1 / cell))
        # Предохранитель от гигантских охватов при мелкой ячейке.
        if (i1 - i0 + 1) * (j1 - j0 + 1) > 250000:
            step_i = max(1, (i1 - i0) // 500)
            step_j = max(1, (j1 - j0) // 500)
            for i in range(i0, i1 + 1, step_i):
                for j in range(j0, j1 + 1, step_j):
                    yield (i, j)
            return
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                yield (i, j)

    def add(self, key, bounds):
        for c in self._keys(bounds, self.cell):
            self.cells.setdefault(c, []).append(key)

    def query(self, bounds):
        out = set()
        for c in self._keys(bounds, self.cell):
            bucket = self.cells.get(c)
            if bucket:
                out.update(bucket)
        return out


def _auto_cell(backend, geoms):
    """Размер ячейки индекса по медианному охвату объектов."""
    sizes = []
    for g in geoms[:2000]:
        if backend.is_empty(g):
            continue
        x0, y0, x1, y1 = backend.bounds(g)
        sizes.append(max(x1 - x0, y1 - y0))
    if not sizes:
        return 1.0
    sizes.sort()
    return max(sizes[len(sizes) // 2], 1e-6)


# ────────────────────────────────────────────────────────────────────────────
# Разбор в кольца и сборка
# ────────────────────────────────────────────────────────────────────────────

def to_parts(backend, geom):
    """Геометрия в виде списка частей, часть это [внешнее кольцо, дыры...]."""
    parts = []
    for poly in backend.parts(geom):
        rings = backend.rings(poly)
        if not rings:
            continue
        cleaned = []
        for r in rings:
            # Кольца из backend замкнуты, внутри работаем без замыкания.
            if len(r) >= 2 and abs(r[0][0] - r[-1][0]) < 1e-12 and abs(r[0][1] - r[-1][1]) < 1e-12:
                r = r[:-1]
            if len(r) >= 3:
                cleaned.append([(p[0], p[1]) for p in r])
        if cleaned:
            parts.append(cleaned)
    return parts


def from_parts(backend, parts):
    polys = []
    for rings in parts:
        if not rings or rings[0] is None or len(rings[0]) < 3:
            continue
        closed = [list(rings[0]) + [rings[0][0]]]
        for inner in rings[1:]:
            if inner is not None and len(inner) >= 3:
                closed.append(list(inner) + [inner[0]])
        polys.append(backend.polygon(closed))
    if not polys:
        return None
    return backend.multipolygon(polys)


# ────────────────────────────────────────────────────────────────────────────
# Проверка
# ────────────────────────────────────────────────────────────────────────────

def check_items(backend, items, tolerance, area_threshold,
                do_overlaps=True, do_gaps=True, do_unsnapped=True,
                spike_angle=DEFAULT_SPIKE_ANGLE, cavity_area=0.0, progress=None):
    """
    items: список (fid, geom). Геометрия не изменяется.

    cavity_area  площадь, начиная с которой полость не считается щелью
                 и находкой не является: целик, озеро, незакартированный
                 участок. Ноль отключает проверку. Смысл в том, что мелкая
                 дыра в покрытии это дефект, а очень крупная почти всегда
                 часть замысла.
    Возвращает (findings, summary).
    """
    findings = []
    fids = [fid for fid, _g in items]
    geoms = [g for _fid, g in items]

    def tick(f):
        if progress:
            progress(f)

    # ── Пообъектные проверки ─────────────────────────────────────────────
    total = max(1, len(items))
    for i, (fid, g) in enumerate(items):
        if backend.is_empty(g):
            findings.append(finding(LOST, SEVERITY_REVIEW, fid, note=tr("пустая геометрия")))
            continue

        valid = backend.is_valid(g)
        if not valid:
            findings.append(finding(
                INVALID, SEVERITY_AUTO, fid, value=backend.area(g),
                xy=_safe_point(backend, g), note=backend.invalid_reason(g)))

        area = backend.area(g)
        if area < area_threshold:
            findings.append(finding(
                TINY_FEATURE, SEVERITY_REVIEW, fid, value=area,
                xy=_safe_point(backend, g),
                note=tr("площадь %.4f при пороге %.4f") % (area, area_threshold)))

        # Вершинные проверки идут независимо от корректности геометрии:
        # именно у некорректных объектов артефактов больше всего.
        if True:
            parts = to_parts(backend, g)
            for rings in parts:
                ext = rings[0]
                a = abs(ring_area(ext))
                if len(parts) > 1 and a < area_threshold:
                    findings.append(finding(
                        TINY_PART, SEVERITY_AUTO, fid, value=a, xy=ext[0],
                        note=tr("часть площадью %.4f из %d") % (a, len(parts))))
                w = ring_width(ext)
                if a >= area_threshold and w < tolerance:
                    findings.append(finding(
                        SLIVER, SEVERITY_REVIEW, fid, value=w, xy=ext[0],
                        note=tr("эффективная ширина меньше допуска")))
                for inner in rings[1:]:
                    ai = abs(ring_area(inner))
                    if ai < area_threshold:
                        findings.append(finding(
                            TINY_HOLE, SEVERITY_AUTO, fid, value=ai, xy=inner[0],
                            note=tr("дыра площадью %.4f при пороге %.4f")
                                 % (ai, area_threshold)))
                for ring in rings:
                    _, dups = drop_repeated_vertices(ring, True, tolerance=1e-9)
                    if dups:
                        findings.append(finding(
                            DUP_VERTEX, SEVERITY_AUTO, fid, value=dups, xy=ring[0],
                            note=tr("вершин подряд в одной точке: %d") % dups))
                    _, spikes = remove_spikes(ring, True, spike_angle)
                    if spikes:
                        findings.append(finding(
                            SPIKE, SEVERITY_AUTO, fid, value=spikes, xy=ring[0],
                            note=tr("разворотов границы назад: %d") % spikes))
                    for pt in self_touch_points(ring, True):
                        findings.append(finding(
                            SELF_TOUCH, SEVERITY_REVIEW, fid, value=1, xy=pt,
                            note=tr("кольцо проходит через точку дважды")))
        if i % 200 == 0:
            tick(0.35 * i / total)
    tick(0.35)

    # ── Парные проверки ──────────────────────────────────────────────────
    if do_overlaps:
        cell = _auto_cell(backend, geoms)
        index = BBoxIndex(cell)
        bounds = []
        for i, g in enumerate(geoms):
            if backend.is_empty(g):
                bounds.append(None)
                continue
            b = backend.bounds(g)
            bounds.append(b)
            index.add(i, b)

        seen_pairs = set()
        for i, g in enumerate(geoms):
            if bounds[i] is None:
                continue
            for j in index.query(bounds[i]):
                if j <= i:
                    continue
                pair = (i, j)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                h = geoms[j]
                if backend.is_empty(h) or not backend.intersects(g, h):
                    continue
                if backend.equals(g, h):
                    findings.append(finding(
                        DUPLICATE, SEVERITY_REVIEW, fids[i], fids[j],
                        value=backend.area(g), xy=_safe_point(backend, g),
                        note=tr("геометрии совпадают, атрибуты могут различаться")))
                    continue
                inter = backend.intersection(g, h)
                a = backend.area(inter)
                if a <= AREA_EPS:
                    continue
                if backend.contains(g, h) or backend.contains(h, g):
                    findings.append(finding(
                        NESTED, SEVERITY_REVIEW, fids[i], fids[j], value=a,
                        xy=_safe_point(backend, inter),
                        note=tr("один объект целиком внутри другого")))
                    continue
                debris = overlap_is_debris(backend, inter, area_threshold, tolerance)
                findings.append(finding(
                    OVERLAP, SEVERITY_AUTO if debris else SEVERITY_REVIEW,
                    fids[i], fids[j], value=a, xy=_safe_point(backend, inter),
                                        note=(tr("полоса шириной меньше допуска") if debris
                          else tr("перекрытие шире допуска, спор за площадь"))))
            if i % 200 == 0:
                tick(0.35 + 0.3 * i / total)
    tick(0.65)

    # ── Щели покрытия ────────────────────────────────────────────────────
    if do_gaps:
        merged = backend.union_all([g for g in geoms if not backend.is_empty(g)])
        for poly in backend.parts(merged):
            rings = backend.rings(poly)
            for inner in rings[1:]:
                hole = backend.polygon([inner])
                a = backend.area(hole)
                if cavity_area > 0.0 and a >= cavity_area:
                    continue
                sev = SEVERITY_AUTO if a < area_threshold else SEVERITY_REVIEW
                findings.append(finding(
                    GAP, sev, value=a, xy=_safe_point(backend, hole),
                    note=tr("дыра в объединении покрытия площадью %.4f") % a))
    tick(0.85)

    # ── Несогласованные узлы ─────────────────────────────────────────────
    if do_unsnapped:
        rings = []
        owner = []
        for fid, g in items:
            if backend.is_empty(g):
                continue
            for part in to_parts(backend, g):
                for ring in part:
                    rings.append(list(ring) + [ring[0]])
                    owner.append(fid)
        if rings:
            probe = clean_topology(rings, tolerance=tolerance, mode=MODE_INSERT)
            # Ноль означает, что вершина лежит точно на ребре соседа.
            # Это дефект вершинности при любом допуске. Ненулевое расстояние
            # означает лишь близость и целиком зависит от выбранного допуска.
            on_edge_eps = max(1e-9, tolerance * 1e-6)
            for x, y, kind, dist, ring_idx in probe["events"]:
                if kind == "insert":
                    on_edge = dist <= on_edge_eps
                    findings.append(finding(
                        ON_EDGE if on_edge else UNSNAPPED,
                        SEVERITY_AUTO,
                        owner[ring_idx] if ring_idx < len(owner) else None,
                        value=dist, xy=(x, y),
                        note=(tr("границы совпадают геометрически, узла нет")
                              if on_edge
                              else tr("вершина в %.4f от ребра соседа") % dist)))
    tick(1.0)

    summary = summarize(findings)
    return findings, summary


def _safe_point(backend, g):
    """
    Точка для отображения находки. Для вырожденной геометрии центроид
    не вычисляется, поэтому есть запасной путь через центр охвата.
    """
    if backend.is_empty(g):
        return None
    point = backend.centroid_xy(g)
    if point is not None:
        return point
    bounds = backend.bounds(g)
    return (0.5 * (bounds[0] + bounds[2]), 0.5 * (bounds[1] + bounds[3]))


def summarize(findings):
    """
    Сводка по типам: сколько auto, сколько review, максимум и медиана значения.

    Медиана важнее максимума: по одному максимуму не видно, единичный это
    выброс или таково всё множество находок.
    """
    values = {}
    out = {}
    for f in findings:
        slot = out.setdefault(
            f["type"], {"auto": 0, "review": 0, "value_max": 0.0, "value_med": 0.0})
        slot[f["severity"]] += 1
        if f["value"] > slot["value_max"]:
            slot["value_max"] = f["value"]
        values.setdefault(f["type"], []).append(f["value"])
    for kind, vals in values.items():
        vals.sort()
        out[kind]["value_med"] = vals[len(vals) // 2]
    return out


def tolerance_hint(findings, tolerance, edge_p05=None, min_width=None):
    """
    Подсказка по допуску, вычисленная из самих данных.

    Умолчание в поле нельзя выбрать заранее: два метра разумны для
    геомеханических зон и велики для карты масштаба 1:10 000. Зато после
    проверки видно распределение расхождений, и по нему можно назвать число.

    Считается по находкам «вершина рядом с ребром соседа»: их value это
    расстояние. Величина усечена сверху заданным допуском, потому что
    дальше него проверка не смотрит, и это оговаривается отдельно.

    edge_p05   пятый процентиль длины ребра, если известен
    min_width  минимальная ширина кольца, если известна

    Возвращает словарь или None, если считать не по чему.
    """
    distances = sorted(f["value"] for f in findings
                       if f["type"] == UNSNAPPED and f["value"] > 0.0)
    if not distances:
        return None

    def quantile(q):
        return distances[min(len(distances) - 1, int(q * len(distances)))]

    median = quantile(0.5)
    p95 = quantile(0.95)
    biggest = distances[-1]

    # Медиана у самого допуска означает, что распределение обрезано:
    # настоящие расхождения крупнее, и проверка их просто не увидела.
    censored = median > 0.5 * tolerance

    # Верхняя граница безопасного допуска: слишком крупный схлопывает
    # короткое ребро и узкий объект.
    limits = [value for value in (edge_p05, min_width) if value]
    ceiling = 0.5 * min(limits) if limits else None

    # Естественный порог ищется как разрыв в распределении: погрешность
    # оцифровки и настоящее разногласие обычно разделены пустотой.
    # Если разрыва нет, число не выдумывается: расхождения размазаны,
    # и выбор допуска остаётся решением человека.
    gap_at = None
    if len(distances) >= 8:
        best_ratio = 1.0
        low = int(0.1 * len(distances))
        high = int(0.9 * len(distances))
        for i in range(max(1, low), max(2, high)):
            before = distances[i - 1]
            after = distances[i]
            if before <= 0.0:
                continue
            ratio = after / before
            if ratio > best_ratio:
                best_ratio = ratio
                gap_at = before
        if best_ratio < 3.0:
            gap_at = None

    return {
        "count": len(distances),
        "median": median,
        "p95": p95,
        "max": biggest,
        "gap_at": gap_at,
        "ceiling": ceiling,
        "censored": censored,
        "edge_p05": edge_p05,
        "min_width": min_width,
    }


# ────────────────────────────────────────────────────────────────────────────
# Исправление
# ────────────────────────────────────────────────────────────────────────────

DEFAULT_OPTIONS = {
    "clean_vertices": True,     # дубли вершин и иглы
    "spike_angle": DEFAULT_SPIKE_ANGLE,
    "snap": True,               # сшивка узлов и вершин
    "fix_invalid": True,        # makeValid с контролем площади
    "drop_tiny_parts": True,    # микрочасти мультиполигонов
    "fill_tiny_holes": True,    # микродыры внутри объектов
    "resolve_overlaps": True,   # мелкие перекрытия
    "fill_gaps": True,          # мелкие щели покрытия
    "drop_tiny_features": False,  # удаление микрообъектов целиком
    "protect_narrow": True,     # не изменять объекты уже допуска
    "cavity_area": 0.0,         # порог площади полости, ноль отключает
    "overlap_winner": "larger",   # larger или first
    "max_area_loss": 0.25,      # доля площади, потеря которой отменяет правку
}


def fix_items(backend, items, tolerance, area_threshold, options=None, progress=None):
    """
    Конвейер исправления. Порядок шагов существенен.

    Возвращает (new_items, stats, findings_left).
    new_items это список (fid, geom или None). None означает, что объект
    исчез и его нельзя записывать.
    """
    opt = dict(DEFAULT_OPTIONS)
    opt.update(options or {})

    stats = {k: 0 for k in (
        "dup_vertices", "spikes", "vertices_moved", "nodes_inserted",
        "tiny_parts", "tiny_holes", "made_valid", "valid_rejected",
        "overlaps_fixed", "overlaps_left", "gaps_filled", "gaps_left",
        "tiny_features_dropped", "features_lost", "rings_frozen",
    )}
    stats["max_move"] = 0.0
    stats["area_before"] = 0.0
    stats["area_after"] = 0.0
    left = []

    def tick(f):
        if progress:
            progress(f)

    fids = [fid for fid, _g in items]
    geoms = [g for _fid, g in items]
    stats["area_before"] = sum(
        backend.area(g) for g in geoms if not backend.is_empty(g))

    # ── Шаг 1. Разбор и артефакты вершин ─────────────────────────────────
    all_parts = []
    for g in geoms:
        parts = [] if backend.is_empty(g) else to_parts(backend, g)
        if opt["clean_vertices"]:
            new_parts = []
            for rings in parts:
                new_rings = []
                for k, ring in enumerate(rings):
                    ring, dups = drop_repeated_vertices(ring, True, tolerance=1e-9)
                    stats["dup_vertices"] += dups
                    ring, spikes = remove_spikes(ring, True, opt["spike_angle"])
                    stats["spikes"] += spikes
                    if len(ring) >= 3:
                        new_rings.append(ring)
                    elif k == 0:
                        new_rings = []
                        break
                if new_rings:
                    new_parts.append(new_rings)
            parts = new_parts
        all_parts.append(parts)
    tick(0.15)

    # ── Шаг 2. Микрочасти и микродыры ────────────────────────────────────
    for idx, parts in enumerate(all_parts):
        if opt["drop_tiny_parts"] and len(parts) > 1:
            keep = [r for r in parts if abs(ring_area(r[0])) >= area_threshold]
            if keep and len(keep) < len(parts):
                stats["tiny_parts"] += len(parts) - len(keep)
                parts = keep
        if opt["fill_tiny_holes"]:
            for rings in parts:
                holes = [h for h in rings[1:] if abs(ring_area(h)) >= area_threshold]
                if len(holes) != len(rings) - 1:
                    stats["tiny_holes"] += (len(rings) - 1) - len(holes)
                    rings[1:] = holes
        all_parts[idx] = parts
    tick(0.2)

    # ── Шаг 3. Сшивка ────────────────────────────────────────────────────
    if opt["snap"]:
        flat = []
        addr = []
        for i, parts in enumerate(all_parts):
            for j, rings in enumerate(parts):
                for k, ring in enumerate(rings):
                    flat.append(list(ring) + [ring[0]])
                    addr.append((i, j, k))
        if flat:
            # Крупные кольца обходятся первыми и притягивают мелкие.
            order = sorted(range(len(flat)), key=lambda t: -abs(ring_area(flat[t])))
            frozen = set()
            if opt["protect_narrow"]:
                for pos, t in enumerate(order):
                    if ring_width(flat[t]) < tolerance:
                        frozen.add(pos)
            stats["rings_frozen"] = len(frozen)
            res = clean_topology(
                [flat[t] for t in order], tolerance=tolerance, mode=MODE_BOTH,
                frozen=frozen)
            stats["vertices_moved"] = res["stats"]["vertices_moved"]
            stats["nodes_inserted"] = res["stats"]["nodes_inserted"]
            stats["max_move"] = res["stats"]["max_move"]
            for pos, t in enumerate(order):
                i, j, k = addr[t]
                ring = res["rings"][pos]
                if ring is None:
                    all_parts[i][j][k] = None
                else:
                    trimmed = [(p[0], p[1]) for p in ring[:-1]]
                    all_parts[i][j][k] = trimmed
            # Убираем выпавшие кольца и части без внешнего кольца.
            for i, parts in enumerate(all_parts):
                new_parts = []
                for rings in parts:
                    if not rings or rings[0] is None:
                        continue
                    new_parts.append([r for r in rings if r is not None])
                all_parts[i] = new_parts
    tick(0.45)

    # ── Шаг 4. Сборка и корректность ─────────────────────────────────────
    out = []
    for i, parts in enumerate(all_parts):
        g = from_parts(backend, parts)
        if g is None or backend.is_empty(g):
            out.append(None)
            continue
        if opt["fix_invalid"] and not backend.is_valid(g):
            before = backend.area(g)
            fixed = backend.polygonal_only(backend.make_valid(g))
            # Отбрасываем лоскуты, оставшиеся от разрешения самопересечений.
            keep = [p for p in backend.parts(fixed)
                    if backend.area(p) >= area_threshold]
            if keep:
                fixed = backend.multipolygon(keep)
            after = backend.area(fixed)
            loss = 0.0 if before <= 0 else abs(before - after) / before
            if backend.is_empty(fixed) or loss > opt["max_area_loss"]:
                # Исправление не годится. Возвращаем объект к исходному виду:
                # результат не должен быть хуже входа. Границы такого объекта
                # останутся несогласованными, поэтому он уходит в разбор.
                stats["valid_rejected"] += 1
                g = geoms[i] if not backend.is_empty(geoms[i]) else g
                left.append(finding(
                    INVALID, SEVERITY_REVIEW, fids[i], value=loss,
                    xy=_safe_point(backend, g),
                    note=tr("сшивка испортила объект, исправление не помогло, "
                         "возвращена исходная геометрия")))
            else:
                g = fixed
                stats["made_valid"] += 1
        out.append(g)
    tick(0.55)

    # ── Шаг 5. Микрообъекты ──────────────────────────────────────────────
    for i, g in enumerate(out):
        if g is None:
            continue
        if backend.area(g) < area_threshold:
            if opt["drop_tiny_features"]:
                out[i] = None
                stats["tiny_features_dropped"] += 1
            else:
                left.append(finding(
                    TINY_FEATURE, SEVERITY_REVIEW, fids[i], value=backend.area(g),
                    xy=_safe_point(backend, g),
                    note=tr("объект мельче порога, удаление не выполнялось")))
    tick(0.6)

    # ── Шаг 6. Перекрытия ────────────────────────────────────────────────
    if opt["resolve_overlaps"]:
        live = [(i, g) for i, g in enumerate(out) if g is not None and not backend.is_empty(g)]
        cell = _auto_cell(backend, [g for _i, g in live])
        index = BBoxIndex(cell)
        for i, g in live:
            index.add(i, backend.bounds(g))
        checked = set()
        for i, g in live:
            if out[i] is None:
                continue
            for j in index.query(backend.bounds(out[i])):
                if j == i or (min(i, j), max(i, j)) in checked:
                    continue
                checked.add((min(i, j), max(i, j)))
                a, b = out[i], out[j]
                if a is None or b is None:
                    continue
                if not backend.intersects(a, b):
                    continue
                inter = backend.intersection(a, b)
                area = backend.area(inter)
                if area <= AREA_EPS:
                    continue
                if backend.equals(a, b) or backend.contains(a, b) or backend.contains(b, a):
                    stats["overlaps_left"] += 1
                    left.append(finding(
                        DUPLICATE if backend.equals(a, b) else NESTED,
                        SEVERITY_REVIEW, fids[i], fids[j], value=area,
                        xy=_safe_point(backend, inter),
                        note=tr("совпадение или вложение решается человеком")))
                    continue
                if not overlap_is_debris(backend, inter, area_threshold, tolerance):
                    stats["overlaps_left"] += 1
                    left.append(finding(
                        OVERLAP, SEVERITY_REVIEW, fids[i], fids[j], value=area,
                        xy=_safe_point(backend, inter),
                        note=tr("перекрытие шире допуска, это спор за площадь")))
                    continue
                # Мусорное перекрытие: вычитаем у проигравшего.
                if opt["overlap_winner"] == "first":
                    loser = j if fids[i] <= fids[j] else i
                else:
                    loser = j if backend.area(a) >= backend.area(b) else i
                keeper = i if loser == j else j
                cut = backend.difference(out[loser], out[keeper])
                cut = backend.polygonal_only(cut)
                before = backend.area(out[loser])
                if backend.is_empty(cut) or (before > 0 and (before - backend.area(cut)) / before > opt["max_area_loss"]):
                    stats["overlaps_left"] += 1
                    left.append(finding(
                        OVERLAP, SEVERITY_REVIEW, fids[i], fids[j], value=area,
                        xy=_safe_point(backend, inter),
                        note=tr("вычитание съедало слишком много площади")))
                    continue
                parts_keep = [p for p in backend.parts(cut)
                              if backend.area(p) >= area_threshold]
                if parts_keep:
                    cut = backend.multipolygon(parts_keep)
                out[loser] = cut
                stats["overlaps_fixed"] += 1
    tick(0.8)

    # ── Шаг 7. Щели ──────────────────────────────────────────────────────
    if opt["fill_gaps"]:
        live = [(i, g) for i, g in enumerate(out) if g is not None and not backend.is_empty(g)]
        if live:
            merged = backend.union_all([g for _i, g in live])
            cell = _auto_cell(backend, [g for _i, g in live])
            index = BBoxIndex(cell)
            for i, g in live:
                index.add(i, backend.bounds(g))
            for poly in backend.parts(merged):
                rings = backend.rings(poly)
                for inner in rings[1:]:
                    hole = backend.polygon([inner])
                    area = backend.area(hole)
                    if opt["cavity_area"] > 0.0 and area >= opt["cavity_area"]:
                        continue
                    if area >= area_threshold:
                        stats["gaps_left"] += 1
                        left.append(finding(
                            GAP, SEVERITY_REVIEW, value=area,
                            xy=_safe_point(backend, hole),
                            note=tr("щель крупнее порога, не заполнялась")))
                        continue
                    # Щель отходит соседу с наибольшей общей границей.
                    hb = backend.boundary(hole)
                    best = None
                    best_len = 0.0
                    for i in index.query(backend.bounds(hole)):
                        g = out[i]
                        if g is None or backend.is_empty(g):
                            continue
                        if not backend.intersects(g, hole):
                            continue
                        shared = backend.length(
                            backend.intersection(hb, backend.boundary(g)))
                        if shared > best_len:
                            best_len = shared
                            best = i
                    if best is None:
                        stats["gaps_left"] += 1
                        left.append(finding(
                            GAP, SEVERITY_REVIEW, value=area,
                            xy=_safe_point(backend, hole), note=tr("сосед не найден")))
                        continue
                    merged_geom = backend.polygonal_only(
                        backend.union_all([out[best], hole]))
                    if backend.is_empty(merged_geom):
                        stats["gaps_left"] += 1
                        continue
                    out[best] = merged_geom
                    stats["gaps_filled"] += 1
    tick(0.95)

    # ── Перепроверка остатков ────────────────────────────────────────────
    # Нарушение могло исчезнуть позже, при обработке соседней пары. Сообщать
    # о том, чего в результате уже нет, значит посылать человека впустую.
    by_fid = {fids[i]: g for i, g in enumerate(out) if g is not None}
    checked_left = []
    for item in left:
        if item["type"] == OVERLAP and item["fid"] in by_fid and item["fid_b"] in by_fid:
            a = by_fid[item["fid"]]
            b_ = by_fid[item["fid_b"]]
            if not backend.intersects(a, b_):
                stats["overlaps_left"] = max(0, stats["overlaps_left"] - 1)
                continue
            if backend.area(backend.intersection(a, b_)) <= AREA_EPS:
                stats["overlaps_left"] = max(0, stats["overlaps_left"] - 1)
                continue
        checked_left.append(item)
    left = checked_left

    # ── Итог ─────────────────────────────────────────────────────────────
    new_items = []
    for i, g in enumerate(out):
        if g is None or backend.is_empty(g):
            if not backend.is_empty(geoms[i]):
                stats["features_lost"] += 1
                left.append(finding(
                    LOST, SEVERITY_REVIEW, fids[i],
                    xy=_safe_point(backend, geoms[i]),
                    note=tr("объект исчез при исправлении")))
            new_items.append((fids[i], None))
        else:
            stats["area_after"] += backend.area(g)
            new_items.append((fids[i], g))
    tick(1.0)

    return new_items, stats, left


# ────────────────────────────────────────────────────────────────────────────
# Контроль сборки по атрибуту
# ────────────────────────────────────────────────────────────────────────────


def _group_parts(backend, parts, max_gap):
    """
    Разбивает части на тела по связности: ребро есть, если расстояние между
    частями не больше max_gap. При max_gap не больше нуля все части считаются
    одним телом, то есть группа обязана быть цельной.
    """
    if not parts:
        return []
    if max_gap <= 0.0:
        return [list(parts)]

    n = len(parts)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    boxes = [backend.bounds(p) for p in parts]
    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            # Расстояние между охватами не больше настоящего, это дешёвый отсев.
            ax0, ay0, ax1, ay1 = boxes[i]
            bx0, by0, bx1, by1 = boxes[j]
            dx = max(0.0, max(bx0 - ax1, ax0 - bx1))
            dy = max(0.0, max(by0 - ay1, ay0 - by1))
            if math.hypot(dx, dy) > max_gap:
                continue
            if backend.distance(parts[i], parts[j]) <= max_gap:
                union(i, j)

    bodies = {}
    for i in range(n):
        bodies.setdefault(find(i), []).append(parts[i])
    return list(bodies.values())


def check_assembly(backend, items, area_threshold=0.0, max_gap=0.0,
                   ignore_holes=False, is_line=False, progress=None):
    """
    Проверяет, собирается ли каждая группа объектов в одно целое тело.

    items: список (fid, geom, key), где key это значение группирующего атрибута.

    Смысл проверки. Объединение объектов одной группы должно давать ровно одну
    часть без внутренних колец. Если частей больше одной, внутри группы остался
    разрыв. Если появилось внутреннее кольцо, внутри группы осталась дыра.

    Проверка ловит то, что не находит поиск щелей по всему покрытию: зазор,
    выходящий на внешний край покрытия, дырой в объединении не является,
    но при сборке группы он разрезает её на части либо становится кольцом.

    max_gap      части, отстоящие от группы дальше этого расстояния, считаются
                 отдельными телами и находкой не являются. Ноль означает,
                 что группа обязана быть цельной. Значение нужно для данных,
                 где одно значение атрибута описывает несколько разнесённых
                 тел: полигоны изолиний, участки одного типа, острова.
    ignore_holes внутренние кольца не считаются нарушением. Нужно там, где
                 полость внутри тела входит в замысел.
    is_line      линейный слой. Вопрос тот же, собирается ли группа в одно
                 связное тело, но внутренних колец у линий не бывает,
                 и мерой служит длина, а не площадь

    Возвращает (findings, summary_by_group).
    """
    groups = {}
    for fid, g, key in items:
        if backend.is_empty(g):
            continue
        groups.setdefault(key, []).append((fid, g))

    findings = []
    per_group = {}
    total = max(1, len(groups))

    for n, (key, members) in enumerate(sorted(groups.items(), key=lambda kv: str(kv[0]))):
        merged = backend.union_all([g for _fid, g in members])
        if is_line:
            # Объединение оставляет участки раздельными, поэтому смежные
            # склеиваются в непрерывные цепи: вопрос в связности, а не
            # в числе исходных отрезков.
            parts = backend.line_parts(backend.merge_lines(merged))
            parts.sort(key=lambda p: -backend.length(p))
        else:
            parts = backend.parts(merged)
            parts.sort(key=lambda p: -backend.area(p))

        holes = 0
        splits = 0

        # Части разбиваются на тела: две части принадлежат одному телу,
        # если расстояние между ними не больше max_gap. Разрывом считается
        # только разделение внутри тела, разные тела нарушением не являются.
        bodies = _group_parts(backend, parts, max_gap)
        separate = len(bodies) - 1 if len(bodies) > 1 else 0

        measure = backend.length if is_line else backend.area
        for body in bodies:
            if len(body) < 2:
                continue
            ordered = sorted(body, key=lambda p: -measure(p))
            for extra in ordered[1:]:
                gap = min(
                    (backend.distance(extra, other) for other in body if other is not extra),
                    default=0.0)
                splits += 1
                findings.append(finding(
                    GROUP_SPLIT, SEVERITY_REVIEW, value=measure(extra),
                    xy=_safe_point(backend, extra), key=key,
                    note=tr("разрыв до ближайшей части %.4f") % gap))

        if not ignore_holes and not is_line:
            for part in parts:
                rings = backend.rings(part)
                for inner in rings[1:]:
                    hole = backend.polygon([inner])
                    a = backend.area(hole)
                    sev = SEVERITY_AUTO if a < area_threshold else SEVERITY_REVIEW
                    holes += 1
                    findings.append(finding(
                        GROUP_HOLE, sev, value=a, xy=_safe_point(backend, hole),
                        key=key, note=tr("полость внутри группы площадью %.4f") % a))

        per_group[key] = {
            "features": len(members),
            "parts": len(parts),
            # При нулевом пороге разрыва все части считаются одним телом,
            # поэтому для отчёта телами показываем сами части: иначе колонка
            # всегда равна единице и ничего не говорит.
            "bodies": len(parts) if max_gap <= 0.0 else len(bodies),
            "splits": splits,
            "separate": separate,
            "holes": holes,
            "area": backend.length(merged) if is_line else backend.area(merged),
        }
        if progress and n % 20 == 0:
            progress(n / total)
    if progress:
        progress(1.0)

    return findings, per_group


# ────────────────────────────────────────────────────────────────────────────
# Работа по группам
# ────────────────────────────────────────────────────────────────────────────

def split_groups(items, group_of):
    """Разбивает items на группы по ключу. Порядок объектов сохраняется."""
    groups = {}
    for entry in items:
        key = group_of(entry[0])
        groups.setdefault(key, []).append(entry)
    return groups


def check_grouped(backend, items, group_of, progress=None, **kwargs):
    """
    Проверка по группам.

    Нужна там, где слой не является единым покрытием: например, зоны нескольких
    пластов лежат в одном слое. Объекты разных пластов накладываются друг
    на друга по замыслу, и без группировки каждое такое наложение попадает
    в перекрытия, дубликаты и вложения. На реальном слое зон это давало
    сто шестьдесят шесть находок вместо сорока одной.

    Каждый объект принадлежит ровно одной группе, поэтому пообъектные проверки
    не удваиваются.
    """
    groups = split_groups(items, group_of)
    findings = []
    total = max(1, len(groups))
    for n, key in enumerate(sorted(groups, key=str)):
        part, _summary = check_items(backend, groups[key], **kwargs)
        for f in part:
            f["key"] = "" if key is None else str(key)
        findings.extend(part)
        if progress:
            progress((n + 1) / total)
    return findings, summarize(findings)


def fix_grouped(backend, items, group_of, progress=None, **kwargs):
    """
    Очистка по группам. Объекты разных групп не сшиваются между собой
    и не спорят за площадь.
    """
    groups = split_groups(items, group_of)
    order = {entry[0]: i for i, entry in enumerate(items)}
    merged_items = []
    merged_left = []
    stats = {}
    total = max(1, len(groups))
    for n, key in enumerate(sorted(groups, key=str)):
        part, part_stats, part_left = fix_items(backend, groups[key], **kwargs)
        merged_items.extend(part)
        for f in part_left:
            f["key"] = "" if key is None else str(key)
        merged_left.extend(part_left)
        for k, v in part_stats.items():
            if k == "max_move":
                stats[k] = max(stats.get(k, 0.0), v)
            else:
                stats[k] = stats.get(k, 0) + v
        if progress:
            progress((n + 1) / total)
    merged_items.sort(key=lambda e: order.get(e[0], 0))
    return merged_items, stats, merged_left
