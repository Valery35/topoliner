# -*- coding: utf-8 -*-
"""
cut
---
Ввод нарисованного контура в полигональное покрытие.

Три режима наложения отвечают на один вопрос, кому достаётся площадь под
контуром. Наложение отдаёт её контуру, отсечение оставляет соседям, врезка
отдаёт контуру только то, что лежит внутри покрытия. Кромка во всех трёх
случаях приходит из одного наложения.

Обычная врезка средствами редактора делает два независимых действия. У нового
объекта отрезается всё, что попало на соседей, а у каждого соседа отрезается
то, что попало под новый объект. Кромка разреза получается двумя разными
вызовами, и совпадает она только по виду. Вершины расходятся, и дальше эти
расхождения находит проверка топологии.

Здесь кромка приходит из одного и того же операнда. Контур собирается в одну
геометрию, и все вычитания и пересечения делаются против неё. GEOS нодирует
оба аргумента наложения, поэтому кромка у обеих сторон получается из одной
нодированной дуги. Совпадение проверяется тестами через модель покрытия:
кромка обязана стать одной дугой с двумя соседями, а не двумя дугами рядом.

Порог площади работает по общему правилу плагина. Остаток мельче порога
не оставляется отдельным осколком, а молча отходит соседу.

Атрибуты нового объекта решает оболочка. Ядро возвращает список объектов,
отдавших площадь, а правило присвоения к геометрии отношения не имеет.

Чистый Python поверх адаптера geom_backend, тестируется headless.
"""

try:  # внутри плагина QGIS
    from .topo_core import MODE_INSERT, clean_topology
except ImportError:  # headless-тесты
    from topo_core import MODE_INSERT, clean_topology

__all__ = ["cut_into_coverage", "MODE_OVERLAY", "MODE_CLIP", "MODE_INSET"]

# Режимы наложения. Различаются тем, что достаётся новому объекту.
MODE_OVERLAY = "overlay"  # наложение: весь контур, соседи урезаются
MODE_CLIP = "clip"        # отсечение: только свободное место, соседи как были
MODE_INSET = "inset"      # врезка: только то, что внутри покрытия


def _parts_of(backend, geometry):
    """Геометрия в виде списка частей, часть это список колец."""
    if geometry is None or backend.is_empty(geometry):
        return []
    polygonal = backend.polygonal_only(geometry)
    if polygonal is None or backend.is_empty(polygonal):
        return []
    out = []
    for part in backend.parts(polygonal):
        rings = backend.rings(part)
        if rings and len(rings[0]) >= 4:
            out.append(rings)
    return out


def _geometry(backend, parts):
    """Части в одну геометрию. Часть это список колец."""
    pieces = [backend.polygon(list(rings)) for rings in parts if rings]
    pieces = [g for g in pieces if g is not None and not backend.is_empty(g)]
    if not pieces:
        return None
    if len(pieces) == 1:
        return pieces[0]
    return backend.multipolygon(pieces)


def _area(backend, geometry):
    if geometry is None or backend.is_empty(geometry):
        return 0.0
    return backend.area(geometry)


def _valid(backend, geometry):
    """Геометрия, пригодная к записи, либо None."""
    if geometry is None or backend.is_empty(geometry):
        return None
    if not backend.is_valid(geometry):
        geometry = backend.make_valid(geometry)
        if geometry is None or backend.is_empty(geometry):
            return None
    geometry = backend.polygonal_only(geometry)
    if geometry is None or backend.is_empty(geometry):
        return None
    return geometry


def _plain(ring):
    """Кольцо без пустой отметки. Ядро дописывает Z, и без Z она равна None."""
    out = []
    for v in ring:
        out.append((v[0], v[1]) if len(v) < 3 or v[2] is None else v)
    return out


def _insert_nodes(pieces, tolerance):
    """
    Вставляет недостающие узлы в набор объектов.

    pieces это список (ключ, parts). Возвращает {ключ: parts} только для тех,
    у кого количество вершин изменилось, и количество вставленных узлов.

    Разрез кладёт вершину на границу донора с третьим объектом, и у этого
    третьего узла в том месте нет. Без вставки врезка оставляла бы после себя
    ровно то нарушение, ради которого сделан инструмент 1.06.
    """
    rings = []
    index = []
    for key, parts in pieces:
        idx_parts = []
        for part in parts:
            idx_ring = []
            for ring in part:
                idx_ring.append(len(rings))
                rings.append(list(ring))
            idx_parts.append(idx_ring)
        index.append((key, idx_parts))
    if not rings:
        return {}, 0

    result = clean_topology(rings, tolerance=tolerance, mode=MODE_INSERT,
                            project_onto_edge=True)
    inserted = result["stats"]["nodes_inserted"]
    if not inserted:
        return {}, 0

    new_rings = result["rings"]
    out = {}
    for key, idx_parts in index:
        before = sum(len(rings[i]) for part in idx_parts for i in part)
        after = 0
        parts = []
        for part in idx_parts:
            new_part = []
            for i in part:
                ring = new_rings[i]
                if not ring:
                    continue
                after += len(ring)
                new_part.append(_plain(ring))
            if new_part:
                parts.append(new_part)
        if after != before and parts:
            out[key] = parts
    return out, inserted


