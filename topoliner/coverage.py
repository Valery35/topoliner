# -*- coding: utf-8 -*-
"""
coverage
--------
Топологическая модель покрытия: узлы, дуги, полигоны как списки дуг.

Та самая модель, что была в ArcInfo coverage. Полигон хранится не своей
границей, а ссылками на дуги, дуга хранится один раз и знает, что лежит
слева и справа. Смысл в том, что правка дуги меняет обоих соседей сразу:
разойтись границам просто негде.

Иван Иванов после публикации на GIS-Lab сформулировал это так: общий набор
узлов, дуги между ними, полигоны и линии как списки дуг.

Три вещи, которые модель даёт:

- узел со степенью, то есть числом сходящихся дуг. Степень 1 это висячий
  конец, 2 псевдоузел, 3 и больше настоящее ветвление;
- дуга с идентификаторами обоих соседей и обоих узлов;
- сборка полигонов обратно из дуг, в том числе исправленных.

Чистый Python, тестируется headless.
"""

try:  # внутри плагина QGIS
    from .boundaries import insert_missing_nodes
    from .topo_simplify import build_arcs
except ImportError:  # headless-тесты
    from boundaries import insert_missing_nodes
    from topo_simplify import build_arcs

__all__ = ["build_coverage", "assemble_from_arcs"]


def _key(x, y, grid):
    return (round(x / grid), round(y / grid))


def build_coverage(items, grid=1e-7, node_eps=1e-6):
    """
    Раскладывает покрытие на узлы и дуги.

    items: список (fid, parts), часть это список колец, первое кольцо
           внешнее, остальные полости. Кольца без повтора первой вершины.

    Возвращает словарь:
        nodes   список узлов: {"id", "x", "y", "degree", "arcs"}
        arcs    список дуг: {"id", "coords", "from_node", "to_node",
                             "left", "right", "left_ring", "right_ring"}
        rings   для каждого исходного кольца список (arc_id, развёрнута ли),
                то есть кольцо как список дуг
        owners  для каждого кольца (fid, номер кольца в части)

    Слева и справа: left это объект, при обходе которого дуга проходится
    в записанном направлении, right это второй сосед. Для края покрытия
    right пуст.
    """
    rings = []
    owners = []
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
        return {"nodes": [], "arcs": [], "rings": [], "owners": []}

    if node_eps > 0:
        rings = insert_missing_nodes(rings, eps=node_eps)

    arcs, ring_paths = build_arcs(rings, grid=grid)

    # ── Владельцы дуг ────────────────────────────────────────────────────
    users = {}
    for ring_index, path in enumerate(ring_paths):
        for arc_index, reversed_flag in path:
            users.setdefault(arc_index, []).append((ring_index, reversed_flag))

    # ── Узлы ─────────────────────────────────────────────────────────────
    # Узел это конец дуги. Одна и та же точка у разных дуг должна получить
    # один номер, поэтому ключ округляется до сетки.
    node_by_key = {}
    nodes = []

    def node_id(x, y):
        key = _key(x, y, grid)
        found = node_by_key.get(key)
        if found is None:
            found = len(nodes)
            node_by_key[key] = found
            nodes.append({"id": found, "x": x, "y": y, "degree": 0,
                          "arcs": []})
        return found

    out_arcs = []
    for arc_index, arc in enumerate(arcs):
        holders = users.get(arc_index, [])
        if not holders or len(arc) < 2:
            continue

        start = node_id(arc[0][0], arc[0][1])
        end = node_id(arc[-1][0], arc[-1][1])

        left = right = None
        left_ring = right_ring = None
        for ring_index, reversed_flag in holders[:2]:
            fid, ring_number = owners[ring_index]
            if not reversed_flag and left is None:
                left, left_ring = fid, ring_number
            elif right is None:
                right, right_ring = fid, ring_number
            elif left is None:
                left, left_ring = fid, ring_number

        arc_id = len(out_arcs)
        out_arcs.append({
            "id": arc_id,
            "coords": list(arc),
            "from_node": start,
            "to_node": end,
            "left": left,
            "right": right,
            "left_ring": left_ring,
            "right_ring": right_ring,
        })
        nodes[start]["arcs"].append(arc_id)
        if end != start:
            nodes[end]["arcs"].append(arc_id)
        else:
            # Замкнутая дуга входит в свой узел дважды.
            nodes[start]["arcs"].append(arc_id)

    for node in nodes:
        node["degree"] = len(node["arcs"])

    # ── Кольца как списки дуг ────────────────────────────────────────────
    # Номера дуг могли сдвинуться, если какие-то отброшены, поэтому
    # соответствие строится заново.
    renumber = {}
    for new_id, arc in enumerate(out_arcs):
        renumber[arc["id"]] = new_id
    ring_arc_lists = []
    for path in ring_paths:
        ring_arc_lists.append([(renumber[a], flag) for a, flag in path
                               if a in renumber])

    return {
        "nodes": nodes,
        "arcs": out_arcs,
        "rings": ring_arc_lists,
        "owners": owners,
    }


def assemble_from_arcs(coverage, arcs_by_id=None):
    """
    Собирает кольца обратно из дуг.

    arcs_by_id  словарь номер дуги -> вершины, если дуги правились снаружи.
                Не указанные берутся из покрытия.

    В этом и смысл модели: правка дуги отражается на обоих соседях сразу,
    поэтому границы не расходятся.

    Возвращает список (fid, номер кольца, вершины).
    """
    source = {}
    for arc in coverage["arcs"]:
        source[arc["id"]] = arc["coords"]
    if arcs_by_id:
        source.update(arcs_by_id)

    out = []
    for ring_index, path in enumerate(coverage["rings"]):
        points = []
        for arc_id, reversed_flag in path:
            piece = list(source.get(arc_id, ()))
            if not piece:
                continue
            if reversed_flag:
                piece = list(reversed(piece))
            # Конец дуги совпадает с началом следующей, поэтому отбрасывается.
            points.extend(piece[:-1])
        if len(points) < 3:
            out.append((coverage["owners"][ring_index][0],
                        coverage["owners"][ring_index][1], None))
            continue
        fid, ring_number = coverage["owners"][ring_index]
        out.append((fid, ring_number, points))
    return out
