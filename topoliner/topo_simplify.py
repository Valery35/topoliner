# -*- coding: utf-8 -*-
"""
topo_simplify
-------------
Топологическое упрощение колец.

Обычное упрощение обрабатывает каждый полигон отдельно, поэтому общая граница
двух соседей прореживается дважды и по-разному: там, где была одна линия,
появляются щели и перехлёсты. Здесь граница сначала опознаётся как общая,
затем прореживается один раз, и обоим соседям достаётся один и тот же результат.

Порядок работы:

1. Кольца раскладываются на рёбра. Ребро опознаётся по паре концов
   без учёта направления, поэтому одно и то же ребро у двух соседей
   даёт одну запись с двумя владельцами.
2. Рёбра склеиваются в дуги. Цепочка продолжается, пока в вершине сходятся
   ровно два ребра с одинаковым набором владельцев. Там, где набор меняется
   или сходятся три ребра, стоит узел ветвления, и дуга обрывается.
3. Каждая дуга прореживается ровно один раз алгоритмом Дугласа-Пекера.
   Концы дуги неподвижны, поэтому узлы ветвления остаются на месте.
4. Кольца собираются обратно из упрощённых дуг.

Работает со списками координат, от QGIS не зависит и тестируется headless.
"""

import math

__all__ = [
    "simplify_topology",
    "build_arcs",
    "douglas_peucker",
]

EPS = 1e-9


def _key(x, y, grid):
    """Ключ вершины. Округление до сетки сводит вместе координаты соседей,
    записанные с разной точностью."""
    return (round(x / grid), round(y / grid))


# ────────────────────────────────────────────────────────────────────────────
# Прореживание
# ────────────────────────────────────────────────────────────────────────────

def douglas_peucker(points, tolerance):
    """
    Прореживание Дугласа-Пекера. Первая и последняя точки неподвижны.

    Реализация без рекурсии: на длинных дугах рекурсия упирается в предел
    глубины интерпретатора.
    """
    n = len(points)
    if n < 3 or tolerance <= 0:
        return list(points)

    keep = [False] * n
    keep[0] = keep[n - 1] = True
    stack = [(0, n - 1)]

    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        x1, y1 = points[first][0], points[first][1]
        x2, y2 = points[last][0], points[last][1]
        dx, dy = x2 - x1, y2 - y1
        d2 = dx * dx + dy * dy

        best = -1.0
        best_i = -1
        for i in range(first + 1, last):
            px, py = points[i][0], points[i][1]
            if d2 <= EPS:
                dist = math.hypot(px - x1, py - y1)
            else:
                t = ((px - x1) * dx + (py - y1) * dy) / d2
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                dist = math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))
            if dist > best:
                best = dist
                best_i = i

        if best > tolerance:
            keep[best_i] = True
            stack.append((first, best_i))
            stack.append((best_i, last))

    return [points[i] for i in range(n) if keep[i]]


# ────────────────────────────────────────────────────────────────────────────
# Разбор на дуги
# ────────────────────────────────────────────────────────────────────────────