def cut_into_coverage(backend, items, cut_parts, area_threshold=0.0,
                      node_eps=1e-6, mode=MODE_OVERLAY):
    """
    Вводит нарисованный контур в участок покрытия.

    items           список (fid, parts), часть это список колец, первое
                    кольцо внешнее. Достаточно объектов вокруг контура,
                    всё покрытие не нужно.
    cut_parts       нарисованный контур в том же виде
    area_threshold  остаток мельче этой площади молча отходит соседу
    node_eps        отклонение при вставке недостающих узлов. Ноль отключает
    mode            кому достаётся спорная площадь

    Режимы различаются одним, что получает новый объект.

    MODE_OVERLAY  весь контур. Соседи урезаются, покрытие растёт на ту
                  часть контура, что легла за его краем
    MODE_CLIP     только свободное место. Соседи не изменяются вовсе,
                  контур ложится в промежутки между ними
    MODE_INSET    только то, что лежит внутри покрытия. Соседи урезаются,
                  площадь покрытия не меняется, она перераспределяется

    Возвращает словарь:
        changed   {fid: parts} новая геометрия объекта. Пустой список
                  означает, что объект поглощён целиком
        created   parts нового объекта, либо пустой список
        donors    идентификаторы объектов, отдавших площадь
        outside   площадь контура вне покрытия, доставшаяся новому объекту
        dropped   площадь контура вне покрытия, отброшенная. Врезка
                  отбрасывает её всю, остальные режимы только ту часть,
                  что мельче порога
        area_before, area_after  площадь участка покрытия до и после.
                  Разница между ними равна outside: врезка не создаёт
                  и не теряет площадь, она только перераспределяет её
                  между объектами и добавляет то, что легло за краем
        untouched идентификаторы объектов, у которых врезка не отрезала
                  площадь
        noded     {fid: parts} соседи, получившие недостающие узлы. Форма
                  и площадь у них прежние, изменилось только количество
                  вершин
        nodes     количество вставленных узлов
    """
    empty = {"changed": {}, "created": [], "donors": [], "outside": 0.0,
             "dropped": 0.0, "area_before": 0.0, "area_after": 0.0,
             "untouched": [], "noded": {}, "nodes": 0}
    if mode not in (MODE_OVERLAY, MODE_CLIP, MODE_INSET):
        raise ValueError("Неизвестный режим: %r" % (mode,))

    cut = _valid(backend, _geometry(backend, cut_parts))
    if cut is None:
        return empty

    covers = []
    for fid, parts in items:
        geometry = _valid(backend, _geometry(backend, parts))
        if geometry is not None:
            covers.append((fid, geometry))
    if not covers:
        # Покрытия рядом нет. Врезке нечего резать, остальным режимам
        # достаётся весь контур.
        if mode == MODE_INSET:
            empty["dropped"] = _area(backend, cut)
            return empty
        empty["created"] = _parts_of(backend, cut)
        empty["outside"] = _area(backend, cut)
        empty["area_after"] = empty["outside"]
        return empty

    area_before = 0.0
    for _fid, geometry in covers:
        area_before += _area(backend, geometry)

    changed = {}
    untouched = []
    donors = []
    taken = []

    for fid, geometry in covers:
        # Отсечение соседей не трогает, у них контур площади не берёт.
        if mode == MODE_CLIP or not backend.intersects(geometry, cut):
            untouched.append(fid)
            continue

        inside = _valid(backend, backend.intersection(geometry, cut))
        rest = _valid(backend, backend.difference(geometry, cut))

        inside_area = _area(backend, inside)
        rest_area = _area(backend, rest)

        # Отрезанный кусок мельче порога. Объект остаётся как был, контур
        # в этом месте площади не получает.
        if inside is None or inside_area < area_threshold:
            untouched.append(fid)
            continue

        # Остаток мельче порога. Объект уходит под контур целиком, осколок
        # не создаётся.
        if rest is None or rest_area < area_threshold:
            changed[fid] = []
            donors.append(fid)
            taken.append(geometry)
            continue

        changed[fid] = _parts_of(backend, rest)
        donors.append(fid)
        taken.append(inside)

    # Часть контура за пределами покрытия. Врезка её отбрасывает,
    # остальные режимы отдают новому объекту.
    covered = backend.union_all([geometry for _fid, geometry in covers])
    outside = _valid(backend, backend.difference(cut, covered))
    outside_area = _area(backend, outside)
    dropped = 0.0
    if outside is None or outside_area < area_threshold:
        dropped = outside_area
        outside_area = 0.0
    elif mode == MODE_INSET:
        dropped = outside_area
        outside_area = 0.0
    else:
        taken.append(outside)

    created_geometry = _valid(backend, backend.union_all(taken)) if taken else None
    created = _parts_of(backend, created_geometry)

    # ── Недостающие узлы ──────────────────────────────────────────────────
    # Кромка разреза заканчивается на границе донора с третьим объектом,
    # и у этого третьего узла в той точке нет.
    noded = {}
    nodes = 0
    if node_eps and node_eps > 0.0:
        pieces = []
        for fid, geometry in covers:
            parts = changed.get(fid)
            if parts is None:
                parts = _parts_of(backend, geometry)
            if parts:
                pieces.append(((0, fid), parts))
        if created:
            pieces.append(((1, 0), created))
        fixed, nodes = _insert_nodes(pieces, node_eps)
        for key, parts in fixed.items():
            if key[0] == 1:
                created = parts
            elif key[1] in changed:
                changed[key[1]] = parts
            else:
                noded[key[1]] = parts

    area_after = _area(backend, _geometry(backend, created))
    for fid, parts in changed.items():
        if parts:
            area_after += _area(backend, _geometry(backend, parts))
    for fid in untouched:
        parts = noded.get(fid)
        if parts is not None:
            area_after += _area(backend, _geometry(backend, parts))
            continue
        for other, geometry in covers:
            if other == fid:
                area_after += _area(backend, geometry)
                break

    return {
        "changed": changed,
        "created": created,
        "donors": donors,
        "outside": outside_area,
        "dropped": dropped,
        "area_before": area_before,
        "area_after": area_after,
        "untouched": untouched,
        "noded": noded,
        "nodes": nodes,
    }
