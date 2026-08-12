# -*- coding: utf-8 -*-
"""
geom_backend
------------
Тонкий адаптер над геометрическими операциями GEOS.

Две реализации с одинаковым интерфейсом:
  QgisBackend    - рабочая, поверх QgsGeometry
  ShapelyBackend - для headless-тестов

QGIS и Shapely используют один и тот же GEOS, поэтому поведение операций
совпадает, и логику проверок можно тестировать без запуска QGIS.

Геометрии внутри модулей проверок трактуются как непрозрачные объекты:
создавать и разбирать их можно только через backend.
"""

__all__ = ["QgisBackend", "ShapelyBackend", "get_backend"]


class _BackendBase:
    """Интерфейс. Все координаты плоские, работа идёт в 2D."""

    name = "base"

    # ── Создание ──────────────────────────────────────────────────────────
    def polygon(self, rings):
        """rings: [внешнее кольцо, дыра, дыра, ...], кольцо это список (x, y)."""
        raise NotImplementedError

    def multipolygon(self, polygons):
        raise NotImplementedError

    def linestring(self, coords):
        raise NotImplementedError

    # ── Разбор ────────────────────────────────────────────────────────────
    def parts(self, g):
        """Список одиночных полигонов."""
        raise NotImplementedError

    def rings(self, g):
        """Для одиночного полигона: [внешнее кольцо, дыры...] в виде списков (x, y)."""
        raise NotImplementedError

    # ── Меры ──────────────────────────────────────────────────────────────
    def area(self, g):
        raise NotImplementedError

    def length(self, g):
        raise NotImplementedError

    def bounds(self, g):
        """(xmin, ymin, xmax, ymax)"""
        raise NotImplementedError

    def is_empty(self, g):
        raise NotImplementedError

    def is_valid(self, g):
        raise NotImplementedError

    def invalid_reason(self, g):
        raise NotImplementedError

    # ── Операции ──────────────────────────────────────────────────────────
    def make_valid(self, g):
        raise NotImplementedError

    def intersection(self, a, b):
        raise NotImplementedError

    def difference(self, a, b):
        raise NotImplementedError

    def union_all(self, geoms):
        raise NotImplementedError

    def boundary(self, g):
        raise NotImplementedError

    def intersects(self, a, b):
        raise NotImplementedError

    def equals(self, a, b):
        raise NotImplementedError

    def contains(self, a, b):
        raise NotImplementedError

    def centroid_xy(self, g):
        raise NotImplementedError

    def distance(self, a, b):
        raise NotImplementedError

    def polygonal_only(self, g):
        """Оставляет только полигональные части (после make_valid бывает смесь)."""
        raise NotImplementedError


# ────────────────────────────────────────────────────────────────────────────
# Shapely
# ────────────────────────────────────────────────────────────────────────────

class ShapelyBackend(_BackendBase):

    name = "shapely"

    def __init__(self):
        from shapely.geometry import (  # noqa: F401
            GeometryCollection,
            LineString,
            MultiPolygon,
            Polygon,
        )
        from shapely import ops, validation  # noqa: F401

        self._Polygon = Polygon
        self._MultiPolygon = MultiPolygon
        self._LineString = LineString
        self._GeometryCollection = GeometryCollection
        self._ops = ops
        self._validation = validation

    def polygon(self, rings):
        if not rings or len(rings[0]) < 3:
            return self._Polygon()
        return self._Polygon(rings[0], [r for r in rings[1:] if r and len(r) >= 3])

    def multipolygon(self, polygons):
        flat = []
        for p in polygons:
            flat.extend(self.parts(p))
        if not flat:
            return self._Polygon()
        if len(flat) == 1:
            return flat[0]
        return self._MultiPolygon(flat)

    def linestring(self, coords):
        return self._LineString(coords)

    def parts(self, g):
        if g is None or g.is_empty:
            return []
        if g.geom_type == "Polygon":
            return [g]
        if g.geom_type in ("MultiPolygon", "GeometryCollection"):
            out = []
            for sub in g.geoms:
                out.extend(self.parts(sub))
            return out
        return []

    def rings(self, g):
        if g is None or g.is_empty or g.geom_type != "Polygon":
            return []
        out = [[(x, y) for x, y in g.exterior.coords]]
        for inner in g.interiors:
            out.append([(x, y) for x, y in inner.coords])
        return out

    def area(self, g):
        return 0.0 if g is None else float(g.area)

    def length(self, g):
        return 0.0 if g is None else float(g.length)

    def bounds(self, g):
        return tuple(g.bounds)

    def is_empty(self, g):
        return g is None or g.is_empty

    def is_valid(self, g):
        return bool(g.is_valid)

    def invalid_reason(self, g):
        return self._validation.explain_validity(g)

    def make_valid(self, g):
        return self._validation.make_valid(g)

    def intersection(self, a, b):
        return a.intersection(b)

    def difference(self, a, b):
        return a.difference(b)

    def union_all(self, geoms):
        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if not geoms:
            return self._Polygon()
        return self._ops.unary_union(geoms)

    def boundary(self, g):
        return g.boundary

    def intersects(self, a, b):
        return bool(a.intersects(b))

    def equals(self, a, b):
        return bool(a.equals(b))

    def contains(self, a, b):
        return bool(a.contains(b))

    def centroid_xy(self, g):
        c = g.representative_point()
        return (c.x, c.y)

    def distance(self, a, b):
        return float(a.distance(b))

    def polygonal_only(self, g):
        parts = self.parts(g)
        if not parts:
            return self._Polygon()
        if len(parts) == 1:
            return parts[0]
        return self._MultiPolygon(parts)