def build_arcs(rings, grid=1e-7):
    """
    Раскладывает кольца на дуги.

    Возвращает (arcs, ring_paths):
        arcs       список дуг, дуга это список вершин
        ring_paths для каждого кольца список (индекс дуги, развёрнута ли она)

    Кольца передаются без повтора первой вершины в конце.
    """
    # ── Рёбра и их владельцы ─────────────────────────────────────────────
    edge_owners = {}
    for ri, ring in enumerate(rings):
        n = len(ring)
        for i in range(n):
            a = _key(ring[i][0], ring[i][1], grid)
            b = _key(ring[(i + 1) % n][0], ring[(i + 1) % n][1], grid)
            if a == b:
                continue
            ek = (a, b) if a <= b else (b, a)
            edge_owners.setdefault(ek, set()).add(ri)

    # ── Степень вершины и наборы владельцев вокруг неё ────────────────────
    around = {}
    for (a, b), owners in edge_owners.items():
        around.setdefault(a, []).append((b, frozenset(owners)))
        around.setdefault(b, []).append((a, frozenset(owners)))

    def is_junction(v):
        """Вершина является узлом, если в ней сходятся не два ребра
        либо у сходящихся рёбер разные владельцы."""
        items = around.get(v, ())
        if len(items) != 2:
            return True
        return items[0][1] != items[1][1]

    # ── Сборка дуг вдоль колец ───────────────────────────────────────────
    # Общая координата для каждого ключа: соседи могут записать одну и ту же
    # вершину с разной точностью, а стык дуг обязан совпадать точно.
    canon = {}
    for ring in rings:
        for x, y in ring:
            canon.setdefault(_key(x, y, grid), (x, y))

    arcs = []
    arc_index = {}      # ключ последовательности вершин -> (индекс, развёрнута)
    ring_paths = []

    def register(kseq, pts):
        """Возвращает (индекс дуги, нужно ли разворачивать при сборке)."""
        forward = tuple(kseq)
        backward = tuple(reversed(kseq))
        if forward in arc_index:
            return arc_index[forward]
        if backward in arc_index:
            idx, _rev = arc_index[backward]
            # Та же дуга, пройденная в обратную сторону. Координаты берутся
            # у первой записи: соседи могли записать одни и те же вершины
            # с разной точностью, и дуга обязана быть у них буквально общей,
            # иначе после прореживания границы разойдутся.
            return (idx, True)
        idx = len(arcs)
        pts = list(pts)
        # Концы дуги приводим к общей координате узла.
        pts[0] = canon.get(kseq[0], pts[0])
        pts[-1] = canon.get(kseq[-1], pts[-1])
        arcs.append(pts)
        arc_index[forward] = (idx, False)
        return (idx, False)

    for ri, ring in enumerate(rings):
        n = len(ring)
        keys = [_key(p[0], p[1], grid) for p in ring]

        starts = [i for i in range(n) if is_junction(keys[i])]
        path = []

        if not starts:
            # Кольцо целиком является одной замкнутой дугой.
            pts = list(ring) + [ring[0]]
            path.append(register(keys + [keys[0]], pts))
            ring_paths.append(path)
            continue

        s0 = starts[0]
        i = s0
        while True:
            pts = [ring[i]]
            kseq = [keys[i]]
            j = (i + 1) % n
            while True:
                pts.append(ring[j])
                kseq.append(keys[j])
                if is_junction(keys[j]):
                    break
                j = (j + 1) % n

            path.append(register(kseq, pts))

            i = j
            if i == s0:
                break

        ring_paths.append(path)

    return arcs, ring_paths


def _arc_key(keys):
    return tuple(keys)


# ────────────────────────────────────────────────────────────────────────────
# Основная функция
# ────────────────────────────────────────────────────────────────────────────

def simplify_topology(rings, tolerance, grid=1e-7, min_points=None):
    """
    Упрощает кольца, сохраняя общие границы.

    rings       список колец, кольцо это список (x, y) без повтора первой вершины
    tolerance   допуск прореживания в единицах координат
    grid        шаг округления при опознании общих вершин
    min_points  не прореживать дугу короче этого числа вершин

    Возвращает словарь:
        rings   список колец той же длины, элемент None если кольцо выродилось
        stats   счётчики
    """
    if tolerance is None or tolerance < 0:
        raise ValueError("Допуск не может быть отрицательным.")

    arcs, ring_paths = build_arcs(rings, grid=grid)

    stats = {
        "rings_in": len(rings),
        "arcs": len(arcs),
        "arcs_shared": 0,
        "vertices_in": sum(len(r) for r in rings),
        "vertices_out": 0,
        "rings_degenerate": 0,
    }

    # Дуга общая, если встречается в путях более чем одного кольца.
    users = {}
    for ri, path in enumerate(ring_paths):
        for idx, _rev in path:
            users.setdefault(idx, set()).add(ri)
    stats["arcs_shared"] = sum(1 for v in users.values() if len(v) > 1)

    # ── Прореживание каждой дуги ровно один раз ──────────────────────────
    simple = []
    for arc in arcs:
        if min_points is not None and len(arc) <= min_points:
            simple.append(list(arc))
            continue
        simple.append(douglas_peucker(arc, tolerance))

    # ── Сборка колец ─────────────────────────────────────────────────────
    out = []
    for ri, path in enumerate(ring_paths):
        pts = []
        for idx, rev in path:
            seq = simple[idx]
            if rev:
                seq = list(reversed(seq))
            pts.extend(seq[:-1] if pts or True else seq)
        # Убираем подряд идущие совпадения.
        cleaned = []
        for p in pts:
            if not cleaned or abs(p[0] - cleaned[-1][0]) > EPS or abs(p[1] - cleaned[-1][1]) > EPS:
                cleaned.append(p)
        while len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) <= EPS \
                and abs(cleaned[0][1] - cleaned[-1][1]) <= EPS:
            cleaned.pop()
        if len(cleaned) < 3:
            stats["rings_degenerate"] += 1
            out.append(None)
            continue
        stats["vertices_out"] += len(cleaned)
        out.append(cleaned)

    return {"rings": out, "stats": stats}
