# -*- coding: utf-8 -*-
"""
boundaries
----------
Извлечение границ полигонального покрытия отдельными линиями.

Обычный перевод полигонов в линии выдаёт границу дважды: по разу от каждого
соседа. Здесь граница между двумя телами выходит одной линией, от узла
до узла, и несёт признак того, с чем она граничит.

Это нужно для оформления: границу между двумя пластами рисуют иначе, чем
внешний край покрытия или край выработки. С двумя совпадающими линиями так
не получится.

Разбор на дуги берётся из topo_simplify: рёбра, общие для двух колец,
склеиваются в дугу между узлами ветвления. Дуга обрывается там, где сходятся
три и более полигона или где меняется пара соседей.

Чистый Python, тестируется headless.
"""

try:  # внутри плагина QGIS
    from .topo_core import MODE_INSERT, clean_topology
    from .topo_simplify import build_arcs
except ImportError:  # headless-тесты
    from topo_core import MODE_INSERT, clean_topology
    from topo_simplify import build_arcs

__all__ = ["extract_boundaries", "KIND_SHARED", "KIND_OUTER", "KIND_HOLE"]

KIND_SHARED = "shared"   # граница между двумя объектами
KIND_OUTER = "outer"     # внешний край покрытия
KIND_HOLE = "hole"       # край полости внутри объекта


def insert_missing_nodes(rings, eps=1e-6, max_passes=8):
    """
    Достраивает узлы там, где вершина одного кольца лежит на ребре другого.

    Без этого общая граница не опознаётся: у соседей разная вершинность,
    рёбра не совпадают, и один и тот же участок выходит двумя линиями
    вместо одной. Вершины при этом не двигаются, форма не меняется.
    """
    current = [list(r) + [r[0]] for r in rings]
    for _ in range(max_passes):
        result = clean_topology(current, tolerance=eps, mode=MODE_INSERT,
                                project_onto_edge=True)
        current = [r if r else [] for r in result["rings"]]
        if result["stats"]["nodes_inserted"] == 0:
            break
    out = []
    for ring in current:
        coords = [(p[0], p[1]) for p in ring]
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        out.append(coords)
    return out


def extract_boundaries(items, grid=1e-7, node_eps=1e-6):
    """
    Извлекает границы покрытия.

    node_eps  отклонение, в пределах которого вершина считается лежащей
              на ребре соседа. Такие узлы достраиваются перед разбором,
              иначе общая граница не опознаётся

    items: список (fid, parts), где parts это список частей объекта,
           часть это список колец, кольцо это список (x, y) без повтора
           первой вершины в конце. Первое кольцо части внешнее, остальные
           это полости.

    Возвращает список словарей:
        coords   вершины линии
        kind     shared, outer или hole
        fid_a    идентификатор одного соседа
        fid_b    идентификатор другого соседа, либо None
        ring_a   0 если участок принадлежит внешнему кольцу объекта a,
                 иначе номер полости
        ring_b   то же для объекта b

    Каждая граница выдаётся один раз. Внешний край покрытия и край полости
    имеют только одного соседа.
    """
    rings = []
    owners = []          # для каждого кольца: (fid, номер кольца в части)
    for fid, parts in items:
        for part in parts:
            for ring_index, ring in enumerate(part):
                coords = [(p[0], p[1]) for p in ring]
                if len(coords) > 1 and coords[0] == coords[-1]:
                    coords = coords[:-1]
                if len(coords) < 3:
                    continue
                rings.append(coords)
                owners.append((fid, ring_index))

    if not rings:
        return []

    if node_eps > 0:
        rings = insert_missing_nodes(rings, eps=node_eps)

    arcs, ring_paths = build_arcs(rings, grid=grid)

    # Кто пользуется каждой дугой. Одна дуга бывает у двух колец: тогда
    # это общая граница. У одного кольца это внешний край или край полости.
    users = {}
    for ring_index, path in enumerate(ring_paths):
        for arc_index, _reversed_flag in path:
            users.setdefault(arc_index, []).append(ring_index)

    out = []
    for arc_index, arc in enumerate(arcs):
        holders = users.get(arc_index, [])
        if not holders:
            continue

        first = holders[0]
        fid_a, ring_a = owners[first]

        if len(holders) >= 2:
            second = holders[1]
            fid_b, ring_b = owners[second]
            kind = KIND_SHARED
        else:
            fid_b, ring_b = None, None
            # Кольцо с номером больше нуля это полость объекта.
            kind = KIND_HOLE if ring_a > 0 else KIND_OUTER

        out.append({
            "coords": list(arc),
            "kind": kind,
            "fid_a": fid_a,
            "fid_b": fid_b,
            "ring_a": ring_a,
            "ring_b": ring_b,
        })

    return out
