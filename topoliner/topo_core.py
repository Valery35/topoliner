# -*- coding: utf-8 -*-
"""
topo_core
---------
Ядро топологической сшивки. Чистый Python, без зависимостей от QGIS,
поэтому тестируется headless (см. tests/test_topo_core.py).

Работает со списком колец. Кольцо это список вершин (x, y) или (x, y, z).
Замкнутость определяется совпадением первой и последней вершины.

Две операции:

1. Слияние близких вершин (merge). Жадная кластеризация по лидеру:
   вершины обходятся в фиксированном порядке, первая незанятая становится
   лидером кластера, остальные в радиусе допуска притягиваются к ней.
   Гарантия: смещение любой вершины не превышает допуск. Цепочек нет,
   потому что лидер выбирается один раз и сам никуда не двигается.

2. Вставка узлов (insert). Если вершина лежит в пределах допуска от
   чужого сегмента, но не совпадает с его концами, в сегмент вставляется
   узел с координатами этой вершины. Смещение линии не превышает допуск,
   а границы соседних объектов после этого совпадают вершина в вершину.

Порядок колец на входе задаёт приоритет: чьи вершины становятся лидерами.
Кольца из fixed_rings обходятся первыми и на выход не идут, их вершины
всегда лидеры (эталонная граница, которую нельзя трогать).
"""

import math

__all__ = [
    "clean_topology",
    "ring_area",
    "ring_perimeter",
    "ring_width",
    "segment_length_stats",
    "drop_repeated_vertices",
    "remove_spikes",
    "self_touch_points",
    "MODE_INSERT",
    "MODE_MERGE",
    "MODE_BOTH",
    "Z_INTERPOLATE",
    "Z_FROM_VERTEX",
]

MODE_INSERT = "insert"
MODE_MERGE = "merge"
MODE_BOTH = "both"

Z_INTERPOLATE = "interpolate"
Z_FROM_VERTEX = "vertex"

# Порог точного совпадения координат. Меньше любого разумного допуска.
EPS = 1e-9


# ────────────────────────────────────────────────────────────────────────────
# Вспомогательная геометрия
# ────────────────────────────────────────────────────────────────────────────

def ring_area(coords):
    """Площадь замкнутого кольца со знаком (формула шнурков)."""
    n = len(coords)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = coords[i][0], coords[i][1]
        x2, y2 = coords[(i + 1) % n][0], coords[(i + 1) % n][1]
        s += x1 * y2 - x2 * y1
    return 0.5 * s


def ring_perimeter(coords):
    """Длина замкнутого кольца."""
    n = len(coords)
    if n < 2:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = coords[i][0], coords[i][1]
        x2, y2 = coords[(i + 1) % n][0], coords[(i + 1) % n][1]
        s += math.hypot(x2 - x1, y2 - y1)
    return s


def ring_width(coords):
    """
    Эффективная ширина кольца: удвоенная площадь, делённая на периметр.

    Для длинной узкой полосы даёт её ширину, для круга радиус.
    Малое значение при заметной площади это признак волосяного полигона.
    """
    p = ring_perimeter(coords)
    if p <= 0.0:
        return 0.0
    return 2.0 * abs(ring_area(coords)) / p


def drop_repeated_vertices(coords, closed, tolerance=EPS):
    """
    Удаляет вершины, отстоящие от предыдущей не дальше допуска.
    При tolerance равном EPS это снятие точных дублей.
    """
    if not coords:
        return list(coords), 0
    out = [coords[0]]
    removed = 0
    for p in coords[1:]:
        q = out[-1]
        if math.hypot(p[0] - q[0], p[1] - q[1]) > tolerance:
            out.append(p)
        else:
            removed += 1
    if closed:
        while len(out) > 1:
            a, b = out[0], out[-1]
            if math.hypot(a[0] - b[0], a[1] - b[1]) <= tolerance:
                out.pop()
                removed += 1
            else:
                break
    return out, removed


def _is_spike(a, b, c, cos_limit, max_length):
    ux, uy = a[0] - b[0], a[1] - b[1]
    vx, vy = c[0] - b[0], c[1] - b[1]
    lu = math.hypot(ux, uy)
    lv = math.hypot(vx, vy)
    if lu <= EPS or lv <= EPS:
        return True
    cos_abc = (ux * vx + uy * vy) / (lu * lv)
    if cos_abc < cos_limit:
        return False
    if max_length is not None and min(lu, lv) > max_length:
        return False
    return True