# ────────────────────────────────────────────────────────────────────────────
# QGIS
# ────────────────────────────────────────────────────────────────────────────

class QgisBackend(_BackendBase):

    name = "qgis"

    def __init__(self):
        from qgis.core import (
            QgsGeometry,
            QgsLineString,
            QgsMultiPolygon,
            QgsPoint,
            QgsPolygon,
            QgsWkbTypes,
        )

        self._G = QgsGeometry
        self._LineString = QgsLineString
        self._MultiPolygon = QgsMultiPolygon
        self._Point = QgsPoint
        self._Polygon = QgsPolygon
        self._WkbTypes = QgsWkbTypes

    def _ring(self, coords):
        return self._LineString([self._Point(c[0], c[1]) for c in coords])

    def polygon(self, rings):
        if not rings or len(rings[0]) < 3:
            return self._G()
        poly = self._Polygon()
        poly.setExteriorRing(self._ring(rings[0]))
        for inner in rings[1:]:
            if inner and len(inner) >= 3:
                poly.addInteriorRing(self._ring(inner))
        return self._G(poly)

    def multipolygon(self, polygons):
        flat = []
        for p in polygons:
            flat.extend(self.parts(p))
        if not flat:
            return self._G()
        if len(flat) == 1:
            return flat[0]
        mp = self._MultiPolygon()
        for p in flat:
            g = p.constGet()
            if g is not None:
                mp.addGeometry(g.clone())
        return self._G(mp)

    def linestring(self, coords):
        return self._G(self._ring(coords))

    def parts(self, g):
        if g is None or g.isEmpty():
            return []
        inner = g.constGet()
        if inner is None:
            return []
        out = []
        if self._WkbTypes.isMultiType(inner.wkbType()):
            for i in range(inner.numGeometries()):
                sub = inner.geometryN(i)
                if (
                    sub is not None
                    and self._WkbTypes.geometryType(sub.wkbType())
                    == self._WkbTypes.PolygonGeometry
                ):
                    out.append(self._G(sub.clone()))
        else:
            if (
                self._WkbTypes.geometryType(inner.wkbType())
                == self._WkbTypes.PolygonGeometry
            ):
                out.append(g)
        return out

    def rings(self, g):
        if g is None or g.isEmpty():
            return []
        poly = g.constGet()
        if poly is None or self._WkbTypes.isMultiType(poly.wkbType()):
            return []
        ext = poly.exteriorRing()
        if ext is None:
            return []
        if not isinstance(ext, self._LineString):
            ext = ext.curveToLine()
        out = [[(ext.xAt(i), ext.yAt(i)) for i in range(ext.numPoints())]]
        for k in range(poly.numInteriorRings()):
            inner = poly.interiorRing(k)
            if not isinstance(inner, self._LineString):
                inner = inner.curveToLine()
            out.append([(inner.xAt(i), inner.yAt(i)) for i in range(inner.numPoints())])
        return out

    def area(self, g):
        return 0.0 if g is None else float(g.area())

    def length(self, g):
        return 0.0 if g is None else float(g.length())

    def bounds(self, g):
        r = g.boundingBox()
        return (r.xMinimum(), r.yMinimum(), r.xMaximum(), r.yMaximum())

    def is_empty(self, g):
        return g is None or g.isEmpty() or g.isNull()

    def is_valid(self, g):
        return bool(g.isGeosValid())

    def invalid_reason(self, g):
        message = g.lastError()
        if message:
            return message
        errors = g.validateGeometry()
        # Валидатор QGIS пользуется другими правилами, чем GEOS, и на
        # некоторых геометриях не находит ничего. Это обычный случай.
        return errors[0].what() if errors else "недопустимая геометрия"

    def make_valid(self, g):
        return g.makeValid()

    def intersection(self, a, b):
        return a.intersection(b)

    def difference(self, a, b):
        return a.difference(b)

    def union_all(self, geoms):
        geoms = [g for g in geoms if g is not None and not g.isEmpty()]
        if not geoms:
            return self._G()
        return self._G.unaryUnion(geoms)

    def boundary(self, g):
        inner = g.constGet()
        if inner is None:
            return self._G()
        b = inner.boundary()
        return self._G(b) if b is not None else self._G()

    def intersects(self, a, b):
        return bool(a.intersects(b))

    def equals(self, a, b):
        return bool(a.equals(b))

    def contains(self, a, b):
        return bool(a.contains(b))

    def distance(self, a, b):
        return float(a.distance(b))

    def centroid_xy(self, g):
        p = g.pointOnSurface()
        if p is None or p.isEmpty():
            p = g.centroid()
        pt = p.asPoint()
        return (pt.x(), pt.y())

    def polygonal_only(self, g):
        return self.multipolygon([g])


def get_backend(name=None):
    """Возвращает рабочий backend. Без аргумента пробует QGIS, затем Shapely."""
    if name == "shapely":
        return ShapelyBackend()
    if name == "qgis":
        return QgisBackend()
    try:
        return QgisBackend()
    except ImportError:
        # QGIS недоступен: значит идут headless-тесты.
        return ShapelyBackend()
