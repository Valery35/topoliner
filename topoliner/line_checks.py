# -*- coding: utf-8 -*-
"""
line_checks
-----------
Проверка и очистка линейных слоёв.

У линий свой набор нарушений. Щели, перекрытия, вложения и волосяные полигоны
к ним не применимы вовсе, зато появляются висячие концы, недоводы, перелёты
и псевдоузлы. Поэтому это отдельный модуль, а не ветвление внутри
полигонального.

Разделение то же, что и везде: заведомый мусор чинится молча, возможный смысл
показывается. Висячий конец у гидросети или сети выработок обычно является
устьем или тупиком, поэтому он остаётся человеку. Недовод и перелёт короче
допуска являются следом оцифровки и убираются.

Чистый Python поверх geom_backend, тестируется headless.
"""

import math

try:  # внутри плагина QGIS
    from .i18n import tr
except ImportError:  # headless-тесты
    from i18n import tr

try:  # внутри плагина QGIS
    from .topo_checks import (
        DUPLICATE,
        DUP_VERTEX,
        INVALID,
        SEVERITY_AUTO,
        SEVERITY_REVIEW,
        SPIKE,
        finding,
        summarize,
    )
    from .topo_core import (
        MODE_INSERT,
        clean_topology,
        drop_repeated_vertices,
        remove_spikes,
    )
except ImportError:  # headless-тесты
    from topo_checks import (
        DUPLICATE,
        DUP_VERTEX,
        INVALID,
        SEVERITY_AUTO,
        SEVERITY_REVIEW,
        SPIKE,
        finding,
        summarize,
    )
    from topo_core import (
        MODE_INSERT,
        clean_topology,
        drop_repeated_vertices,
        remove_spikes,
    )

__all__ = [
    "check_lines",
    "SEVERITY_AUTO",
    "SEVERITY_REVIEW",
    "fix_lines",
    "DANGLE",
    "UNDERSHOOT",
    "OVERSHOOT",
    "PSEUDO_NODE",
    "CROSSING",
    "ZERO_LENGTH",
    "SHORT_LINE",
    "LINE_TYPE_LABELS",
]

# Типы нарушений, свойственные линиям
DANGLE = "dangle"
UNDERSHOOT = "undershoot"
OVERSHOOT = "overshoot"
PSEUDO_NODE = "pseudo_node"
CROSSING = "crossing"
ZERO_LENGTH = "zero_length"
SHORT_LINE = "short_line"

LINE_TYPE_LABELS = {
    DANGLE: "висячий конец",
    UNDERSHOOT: "недовод до соседней линии",
    OVERSHOOT: "перелёт за узел",
    PSEUDO_NODE: "псевдоузел",
    CROSSING: "пересечение без узла",
    ZERO_LENGTH: "линия нулевой длины",
    SHORT_LINE: "линия короче порога",
}

EPS = 1e-9


# ────────────────────────────────────────────────────────────────────────────
# Вспомогательное
# ────────────────────────────────────────────────────────────────────────────

def _round_key(x, y, grid):
    return (round(x / grid), round(y / grid))


def _length(coords):
    total = 0.0
    for i in range(len(coords) - 1):
        total += math.hypot(coords[i + 1][0] - coords[i][0],
                            coords[i + 1][1] - coords[i][1])
    return total


def _point_segment(px, py, x1, y1, x2, y2):
    """Расстояние от точки до отрезка и параметр проекции."""
    dx, dy = x2 - x1, y2 - y1
    d2 = dx * dx + dy * dy
    if d2 <= 0.0:
        return math.hypot(px - x1, py - y1), 0.0
    t = ((px - x1) * dx + (py - y1) * dy) / d2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy)), t


def _distance_to_line(px, py, coords):
    """Минимальное расстояние от точки до ломаной."""
    best = float("inf")
    for i in range(len(coords) - 1):
        d, _t = _point_segment(px, py, coords[i][0], coords[i][1],
                               coords[i + 1][0], coords[i + 1][1])
        if d < best:
            best = d
    return best


