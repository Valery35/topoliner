# -*- coding: utf-8 -*-
"""
i18n
----
Перевод интерфейса. Язык определяется локалью QGIS, а не системы: человек
мог выставить в QGIS английский на русской машине.

Исходный язык русский, поэтому строки в коде остаются читаемыми и при
отсутствии перевода выводятся как есть. Функция tr возвращает перевод,
если он есть, и исходную строку в противном случае.

Механизм словарный, без внешних файлов .qm: компиляция переводов требует
lrelease, которого может не быть у того, кто ставит плагин из ZIP.
"""

__all__ = ["tr", "is_russian", "set_language"]

_language = None


def _detect():
    """Двухбуквенный код языка интерфейса QGIS."""
    value = ""
    try:
        from qgis.core import QgsSettings
    except ImportError:
        # QGIS недоступен: значит идут headless-тесты, язык берётся
        # из локали системы ниже.
        QgsSettings = None
    if QgsSettings is not None:
        value = QgsSettings().value("locale/userLocale", "") or ""

    if not value:
        import locale
        try:
            value = locale.getdefaultlocale()[0] or ""
        except ValueError:
            # Некорректная переменная окружения с локалью.
            value = ""

    return (value or "en")[:2].lower()


def set_language(code):
    """Задать язык принудительно. Нужно тестам."""
    global _language
    _language = (code or "en")[:2].lower()


def is_russian():
    global _language
    if _language is None:
        _language = _detect()
    return _language == "ru"


def tr(text):
    """Перевод строки. Без перевода возвращается исходный текст."""
    if is_russian():
        return text
    return EN.get(text, text)


# ────────────────────────────────────────────────────────────────────────────
# Словарь. Ключ это русская строка из кода.
# ────────────────────────────────────────────────────────────────────────────