def remove_spikes(coords, closed, max_angle_deg=1.0, max_length=None):
    """
    Удаляет иглы: вершины, в которых линия разворачивается почти назад.

    Игла это вершина B в цепочке A-B-C, где угол ABC близок к нулю, то есть
    ребро BC идёт обратно поверх AB. Такая вершина не несёт формы и почти
    всегда является следом оцифровки или сбойного снапа.

    Для замкнутого кольца вершины передаются без повтора первой в конце.

    max_angle_deg  порог угла ABC в градусах, ниже которого вершина это игла
    max_length     если задано, игла снимается только когда более короткое
                   из рёбер AB и BC не длиннее этого значения

    Возвращает (новые вершины, число снятых игл). Сложность линейная.
    """
    if len(coords) < 3:
        return list(coords), 0

    cos_limit = math.cos(math.radians(max_angle_deg))
    min_pts = 3 if closed else 2
    removed = 0

    out = []
    for p in coords:
        out.append(p)
        while len(out) >= 3 and _is_spike(out[-3], out[-2], out[-1], cos_limit, max_length):
            del out[-2]
            removed += 1

    if closed:
        # Стык кольца: игла может сидеть на первой или последней вершине.
        guard = 0
        while len(out) > min_pts and guard < len(coords) + 8:
            guard += 1
            if _is_spike(out[-2], out[-1], out[0], cos_limit, max_length):
                out.pop()
                removed += 1
                continue
            if _is_spike(out[-1], out[0], out[1], cos_limit, max_length):
                out.pop(0)
                removed += 1
                continue
            break

    if len(out) < min_pts:
        return list(coords), 0
    return out, removed


def self_touch_points(coords, closed):
    """
    Вершины, встречающиеся в кольце более одного раза.

    Кольцо, касающееся само себя в точке, формально может быть корректным,
    но при дальнейшей обработке даёт непредсказуемый результат.
    Для замкнутого кольца вершины передаются без повтора первой в конце.
    """
    seen = {}
    for c in coords:
        key = (round(c[0], 9), round(c[1], 9))
        seen[key] = seen.get(key, 0) + 1
    return [k for k, v in seen.items() if v > 1]


def _point_segment(px, py, x1, y1, x2, y2):
    """Расстояние от точки до отрезка и параметр проекции t в диапазоне [0, 1]."""
    dx = x2 - x1
    dy = y2 - y1
    d2 = dx * dx + dy * dy
    if d2 <= 0.0:
        return math.hypot(px - x1, py - y1), 0.0
    t = ((px - x1) * dx + (py - y1) * dy) / d2
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    qx = x1 + t * dx
    qy = y1 + t * dy
    return math.hypot(px - qx, py - qy), t


def _cells_along_segment(x1, y1, x2, y2, cell):
    """Ячейки регулярной сетки, которые пересекает отрезок (обход Amanatides-Woo)."""
    cx = int(math.floor(x1 / cell))
    cy = int(math.floor(y1 / cell))
    ex = int(math.floor(x2 / cell))
    ey = int(math.floor(y2 / cell))
    yield (cx, cy)
    if cx == ex and cy == ey:
        return

    dx = x2 - x1
    dy = y2 - y1
    step_x = 1 if dx > 0 else (-1 if dx < 0 else 0)
    step_y = 1 if dy > 0 else (-1 if dy < 0 else 0)

    inf = float("inf")
    if step_x != 0:
        border_x = (cx + (1 if step_x > 0 else 0)) * cell
        t_max_x = (border_x - x1) / dx
        t_delta_x = abs(cell / dx)
    else:
        t_max_x = inf
        t_delta_x = inf
    if step_y != 0:
        border_y = (cy + (1 if step_y > 0 else 0)) * cell
        t_max_y = (border_y - y1) / dy
        t_delta_y = abs(cell / dy)
    else:
        t_max_y = inf
        t_delta_y = inf

    # Число шагов известно заранее: по одному на каждую границу ячейки
    # вдоль обеих осей. Фиксированный счётчик надёжнее сравнения с конечной
    # ячейкой: накопленная погрешность может увести счётчик мимо неё,
    # и цикл по совпадению никогда не завершится.
    steps = abs(ex - cx) + abs(ey - cy)
    for _ in range(steps):
        if t_max_x < t_max_y:
            cx += step_x
            t_max_x += t_delta_x
        else:
            cy += step_y
            t_max_y += t_delta_y
        yield (cx, cy)