class _Grid:
    """Сеточный индекс линий по охватам."""

    def __init__(self, cell):
        self.cell = cell if cell > 0 else 1.0
        self.cells = {}

    def add(self, key, coords):
        xs = [p[0] for p in coords]
        ys = [p[1] for p in coords]
        i0 = int(math.floor(min(xs) / self.cell))
        i1 = int(math.floor(max(xs) / self.cell))
        j0 = int(math.floor(min(ys) / self.cell))
        j1 = int(math.floor(max(ys) / self.cell))
        if (i1 - i0 + 1) * (j1 - j0 + 1) > 200000:
            step_i = max(1, (i1 - i0) // 400)
            step_j = max(1, (j1 - j0) // 400)
            rng = [(i, j) for i in range(i0, i1 + 1, step_i)
                   for j in range(j0, j1 + 1, step_j)]
        else:
            rng = [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]
        for c in rng:
            self.cells.setdefault(c, []).append(key)

    def near(self, x, y, radius):
        cx = int(math.floor(x / self.cell))
        cy = int(math.floor(y / self.cell))
        span = max(1, int(math.ceil(radius / self.cell)))
        out = set()
        for i in range(cx - span, cx + span + 1):
            for j in range(cy - span, cy + span + 1):
                out.update(self.cells.get((i, j), ()))
        return out


# ────────────────────────────────────────────────────────────────────────────
# Проверка
# ────────────────────────────────────────────────────────────────────────────

def check_lines(items, tolerance, min_length=0.0, grid=1e-7,
                do_dangles=True, do_crossings=True, do_pseudo=True,
                spike_angle=1.0, progress=None):
    """
    items: список (fid, coords), coords это список (x, y).

    tolerance   расстояние, ниже которого расхождение считается погрешностью
    min_length  длина, ниже которой линия считается мусором. Ноль отключает

    Возвращает (findings, summary).
    """
    findings = []
    fids = [fid for fid, _c in items]
    lines = [list(c) for _fid, c in items]

    def tick(f):
        if progress:
            progress(f)

    # ── Пообъектные проверки ─────────────────────────────────────────────
    total = max(1, len(items))
    for i, coords in enumerate(lines):
        fid = fids[i]
        if len(coords) < 2:
            findings.append(finding(INVALID, SEVERITY_REVIEW, fid,
                                    note=tr("в линии меньше двух вершин")))
            continue

        length = _length(coords)
        if length <= EPS:
            findings.append(finding(ZERO_LENGTH, SEVERITY_AUTO, fid,
                                    value=length, xy=coords[0],
                                    note=tr("все вершины в одной точке")))
            continue
        if min_length > 0 and length < min_length:
            findings.append(finding(SHORT_LINE, SEVERITY_REVIEW, fid,
                                    value=length, xy=coords[0],
                                    note=tr("длина %.4f при пороге %.4f")
                                         % (length, min_length)))

        _, dups = drop_repeated_vertices(coords, False, tolerance=EPS)
        if dups:
            findings.append(finding(DUP_VERTEX, SEVERITY_AUTO, fid,
                                    value=dups, xy=coords[0],
                                    note=tr("вершин подряд в одной точке: %d") % dups))
        _, spikes = remove_spikes(coords, False, spike_angle)
        if spikes:
            findings.append(finding(SPIKE, SEVERITY_AUTO, fid,
                                    value=spikes, xy=coords[0],
                                    note=tr("разворотов линии назад: %d") % spikes))
        if i % 200 == 0:
            tick(0.3 * i / total)
    tick(0.3)

    # ── Индексы концов и линий ───────────────────────────────────────────
    ends = {}          # ключ вершины -> список (индекс линии, 0 начало 1 конец)
    for i, coords in enumerate(lines):
        if len(coords) < 2:
            continue
        for side, point in ((0, coords[0]), (1, coords[-1])):
            ends.setdefault(_round_key(point[0], point[1], grid), []).append((i, side))

    cell = max(tolerance * 4, 1e-6)
    index = _Grid(cell)
    for i, coords in enumerate(lines):
        if len(coords) >= 2:
            index.add(i, coords)

    # ── Дубликаты ────────────────────────────────────────────────────────
    seen = {}
    for i, coords in enumerate(lines):
        if len(coords) < 2:
            continue
        key = tuple(_round_key(p[0], p[1], grid) for p in coords)
        rev = tuple(reversed(key))
        signature = min(key, rev)
        if signature in seen:
            findings.append(finding(DUPLICATE, SEVERITY_REVIEW,
                                    fids[seen[signature]], fids[i],
                                    value=_length(coords), xy=coords[0],
                                    note=tr("вершины совпадают, атрибуты могут "
                                         "различаться")))
        else:
            seen[signature] = i
    tick(0.4)

    # ── Висячие концы, недоводы, перелёты ────────────────────────────────
    if do_dangles:
        for i, coords in enumerate(lines):
            if len(coords) < 2:
                continue
            for side, point in ((0, coords[0]), (1, coords[-1])):
                key = _round_key(point[0], point[1], grid)
                if len(ends.get(key, ())) > 1:
                    continue          # конец стыкуется с другим концом

                px, py = point[0], point[1]
                on_line = False
                nearest = float("inf")
                for j in index.near(px, py, tolerance):
                    if j == i:
                        continue
                    d = _distance_to_line(px, py, lines[j])
                    if d <= EPS:
                        on_line = True
                        break
                    if d < nearest:
                        nearest = d
                if on_line:
                    continue

                # Перелёт проверяется раньше недовода: у хвоста, торчащего
                # за пересечением, конец тоже отстоит от соседней линии,
                # и без этой очерёдности перелёт попал бы в недоводы.
                tail = _overshoot_length(lines, index, i, side, tolerance)
                if tail is not None and tail <= tolerance:
                    findings.append(finding(OVERSHOOT, SEVERITY_AUTO, fids[i],
                                            value=tail, xy=point,
                                            note=tr("хвост за узлом длиной %.4f")
                                                 % tail))
                    continue

                if nearest <= tolerance:
                    findings.append(finding(UNDERSHOOT, SEVERITY_AUTO, fids[i],
                                            value=nearest, xy=point,
                                            note=tr("не доходит до соседней линии "
                                                 "на %.4f") % nearest))
                    continue

                findings.append(finding(DANGLE, SEVERITY_REVIEW, fids[i],
                                        value=0.0, xy=point,
                                        note=tr("конец ни с чем не соединён, "
                                             "соседей ближе допуска нет")))
    tick(0.6)

    # ── Пересечения без узла ─────────────────────────────────────────────
    if do_crossings:
        checked = set()
        for point, i, j in _crossings(lines, index, grid):
            pair = (min(i, j), max(i, j), point)
            if pair in checked:
                continue
            checked.add(pair)
            findings.append(finding(CROSSING, SEVERITY_AUTO, fids[i], fids[j],
                                    value=0.0, xy=point,
                                    note=tr("линии пересекаются, узла в точке нет")))
    tick(0.8)

    # ── Псевдоузлы ───────────────────────────────────────────────────────
    if do_pseudo:
        for key, owners in ends.items():
            if len(owners) != 2:
                continue
            a, b = owners[0][0], owners[1][0]
            if a == b:
                continue          # кольцо, замкнутое само на себя
            point = lines[a][0] if owners[0][1] == 0 else lines[a][-1]
            findings.append(finding(PSEUDO_NODE, SEVERITY_REVIEW, fids[a], fids[b],
                                    value=0.0, xy=point,
                                    note=tr("две линии можно объединить в одну")))
    tick(1.0)

    return findings, summarize(findings)


def _overshoot_length(lines, index, i, side, tolerance):
    """
    Длина хвоста за ближайшим пересечением с чужой линией.

    Перелёт это короткий хвост, торчащий за узлом: линия пересекла соседа
    и продолжилась дальше на несколько сантиметров. Возвращает длину хвоста
    или None, если пересечения рядом нет.
    """
    coords = lines[i] if side == 1 else list(reversed(lines[i]))
    walked = 0.0
    for k in range(len(coords) - 1, 0, -1):
        x1, y1 = coords[k][0], coords[k][1]
        x2, y2 = coords[k - 1][0], coords[k - 1][1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        for j in index.near(x1, y1, tolerance + seg_len):
            if j == i:
                continue
            for m in range(len(lines[j]) - 1):
                hit = _segment_intersection(
                    x1, y1, x2, y2,
                    lines[j][m][0], lines[j][m][1],
                    lines[j][m + 1][0], lines[j][m + 1][1])
                if hit is None:
                    continue
                tail = walked + math.hypot(hit[0] - x1, hit[1] - y1)
                return tail
        walked += seg_len
        if walked > tolerance:
            return None
    return None


def _segment_intersection(x1, y1, x2, y2, x3, y3, x4, y4):
    """Точка пересечения двух отрезков строго внутри обоих."""
    ax, ay = x2 - x1, y2 - y1
    bx, by = x4 - x3, y4 - y3
    den = ax * by - ay * bx
    if abs(den) < 1e-15:
        return None
    dx, dy = x3 - x1, y3 - y1
    t = (dx * by - dy * bx) / den
    u = (dx * ay - dy * ax) / den
    if t <= 0.0 or t >= 1.0 or u <= 0.0 or u >= 1.0:
        return None
    return (x1 + t * ax, y1 + t * ay)


def _crossings(lines, index, grid):
    """Точки, где две линии пересекаются, а вершины там нет ни у одной."""
    out = []
    checked = set()
    for i, a in enumerate(lines):
        if len(a) < 2:
            continue
        for k in range(len(a) - 1):
            for j in index.near(a[k][0], a[k][1], 0.0):
                if j <= i:
                    continue
                pair = (i, j)
                if pair in checked:
                    continue
                b = lines[j]
                for m in range(len(b) - 1):
                    hit = _segment_intersection(
                        a[k][0], a[k][1], a[k + 1][0], a[k + 1][1],
                        b[m][0], b[m][1], b[m + 1][0], b[m + 1][1])
                    if hit is None:
                        continue
                    key = _round_key(hit[0], hit[1], grid)
                    has_vertex = any(_round_key(p[0], p[1], grid) == key
                                     for p in (a[k], a[k + 1], b[m], b[m + 1]))
                    if not has_vertex:
                        out.append(((round(hit[0], 9), round(hit[1], 9)), i, j))
                        checked.add(pair)
                        break
    return out


# ────────────────────────────────────────────────────────────────────────────
# Очистка
# ────────────────────────────────────────────────────────────────────────────

DEFAULT_LINE_OPTIONS = {
    "clean_vertices": True,     # дубли вершин и иглы
    "spike_angle": 1.0,
    "snap": True,               # сшивка концов и вставка узлов
    "trim_overshoots": True,    # обрезка перелётов короче допуска
    "close_undershoots": True,  # дотягивание недоводов до соседней линии
    "drop_zero_length": True,
    "drop_short": False,        # удаление линий короче порога
}


def fix_lines(items, tolerance, min_length=0.0, options=None, grid=1e-7,
              progress=None):
    """
    Очистка линейного слоя.

    Возвращает (new_items, stats, findings_left), где new_items это список
    (fid, coords или None).
    """
    opt = dict(DEFAULT_LINE_OPTIONS)
    opt.update(options or {})

    stats = {k: 0 for k in (
        "dup_vertices", "spikes", "vertices_moved", "nodes_inserted",
        "overshoots_trimmed", "undershoots_closed", "zero_dropped",
        "short_dropped", "lines_lost",
    )}
    stats["max_move"] = 0.0
    stats["length_before"] = 0.0
    stats["length_after"] = 0.0
    left = []

    fids = [fid for fid, _c in items]
    lines = [list(c) for _fid, c in items]
    stats["length_before"] = sum(_length(c) for c in lines if len(c) >= 2)

    def tick(f):
        if progress:
            progress(f)

    # ── Шаг 1. Артефакты вершин ──────────────────────────────────────────
    if opt["clean_vertices"]:
        for i, coords in enumerate(lines):
            if len(coords) < 2:
                continue
            coords, dups = drop_repeated_vertices(coords, False, tolerance=EPS)
            stats["dup_vertices"] += dups
            coords, spikes = remove_spikes(coords, False, opt["spike_angle"])
            stats["spikes"] += spikes
            lines[i] = coords
    tick(0.2)

    # ── Шаг 2. Обрезка перелётов ─────────────────────────────────────────
    if opt["trim_overshoots"]:
        cell = max(tolerance * 4, 1e-6)
        index = _Grid(cell)
        for i, coords in enumerate(lines):
            if len(coords) >= 2:
                index.add(i, coords)
        ends = {}
        for i, coords in enumerate(lines):
            if len(coords) < 2:
                continue
            for point in (coords[0], coords[-1]):
                ends.setdefault(_round_key(point[0], point[1], grid), 0)
                ends[_round_key(point[0], point[1], grid)] += 1

        for i, coords in enumerate(lines):
            if len(coords) < 2:
                continue
            for side in (1, 0):
                point = coords[-1] if side == 1 else coords[0]
                if ends.get(_round_key(point[0], point[1], grid), 0) > 1:
                    continue
                tail = _overshoot_length(lines, index, i, side, tolerance)
                if tail is None or tail > tolerance:
                    continue
                trimmed = _trim_tail(lines[i], side, tolerance, lines, index)
                if trimmed is not None and len(trimmed) >= 2:
                    lines[i] = trimmed
                    coords = trimmed
                    stats["overshoots_trimmed"] += 1
    tick(0.5)

    # ── Шаг 2а. Дотягивание недоводов ────────────────────────────────────
    # Вставка узлов вершины не двигает, поэтому недовод она не закрывает:
    # конец надо перенести на проекцию, на соседнюю линию.
    if opt["close_undershoots"]:
        cell = max(tolerance * 4, 1e-6)
        index = _Grid(cell)
        for i, coords in enumerate(lines):
            if len(coords) >= 2:
                index.add(i, coords)
        ends = {}
        for i, coords in enumerate(lines):
            if len(coords) < 2:
                continue
            for point in (coords[0], coords[-1]):
                key = _round_key(point[0], point[1], grid)
                ends[key] = ends.get(key, 0) + 1

        for i, coords in enumerate(lines):
            if len(coords) < 2:
                continue
            for side in (0, 1):
                point = coords[0] if side == 0 else coords[-1]
                if ends.get(_round_key(point[0], point[1], grid), 0) > 1:
                    continue
                target = _nearest_point_on_lines(point[0], point[1], lines,
                                                 index, i, tolerance)
                if target is None:
                    continue
                moved = list(lines[i])
                shift = math.hypot(target[0] - point[0], target[1] - point[1])
                if shift <= EPS:
                    continue
                moved[0 if side == 0 else -1] = target
                lines[i] = moved
                stats["undershoots_closed"] += 1
                if shift > stats["max_move"]:
                    stats["max_move"] = shift
                stats["vertices_moved"] += 1
    tick(0.65)

    # ── Шаг 3. Сшивка и вставка узлов ────────────────────────────────────
    if opt["snap"]:
        usable = [(i, c) for i, c in enumerate(lines) if len(c) >= 2]
        if usable:
            res = clean_topology([c for _i, c in usable], tolerance=tolerance,
                                 mode=MODE_INSERT, project_onto_edge=True)
            stats["nodes_inserted"] = res["stats"]["nodes_inserted"]
            for pos, (i, _c) in enumerate(usable):
                ring = res["rings"][pos]
                if ring:
                    lines[i] = [(p[0], p[1]) for p in ring]
    tick(0.8)

    # ── Шаг 4. Итог ──────────────────────────────────────────────────────
    out = []
    for i, coords in enumerate(lines):
        length = _length(coords) if len(coords) >= 2 else 0.0
        if len(coords) < 2 or length <= EPS:
            if opt["drop_zero_length"]:
                stats["zero_dropped"] += 1
                out.append((fids[i], None))
                continue
        if min_length > 0 and length < min_length:
            if opt["drop_short"]:
                stats["short_dropped"] += 1
                out.append((fids[i], None))
                continue
            left.append(finding(SHORT_LINE, SEVERITY_REVIEW, fids[i],
                                value=length, xy=coords[0] if coords else None,
                                note=tr("линия короче порога, удаление не выполнялось")))
        stats["length_after"] += length
        out.append((fids[i], coords))
    tick(1.0)

    return out, stats, left


def _trim_tail(coords, side, tolerance, lines, index):
    """Обрезает хвост линии до ближайшего пересечения с чужой линией."""
    work = coords if side == 1 else list(reversed(coords))
    walked = 0.0
    for k in range(len(work) - 1, 0, -1):
        x1, y1 = work[k][0], work[k][1]
        x2, y2 = work[k - 1][0], work[k - 1][1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        best = None
        for j in index.near(x1, y1, tolerance + seg_len):
            if lines[j] is coords:
                continue
            for m in range(len(lines[j]) - 1):
                hit = _segment_intersection(
                    x1, y1, x2, y2,
                    lines[j][m][0], lines[j][m][1],
                    lines[j][m + 1][0], lines[j][m + 1][1])
                if hit is None:
                    continue
                d = math.hypot(hit[0] - x1, hit[1] - y1)
                if best is None or d < best[1]:
                    best = (hit, d)
        if best is not None:
            cut = work[:k] + [best[0]]
            result = cut if side == 1 else list(reversed(cut))
            return result
        walked += seg_len
        if walked > tolerance:
            return None
    return None


def _nearest_point_on_lines(px, py, lines, index, skip, tolerance):
    """Ближайшая точка на чужой линии в пределах допуска, либо None."""
    best = None
    best_d = tolerance
    for j in index.near(px, py, tolerance):
        if j == skip:
            continue
        coords = lines[j]
        for k in range(len(coords) - 1):
            x1, y1 = coords[k][0], coords[k][1]
            x2, y2 = coords[k + 1][0], coords[k + 1][1]
            d, t = _point_segment(px, py, x1, y1, x2, y2)
            if d <= best_d:
                best_d = d
                best = (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return best