EN = {
    # Группы и названия инструментов
    "1. Топология": "1. Topology",
    "2. Генерализация": "2. Generalisation",
    "1.01 Проверка топологии полигонов": "1.01 Polygon topology check",
    "1.03 Очистка топологии полигонов": "1.03 Polygon topology cleanup",
    "1.05 Сшивка узлов и вершин": "1.05 Node and vertex snapping",
    "1.07 Контроль сборки по атрибуту": "1.07 Assembly check by attribute",
    "1.06 Вставка недостающих узлов": "1.06 Insertion of missing nodes",
    "2.01 Топологическое упрощение": "2.01 Topology-preserving simplify",
    "Topoliner - топология и обработка геометрии":
        "Topoliner - topology and geometry processing",

    # Параметры, общие
    "Входной слой (полигоны)": "Input layer (polygons)",
    "Входной слой (полигоны или линии)": "Input layer (polygons or lines)",
    "Проверяемый слой (полигоны)": "Layer to check (polygons)",
    "Слой (полигоны)": "Layer (polygons)",
    "Допуск (в единицах CRS слоя)": "Tolerance (in layer CRS units)",
    "Порог площади мусора (в кв. единицах CRS)":
        "Debris area threshold (in square CRS units)",
    "Поле или поля группировки (необязательно)":
        "Grouping field or fields (optional)",
    "Поле или поля группировки": "Grouping field or fields",
    "Полость крупнее этой площади щелью не считается (0 - не учитывать)":
        "Cavity larger than this area is not counted as a gap (0 - ignore)",
    "Эталонный слой (необязательно)": "Reference layer (optional)",
    "Опорный слой (необязательно)": "Donor layer (optional)",
    "Сохранять отметки Z": "Keep Z values",
    "Восстанавливать отметки Z": "Restore Z values",

    # Параметры проверки
    "Искать перекрытия, дубликаты и вложения":
        "Find overlaps, duplicates and nested objects",
    "Искать щели в покрытии": "Find gaps in the coverage",
    "Искать вершины без узла на соседнем ребре":
        "Find vertices without a node on a neighbour edge",
    "Находки": "Findings",
    "Находки сборки": "Assembly findings",

    # Параметры очистки и сшивки
    "Сшивать вершины и узлы": "Snap vertices and nodes",
    "Исправлять некорректную геометрию": "Repair invalid geometry",
    "Убирать мелкие перекрытия": "Remove small overlaps",
    "Заполнять мелкие щели": "Fill small gaps",
    "При перекрытии площадь сохраняет": "On overlap the area is kept by",
    "Более крупный объект": "The larger object",
    "Объект с меньшим идентификатором": "The object with the smaller identifier",
    "Удалять объекты мельче порога площади":
        "Delete objects smaller than the area threshold",
    "Порог угла иглы, градусы": "Spike angle threshold, degrees",
    "Не изменять объекты уже допуска":
        "Do not modify objects narrower than the tolerance",
    "Проверять корректность геометрии до и после":
        "Check geometry validity before and after",
    "Ставить узлы в точках пересечения рёбер":
        "Insert nodes at edge intersections",
    "Кто кого притягивает": "Which object attracts which",
    "По порядку объектов в слое": "By object order in the layer",
    "Крупные объекты притягивают мелкие": "Larger objects attract smaller ones",
    "Отметка Z вставленного узла": "Z value of an inserted node",
    "Интерполировать вдоль ребра": "Interpolate along the edge",
    "Взять у притянутой вершины": "Take from the attracted vertex",
    "Режим": "Mode",
    "Слияние вершин и вставка узлов (полная сшивка)":
        "Merge vertices and insert nodes (full snap)",
    "Только вставка узлов (вершины не двигаются)":
        "Insert nodes only (vertices do not move)",
    "Только слияние вершин": "Merge vertices only",
    "Если сшивка испортила геометрию": "If snapping broke the geometry",
    "Исправить, а если не выходит, вернуть исходную геометрию":
        "Repair, and if that fails restore the original geometry",
    "Вернуть исходную геометрию объекта": "Restore the original geometry",
    "Оставить как есть": "Leave as is",

    # Параметры сборки
    "Максимальный разрыв внутри тела (в единицах CRS)":
        "Maximum gap within one body (in CRS units)",
    "Внутренние кольца допустимы": "Interior rings are acceptable",
    "Находки сборки": "Assembly findings",

    # Параметры вставки узлов
    "Допустимое отклонение вершины от ребра":
        "Allowed vertex deviation from the edge",
    "Вставленные узлы (необязательно)": "Inserted nodes (optional)",
    "Слой с узлами": "Layer with nodes",

    # Параметры упрощения
    "Допуск упрощения (в единицах CRS слоя)":
        "Simplification tolerance (in layer CRS units)",
    "Не упрощать дуги короче, вершин": "Do not simplify arcs shorter than, vertices",
    "Точность опознания общих вершин": "Precision for matching shared vertices",
    "Упрощённый слой": "Simplified layer",

    # Выходные слои
    "Сшитый слой": "Snapped layer",
    "Очищенный слой": "Cleaned layer",
    "Оставшиеся проблемы": "Remaining problems",
    "Точки правок (необязательно)": "Edit points (optional)",

    # Типы нарушений
    "некорректная геометрия": "invalid geometry",
    "самокасание кольца": "ring self-touch",
    "повторяющиеся вершины": "repeated vertices",
    "игла": "spike",
    "вершина рядом с ребром соседа": "vertex near a neighbour edge",
    "вершина лежит на ребре соседа без узла":
        "vertex lies on a neighbour edge without a node",
    "микродыра": "tiny hole",
    "микрочасть": "tiny part",
    "микрообъект": "tiny object",
    "волосяной полигон": "sliver polygon",
    "перекрытие": "overlap",
    "щель в покрытии": "gap in the coverage",
    "дубликат объекта": "duplicate object",
    "объект внутри другого": "object inside another",
    "объект потерян при исправлении": "object lost during repair",
    "группа распалась на части": "group split into parts",
    "внутреннее кольцо в группе": "interior ring within a group",

    # Отчёты
    "Чтение слоя...": "Reading the layer...",
    "── Результат ──": "-- Result --",
    "── Топология ──": "-- Topology --",
    "── Исправлено молча ──": "-- Fixed silently --",
    "── Оставлено человеку ──": "-- Left to the operator --",
    "Нарушений не найдено.": "No violations found.",
    "Дефектов сборки не найдено.": "No assembly defects found.",
    "нарушение": "violation",
    "чинится": "auto-fixed",
    "решать": "to decide",
    "медиана": "median",
    "максимум": "maximum",
    "группа": "group",
    "тел": "bodies",
    "разрыв": "split",
    "колец": "rings",
    "площадь": "area",

    # Отчёты в панели Processing
    "  возвращено к исходным:    %d": "  restored to original:     %d",
    "  из них исправлено:        %d": "  of which repaired:        %d",
    "... и ещё %d групп, см. слой находок":
        "... and %d more groups, see the findings layer",
    "Вершин было/стало:    %d / %d": "Vertices before/after: %d / %d",
    "Вершин было/стало: %d / %d (%.1f %%)":
        "Vertices before/after: %d / %d (%.1f %%)",
    "Вершин сведено:              %d (макс. смещение %.4f)":
        "Vertices merged:             %d (max shift %.4f)",
    "Вершин сдвинуто:      %d": "Vertices moved:       %d",
    "Всего находок: %d, из них чинится автоматически: %d, решать человеку: %d":
        "Findings in total: %d, auto-fixed: %d, left to the operator: %d",
    "Вырожденных колец: %d": "Degenerate rings: %d",
    "Геометрий исправлено:        %d": "Geometries repaired:         %d",
    "Групп: %d, без дефектов сборки: %d":
        "Groups: %d, without assembly defects: %d",
    "Группировка по %s: групп %d": "Grouped by %s: %d groups",
    "Дефектов сборки не найдено.": "No assembly defects found.",
    "Дуг: %d, из них общих для соседей: %d":
        "Arcs: %d, of which shared by neighbours: %d",
    "Игл снято:                   %d": "Spikes removed:              %d",
    "Исправлений отменено из-за потери площади: %d":
        "Repairs cancelled due to area loss: %d",
    "Колец %d, вершин %d, отклонение %g": "Rings %d, vertices %d, deviation %g",
    "Колец не изменялось:         %d (уже допуска)":
        "Rings left unchanged:        %d (narrower than the tolerance)",
    "Колец не изменялось:  %d (уже допуска)":
        "Rings left unchanged: %d (narrower than the tolerance)",
    "Микродыр залито:             %d": "Tiny holes filled:           %d",
    "Микрообъектов удалено:       %d": "Tiny objects deleted:        %d",
    "Микрочастей удалено:         %d": "Tiny parts removed:          %d",
    "Нарушений не найдено.": "No violations found.",
    "Объектов без геометрии пропущено: %d":
        "Objects without geometry skipped: %d",
    "Объектов записано:    %d": "Objects written:      %d",
    "Объектов изменено:    %d": "Objects changed:      %d",
    "Объектов испорчено сшивкой: %d": "Objects broken by snapping: %d",
    "Объектов исчезло: %d, см. слой оставшихся проблем":
        "Objects disappeared: %d, see the remaining problems layer",
    "Объектов на входе/выходе: %d / %d": "Objects in/out: %d / %d",
    "Объектов потеряно целиком: %d": "Objects lost entirely: %d",
    "Объектов потеряно: %d. Этого быть не должно.":
        "Objects lost: %d. This should not happen.",
    "Объектов: %d, допуск %g, порог площади %g":
        "Objects: %d, tolerance %g, area threshold %g",
    "Опорный слой: колец %d": "Donor layer: %d rings",
    "Перекрытий убрано:           %d": "Overlaps removed:            %d",
    "Площадь до/после:     %.6f / %.6f": "Area before/after:    %.6f / %.6f",
    "Площадь до/после: %.3f / %.3f (%+.6f %%)":
        "Area before/after: %.3f / %.3f (%+.6f %%)",
    "Площадь не изменилась ни на единицу.":
        "The area did not change by a single unit.",
    "Повторяющихся вершин снято:  %d": "Repeated vertices removed:   %d",
    "Проход %d: узлов %d": "Pass %d: %d nodes",
    "Проходов до полного согласования: %d": "Passes until full agreement: %d",
    "Узлов вставлено:             %d": "Nodes inserted:              %d",
    "Узлов вставлено:      %d (из них в пересечениях рёбер: %d)":
        "Nodes inserted:       %d (of which at edge intersections: %d)",
    "Чтение слоя...": "Reading the layer...",
    "Щелей заполнено:             %d": "Gaps filled:                 %d",
    "Эталон: колец %d": "Reference layer: %d rings",
    "── Исправлено молча ──": "-- Fixed silently --",
    "── Оставлено человеку ──": "-- Left to the operator --",
    "── Результат ──": "-- Result --",
    "── Сборка по %s ──": "-- Assembly by %s --",
    "── Топология ──": "-- Topology --",

    # Длинные строки отчётов и предупреждения
    "  идентификаторы: %s%s":
        "  identifiers: %s%s",
    "Вырожденных колец удалено: %d (допуск больше размера объекта)":
        "Degenerate rings removed: %d (the tolerance exceeds the object size)",
    "Групп из нескольких отдельных тел: %d (разрыв больше заданного порога, нарушением не считается)":
        "Groups made of several separate bodies: %d (the gap exceeds the given threshold and is not a violation)",
    "Групп с дефектами сборки: %d. Смотрите поле note: там расстояние, которого не хватило допуску. Если разрывы измеряются сотнями метров, значит группы не обязаны быть цельными и нужно задать максимальный разрыв.":
        "Groups with assembly defects: %d. See the note field: it holds the distance the tolerance was missing. If the gaps are hundreds of metres, the groups need not be whole and a maximum gap should be set.",
    "Длина ребра: медиана %.4f, пятый процентиль %.4f (рёбер %d)":
        "Edge length: median %.4f, fifth percentile %.4f (%d edges)",
    "Допуск больше пяти процентов самых коротких рёбер (%.4f), мелкие изгибы будут сглажены.":
        "The tolerance exceeds the fifth percentile of edge length (%.4f), small bends will be smoothed out.",
    "Достигнут предел числа проходов. Возможно, узлы ещё нужны: запустите инструмент повторно по результату.":
        "The pass limit has been reached. More nodes may still be needed: run the tool again over the result.",
    "Колец уже допуска: %d. Они оставлены без изменений и служат опорой для соседей.":
        "Rings narrower than the tolerance: %d. They are left unchanged and serve as an anchor for their neighbours.",
    "Колец уже допуска: %d. У такого кольца противоположные берега слипнутся, и оно схлопнется само в себя. Включите защиту узких объектов либо возьмите допуск меньше %.4f.":
        "Rings narrower than the tolerance: %d. The opposite banks of such a ring would stick together and it would collapse into itself. Enable the protection of narrow objects or use a tolerance below %.4f.",
    "Некорректных геометрий до/после: %d / %d":
        "Invalid geometries before/after: %d / %d",
    "Некорректных геометрий: %d. Уменьшите допуск.":
        "Invalid geometries: %d. Reduce the tolerance.",
    "Некорректных стало больше. Уменьшите допуск: ориентир это пятый процентиль длины ребра, он напечатан выше.":
        "The number of invalid geometries has grown. Reduce the tolerance: the fifth percentile of edge length printed above is a good reference.",
    "Общих границ не найдено. Если объекты соприкасаются, увеличьте точность опознания общих вершин.":
        "No shared borders were found. If the objects do touch, increase the precision for matching shared vertices.",
    "Объектов возвращено к исходному виду: %d. Вставка узла вывернула их геометрию, узлы для них не добавлены. Идентификаторы: %s%s":
        "Objects restored to their original form: %d. Node insertion turned their geometry inside out, so no nodes were added for them. Identifiers: %s%s",
    "Объектов потеряно: %d. Допуск больше размера объекта.":
        "Objects lost: %d. The tolerance exceeds the object size.",
    "Объектов с самокасанием колец: %d. GEOS считает такую геометрию корректной, а SQL Server может её отклонить. При заливке в MSSQL применяйте MakeValid на стороне сервера.":
        "Objects with ring self-touches: %d. GEOS considers such geometry valid while SQL Server may reject it. When loading into MSSQL apply MakeValid on the server side.",
    "Площадь до/после:     %.3f / %.3f (%+.5f, %+.6f %%)":
        "Area before/after:    %.3f / %.3f (%+.5f, %+.6f %%)",
    "Площадь изменилась на %.6f. Инструмент обещает не менять её вовсе, поэтому проверьте отклонение от ребра: скорее всего оно завышено.":
        "The area changed by %.6f. The tool promises not to change it at all, so check the deviation from the edge: it is most likely too large.",
    "Расхождение площади %.3e, это ошибка округления.":
        "Area discrepancy %.3e, this is a rounding error.",
    "Смещение макс/сред:   %.4f / %.4f":
        "Shift max/mean:       %.4f / %.4f",
    "Совпадающих вершин снято: %d (точные дубликаты, на форму не влияют)":
        "Coincident vertices removed: %d (exact duplicates, they do not affect the shape)",
    "Суммарная площадь изменилась более чем на процент. Проверьте пороги: скорее всего порог площади завышен.":
        "The total area changed by more than one per cent. Check the thresholds: the area threshold is most likely too high.",
    "Сшивка: колец %d, вершин %d, допуск %g":
        "Snapping: %d rings, %d vertices, tolerance %g",
    "Чтобы понять природу, запустите ещё раз со снятой галочкой об узлах в пересечениях рёбер. Если откаты исчезнут, дело в пересечениях, если останутся, в самих вершинах на рёбрах.":
        "To understand the cause, run again with the edge intersection nodes option turned off. If the rollbacks disappear, the intersections are to blame; if they remain, the vertices on edges are.",
    "Ширина колец: минимум %.4f, медиана %.4f":
        "Ring width: minimum %.4f, median %.4f",
    "GEOS считает геометрию некорректной, подробностей нет":
        "GEOS considers the geometry invalid, no details available",
    "Сглаживание, число проходов (0 - без сглаживания)":
        "Smoothing, number of passes (0 - no smoothing)",
    "Сглаживание: проходов %d": "Smoothing: %d passes",
    "Длина до/после: %.3f / %.3f (%+.6f %%)":
        "Length before/after: %.3f / %.3f (%+.6f %%)",

    # Линейные инструменты
    "1.02 Проверка топологии линий": "1.02 Line topology check",
    "1.04 Очистка топологии линий": "1.04 Line topology cleanup",
    "── Топология линий ──": "-- Line topology --",
    "Проверяемый слой (линии)": "Layer to check (lines)",
    "Входной слой (линии)": "Input layer (lines)",
    "Порог длины линии (0 - не учитывать)":
        "Line length threshold (0 - ignore)",
    "Искать висячие концы, недоводы и перелёты":
        "Find dangles, undershoots and overshoots",
    "Искать пересечения без узла": "Find crossings without a node",
    "Искать псевдоузлы": "Find pseudo nodes",
    "Обрезать перелёты за узел": "Trim overshoots past a node",
    "Дотягивать недоводы до соседней линии":
        "Close undershoots onto the neighbouring line",
    "Вставлять недостающие узлы": "Insert missing nodes",
    "Удалять линии короче порога длины":
        "Delete lines shorter than the length threshold",
    "Линий: %d, допуск %g": "Lines: %d, tolerance %g",
    "── Топология линий ──": "-- Line topology --",
    "Перелётов обрезано:          %d": "Overshoots trimmed:          %d",
    "Недоводов закрыто:           %d (макс. смещение %.4f)":
        "Undershoots closed:          %d (max shift %.4f)",
    "Линий нулевой длины удалено: %d": "Zero-length lines removed:   %d",
    "Коротких линий удалено:      %d": "Short lines removed:         %d",
    "Объектов потеряно: %d": "Objects lost: %d",
    "висячий конец": "dangle",
    "недовод до соседней линии": "undershoot to the neighbouring line",
    "перелёт за узел": "overshoot past a node",
    "псевдоузел": "pseudo node",
    "пересечение без узла": "crossing without a node",
    "линия нулевой длины": "zero-length line",
    "линия короче порога": "line shorter than the threshold",
    "Слой (полигоны или линии)": "Layer (polygons or lines)",
    "длина": "length",

    # Пояснения к находкам
    "все вершины в одной точке": "all vertices at the same point",
    "в линии меньше двух вершин": "fewer than two vertices in the line",
    "вершины совпадают, атрибуты могут различаться":
        "the vertices coincide, the attributes may differ",
    "геометрии совпадают, атрибуты могут различаться":
        "the geometries coincide, the attributes may differ",
    "линии пересекаются, узла в точке нет":
        "the lines cross, there is no node at the point",
    "конец ни с чем не соединён, соседей ближе допуска нет":
        "the end is connected to nothing, no neighbour within the tolerance",
    "один объект целиком внутри другого":
        "one object entirely inside another",
    "кольцо проходит через точку дважды":
        "the ring passes through the point twice",
    "границы совпадают геометрически, узла нет":
        "the borders coincide geometrically, there is no node",
    "перекрытие шире допуска, спор за площадь":
        "the overlap is wider than the tolerance, a dispute over area",
    "полоса шириной меньше допуска": "a strip narrower than the tolerance",
    "две линии можно объединить в одну":
        "the two lines can be merged into one",

    # Пояснения с измеренными величинами
    "вершин подряд в одной точке: %d":
        "vertices in a row at the same point: %d",
    "вычитание съедало слишком много площади":
        "the subtraction was taking too much area",
    "длина %.4f при пороге %.4f": "length %.4f against the threshold %.4f",
    "дыра в объединении покрытия площадью %.4f":
        "a hole in the union of the coverage, area %.4f",
    "дыра площадью %.4f при пороге %.4f":
        "a hole of area %.4f against the threshold %.4f",
    "линия короче порога, удаление не выполнялось":
        "the line is shorter than the threshold, no deletion was performed",
    "не доходит до соседней линии на %.4f":
        "falls short of the neighbouring line by %.4f",
    "объект исчез при исправлении": "the object disappeared during repair",
    "объект мельче порога, удаление не выполнялось":
        "the object is smaller than the threshold, no deletion was performed",
    "перекрытие шире допуска, это спор за площадь":
        "the overlap is wider than the tolerance, a dispute over area",
    "площадь %.4f при пороге %.4f": "area %.4f against the threshold %.4f",
    "полость внутри группы площадью %.4f":
        "a cavity inside the group, area %.4f",
    "пустая геометрия": "empty geometry",
    "разворотов границы назад: %d": "border turns back on itself: %d",
    "разворотов линии назад: %d": "line turns back on itself: %d",
    "разрыв до ближайшей части %.4f": "gap to the nearest part %.4f",
    "совпадение или вложение решается человеком":
        "coincidence or nesting is decided by the operator",
    "сосед не найден": "no neighbour found",
    "сшивка испортила объект, исправление не помогло, возвращена исходная геометрия":
        "snapping broke the object, the repair did not help, the original geometry was restored",
    "хвост за узлом длиной %.4f": "a tail past a node, length %.4f",
    "часть площадью %.4f из %d": "a part of area %.4f out of %d",
    "щель крупнее порога, не заполнялась":
        "the gap is larger than the threshold, it was not filled",
    "эффективная ширина меньше допуска":
        "the effective width is below the tolerance",
    "вершина в %.4f от ребра соседа": "vertex %.4f away from a neighbour edge",

    # Извлечение границ
    "2.02 Границы полигонов линиями": "2.02 Polygon borders as lines",
    "Поле, значения которого записать по обе стороны":
        "Field whose values to record on both sides",
    "Отклонение при поиске общих вершин":
        "Deviation when matching shared vertices",
    "Границы": "Borders",
    "граница между объектами": "border between objects",
    "внешний край покрытия": "outer edge of the coverage",
    "край полости": "edge of a cavity",
    "Объектов: %d": "Objects: %d",
    "Границ между объектами: %d": "Borders between objects: %d",
    "Внешний край покрытия:  %d": "Outer edge of the coverage: %d",
    "Краёв полостей:         %d": "Cavity edges:              %d",
    "Всего линий:            %d": "Lines in total:            %d",
    "Метод прореживания": "Thinning method",
    "Дуглас-Пекер (по отклонению)": "Douglas-Peucker (by deviation)",
    "Висвалингам (по площади)": "Visvalingam (by area)",
    "Метод: Дуглас-Пекер": "Method: Douglas-Peucker",
    "Метод: Висвалингам": "Method: Visvalingam",

    # Отчёт вставки узлов
    "Предельное число проходов":
        "Maximum number of passes",
    "Узлов вставлено всего: %d":
        "Nodes inserted in total: %d",
    "  на рёбрах соседей:   %d":
        "  on neighbour edges:    %d",
    "  в пересечениях рёбер: %d":
        "  at edge intersections: %d",
    "Проходов: %d":
        "Passes: %d",
    "Предел числа проходов достигнут, узлы могут быть ещё нужны. На согласованном покрытии хватает двух-трёх проходов. Запустите инструмент повторно по результату либо поднимите предел.":
        "The pass limit has been reached and more nodes may still be needed. Two or three passes are enough for a consistent coverage. Run the tool again over the result or raise the limit.",
    "Больше половины узлов пришлось на пересечения рёбер. Это признак того, что объекты слоя накладываются друг на друга, то есть слой не является единым покрытием. Посмотрите перекрытия инструментом 1.01. Если наложение входит в замысел, снимите галочку об узлах в пересечениях: тогда инструмент достроит только недостающие общие вершины.":
        "More than half of the nodes fell on edge intersections. This means the objects of the layer overlap each other, that is the layer is not a single coverage. Look at the overlaps with tool 1.01. If the overlap is by design, clear the edge intersection option: the tool will then only add the missing shared vertices.",
    "Вершин добавлено больше половины от исходного числа. Проверьте, то ли это, чего вы ждали.":
        "More than half as many vertices were added as there were to begin with. Check that this is what you expected.",

    # Отчёт вставки узлов,
    "Пересечений пропущено как неустойчивые: %d":
        "Crossings skipped as unstable: %d",
}
