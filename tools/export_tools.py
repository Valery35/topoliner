# -*- coding: utf-8 -*-
"""
Машинное описание инструментов и образцы прогонов для переноса на Rust.

Скрипт поднимает QGIS без окна, берёт провайдер topoliner из рабочей копии
и пишет два результата.

    tools.json                описание 11 инструментов в схеме toolspec,
                              её читает Catalog крейта rustgis-kit
    fixtures/tool_runs.json   прогоны в формате крейта: значения полей,
                              вход, выход и журнал

Источник описания - сами диалоги Processing. Параметры берутся из
initAlgorithm, поля выходных слоёв - из настоящего прогона, потому что
алгоритмы собирают поля внутри processAlgorithm. Поэтому описание
не расходится с кодом. Формат крейта описан в его README, раздел
«Граница между крейтом и продуктом».

Запуск только Python'ом QGIS с его окружением.

    "C:\\Program Files\\QGIS 4.2.3\\bin\\python-qgis.bat" tools/export_tools.py
    "C:\\Program Files\\QGIS 4.2.3\\bin\\python-qgis.bat" tools/export_tools.py --check

Ключ --check ничего не пишет. Он сравнивает свежий результат с файлами
в репозитории и завершается с кодом 1 при расхождении.

Каждый случай прогоняется дважды, с русским и с английским интерфейсом.
Геометрия обоих прогонов обязана совпасть, иначе скрипт останавливается.
Строковые значения, которые зависят от языка, пишутся в values_en.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsFeature,
    QgsGeometry,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsProcessingUtils,
    QgsVectorLayer,
    QgsWkbTypes,
)

CRS = "EPSG:32637"
FORMAT = 1

GEOMETRY_NAMES = {0: "point", 1: "line", 2: "polygon", -1: "any", 5: "any"}
FIELD_TYPES = {1: "bool", 2: "int", 4: "long", 6: "double", 10: "string"}


# ────────────────────────────────────────────────────────────────────────────
# Входные данные. Фигуры повторяют случаи из topoliner/tests.
# ────────────────────────────────────────────────────────────────────────────

def rect(x0, y0, x1, y1):
    return "POLYGON((%r %r, %r %r, %r %r, %r %r, %r %r))" % (
        x0, y0, x1, y0, x1, y1, x0, y1, x0, y0)


def ring(points):
    return "POLYGON((%s))" % ", ".join("%r %r" % p for p in points)


def line(points):
    return "LINESTRING(%s)" % ", ".join("%r %r" % p for p in points)


def wiggly_border(n=9, amp=0.4):
    out = []
    for i in range(n):
        y = i * 10.0 / (n - 1)
        x = 10.0 + (amp if i % 2 else -amp) * (0 if i in (0, n - 1) else 1)
        out.append((x, y))
    return out


def wiggly_pair():
    border = wiggly_border()
    left = [(0.0, 0.0)] + border + [(0.0, 10.0), (0.0, 0.0)]
    right = list(reversed(border)) + [(20.0, 0.0), (20.0, 10.0),
                                      border[-1]]
    return ring(left), ring(right)


def layer(kind, wkts, extra=None):
    """Описание входного слоя. Поля id и name есть всегда."""
    fields = [{"name": "id", "type": "int"}, {"name": "name", "type": "string"}]
    if extra:
        fields.append({"name": extra[0], "type": "string"})
    features = []
    for i, item in enumerate(wkts, start=1):
        wkt, value = (item if isinstance(item, tuple) else (item, None))
        attrs = {"id": i, "name": "f%d" % i}
        if extra:
            attrs[extra[0]] = value
        features.append({"fid": i, "wkt": wkt, "attributes": attrs})
    return {"geometry": kind, "fields": fields, "features": features}


A = rect(0, 0, 10, 10)
B_TOUCH = rect(10, 0, 20, 10)
T_RIGHT = ring([(10, 0), (20, 0), (20, 10), (10, 10), (10, 5), (10, 0)])
NEAR_RIGHT = ring([(10.5, 0), (20, 0), (20, 10), (10.5, 10), (10.5, 5),
                   (10.5, 0)])
MAIN = line([(0, 0), (100, 0)])


def gap_ring(w):
    return [rect(0, 0, 10, 10), rect(10 + w, 0, 20, 10),
            rect(0, 10, 20 + w, 20), rect(0, -10, 20 + w, 0)]


CASES = [
    # 1.01
    ("topologyaudit", "small_overlap",
     "Перекрытие площадью 1 при пороге 10, разряд auto.",
     {"INPUT": layer("polygon", [A, rect(9.9, 0, 20, 10)])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyaudit", "large_overlap",
     "Перекрытие площадью 50 при пороге 10, разряд review.",
     {"INPUT": layer("polygon", [A, rect(5, 0, 20, 10)])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyaudit", "gap_ring",
     "Замкнутая щель шириной 0.1 между четырьмя полигонами.",
     {"INPUT": layer("polygon", gap_ring(0.1))},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyaudit", "duplicate_nested",
     "Дубликат и вложенный объект.",
     {"INPUT": layer("polygon", [A, A, rect(100, 0, 200, 100),
                                 rect(110, 10, 120, 20)])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyaudit", "vertex_near_edge",
     "Вершины соседа в 0.5 от ребра.",
     {"INPUT": layer("polygon", [A, NEAR_RIGHT])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyaudit", "sliver_hole_spike",
     "Тонкий объект, малая дыра и игла.",
     {"INPUT": layer("polygon", [
         rect(0, 0, 200, 0.5),
         "POLYGON((0 10, 100 10, 100 110, 0 110, 0 10),"
         "(50 60, 51 60, 51 61, 50 61, 50 60))",
         ring([(300, 0), (310, 0), (310, 10), (305, 10), (305.0001, 25),
               (305, 10), (300, 10), (300, 0)])])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyaudit", "clean",
     "Чистое покрытие из двух соседей, находок нет.",
     {"INPUT": layer("polygon", [A, B_TOUCH])},
     {"TOLERANCE": 2.0, "AREA": 1.0}),
    # 1.02
    ("lineaudit", "endpoints",
     "Недовод 0.5, перелёт 1.5 и висячий конец.",
     {"INPUT": layer("line", [MAIN, line([(50, 20), (50, 0.5)]),
                              line([(30, -20), (30, 1.5)]),
                              line([(70, 20), (70, 10)])])},
     {"TOLERANCE": 2.0}),
    ("lineaudit", "crossing_duplicate",
     "Пересечение без узла и дубликат линии.",
     {"INPUT": layer("line", [MAIN, line([(10, -10), (10, 10)]),
                              line([(0, 50), (100, 50)]),
                              line([(100, 50), (0, 50)])])},
     {"TOLERANCE": 2.0}),
    ("lineaudit", "pseudo_short",
     "Псевдоузел и короткая линия.",
     {"INPUT": layer("line", [line([(0, 0), (50, 0)]),
                              line([(50, 0), (100, 0)]),
                              line([(200, 0), (200.4, 0)])])},
     {"TOLERANCE": 2.0, "MIN_LENGTH": 1.0, "DO_PSEUDO": True}),
    ("lineaudit", "vertices",
     "Повтор вершины и игла.",
     {"INPUT": layer("line", [line([(0, 0), (10, 0), (10, 0), (20, 0)]),
                              line([(0, 50), (10, 50), (10.0001, 60),
                                    (10, 50), (20, 50)])])},
     {"TOLERANCE": 2.0}),
    # 1.03
    ("topologyfix", "small_overlap",
     "Допуск 0.05 меньше перекрытия, работает шаг вычитания.",
     {"INPUT": layer("polygon", [A, rect(9.9, 0, 20, 10)])},
     {"TOLERANCE": 0.05, "AREA": 10.0}),
    ("topologyfix", "large_overlap",
     "Крупное перекрытие не вычитается и уходит в оставшиеся проблемы.",
     {"INPUT": layer("polygon", [A, rect(5, 0, 20, 10)])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyfix", "gap_ring",
     "Замкнутая щель шириной 0.1.",
     {"INPUT": layer("polygon", gap_ring(0.1))},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyfix", "open_gap",
     "Зазор 0.05, выходящий на край, закрывается сшивкой.",
     {"INPUT": layer("polygon", [rect(0, 0, 20, 9.95),
                                 rect(0, 10, 20, 20)])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    ("topologyfix", "dirty_three",
     "Три грязных соседа из теста полного цикла.",
     {"INPUT": layer("polygon", [
         rect(0, 0, 10.3, 10),
         ring([(10, 0), (20, 0), (20, 10), (10, 10), (10, 6), (10, 0)]),
         rect(0, 9.8, 20.1, 20)])},
     {"TOLERANCE": 2.0, "AREA": 10.0}),
    # 1.04
    ("linefix", "endpoints",
     "Недовод и перелёт исправляются, висячий конец остаётся.",
     {"INPUT": layer("line", [MAIN, line([(50, 20), (50, 0.5)]),
                              line([(30, -20), (30, 1.5)]),
                              line([(70, 20), (70, 10)])])},
     {"TOLERANCE": 2.0}),
    ("linefix", "vertices",
     "Повтор вершины и игла.",
     {"INPUT": layer("line", [line([(0, 0), (10, 0), (10, 0), (20, 0)]),
                              line([(0, 50), (10, 50), (10.0001, 60),
                                    (10, 50), (20, 50)])])},
     {"TOLERANCE": 2.0}),
    # 1.05
    ("topologyclean", "vertex_near_edge_full",
     "Полная сшивка, вершины соседа в 0.5 от ребра.",
     {"INPUT": layer("polygon", [A, NEAR_RIGHT])},
     {"TOLERANCE": 2.0, "MODE": 0}),
    ("topologyclean", "t_junction_insert",
     "Только вставка узлов, вершина соседа на ребре.",
     {"INPUT": layer("polygon", [A, T_RIGHT])},
     {"TOLERANCE": 2.0, "MODE": 1}),
    ("topologyclean", "vertex_near_edge_merge",
     "Только слияние вершин.",
     {"INPUT": layer("polygon", [A, NEAR_RIGHT])},
     {"TOLERANCE": 2.0, "MODE": 2}),
    ("topologyclean", "lines",
     "Линии, недовод 0.5.",
     {"INPUT": layer("line", [MAIN, line([(50, 20), (50, 0.5)])])},
     {"TOLERANCE": 2.0}),
    # 1.06
    ("insertnodes", "t_junction",
     "Вершина соседа на ребре, узел вставляется в ребро.",
     {"INPUT": layer("polygon", [A, T_RIGHT])}, {}),
    ("insertnodes", "crossing_lines",
     "Пересечение линий без узла.",
     {"INPUT": layer("line", [MAIN, line([(10, -10), (10, 10)])])}, {}),
    # 1.07
    ("assemblycheck", "open_gap_split",
     "Зазор 0.05 разрезает группу B1.",
     {"INPUT": layer("polygon", [(rect(0, 0, 20, 9.95), "B1"),
                                 (rect(0, 10, 20, 20), "B1")],
                     extra=("unit",))},
     {"FIELDS": ["unit"]}),
    ("assemblycheck", "hole",
     "Дыра площадью 20 внутри группы.",
     {"INPUT": layer("polygon", [(rect(0, 0, 10, 20), "B1"),
                                 (rect(10, 0, 20, 9), "B1"),
                                 (rect(10, 11, 20, 20), "B1"),
                                 (rect(20, 0, 30, 20), "B1")],
                     extra=("unit",))},
     {"FIELDS": ["unit"]}),
    ("assemblycheck", "distant_body",
     "Дальнее тело при MAX_GAP 100 не находка, микроразрыв находка.",
     {"INPUT": layer("polygon", [(rect(0, 0, 10, 9.95), "-145"),
                                 (rect(0, 10, 10, 20), "-145"),
                                 (rect(3000, 0, 3010, 10), "-145")],
                     extra=("unit",))},
     {"FIELDS": ["unit"], "MAX_GAP": 100.0}),
    # 1.08
    ("cutintocoverage", "overlay",
     "Контур поперёк общей границы, режим наложения.",
     {"INPUT": layer("polygon", [A, B_TOUCH]),
      "CUT": layer("polygon", [rect(8, -2, 12, 4)])},
     {"MODE": 0}),
    ("cutintocoverage", "clip",
     "Тот же контур, режим отсечения.",
     {"INPUT": layer("polygon", [A, B_TOUCH]),
      "CUT": layer("polygon", [rect(8, -2, 12, 4)])},
     {"MODE": 1}),
    ("cutintocoverage", "inset",
     "Тот же контур, режим врезки.",
     {"INPUT": layer("polygon", [A, B_TOUCH]),
      "CUT": layer("polygon", [rect(8, -2, 12, 4)])},
     {"MODE": 2}),
    # 2.01
    ("topologysimplify", "douglas_peucker",
     "Общая извилистая граница, Дуглас-Пекер, допуск 1.",
     {"INPUT": layer("polygon", list(wiggly_pair()))},
     {"TOLERANCE": 1.0, "METHOD": 0}),
    ("topologysimplify", "visvalingam",
     "Та же пара, Висвалингам.",
     {"INPUT": layer("polygon", list(wiggly_pair()))},
     {"TOLERANCE": 1.0, "METHOD": 1}),
    ("topologysimplify", "smooth",
     "Та же пара, сглаживание 1.",
     {"INPUT": layer("polygon", list(wiggly_pair()))},
     {"TOLERANCE": 1.0, "SMOOTH": 1}),
    ("topologysimplify", "lines",
     "Линии с общим концом.",
     {"INPUT": layer("line", [line(wiggly_border()),
                              line([(10, 10), (15, 10.3), (20, 9.8),
                                    (25, 10.2), (30, 10)])])},
     {"TOLERANCE": 1.0}),
    # 2.02
    ("boundaries", "three",
     "Три полигона, граница с полем name.",
     {"INPUT": layer("polygon", [A, B_TOUCH, rect(0, 10, 20, 20)])},
     {"FIELD": "name"}),
    ("boundaries", "hole",
     "Полигон с островом внутри.",
     {"INPUT": layer("polygon", [
         "POLYGON((0 0, 30 0, 30 30, 0 30, 0 0),(10 10, 20 10, 20 20, 10 20, 10 10))",
         rect(10, 10, 20, 20)])},
     {}),
    # 2.03
    ("coverage", "grid_2x2",
     "Четыре квадрата, узел степени 4 в центре.",
     {"INPUT": layer("polygon", [A, B_TOUCH, rect(0, 10, 10, 20),
                                 rect(10, 10, 20, 20)])},
     {}),
    ("coverage", "hole",
     "Полигон с островом внутри.",
     {"INPUT": layer("polygon", [
         "POLYGON((0 0, 30 0, 30 30, 0 30, 0 0),(10 10, 20 10, 20 20, 10 20, 10 10))",
         rect(10, 10, 20, 20)])},
     {}),
]


# ────────────────────────────────────────────────────────────────────────────
# Описание параметров в схеме toolspec (крейт rustgis-kit, Catalog).
# ────────────────────────────────────────────────────────────────────────────

def enum_value(value):
    """Целое значение перечисления Qt5 и Qt6."""
    raw = getattr(value, "value", value)
    return int(raw)


def flag_set(param, name):
    flags = enum_value(param.flags())
    masks = {"optional": 8, "advanced": 2, "hidden": 4}
    return bool(flags & masks[name])


def plain(value):
    """Значение QGIS в виде, годном для JSON."""
    if value is None:
        return None
    if hasattr(value, "isNull") and not isinstance(value, str):
        if value.isNull():
            return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    return str(value)


def text(ru, en):
    return {"ru": ru, "en": en}


def layer_kind(param):
    """Вид поля-слоя крейта. Линии отдельно, всё прочее - features."""
    types = [GEOMETRY_NAMES.get(t, "any") for t in param.dataTypes()]
    if types == ["line"]:
        return "lines"
    if types == ["point"]:
        return "points"
    return "features"


# Параметры, у которых в крейте нет вида поля. Пишутся в omitted.
OMITTED = {"fileDestination": "У крейта нет вида поля для файла. Текстовый "
                              "отчёт строится по слою находок."}


def describe_param(ru, en):
    """Параметр в схеме toolspec. None, если вида поля нет."""
    kind = ru.type()
    out = {"key": ru.name(), "kind": None,
           "label": text(ru.description(), en.description()),
           "hint": text(ru.help(), en.help())}
    default = plain(ru.defaultValue())
    if kind == "source":
        out["kind"] = layer_kind(ru)
        out["geometry"] = [GEOMETRY_NAMES.get(t, "any") for t in ru.dataTypes()]
    elif kind == "number":
        integer = enum_value(ru.dataType()) == 0
        out["kind"] = "integer" if integer else "number"
        if default is not None:
            default = int(default) if integer else float(default)
        out["minimum"] = ru.minimum()
        if ru.maximum() < 1e300:
            out["maximum"] = ru.maximum()
    elif kind == "boolean":
        out["kind"] = "bool"
    elif kind == "enum":
        out["kind"] = "enum"
        out["options"] = [text(a, b) for a, b in zip(ru.options(), en.options())]
        if ru.allowMultiple():
            out["multiple"] = True
        if default is not None:
            default = int(default)
    elif kind == "field":
        out["kind"] = "field"
        out["parent"] = ru.parentLayerParameterName()
        if ru.allowMultiple():
            out["multiple"] = True
        if enum_value(ru.dataType()) == 0:
            out["numeric"] = True
    elif kind == "sink":
        out["kind"] = "sink"
        out["geometry"] = GEOMETRY_NAMES.get(enum_value(ru.dataType()), "any")
    elif kind in ("string", "file"):
        out["kind"] = "string"
    else:
        return None
    if default is not None:
        out["default"] = default
    if flag_set(ru, "optional"):
        out["optional"] = True
    if flag_set(ru, "advanced"):
        out["advanced"] = True
    return out


# ────────────────────────────────────────────────────────────────────────────
# Прогоны.
# ────────────────────────────────────────────────────────────────────────────

def make_layer(name, spec):
    kind = {"polygon": "Polygon", "line": "LineString"}[spec["geometry"]]
    qtypes = {"int": "integer", "string": "string"}
    uri = "%s?crs=%s&%s" % (kind, CRS, "&".join(
        "field=%s:%s" % (f["name"], qtypes[f["type"]])
        for f in spec["fields"]))
    lay = QgsVectorLayer(uri, name, "memory")
    feats = []
    for item in spec["features"]:
        feat = QgsFeature(lay.fields())
        feat.setGeometry(QgsGeometry.fromWkt(item["wkt"]))
        for key, value in item["attributes"].items():
            feat[key] = value
        feats.append(feat)
    lay.dataProvider().addFeatures(feats)
    got = [f.id() for f in lay.getFeatures()]
    expected = [f["fid"] for f in spec["features"]]
    if got != expected:
        raise RuntimeError("fid входа %r вместо %r" % (got, expected))
    return lay


def field_type(field):
    return FIELD_TYPES.get(enum_value(field.type()), field.typeName())


def geometry_name(wkb):
    return {0: "point", 1: "line", 2: "polygon"}.get(
        enum_value(QgsWkbTypes.geometryType(wkb)), "none")


def xyz(point):
    z = point.z()
    return [point.x(), point.y(), None if z != z else z]


def rings_of(geom):
    """Кольца или линии геометрии по порядку, как части у крейта."""
    out = []
    for part in geom.constParts():
        if hasattr(part, "exteriorRing"):
            rings = [part.exteriorRing()] + [part.interiorRing(i) for i in
                                             range(part.numInteriorRings())]
        else:
            rings = [part]
        for ring in rings:
            out.append([xyz(p) for p in ring.vertices()])
    return out


def run_geometry(geom, kind):
    """Геометрия объекта выхода в виде прогонов крейта."""
    if geom.isNull():
        return None
    if kind == "point":
        return {"xyz": xyz(next(geom.vertices()))}
    if kind == "line" and not geom.isMultipart():
        return {"points": rings_of(geom)[0]}
    # Полигон и составная линия. У крейта своего вида для них нет, кольца
    # лежат частями, как на входе, рядом WKT для точной сборки.
    return {"parts": rings_of(geom), "wkt": geom.asWkt()}


class Recorder(QgsProcessingFeedback):
    """Сообщения журнала прогона, как report у прогонов крейта."""

    def __init__(self):
        super().__init__()
        self.lines = []

    def pushInfo(self, info):
        self.lines.append(["info", info])

    def pushWarning(self, warning):
        self.lines.append(["warn", warning])

    def reportError(self, error, fatalError=False):
        self.lines.append(["error", error])


def read_output(lay):
    fields = [[f.name(), field_type(f)] for f in lay.fields()]
    kind = geometry_name(lay.wkbType())
    feats = []
    for feat in lay.getFeatures():
        feats.append({
            "values": [plain(feat[name]) for name, _t in fields],
            "geometry": run_geometry(feat.geometry(), kind),
        })
    return {"geometry": kind, "multi": QgsWkbTypes.isMultiType(lay.wkbType()),
            "hasz": QgsWkbTypes.hasZ(lay.wkbType()),
            "fields": fields, "features": feats}


def load_plugin(language):
    """
    Провайдер плагина с интерфейсом на заданном языке.

    Часть строк плагин переводит при импорте модуля, поэтому язык
    задаётся до импорта, а модули импортируются заново для каждого языка.
    Модули прежнего языка остаются жить в своих алгоритмах.
    """
    for name in [n for n in sys.modules
                 if n == "topoliner" or n.startswith("topoliner.")]:
        del sys.modules[name]
    from topoliner import i18n
    i18n.set_language(language)
    from topoliner.provider import TopolinerProvider
    from topoliner import help_texts
    provider = TopolinerProvider()
    provider.loadAlgorithms()
    algorithms = {a.name(): a for a in provider.algorithms()}
    return provider, algorithms, help_texts, i18n


def run_case(algorithms, tool, inputs, params):
    alg = algorithms[tool].create()
    layers = {key: make_layer(key, spec) for key, spec in inputs.items()}
    full = dict(params)
    full.update(layers)
    sinks = [d.name() for d in alg.parameterDefinitions() if d.type() == "sink"]
    for name in sinks:
        full[name] = "TEMPORARY_OUTPUT"
    context = QgsProcessingContext()
    feedback = Recorder()
    results, ok = alg.run(full, context, feedback)
    if not ok:
        raise RuntimeError("%s: прогон не удался" % tool)
    outputs = {}
    for name in sinks:
        lay = QgsProcessingUtils.mapLayerFromString(results.get(name, ""),
                                                    context)
        if lay is not None:
            outputs[name] = read_output(lay)
    return outputs, feedback.lines


def merge_languages(tool, case, ru, en):
    """Русский прогон с английскими строками там, где они отличаются."""
    for name, out_ru in ru.items():
        out_en = en[name]
        if len(out_ru["features"]) != len(out_en["features"]):
            raise RuntimeError("%s/%s: разное количество объектов в %s"
                               % (tool, case, name))
        names = [f[0] for f in out_ru["fields"]]
        for f_ru, f_en in zip(out_ru["features"], out_en["features"]):
            if f_ru["geometry"] != f_en["geometry"]:
                raise RuntimeError("%s/%s: геометрия зависит от языка"
                                   % (tool, case))
            diff = {n: b for n, a, b in zip(names, f_ru["values"],
                                             f_en["values"]) if a != b}
            if diff:
                f_ru["values_en"] = diff
    return ru


def input_features(spec):
    """Объекты входа в виде прогонов крейта, рядом WKT."""
    out = []
    for item in spec["features"]:
        geom = QgsGeometry.fromWkt(item["wkt"])
        out.append({"id": item["fid"], "attrs": item["attributes"],
                    "parts": rings_of(geom), "wkt": item["wkt"]})
    return out


def layer_info(key, spec):
    return {"name": key.lower(), "geometry": spec["geometry"], "hasz": False,
            "fields": [f["name"] for f in spec["fields"]],
            "numeric": [f["name"] for f in spec["fields"]
                        if f["type"] in ("int", "double")]}


def run_values(spec_tool, inputs, params):
    """Значения всех полей инструмента: заданные и умолчания."""
    values = {}
    for param in spec_tool["params"]:
        key = param["key"]
        if param["kind"] == "sink":
            if param.get("optional"):
                values[key] = True
            continue
        if key in inputs:
            values["@" + key] = layer_info(key, inputs[key])
            continue
        if param["kind"] in ("lines", "points", "features"):
            values[key] = None
            continue
        values[key] = params.get(key, param.get("default"))
    return values


# ────────────────────────────────────────────────────────────────────────────
# Сообщения расчёта.
# ────────────────────────────────────────────────────────────────────────────

SKIP_METHODS = {"initAlgorithm", "displayName", "group", "groupId",
                "shortHelpString", "name", "createInstance", "helpUrl", "icon"}


def class_messages(alg, english):
    """Строки tr из методов расчёта класса алгоритма."""
    import ast
    import inspect
    path = inspect.getsourcefile(type(alg))
    with open(path, encoding="utf-8") as handle:
        tree = ast.parse(handle.read())
    found = []
    for node in tree.body:
        if not (isinstance(node, ast.ClassDef) and node.name == type(alg).__name__):
            continue
        for item in node.body:
            if not isinstance(item, ast.FunctionDef) or item.name in SKIP_METHODS:
                continue
            for call in ast.walk(item):
                if (isinstance(call, ast.Call)
                        and getattr(call.func, "id", "") == "tr" and call.args
                        and isinstance(call.args[0], ast.Constant)):
                    value = call.args[0].value
                    if value in english and value not in found:
                        found.append(value)
    return [text(s, english[s]) for s in found]


def value_messages(runs, tool):
    """Строковые значения выходов, у которых английский текст другой."""
    pairs = []
    for run in runs:
        if run["tool"] != tool:
            continue
        for out in run["output"].values():
            names = [f[0] for f in out["fields"]]
            for feat in out["features"]:
                for name, en in feat.get("values_en", {}).items():
                    ru = feat["values"][names.index(name)]
                    if isinstance(ru, str) and {"ru": ru, "en": en} not in pairs:
                        pairs.append({"ru": ru, "en": en})
    return pairs


# ────────────────────────────────────────────────────────────────────────────
# Сборка.
# ────────────────────────────────────────────────────────────────────────────

def plugin_version():
    path = os.path.join(ROOT, "topoliner", "metadata.txt")
    with open(path, encoding="utf-8") as handle:
        for line_text in handle:
            if line_text.startswith("version="):
                return line_text.split("=", 1)[1].strip()
    return None


def build():
    provider_ru, algs_ru, help_ru, i18n_ru = load_plugin("ru")
    provider_en, algs_en, help_en, _i18n_en = load_plugin("en")
    keep = (provider_ru, provider_en)  # держат алгоритмы живыми
    english = i18n_ru.EN

    version = plugin_version()
    order = sorted(algs_ru, key=lambda n: algs_ru[n].displayName())

    tools = []
    omitted = []
    for name in order:
        ru = algs_ru[name].create()
        en = algs_en[name].create()
        code, title_ru = ru.displayName().split(" ", 1)
        params = []
        for p_ru, p_en in zip(ru.parameterDefinitions(), en.parameterDefinitions()):
            item = describe_param(p_ru, p_en)
            if item is None:
                omitted.append({"tool": name, "key": p_ru.name(),
                                "why": OMITTED.get(p_ru.type(), p_ru.type())})
                continue
            params.append(item)
        tools.append({
            "code": code, "name": name,
            "title": text(title_ru, en.displayName().split(" ", 1)[1]),
            "group": code.split(".")[0],
            "help": text(help_ru.help_for(name), help_en.help_for(name)),
            "params": params,
            "messages": class_messages(ru, english),
        })

    runs = []
    by_name = {t["name"]: t for t in tools}
    for tool, case, note, inputs, params in CASES:
        out_ru, report = run_case(algs_ru, tool, inputs, params)
        out_en, _report = run_case(algs_en, tool, inputs, params)
        output = merge_languages(tool, case, out_ru, out_en)
        runs.append({
            "tool": tool, "case": case, "about": note,
            "values": run_values(by_name[tool], inputs, params),
            "input": {key: input_features(spec) for key, spec in inputs.items()},
            "output": output,
            "report": report,
            "tolerance": {"xy": 1e-9, "fields": 1e-9},
        })

    # Поля выходных слоёв в описание выхода и сообщения из значений.
    for spec_tool in tools:
        for param in spec_tool["params"]:
            if param["kind"] != "sink":
                continue
            for run in runs:
                out = run["output"].get(param["key"]) if run["tool"] == spec_tool["name"] else None
                if out is not None:
                    param["fields"] = out["fields"]
                    break
        known = {m["ru"] for m in spec_tool["messages"]}
        for pair in value_messages(runs, spec_tool["name"]):
            if pair["ru"] not in known:
                spec_tool["messages"].append(pair)
                known.add(pair["ru"])

    catalog = {"format": FORMAT, "module": "topoliner", "version": version,
               "generated_by": "tools/export_tools.py",
               "omitted": omitted, "tools": tools}
    tool_runs = {"format": FORMAT, "module": "topoliner", "version": version,
                 "crs": CRS, "language": "ru",
                 "about": ABOUT, "skipped": SKIPPED, "runs": runs}
    del keep
    return catalog, tool_runs


ABOUT = ("Прогоны алгоритмов Processing модуля QGIS без окна, QGIS 4. "
         "Координаты - метры системы " + CRS + ". Строки на русском, "
         "английские строки, которые отличаются, лежат в values_en. "
         "Величина value округлена до четырёх значащих цифр. "
         "Полигоны на входе и на выходе лежат кольцами в parts, рядом WKT.")

SKIPPED = [
    {"tool": "topologyaudit", "case": "report_file",
     "why": "Текстовый отчёт REPORT_FILE. У крейта нет вида поля для файла."},
    {"tool": "topologyclean", "case": "reference",
     "why": "Слой-эталон REFERENCE не прогонялся, случаев с ним нет."},
    {"tool": "insertnodes", "case": "reference",
     "why": "Слой-эталон REFERENCE не прогонялся, случаев с ним нет."},
]


def dump(data):
    return (json.dumps(data, ensure_ascii=False, indent=1) + "\n").encode(
        "utf-8")


def main():
    check = "--check" in sys.argv[1:]
    app = QgsApplication([], False)
    app.initQgis()
    catalog, tool_runs = build()

    targets = {os.path.join(ROOT, "tools.json"): dump(catalog),
               os.path.join(ROOT, "fixtures", "tool_runs.json"): dump(tool_runs)}

    stale = []
    for path, body in sorted(targets.items()):
        old = None
        if os.path.exists(path):
            with open(path, "rb") as handle:
                old = handle.read()
        if old == body:
            continue
        stale.append(os.path.relpath(path, ROOT))
        if not check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as handle:
                handle.write(body)

    print("Инструментов: %d, прогонов: %d" % (len(catalog["tools"]),
                                              len(tool_runs["runs"])))
    if check:
        print("Расхождений: %d" % len(stale))
        for name in stale:
            print("  " + name)
        return 1 if stale else 0
    print("Записано файлов: %d" % len(stale))
    return 0


if __name__ == "__main__":
    sys.exit(main())
