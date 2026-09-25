# -*- coding: utf-8 -*-
"""
z_restore
---------
Возврат отметок Z после операций наложения.

Пересечение и вычитание работают в плане. Вершины результата бывают двух
родов. Одни совпадают с исходными вершинами, другие поставлены наложением
на середине исходного ребра. Отметки у тех и у других после наложения
недостоверны.

Отметка берётся с ближайшего исходного ребра. Вершина проецируется на ребро,
дальше отметка считается по параметру проекции. Совпавшая вершина получает
отметку конца ребра, потому что параметр проекции равен нулю или единице.
Вершина на середине ребра получает отметку, посчитанную вдоль ребра. Так же
считает отметки вставка узлов инструментом 1.06.

Чистый Python, без QGIS.
"""

try:  # внутри плагина QGIS
    from .topo_core import _cells_along_segment, _point_segment
except ImportError:  # headless-тесты
    from topo_core import _cells_along_segment, _point_segment

__all__ = ["ZEdges", "edges_from", "restore_z"]

# Сторона квадрата поиска в ячейках. Первый шаг покрывает окрестность вершины,
# следующие нужны вершинам на отшибе. Дальше идёт полный перебор, потому что
# осматривать пустые ячейки дороже, чем пройти по всем рёбрам.
RINGS = (1, 3, 9)


def _z(vertex):
    return vertex[2] if len(vertex) > 2 else 0.0


class ZEdges:
    """Исходные рёбра с отметками и поиск ближайшего ребра по сетке."""

    def __init__(self, cell=None):
        self.edges = []
        self.cells = {}
        self.cell = cell if cell and cell > 0 else None

    def add_ring(self, ring):
        """Добавляет рёбра кольца. Кольцо замыкается, если не замкнуто."""
        if not ring or len(ring) < 2:
            return
        previous = None
        for vertex in ring:
            if previous is not None:
                self._add_edge(previous, vertex)
            previous = vertex
        self._add_edge(ring[-1], ring[0])

    def add_parts(self, parts):
        """Добавляет рёбра объекта. Часть это список колец."""
        for rings in parts:
            for ring in rings:
                self.add_ring(ring)

    def _add_edge(self, a, b):
        if a[0] == b[0] and a[1] == b[1]:
            return
        self.edges.append((a[0], a[1], _z(a), b[0], b[1], _z(b)))

    def build(self):
        """Раскладывает рёбра по сетке. Вызывается после добавления."""
        self.cells = {}
        if not self.edges:
            return
        if self.cell is None:
            self.cell = self._mean_length()
        cell = self.cell
        cells = self.cells
        for key, edge in enumerate(self.edges):
            x1, y1, _z1, x2, y2, _z2 = edge
            cx = int(x1 // cell)
            cy = int(y1 // cell)
            if cx == int(x2 // cell) and cy == int(y2 // cell):
                bucket = cells.get((cx, cy))
                if bucket is None:
                    cells[(cx, cy)] = [key]
                else:
                    bucket.append(key)
                continue
            for c in _cells_along_segment(x1, y1, x2, y2, cell):
                bucket = cells.get(c)
                if bucket is None:
                    cells[c] = [key]
                else:
                    bucket.append(key)

    def _mean_length(self):
        """Средняя длина ребра. Ячейка мельче неё дробит длинные рёбра зря."""
        total = 0.0
        for x1, y1, _z1, x2, y2, _z2 in self.edges:
            total += abs(x2 - x1) + abs(y2 - y1)
        mean = total / len(self.edges)
        return mean if mean > 0.0 else 1.0

    def z_at(self, x, y, default=0.0):
        """Отметка в точке, посчитанная по ближайшему ребру."""
        if not self.cells:
            return default
        cell = self.cell
        cx = int(x // cell)
        cy = int(y // cell)
        get = self.cells.get
        edges = self.edges
        seen = set()
        for rings in RINGS:
            found = []
            for i in range(cx - rings, cx + rings + 1):
                for j in range(cy - rings, cy + rings + 1):
                    bucket = get((i, j))
                    if bucket:
                        found.extend(bucket)
            if not found:
                continue
            best = None
            for key in found:
                if key in seen:
                    continue
                seen.add(key)
                x1, y1, z1, x2, y2, z2 = edges[key]
                distance, t = _point_segment(x, y, x1, y1, x2, y2)
                if best is None or distance < best[0]:
                    best = (distance, z1 + t * (z2 - z1))
            if best is not None:
                return best[1]
        return self._scan(x, y, default)

    def _scan(self, x, y, default):
        """Полный перебор рёбер. Достаётся вершинам, вокруг которых пусто."""
        best = None
        for x1, y1, z1, x2, y2, z2 in self.edges:
            distance, t = _point_segment(x, y, x1, y1, x2, y2)
            if best is None or distance < best[0]:
                best = (distance, z1 + t * (z2 - z1))
        return default if best is None else best[1]


def edges_from(sources, cell=None):
    """Индекс рёбер по нескольким наборам частей."""
    index = ZEdges(cell)
    for parts in sources:
        index.add_parts(parts)
    index.build()
    return index


def restore_z(parts, index, default=0.0):
    """Те же части, у каждой вершины отметка с ближайшего исходного ребра."""
    out = []
    for rings in parts:
        new_rings = []
        for ring in rings:
            new_rings.append([(v[0], v[1], index.z_at(v[0], v[1], default))
                              for v in ring])
        out.append(new_rings)
    return out