# ────────────────────────────────────────────────────────────────────────────
# Пространственные индексы
# ────────────────────────────────────────────────────────────────────────────

class _PointGrid:
    """Сетка точек с поиском ближайшей в радиусе."""

    def __init__(self, cell):
        self.cell = cell if cell > 0 else 1.0
        self.cells = {}
        self.xs = []
        self.ys = []

    def add(self, x, y):
        idx = len(self.xs)
        self.xs.append(x)
        self.ys.append(y)
        key = (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))
        self.cells.setdefault(key, []).append(idx)
        return idx

    def nearest(self, x, y, radius):
        """Индекс ближайшей точки в радиусе или None."""
        cx = int(math.floor(x / self.cell))
        cy = int(math.floor(y / self.cell))
        best = None
        best_d2 = radius * radius
        span = max(1, int(math.ceil(radius / self.cell)))
        for i in range(cx - span, cx + span + 1):
            for j in range(cy - span, cy + span + 1):
                for idx in self.cells.get((i, j), ()):
                    ddx = self.xs[idx] - x
                    ddy = self.ys[idx] - y
                    d2 = ddx * ddx + ddy * ddy
                    if d2 <= best_d2:
                        best_d2 = d2
                        best = idx
        return best, math.sqrt(best_d2) if best is not None else 0.0


class _RingVertexGrid:
    """
    Вершины с привязкой к кольцу. Отвечает на вопрос: есть ли у этого кольца
    своя вершина рядом с данной точкой.

    Нужен потому, что кольцо может касаться само себя: одна и та же точка
    бывает и вершиной кольца, и точкой на другом его ребре, к которому она
    не примыкает. Вставка узла в такое ребро превращает касание в шпильку,
    контур уходит и возвращается, и геометрия становится некорректной.
    """

    def __init__(self, cell):
        self.cell = cell if cell > 0 else 1.0
        self.cells = {}

    def add(self, ring_index, x, y):
        key = (int(math.floor(x / self.cell)), int(math.floor(y / self.cell)))
        self.cells.setdefault(key, []).append((ring_index, x, y))

    def has_vertex(self, ring_index, x, y, radius):
        cx = int(math.floor(x / self.cell))
        cy = int(math.floor(y / self.cell))
        r2 = radius * radius
        for i in (cx - 1, cx, cx + 1):
            for j in (cy - 1, cy, cy + 1):
                for ri, vx, vy in self.cells.get((i, j), ()):
                    if ri != ring_index:
                        continue
                    dx = vx - x
                    dy = vy - y
                    if dx * dx + dy * dy <= r2:
                        return True
        return False


class _SegmentGrid:
    """Сетка сегментов. Ячейка равна допуску, запрос смотрит окрестность 3x3."""

    def __init__(self, cell):
        self.cell = cell if cell > 0 else 1.0
        self.cells = {}

    def add(self, key, x1, y1, x2, y2):
        for c in _cells_along_segment(x1, y1, x2, y2, self.cell):
            self.cells.setdefault(c, []).append(key)

    def query(self, x, y):
        cx = int(math.floor(x / self.cell))
        cy = int(math.floor(y / self.cell))
        out = set()
        for i in (cx - 1, cx, cx + 1):
            for j in (cy - 1, cy, cy + 1):
                bucket = self.cells.get((i, j))
                if bucket:
                    out.update(bucket)
        return out


# ────────────────────────────────────────────────────────────────────────────
# Нормализация колец
# ────────────────────────────────────────────────────────────────────────────

def _norm(coords):
    """Приводит вершины к (x, y, z) и снимает замыкание. Возвращает (список, closed)."""
    out = []
    for c in coords:
        if len(c) >= 3:
            out.append((float(c[0]), float(c[1]), None if c[2] is None else float(c[2])))
        else:
            out.append((float(c[0]), float(c[1]), None))
    closed = False
    if len(out) >= 2:
        a = out[0]
        b = out[-1]
        if abs(a[0] - b[0]) <= EPS and abs(a[1] - b[1]) <= EPS:
            closed = True
            out = out[:-1]
    return out, closed


def _drop_repeats(coords, closed):
    """Удаляет подряд идущие совпадающие вершины (для кольца проверяется и стык)."""
    if not coords:
        return coords
    out = [coords[0]]
    for p in coords[1:]:
        q = out[-1]
        if abs(p[0] - q[0]) > EPS or abs(p[1] - q[1]) > EPS:
            out.append(p)
    if closed:
        while len(out) > 1:
            a, b = out[0], out[-1]
            if abs(a[0] - b[0]) <= EPS and abs(a[1] - b[1]) <= EPS:
                out.pop()
            else:
                break
    return out


def _is_degenerate(coords, closed):
    return len(coords) < (3 if closed else 2)


# ────────────────────────────────────────────────────────────────────────────
# Основная функция
# ────────────────────────────────────────────────────────────────────────────

def _segment_crossing(x1, y1, x2, y2, x3, y3, x4, y4, near_vertex=EPS):
    """
    Точка пересечения двух отрезков строго внутри обоих.

    Возвращает (x, y, t, u) или None. Коллинеарные и параллельные отрезки
    пропускаются: у них нет единственной точки пересечения, а перекрытие
    вдоль общей линии решается вставкой узлов по вершинам.
    """
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
    px = x1 + t * ax
    py = y1 + t * ay
    # Пересечение, попавшее в существующую вершину, узла не требует.
    for vx, vy in ((x1, y1), (x2, y2), (x3, y3), (x4, y4)):
        if math.hypot(px - vx, py - vy) <= near_vertex:
            return None
    return (px, py, t, u)


def _apply_inserts(norm, inserts, events, kind):
    """Вставляет накопленные точки в сегменты. inserts: (ring, seg) -> [(t, x, y, z, d)]."""
    count = 0
    by_ring = {}
    for (ri, si), items in inserts.items():
        by_ring.setdefault(ri, []).append((si, items))
    for ri, seg_items in by_ring.items():
        coords, closed = norm[ri]
        if coords is None:
            continue
        coords = list(coords)
        for si, items in sorted(seg_items, key=lambda p: -p[0]):
            items.sort(key=lambda p: p[0])
            add = []
            prev_t = -1.0
            for t, px, py, nz, dist in items:
                if t - prev_t <= 0.0:
                    continue
                add.append((px, py, nz))
                events.append((px, py, kind, dist, ri))
                prev_t = t
            if add:
                coords[si + 1:si + 1] = add
                count += len(add)
        norm[ri] = (coords, closed)
    return count


def segment_length_stats(rings):
    """
    Статистика длин рёбер: (медиана, пятый процентиль, всего рёбер).

    Нужна для подбора допуска. Если допуск сравним с длиной ребра, слияние
    начинает схлопывать соседние вершины одного кольца, и форма выворачивается
    сама через себя. Безопасный допуск заметно меньше короткого ребра.
    """
    lengths = []
    for coords in rings:
        if not coords or len(coords) < 2:
            continue
        closed = (abs(coords[0][0] - coords[-1][0]) <= EPS
                  and abs(coords[0][1] - coords[-1][1]) <= EPS)
        body = coords[:-1] if closed else coords
        n = len(body)
        last = n if closed else n - 1
        for i in range(last):
            x1, y1 = body[i][0], body[i][1]
            x2, y2 = body[(i + 1) % n][0], body[(i + 1) % n][1]
            d = math.hypot(x2 - x1, y2 - y1)
            if d > EPS:
                lengths.append(d)
    if not lengths:
        return (0.0, 0.0, 0)
    lengths.sort()
    median = lengths[len(lengths) // 2]
    p05 = lengths[max(0, int(0.05 * len(lengths)) - 1)]
    return (median, p05, len(lengths))


def _mean_segment_length(norm):
    total = 0.0
    n = 0
    for coords, closed in norm:
        if not coords:
            continue
        m = len(coords)
        last = m if closed else m - 1
        for i in range(last):
            x1, y1, _z = coords[i]
            x2, y2, _z2 = coords[(i + 1) % m]
            total += math.hypot(x2 - x1, y2 - y1)
            n += 1
    return (total / n) if n else 0.0


def _node_crossings(norm, tolerance, events, frozen=None, project_onto_edge=False):
    """
    Вставляет узлы в точках пересечения рёбер.

    Нужен для перехлёстов, где рёбра пересекаются крест-накрест, но общих
    вершин нет. Вставка узлов по вершинам такой случай не закрывает,
    потому что вставлять там нечего.
    """
    frozen = frozen or set()
    cell = max(tolerance, _mean_segment_length(norm), 1e-9)
    grid = _SegmentGrid(cell)
    segs = {}
    for ri, (coords, closed) in enumerate(norm):
        if coords is None or ri in frozen:
            continue
        n = len(coords)
        last = n if closed else n - 1
        for si in range(last):
            x1, y1, z1 = coords[si]
            x2, y2, z2 = coords[(si + 1) % n]
            segs[(ri, si)] = (x1, y1, z1, x2, y2, z2)
            grid.add((ri, si), x1, y1, x2, y2)

    own = _RingVertexGrid(max(tolerance, 1e-9))
    for ri, (coords, _closed) in enumerate(norm):
        if coords is None or ri in frozen:
            continue
        for vx, vy, _vz in coords:
            own.add(ri, vx, vy)

    inserts = {}
    checked = set()
    for bucket in grid.cells.values():
        if len(bucket) < 2:
            continue
        for a in range(len(bucket)):
            ka = bucket[a]
            for b in range(a + 1, len(bucket)):
                kb = bucket[b]
                pair = (ka, kb) if ka <= kb else (kb, ka)
                if pair in checked:
                    continue
                checked.add(pair)
                # Соседние сегменты одного кольца имеют общую вершину.
                if ka[0] == kb[0] and abs(ka[1] - kb[1]) <= 1:
                    continue
                x1, y1, z1, x2, y2, z2 = segs[ka]
                x3, y3, z3, x4, y4, z4 = segs[kb]
                hit = _segment_crossing(x1, y1, x2, y2, x3, y3, x4, y4,
                                        near_vertex=tolerance)
                if hit is None:
                    continue
                px, py, t, u = hit
                za = None if (z1 is None or z2 is None) else z1 + (z2 - z1) * t
                zb = None if (z3 is None or z4 is None) else z3 + (z4 - z3) * u
                # Точку пересечения считают по параметру одного из рёбер,
                # поэтому на втором она лежит лишь в пределах округления.
                # Там, где кольцо касается само себя, такого отклонения хватает,
                # чтобы касание стало пересечением. Каждую вставку кладём
                # на её собственное ребро.
                if project_onto_edge:
                    ax, ay = x1 + t * (x2 - x1), y1 + t * (y2 - y1)
                    bx_, by_ = x3 + u * (x4 - x3), y3 + u * (y4 - y3)
                else:
                    ax, ay = px, py
                    bx_, by_ = px, py
                if not own.has_vertex(ka[0], ax, ay, tolerance):
                    inserts.setdefault(ka, []).append((t, ax, ay, za, 0.0))
                if not own.has_vertex(kb[0], bx_, by_, tolerance):
                    inserts.setdefault(kb, []).append((u, bx_, by_, zb, 0.0))

    return _apply_inserts(norm, inserts, events, "cross")


def clean_topology(rings, tolerance, mode=MODE_BOTH, fixed_rings=None,
                   z_insert=Z_INTERPOLATE, node_crossings=True, frozen=None,
                   project_onto_edge=False, progress=None):
    """
    Сшивает набор колец.

    rings        список колец, каждое кольцо это список (x, y) или (x, y, z)
    tolerance    допуск в единицах координат, больше нуля
    mode         MODE_INSERT, MODE_MERGE или MODE_BOTH
    fixed_rings  кольца эталона, они не изменяются и дают вершины-лидеры
    z_insert     Z_INTERPOLATE (Z вставленного узла берётся из сегмента)
                 или Z_FROM_VERTEX (Z берётся у притянутой вершины)
    node_crossings  вставлять ли узлы в точках пересечения рёбер
    project_onto_edge  вставлять проекцию точки на ребро вместо самой точки.
                 Проекция лежит на прямой ребра, поэтому форма кольца
                 не меняется вовсе и самопересечение возникнуть не может.
                 Без этого в ребро попадает координата чужой вершины, а она
                 лежит на ребре лишь в пределах допуска, и ребро смещается
                 вбок на эту величину. Там, где рядом проходит другая часть
                 того же кольца, такого смещения хватает, чтобы контур
                 пересёк сам себя. Для сшивки проекция не годится: там узел
                 обязан совпасть с вершиной соседа.
    frozen       множество индексов колец, которые нельзя изменять. Их вершины
                 неподвижны и служат опорой для соседей, а рёбра не принимают
                 узлов. Нужно для объектов уже допуска: у такого кольца
                 противоположные берега слиплись бы, и оно схлопнулось бы
                 само в себя. Лучше оставить его как есть, чем потерять.
    progress     необязательный вызываемый объект progress(доля от 0 до 1)

    Возвращает словарь:
        rings   список той же длины, элемент None если кольцо выродилось
        stats   словарь со счётчиками
        events  список (x, y, kind, value, ring_index), kind это move или insert
    """
    if tolerance is None or tolerance <= 0:
        raise ValueError("Допуск должен быть больше нуля.")
    if mode not in (MODE_INSERT, MODE_MERGE, MODE_BOTH):
        raise ValueError("Неизвестный режим: %r" % (mode,))

    do_merge = mode in (MODE_MERGE, MODE_BOTH)
    do_insert = mode in (MODE_INSERT, MODE_BOTH)

    fixed_rings = fixed_rings or []
    frozen = set(frozen or ())

    norm = [_norm(r) for r in rings]
    norm_fixed = [_norm(r) for r in fixed_rings]

    stats = {
        "rings_in": len(rings),
        "rings_fixed": len(fixed_rings),
        "vertices_in": sum(len(c) for c, _ in norm),
        "clusters": 0,
        "vertices_moved": 0,
        "max_move": 0.0,
        "sum_move": 0.0,
        "nodes_inserted": 0,
        "nodes_crossing": 0,
        "rings_degenerate": 0,
        "rings_frozen": len(frozen),
        "rings_changed": 0,
        "vertices_out": 0,
    }
    events = []

    def tick(fraction):
        if progress is not None:
            progress(fraction)

    # ── Шаг 1. Слияние вершин ────────────────────────────────────────────
    if do_merge:
        grid = _PointGrid(tolerance)

        # Эталон первым: его вершины гарантированно становятся лидерами.
        for coords, _closed in norm_fixed:
            for x, y, _z in coords:
                idx, _d = grid.nearest(x, y, tolerance)
                if idx is None:
                    grid.add(x, y)

        # Неизменяемые кольца обходятся до остальных: их вершины становятся
        # опорой, к которой притягиваются соседи, а сами они не двигаются.
        for ri in frozen:
            if ri < len(norm):
                for x, y, _z in norm[ri][0]:
                    grid.add(x, y)

        moved = []
        total = max(1, len(norm))
        for ri, (coords, closed) in enumerate(norm):
            if ri in frozen:
                moved.append((list(coords), closed))
                continue
            new_coords = []
            for x, y, z in coords:
                idx, dist = grid.nearest(x, y, tolerance)
                if idx is None:
                    grid.add(x, y)
                    new_coords.append((x, y, z))
                else:
                    lx, ly = grid.xs[idx], grid.ys[idx]
                    if dist > EPS:
                        stats["vertices_moved"] += 1
                        stats["sum_move"] += dist
                        if dist > stats["max_move"]:
                            stats["max_move"] = dist
                        events.append((lx, ly, "move", dist, ri))
                    new_coords.append((lx, ly, z))
            moved.append((new_coords, closed))
            if ri % 512 == 0:
                tick(0.45 * ri / total)
        norm = moved
        stats["clusters"] = len(grid.xs)
    tick(0.45)

    # ── Шаг 2. Чистка дублей и отбраковка вырожденных колец ──────────────
    cleaned = []
    for coords, closed in norm:
        coords = _drop_repeats(coords, closed)
        if _is_degenerate(coords, closed):
            stats["rings_degenerate"] += 1
            cleaned.append((None, closed))
        else:
            cleaned.append((coords, closed))
    norm = cleaned
    tick(0.5)

    # ── Шаг 2а. Узлы в точках пересечения рёбер ──────────────────────────
    if do_insert and node_crossings:
        stats["nodes_crossing"] = _node_crossings(
            norm, tolerance, events, frozen, project_onto_edge)
        stats["nodes_inserted"] += stats["nodes_crossing"]
    tick(0.55)

    # ── Шаг 3. Вставка узлов по вершинам ─────────────────────────────────
    if do_insert:
        # Точки-кандидаты: все вершины эталона и все вершины рабочих колец,
        # без повторов по координатам.
        pts = {}
        for coords, _closed in norm_fixed:
            for x, y, z in coords:
                pts.setdefault((x, y), z)
        for coords, _closed in norm:
            if coords is None:
                continue
            for x, y, z in coords:
                pts.setdefault((x, y), z)

        # Индекс сегментов только по рабочим кольцам: эталон не меняем.
        # Ячейка не меньше допуска, иначе запрос по соседним девяти ячейкам
        # перестанет покрывать радиус поиска. Брать её крупнее допуска можно
        # и нужно: при мелком допуске длинное ребро иначе дробится на сотни
        # ячеек, и построение индекса становится дороже самого поиска.
        seg_grid = _SegmentGrid(max(tolerance, _mean_segment_length(norm)))
        for ri, (coords, closed) in enumerate(norm):
            if coords is None or ri in frozen:
                continue
            n = len(coords)
            last = n if closed else n - 1
            for si in range(last):
                x1, y1, _z1 = coords[si]
                x2, y2, _z2 = coords[(si + 1) % n]
                seg_grid.add((ri, si), x1, y1, x2, y2)
        tick(0.65)

        # Собственные вершины колец: узел не нужен там, где вершина уже есть.
        own = _RingVertexGrid(max(tolerance, 1e-9))
        for ri, (coords, _closed) in enumerate(norm):
            if coords is None:
                continue
            for vx, vy, _vz in coords:
                own.add(ri, vx, vy)

        # Кандидаты на вставку, сгруппированные по сегменту.
        inserts = {}
        total = max(1, len(pts))
        for k, (vx, vy) in enumerate(pts.keys()):
            pz = pts[(vx, vy)]
            for (ri, si) in seg_grid.query(vx, vy):
                px, py = vx, vy
                coords, closed = norm[ri]
                if coords is None:
                    continue
                n = len(coords)
                x1, y1, z1 = coords[si]
                x2, y2, z2 = coords[(si + 1) % n]
                # Узел не нужен, если в пределах допуска у ребра уже есть
                # вершина. Порог именно допуск, а не машинный эпсилон: иначе
                # вставка порождает рёбра длиной в доли нанометра, которые
                # ничего не выражают и мешают проверке корректности.
                if math.hypot(px - x1, py - y1) <= tolerance:
                    continue
                if math.hypot(px - x2, py - y2) <= tolerance:
                    continue
                if abs(px - x1) <= EPS and abs(py - y1) <= EPS:
                    continue
                if abs(px - x2) <= EPS and abs(py - y2) <= EPS:
                    continue
                # Точка уже есть среди вершин этого кольца: узла достаточно.
                if own.has_vertex(ri, px, py, tolerance):
                    continue
                dist, t = _point_segment(px, py, x1, y1, x2, y2)
                if dist > tolerance:
                    continue
                if t <= 0.0 or t >= 1.0:
                    continue
                if project_onto_edge:
                    # Точка на прямой ребра: форма не меняется вовсе.
                    px = x1 + t * (x2 - x1)
                    py = y1 + t * (y2 - y1)
                if z_insert == Z_FROM_VERTEX and pz is not None:
                    nz = pz
                elif z1 is None or z2 is None:
                    nz = pz
                else:
                    nz = z1 + (z2 - z1) * t
                inserts.setdefault((ri, si), []).append((t, px, py, nz, dist))
            if k % 1024 == 0:
                tick(0.65 + 0.25 * k / total)

        stats["nodes_inserted"] += _apply_inserts(norm, inserts, events, "insert")
    tick(0.92)

    # ── Шаг 4. Финальная сборка ──────────────────────────────────────────
    out_rings = []
    for i, (coords, closed) in enumerate(norm):
        if coords is None:
            out_rings.append(None)
            continue
        coords = _drop_repeats(coords, closed)
        if _is_degenerate(coords, closed):
            stats["rings_degenerate"] += 1
            out_rings.append(None)
            continue
        src, src_closed = _norm(rings[i])
        if closed:
            coords = coords + [coords[0]]
        if len(coords) != len(src) + (1 if src_closed else 0) or any(
            abs(a[0] - b[0]) > EPS or abs(a[1] - b[1]) > EPS
            for a, b in zip(coords, src + ([src[0]] if src_closed else []))
        ):
            stats["rings_changed"] += 1
        stats["vertices_out"] += len(coords)
        out_rings.append(coords)

    stats["mean_move"] = (
        stats["sum_move"] / stats["vertices_moved"] if stats["vertices_moved"] else 0.0
    )
    tick(1.0)

    return {"rings": out_rings, "stats": stats, "events": events}
