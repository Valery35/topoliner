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
        # locale.getdefaultlocale объявлен устаревшим и выдаёт предупреждение
        # Python. Само по себе оно безобидно, но обработчик предупреждений
        # QGIS, вызванный из фонового потока Processing, роняет программу
        # с нарушением доступа. Поэтому берём язык из переменных окружения
        # напрямую, как это делает сама библиотека.
        import os
        for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
            found = os.environ.get(name)
            if found:
                value = found.split(":")[0].split(".")[0]
                break

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
    "1.08 Ввод контуров в покрытие": "1.08 Contours into a coverage",
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
    "Вершин сведено:              %d (макс. смещение %s)":
        "Vertices merged:             %d (max shift %s)",
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
    "Площадь до/после: %s / %s (%+.3f %%)":
        "Area before/after: %s / %s (%+.3f %%)",
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
    "Групп с дефектами сборки: %d. Смотрите поле note. Там стоит расстояние, которого не хватило допуску. Если разрывы измеряются сотнями метров, значит группы не обязаны быть цельными и нужно задать максимальный разрыв.":
        "Groups with assembly defects: %d. See the note field. It holds the distance the tolerance was missing. If the gaps are hundreds of metres, the groups need not be whole and a maximum gap should be set.",
    "Длина ребра: медиана %s, пятый процентиль %s (рёбер %d)":
        "Edge length: median %s, fifth percentile %s (%d edges)",
    "Допуск больше пяти процентов самых коротких рёбер (%s), мелкие изгибы будут сглажены.":
        "The tolerance exceeds the fifth percentile of edge length (%s), small bends will be smoothed out.",
    "Достигнут предел количества проходов. Возможно, узлы ещё нужны, запустите инструмент повторно по результату.":
        "The pass limit has been reached. More nodes may still be needed, run the tool again over the result.",
    "Колец уже допуска: %d. Они оставлены без изменений и служат опорой для соседей.":
        "Rings narrower than the tolerance: %d. They are left unchanged and serve as an anchor for their neighbours.",
    "Колец уже допуска: %d. У такого кольца противоположные берега слипнутся, и оно схлопнется само в себя. Включите защиту узких объектов либо возьмите допуск меньше %s.":
        "Rings narrower than the tolerance: %d. The opposite banks of such a ring would stick together and it would collapse into itself. Enable the protection of narrow objects or use a tolerance below %s.",
    "Некорректных геометрий до/после: %d / %d":
        "Invalid geometries before/after: %d / %d",
    "Некорректных геометрий: %d. Уменьшите допуск.":
        "Invalid geometries: %d. Reduce the tolerance.",
    "Некорректных стало больше. Уменьшите допуск. Ориентир это пятый процентиль длины ребра, он напечатан выше.":
        "The number of invalid geometries has grown. Reduce the tolerance. The fifth percentile of edge length printed above is a good reference.",
    "Общих границ не найдено. Если объекты соприкасаются, увеличьте точность опознания общих вершин.":
        "No shared borders were found. If the objects do touch, increase the precision for matching shared vertices.",
    "Объектов возвращено к исходному виду: %d. Вставка узла вывернула их геометрию, узлы для них не добавлены. Идентификаторы: %s%s":
        "Objects restored to their original form: %d. Node insertion turned their geometry inside out, so no nodes were added for them. Identifiers: %s%s",
    "Объектов потеряно: %d. Допуск больше размера объекта.":
        "Objects lost: %d. The tolerance exceeds the object size.",
    "Объектов с самокасанием колец: %d. GEOS считает такую геометрию корректной, а SQL Server может её отклонить. При заливке в MSSQL применяйте MakeValid на стороне сервера.":
        "Objects with ring self-touches: %d. GEOS considers such geometry valid while SQL Server may reject it. When loading into MSSQL apply MakeValid on the server side.",
    "Площадь до/после:     %s / %s (%s, %+.3f %%)":
        "Area before/after:    %s / %s (%s, %+.3f %%)",
    "Площадь изменилась на %s. Инструмент обещает не менять её вовсе, поэтому проверьте отклонение от ребра. Скорее всего оно завышено.":
        "The area changed by %s. The tool promises not to change it at all, so check the deviation from the edge. It is most likely too large.",
    "Расхождение площади %.3e, это ошибка округления.":
        "Area discrepancy %.3e, this is a rounding error.",
    "Смещение макс/сред:   %s / %s":
        "Shift max/mean:       %s / %s",
    "Совпадающих вершин снято: %d (точные дубликаты, на форму не влияют)":
        "Coincident vertices removed: %d (exact duplicates, they do not affect the shape)",
    "Суммарная площадь изменилась более чем на процент. Проверьте пороги. Скорее всего порог площади завышен.":
        "The total area changed by more than one per cent. Check the thresholds. The area threshold is most likely too high.",
    "Сшивка: колец %d, вершин %d, допуск %g":
        "Snapping: %d rings, %d vertices, tolerance %g",
    "Чтобы понять природу, запустите ещё раз со снятой галочкой об узлах в пересечениях рёбер. Если откаты исчезнут, дело в пересечениях, если останутся, в самих вершинах на рёбрах.":
        "To understand the cause, run again with the edge intersection nodes option turned off. If the rollbacks disappear, the intersections are to blame; if they remain, the vertices on edges are.",
    "Ширина колец: минимум %s, медиана %s":
        "Ring width: minimum %s, median %s",
    "GEOS считает геометрию некорректной, подробностей нет":
        "GEOS considers the geometry invalid, no details available",
    "Сглаживание, количество проходов (0 - без сглаживания)":
        "Smoothing, number of passes (0 - no smoothing)",
    "Сглаживание: проходов %d": "Smoothing: %d passes",
    "Длина до/после: %s / %s (%+.3f %%)":
        "Length before/after: %s / %s (%+.3f %%)",

    # Линейные инструменты
    "1.02 Проверка топологии линий": "1.02 Line topology check",
    "1.04 Очистка топологии линий": "1.04 Line topology cleanup",
    "── Топология линий ──": "-- Line topology --",
    "Проверяемый слой (линии)": "Layer to check (lines)",
    "Входной слой (линии)": "Input layer (lines)",
    # Панель «Покрытие»
    "Покрытие": "Coverage",
    "Слой покрытия": "Coverage layer",
    "Таблица классов": "Table of classes",
    "нет таблицы": "no table",
    "Поле": "Field",
    "Поле класса не выбрано.": "No class field is selected.",
    "Подпись": "Label",
    "Заполняются поля: %s": "Fields filled: %s",
    "Таблица классов не выбрана. Новый объект возьмёт атрибуты у соседей.":
        "No table of classes is selected. The new feature will take its "
        "attributes from the neighbours.",
    "Совпадающих полей у таблицы и слоя нет. Класс записать некуда.":
        "The table and the layer share no field names. There is nowhere to "
        "write the class.",
    "Автозаполнять при создании": "Fill in on creation",
    "Флажок снят, и после отрисовки открывается обычная форма атрибутов слоя.":
        "With the box cleared, the usual attribute form of the layer opens "
        "once the contour is drawn.",
    "Применить к выделенным объектам": "Apply to the selected features",
    "Класс выделенным объектам": "Class for the selected features",
    "Класс не выбран.": "No class is selected.",
    "Не выделено ни одного объекта.": "Not a single feature is selected.",
    "Класс записан объектам: %d": "The class was written to features: %d",
    "Режим наложения": "Overlay mode",
    "Наложение": "Overlay",
    "Отсечение": "Clipping",
    "Новый объект получает весь контур, соседи урезаются.":
        "The new feature gets the whole contour, the neighbours are trimmed.",
    "Новый объект ложится только в свободное место, соседи площади не теряют.":
        "The new feature lies in free space only, the neighbours lose no area.",
    "Новый объект получает только то, что лежит внутри покрытия. Площадь покрытия не меняется.":
        "The new feature gets only what lies inside the coverage. The area of "
        "the coverage does not change.",
    "Включает правку слоя и штатное добавление полигона. Каждый добавленный полигон сразу обрабатывается по выбранному режиму.":
        "Starts editing the layer and the standard Add Polygon tool. Every "
        "polygon added is processed at once by the chosen mode.",
    "В этом режиме контуру не досталось площади, объект убран.":
        "In this mode the contour got no area, the feature was removed.",
    "Режим рисования: ВКЛ": "Drawing mode: ON",
    "Режим рисования: ВЫКЛ": "Drawing mode: OFF",
    "Сглаживать линии": "Smooth the lines",
    "Тот же переключатель стоит на клавише S во время рисования.":
        "The same switch sits on the S key while drawing.",
    "Панель ввода нарисованных контуров в покрытие":
        "The panel that puts drawn contours into a coverage",
    "Ввод контура": "Putting a contour in",
    "Нужен слой полигонов.": "A polygon layer is needed.",
    "Отменено.": "Cancelled.",
    "Одиннадцать инструментов стоят в панели Processing, в группах «1. Топология» и «2. Генерализация». Они работают в моделях и в пакетном режиме.":
        "Eleven tools stand in the Processing panel, in the groups "
        "\"1. Topology\" and \"2. Generalisation\". They work in models and "
        "in batch mode.",

    # Кнопка врезки и окна плагина
    "Врезка": "Cutting in",
    "Контуру нужно не меньше трёх вершин.":
        "The contour needs at least three vertices.",
    "Изменено %d, добавлено %d, удалено %d, узлов вставлено %d":
        "Changed %d, added %d, deleted %d, nodes inserted %d",
    "Нарисовать контур и врезать его в активный слой":
        "Draw a contour and cut it into the active layer",
    "Параметры врезки": "Cutting parameters",
    "О модуле": "About",
    "О модуле Topoliner": "About Topoliner",
    "Руководство": "Manual",
    "Порог площади": "Area threshold",
    "Отклонение вершины от ребра": "Deviation of a vertex from an edge",
    "Остаток соседа мельче этой площади отходит контуру целиком. Кусок соседа мельче этой площади контуру не достаётся.":
        "A remainder of a neighbour smaller than this area goes to the contour "
        "whole. A piece of a neighbour smaller than this area does not reach "
        "the contour.",
    "Разрез кладёт вершину на границу соседа с третьим объектом. Узел в этой точке достраивается. Ноль отключает вставку.":
        "The cut puts a vertex on the border of a neighbour with a third "
        "feature. A node is added at that point. Zero switches the insertion "
        "off.",
    "Отметка вершины берётся с ближайшего исходного ребра.":
        "The value of a vertex is taken from the nearest source edge.",
    "Топология полигональных и линейных покрытий. Инструменты находят нарушения и отделяют технический мусор от того, что может нести смысл. Мусор исправляется в новый слой.":
        "Topology of polygon and line coverages. The tools find violations and "
        "separate certain debris from what may carry meaning. The debris is "
        "repaired into a new layer.",
    "Одиннадцать инструментов стоят в панели Processing, в группах «1. Топология» и «2. Генерализация». Врезка контура работает кнопкой, прямо в режиме редактирования.":
        "Eleven tools stand in the Processing panel, in the groups "
        "\"1. Topology\" and \"2. Generalisation\". Cutting a contour in works "
        "from a button, right in edit mode.",
    "Исходный слой не изменяется никогда. Автоматика не решает, чья граница верна, она смотрит только на масштаб расхождения.":
        "The input layer is never changed. The automatic part does not decide "
        "whose border is right, it looks only at the scale of the discrepancy.",
    "Лицензия GPL 3. Развивается на задачах реальных предприятий: %s":
        "Licence GPL 3. Grown on the tasks of real enterprises: %s",
    "Страница плагина": "Plugin page",
    "Isoliner, кригинг и изолинии": "Isoliner, kriging and contouring",
    "Isoliner3D, просмотр поверхностей и тел":
        "Isoliner3D, viewer for surfaces and bodies",
    "Поддержать разработку": "Support development",

    # Врезка контуров, 1.08
    "Врезка контура": "Cutting a contour in",
    "Слой не выбран.": "No layer is selected.",
    "Врезка работает только по слою полигонов.":
        "Cutting in works on a polygon layer only.",
    "Слой не в режиме редактирования.": "The layer is not in edit mode.",
    "Контур пуст.": "The contour is empty.",
    "Контур не даёт ни одного кольца.": "The contour yields no ring at all.",
    "Контур ничего не изменил.": "The contour changed nothing.",
    "Покрытие (полигоны)": "Coverage (polygons)",
    "Контуры (полигоны)": "Contours (polygons)",
    "Порог площади (в кв. единицах CRS)": "Area threshold (in square CRS units)",
    "Покрытие с контурами": "Coverage with the contours",
    "Объектов %d, контуров %d, порог площади %g":
        "Objects %d, contours %d, area threshold %g",
    "Контур %d: соседей затронуто %d, вне покрытия %s":
        "Contour %d: neighbours touched %d, outside the coverage %s",
    "Контуров врезано:            %d": "Contours cut in:              %d",
    "Объектов изменено:           %d": "Objects changed:              %d",
    "Объектов поглощено целиком:  %d": "Objects absorbed whole:       %d",
    "Объектов добавлено:          %d": "Objects added:                %d",
    "Узлов вставлено соседям:     %d": "Nodes inserted for neighbours: %d",
    "Площадь до/после: %s / %s": "Area before/after: %s / %s",
    "Легло вне покрытия: %s": "Fell outside the coverage: %s",
    "Режим наложения: %s": "Overlay mode: %s",
    "Отброшено за краем покрытия: %s": "Dropped beyond the coverage edge: %s",
    "Расхождение площади: %s. Врезка обязана площадь только перераспределять.":
        "Area discrepancy: %s. Cutting in must only redistribute the area.",
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
    "Недоводов закрыто:           %d (макс. смещение %s)":
        "Undershoots closed:          %d (max shift %s)",
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
    "длина %s при пороге %s": "length %s against the threshold %s",
    "дыра в объединении покрытия площадью %s":
        "a hole in the union of the coverage, area %s",
    "дыра площадью %s при пороге %s":
        "a hole of area %s against the threshold %s",
    "линия короче порога, удаление не выполнялось":
        "the line is shorter than the threshold, no deletion was performed",
    "не доходит до соседней линии на %s":
        "falls short of the neighbouring line by %s",
    "объект исчез при исправлении": "the object disappeared during repair",
    "объект мельче порога, удаление не выполнялось":
        "the object is smaller than the threshold, no deletion was performed",
    "перекрытие шире допуска, это спор за площадь":
        "the overlap is wider than the tolerance, a dispute over area",
    "площадь %s при пороге %s": "area %s against the threshold %s",
    "полость внутри группы площадью %s":
        "a cavity inside the group, area %s",
    "пустая геометрия": "empty geometry",
    "разворотов границы назад: %d": "border turns back on itself: %d",
    "разворотов линии назад: %d": "line turns back on itself: %d",
    "разрыв до ближайшей части %s": "gap to the nearest part %s",
    "совпадение или вложение решается человеком":
        "coincidence or nesting is decided by the operator",
    "сосед не найден": "no neighbour found",
    "сшивка испортила объект, исправление не помогло, возвращена исходная геометрия":
        "snapping broke the object, the repair did not help, the original geometry was restored",
    "хвост за узлом длиной %s": "a tail past a node, length %s",
    "часть площадью %s из %d": "a part of area %s out of %d",
    "щель крупнее порога, не заполнялась":
        "the gap is larger than the threshold, it was not filled",
    "эффективная ширина меньше допуска":
        "the effective width is below the tolerance",
    "вершина в %s от ребра соседа": "vertex %s away from a neighbour edge",

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
    "Предельное количество проходов":
        "Maximum number of passes",
    "Узлов вставлено всего: %d":
        "Nodes inserted in total: %d",
    "  на рёбрах соседей:   %d":
        "  on neighbour edges:    %d",
    "  в пересечениях рёбер: %d":
        "  at edge intersections: %d",
    "Проходов: %d":
        "Passes: %d",
    "Предел количества проходов достигнут, узлы могут быть ещё нужны. На согласованном покрытии хватает двух-трёх проходов. Запустите инструмент повторно по результату либо поднимите предел.":
        "The pass limit has been reached and more nodes may still be needed. Two or three passes are enough for a consistent coverage. Run the tool again over the result or raise the limit.",
    "Больше половины узлов пришлось на пересечения рёбер. Это признак того, что объекты слоя накладываются друг на друга, то есть слой не является единым покрытием. Посмотрите перекрытия инструментом 1.01. Если наложение входит в замысел, снимите галочку об узлах в пересечениях. Тогда инструмент достроит только недостающие общие вершины.":
        "More than half of the nodes fell on edge intersections. This means the objects of the layer overlap each other, that is the layer is not a single coverage. Look at the overlaps with tool 1.01. If the overlap is by design, clear the edge intersection option. The tool will then only add the missing shared vertices.",
    "Вершин добавлено больше половины от исходного количества. Проверьте, соответствует ли это ожидаемому.":
        "More than half as many vertices were added as there were to begin with. Check that this matches what you expected.",

    # Отчёт вставки узлов,
    "Пересечений пропущено как неустойчивые: %d":
        "Crossings skipped as unstable: %d",

    # Подсказка по допуску
    "── Расхождения вершин с рёбрами соседей ──":
        "-- Discrepancies between vertices and neighbour edges --",
    "Найдено: %d, медиана %s, 95 процентиль %s, максимум %s":
        "Found: %d, median %s, 95th percentile %s, maximum %s",
    "Пятый процентиль длины ребра: %s":
        "Fifth percentile of edge length: %s",
    "Минимальная ширина объекта: %s":
        "Minimum object width: %s",
    "Допуск для этого слоя разумно взять около %.4f":
        "A sensible tolerance for this layer is around %.4f",
    "Медиана расхождений близка к заданному допуску. Дальше него проверка не смотрит, поэтому распределение обрезано и настоящие расхождения крупнее. Повторите с допуском покрупнее, чтобы увидеть картину целиком.":
        "The median discrepancy is close to the tolerance given. The check does not look beyond it, so the distribution is truncated and the real discrepancies are larger. Repeat with a larger tolerance to see the whole picture.",

    "В распределении есть разрыв около %s. До него погрешность оцифровки, за ним разногласие между источниками. Допуск разумно взять чуть больше этой величины.":
        "There is a break in the distribution around %s. Below it lies digitising error, above it a disagreement between sources. A sensible tolerance is slightly above that value.",
    "Разрыва в распределении нет. Расхождения идут сплошь, и естественной границы между погрешностью и разногласием в этих данных не видно. Выбор допуска остаётся за вами.":
        "There is no break in the distribution. The discrepancies run continuously, and no natural boundary between error and disagreement is visible in this data. The choice of tolerance is yours.",
    "Выше %s допуск брать не следует. Он схлопнет короткие рёбра и узкие объекты.":
        "The tolerance should not exceed %s. It would collapse short edges and narrow objects.",
    "Отчёт списком": "Report as a list",
    "Отчёт записан: %s": "Report written: %s",
    "Topoliner. Проверка топологии слоя %s":
        "Topoliner. Topology check of layer %s",

    # Топологическая модель
    "2.03 Топологическая модель покрытия": "2.03 Coverage topology model",
    "Узлы": "Nodes",
    "Дуги": "Arcs",
    "висячий": "dangle",
    "ветвление": "junction",
    "Узлов: %d, дуг: %d": "Nodes: %d, arcs: %d",
    "Дуг между двумя объектами: %d": "Arcs between two objects: %d",
    "Висячих узлов: %d, псевдоузлов: %d": "Dangling nodes: %d, pseudo nodes: %d",

    # Псевдонимы полей выходных слоёв
    "Номер": "Number",
    "Код нарушения": "Violation code",
    "Нарушение": "Violation",
    "Разряд": "Severity",
    "Объект": "Feature",
    "Второй объект": "Second feature",
    "Величина": "Value",
    "Пояснение": "Note",
    "Группа": "Group",
    "Вид правки": "Edit kind",
    "Смещение": "Displacement",
    "Кольцо": "Ring",
    "Вид узла": "Node kind",
    "Отклонение от ребра": "Offset from the edge",
    "Номер узла": "Node number",
    "Степень": "Degree",
    "Номер дуги": "Arc number",
    "Узел начала": "Start node",
    "Узел конца": "End node",
    "Объект слева": "Feature on the left",
    "Объект справа": "Feature on the right",
    "Длина": "Length",
    "Код вида": "Kind code",
    "Вид границы": "Border kind",
    "Объект с одной стороны": "Feature on one side",
    "Объект с другой стороны": "Feature on the other side",
    "Значение с одной стороны": "Value on one side",
    "Значение с другой стороны": "Value on the other side",

    # Подсказки полей и прочие строки диалогов Processing
    "Полигональный слой, который проверяется.\n"
    "Слой не изменяется, находки пишутся в отдельный слой точек.":
        "The polygon layer to check. The layer is not modified, findings go\n"
        "to a separate point layer.",
    "Расстояние, ниже которого расхождение считается технической погрешностью.":
        "The distance below which a discrepancy counts as a technical error.",
    "Площадь, ниже которой фрагмент считается техническим мусором.\n"
    "Разумная точка отсчёта это квадрат допуска.":
        "The area below which a fragment counts as technical debris. A\n"
        "reasonable starting point is the square of the tolerance.",
    "Нужно, когда слой не является единым покрытием, например когда\n"
    "зоны нескольких пластов лежат в одном слое. Объекты разных групп\n"
    "накладываются друг на друга по замыслу, и без группировки каждое\n"
    "такое наложение попадает в перекрытия, дубликаты и вложения.":
        "Needed when the layer is not a single coverage, for example when\n"
        "zones of several seams lie in one layer. Features of different\n"
        "groups overlap by design, and without grouping each such overlap\n"
        "goes into overlaps, duplicates and nesting.",
    "Полость крупнее этой площади считается частью замысла и находкой\n"
    "не является. Это целик, озеро, незакартированный участок.\n"
    "Мелкая дыра в покрытии это дефект, очень крупная почти всегда нет.":
        "A cavity larger than this area is taken as part of the design and is\n"
        "not a finding. This is a pillar, a lake, an unmapped area. A small\n"
        "hole in a coverage is a defect, a very large one almost never is.",
    "Попарное сравнение объектов. На больших слоях это самая долгая часть\n"
    "проверки, и её можно отключить, если интересуют только вершины и щели.":
        "Pairwise comparison of features. On large layers this is the longest\n"
        "part of the check, and it can be switched off when only vertices and\n"
        "gaps are of interest.",
    "Щель это дыра в объединении покрытия. Зазор, выходящий на внешний край,\n"
    "дырой не является и здесь не находится. Его закрывает сшивка вершин.":
        "A gap is a hole in the union of the coverage. A gap that opens onto\n"
        "the outer edge is not a hole and is not found here. Vertex snapping\n"
        "closes it.",
    "Вершина одного объекта лежит на ребре соседа или рядом с ним,\n"
    "а у соседа в этой точке узла нет. Такие места мешают сшивке\n"
    "и построению модели покрытия.":
        "A vertex of one feature lies on or near a neighbour's edge, and the\n"
        "neighbour has no node at that point. Such places hinder snapping and\n"
        "building the coverage model.",
    "Нумерованный список находок. В нём номер, что не так, у каких\n"
    "объектов, где именно. Номер совпадает с полем num в слое\n"
    "находок, поэтому по списку место ищется на карте, а по\n"
    "идентификатору объекта в исходных данных.\n"
    "Список удобно передать тому, кто данные готовил.":
        "A numbered list of findings. It gives the number, what is wrong, for\n"
        "which features and where exactly. The number matches the num field\n"
        "in the findings layer, so the list leads to the place on the map,\n"
        "and the feature identifier leads to it in the source data. The list\n"
        "is convenient to hand over to whoever prepared the data.",
    "Слой точек, по одной на каждую находку.\n"
    "Поле severity делит находки на auto и review.":
        "A point layer with one point per finding. The severity field splits\n"
        "findings into auto and review.",
    "Полигональный слой, который очищается.\n"
    "Слой не изменяется, результат пишется в новый слой.":
        "The polygon layer to clean. The layer is not modified, the result\n"
        "goes to a new layer.",
    "Предельное смещение вершины и радиус поиска соседних рёбер.":
        "The maximum displacement of a vertex and the search radius for\n"
        "neighbouring edges.",
    "Фрагменты мельче этого порога считаются мусором и убираются молча.\n"
    "Перекрытия и щели крупнее порога не изменяются.":
        "Fragments smaller than this threshold count as debris and are\n"
        "removed silently. Overlaps and gaps larger than the threshold are\n"
        "not modified.",
    "Объекты разных групп не сшиваются между собой и не спорят\n"
    "за площадь. Нужно, когда в одном слое лежат несколько покрытий,\n"
    "например зоны разных пластов.":
        "Features of different groups are not snapped to each other and do\n"
        "not compete for area. Needed when several coverages lie in one\n"
        "layer, for example zones of different seams.",
    "Слияние близких вершин и вставка недостающих узлов. Без этого шага\n"
    "остальные работают по несогласованному покрытию.":
        "Merging of close vertices and insertion of missing nodes. Without\n"
        "this step the other steps work on an inconsistent coverage.",
    "Самопересечения и вывернутые кольца. Правка, отнимающая больше четверти\n"
    "площади объекта, отменяется, и объект попадает в оставшиеся проблемы.":
        "Self-intersections and inverted rings. An edit that takes more than\n"
        "a quarter of a feature's area is cancelled, and the feature goes to\n"
        "the remaining problems.",
    "Вычитается только узкая полоса, шириной меньше допуска. Широкое\n"
    "перекрытие это спор за площадь, и оно остаётся человеку.":
        "Only a narrow strip, narrower than the tolerance, is subtracted. A\n"
        "wide overlap is a dispute over area, and it is left to the operator.",
    "Щель мельче порога площади отходит соседу с наибольшей общей\n"
    "границей. Щель крупнее порога не заполняется и попадает\n"
    "в оставшиеся проблемы.":
        "A gap smaller than the area threshold goes to the neighbour with the\n"
        "longest shared border. A gap larger than the threshold is not filled\n"
        "and goes to the remaining problems.",
    "Проигравший объект отдаёт полосу перекрытия.":
        "The losing feature gives up the overlap strip.",
    "По умолчанию выключено. Удаление объекта уничтожает и его атрибуты.\n"
    "Без этой галочки такие объекты только попадают в слой оставшихся проблем.":
        "Off by default. Deleting a feature destroys its attributes as well.\n"
        "Without this checkbox such features only go to the remaining\n"
        "problems layer.",
    "Вершина снимается, если линия разворачивается в ней назад\n"
    "с углом меньше указанного. Значение около одного градуса\n"
    "убирает только явные артефакты оцифровки.":
        "A vertex is removed when the line turns back at it with an angle\n"
        "smaller than this value. A value of about one degree removes only\n"
        "obvious digitising artefacts.",
    "Операции пересечения работают в плане, поэтому Z берётся у ближайшей\n"
    "исходной вершины. Для покрытий это верно, для слоёв с резким перепадом\n"
    "высоты вдоль границы результат стоит проверить.":
        "Intersection operations work in plan, so Z is taken from the nearest\n"
        "original vertex. For coverages this is correct. For layers with a\n"
        "sharp change in height along a border, check the result.",
    "Новый слой с исправленной геометрией и атрибутами исходного.":
        "A new layer with the fixed geometry and the attributes of the\n"
        "source.",
    "Точки на месте того, что исправить нельзя или не разрешено.\n"
    "Поля те же, что у слоя находок инструмента 1.01.":
        "Points where something cannot be fixed or is not allowed to be\n"
        "fixed. The fields are the same as in the findings layer of tool\n"
        "1.01.",
    "Слой полигонов или линий. Объекты собираются в группы\n"
    "по значению полей группировки.":
        "A layer of polygons or lines. Features are assembled into groups by\n"
        "the value of the grouping fields.",
    "Объекты с одинаковым значением этих полей собираются в одно тело.\n"
    "Каждое тело проверяется на разрывы и полости.":
        "Features with the same value of these fields are assembled into one\n"
        "body. Each body is checked for breaks and cavities.",
    "Внутренние кольца мельче порога помечаются как технический мусор.":
        "Inner rings smaller than the threshold are marked as technical\n"
        "debris.",
    "Части, отстоящие друг от друга дальше этого расстояния, считаются\n"
    "отдельными телами и находкой не являются.\n"
    "Ноль означает, что группа обязана собираться в одно целое.\n"
    "Ноль подходит для зон, блоков и панелей. Для полигонов изолиний\n"
    "и подобных данных задавайте величину порядка нескольких допусков.":
        "Parts farther apart than this distance count as separate bodies and\n"
        "are not a finding. Zero means that the group must assemble into one\n"
        "piece. Zero suits zones, blocks and panels. For isoline polygons and\n"
        "similar data set a value of several tolerances.",
    "Отключает поиск полостей внутри тел. Нужно там, где полость\n"
    "входит в замысел, например у полигонов изолиний.":
        "Switches off the search for cavities inside bodies. Needed where a\n"
        "cavity is part of the design, for example for isoline polygons.",
    "Слой точек, по одной на каждую находку сборки.\n"
    "Поля те же, что у слоя находок инструмента 1.01.":
        "A point layer with one point per assembly finding. The fields are\n"
        "the same as in the findings layer of tool 1.01.",
    "Текстовый файл (*.txt)":
        "Text file (*.txt)",
    "Полигональный слой покрытия, в которое вводятся контуры.\n"
    "Слой не изменяется, результат пишется в новый слой.":
        "The polygon coverage layer that receives the contours. The layer is\n"
        "not modified, the result goes to a new layer.",
    "Каждый объект слоя это отдельный контур. Контуры применяются\n"
    "по одному, в порядке слоя, и результат каждого входит в покрытие\n"
    "до начала следующего. Линию перед врезкой превращают в полигон\n"
    "построением буфера.":
        "Each feature of the layer is a separate contour. Contours are\n"
        "applied one by one, in layer order, and the result of each enters\n"
        "the coverage before the next one starts. A line is turned into a\n"
        "polygon by a buffer before it is cut in.",
    "Наложение отдаёт новому объекту весь контур, соседи урезаются.\n"
    "Отсечение оставляет соседям их площадь, а контур ложится только\n"
    "в свободное место. Врезка отдаёт новому объекту то, что лежит\n"
    "внутри покрытия, и площадь покрытия при этом не меняется.":
        "Overlay gives the new feature the whole contour, the neighbours are\n"
        "trimmed. Clip leaves the neighbours their area, and the contour\n"
        "takes only free space. Inset gives the new feature what lies inside\n"
        "the coverage, and the area of the coverage does not change.",
    "Остаток соседа мельче этой площади не оставляется отдельным\n"
    "объектом, а отходит контуру целиком. Кусок соседа мельче этой\n"
    "площади контуру не достаётся, и сосед остаётся как был.\n"
    "Ноль режет всё, что пересеклось, вплоть до осколков в микроны.":
        "A neighbour remainder smaller than this area is not kept as a\n"
        "separate feature and goes to the contour entirely. A piece of a\n"
        "neighbour smaller than this area does not go to the contour, and the\n"
        "neighbour stays as it was. Zero cuts everything that intersected,\n"
        "down to slivers of microns.",
    "Разрез кладёт вершину на границу соседа с третьим объектом,\n"
    "и у этого третьего узла в той точке нет. Инструмент достраивает\n"
    "такие узлы, как это делает инструмент 1.06. Узел ставится\n"
    "в проекцию точки на ребро, поэтому форма и площадь не меняются.\n"
    "Ноль отключает вставку, и врезка оставит нарушение после себя.":
        "The cut puts a vertex on the border between a neighbour and a third\n"
        "feature, and the third feature has no node at that point. The tool\n"
        "adds such nodes the way tool 1.06 does. The node is placed at the\n"
        "projection of the point onto the edge, so the shape and the area do\n"
        "not change. Zero switches the insertion off, and the cut leaves a\n"
        "violation behind.",
    "Наложение работает в плане, поэтому отметка вершины берётся\n"
    "с ближайшего исходного ребра. Вершина на середине ребра получает\n"
    "отметку, посчитанную вдоль этого ребра. Объекты, которых врезка\n"
    "не коснулась, переносятся без изменения.":
        "The overlay works in plan, so the elevation of a vertex is taken\n"
        "from the nearest original edge. A vertex in the middle of an edge\n"
        "gets an elevation computed along that edge. Features the cut did not\n"
        "touch are carried over unchanged.",
    "Новый слой покрытия с введёнными контурами.\n"
    "Объекты, которых врезка не коснулась, переносятся без изменения.":
        "A new coverage layer with the contours cut in. Features the cut did\n"
        "not touch are carried over unchanged.",
    "Линейный слой, который проверяется.\n"
    "Слой не изменяется, находки пишутся в отдельный слой точек.":
        "The line layer to check. The layer is not modified, findings go to a\n"
        "separate point layer.",
    "Расстояние, ниже которого расхождение считается погрешностью.\n"
    "Недовод и перелёт короче допуска относятся к мусору.":
        "The distance below which a discrepancy counts as an error. An\n"
        "undershoot or overshoot shorter than the tolerance counts as debris.",
    "Линии короче этой длины попадают в находки.":
        "Lines shorter than this length go to the findings.",
    "Три разных случая на конце линии. Недовод и перелёт короче допуска\n"
    "относятся к мусору, висячий конец остаётся человеку. У гидросети\n"
    "или сети выработок это устье либо тупик.":
        "Three different cases at the end of a line. An undershoot or\n"
        "overshoot shorter than the tolerance counts as debris, a dangle is\n"
        "left to the operator. In a river network or a network of workings it\n"
        "is a mouth or a dead end.",
    "Линии пересекаются, а вершины в точке пересечения нет ни у одной.":
        "Lines cross, and neither of them has a vertex at the crossing point.",
    "Две линии сходятся концами, и больше в этой точке ничего нет. Их можно\n"
    "объединить. Выключено намеренно, во многих слоях разбиение на участки\n"
    "сделано специально.":
        "Two lines meet at their ends, and nothing else is at that point.\n"
        "They can be merged. Off on purpose, many layers are split into\n"
        "segments deliberately.",
    "Линейный слой, который очищается.\n"
    "Слой не изменяется, результат пишется в новый слой.":
        "The line layer to clean. The layer is not modified, the result goes\n"
        "to a new layer.",
    "Предельное смещение конца линии и предельная длина\n"
    "обрезаемого хвоста.":
        "The maximum displacement of a line end and the maximum length of a\n"
        "trimmed tail.",
    "Линии короче этой длины попадают в оставшиеся проблемы. Удаляются\n"
    "они только с отдельной галочки. Удаление уничтожает и атрибуты.":
        "Lines shorter than this length go to the remaining problems. They\n"
        "are deleted only with a separate checkbox. Deletion destroys the\n"
        "attributes as well.",
    "Хвост, торчащий за пересечением, отрезается до самой точки пересечения.\n"
    "Обрезаются только хвосты короче допуска.":
        "A tail sticking out past a crossing is cut back to the crossing\n"
        "point. Only tails shorter than the tolerance are trimmed.",
    "Конец переносится на проекцию, то есть на ближайшую точку соседнего\n"
    "ребра. Смещение не превышает допуска.":
        "The end is moved to the projection, that is to the nearest point of\n"
        "the neighbouring edge. The displacement does not exceed the\n"
        "tolerance.",
    "Сшивка концов и вставка недостающих узлов на рёбра соседних линий.\n"
    "Вершина не смещается дальше допуска.":
        "Snapping of ends and insertion of missing nodes into the edges of\n"
        "neighbouring lines. A vertex is never moved farther than the\n"
        "tolerance.",
    "По умолчанию выключено. Удаление объекта уничтожает и его атрибуты.\n"
    "Без этой галочки такие линии только попадают в оставшиеся проблемы.":
        "Off by default. Deleting a feature destroys its attributes as well.\n"
        "Without this checkbox such lines only go to the remaining problems.",
    "Игла это разворот линии назад почти на месте. Угол между входящим\n"
    "и исходящим ребром меньше этого значения считается иглой.":
        "A spike is a line turning back almost in place. An angle between the\n"
        "incoming and the outgoing edge smaller than this value counts as a\n"
        "spike.",
    "Точки на месте того, что исправить нельзя или не разрешено.\n"
    "Поля те же, что у слоя находок инструмента 1.02.":
        "Points where something cannot be fixed or is not allowed to be\n"
        "fixed. The fields are the same as in the findings layer of tool\n"
        "1.02.",
    "Полигональный или линейный слой.\n"
    "Слой не изменяется, результат пишется в новый слой.":
        "A polygon or line layer. The layer is not modified, the result goes\n"
        "to a new layer.",
    "Предельное отклонение упрощённой линии от исходной.\n"
    "Ноль означает, что ничего не прореживается.":
        "The maximum deviation of the simplified line from the original. Zero\n"
        "means nothing is thinned out.",
    "Дуглас-Пекер меряет отклонение вершины от хорды. Он держит углы\n"
    "и характерные изломы, но на плавной кривой оставляет грани.\n"
    "Висвалингам меряет площадь треугольника из трёх соседних\n"
    "вершин. На плавных линиях результат мягче, зато острый угол\n"
    "из коротких рёбер может срезаться.\n"
    "Для границ блоков и выработок подходит первый, для изолиний\n"
    "и гидросети второй.":
        "Douglas-Peucker measures the deviation of a vertex from the chord.\n"
        "It keeps corners and characteristic bends, but leaves facets on a\n"
        "smooth curve. Visvalingam measures the area of the triangle formed\n"
        "by three neighbouring vertices. On smooth lines the result is\n"
        "softer, but a sharp corner made of short edges may be cut off. The\n"
        "first suits borders of blocks and workings, the second suits\n"
        "isolines and river networks.",
    "Защита коротких участков границы. Ноль отключает её.":
        "Protection of short border segments. Zero switches it off.",
    "Срезание углов по схеме Чайкина после прореживания.\n"
    "Линия остаётся внутри исходной, поэтому выбросов и новых\n"
    "самопересечений не возникает. Сглаживание идёт по тем же дугам,\n"
    "поэтому общая граница соседей остаётся общей.\n"
    "Каждый проход примерно удваивает количество вершин, обычно хватает\n"
    "одного или двух.":
        "Corner cutting by the Chaikin scheme after thinning. The line stays\n"
        "inside the original, so no overshoots or new self-intersections\n"
        "appear. Smoothing runs along the same arcs, so the shared border of\n"
        "neighbours stays shared. Each pass roughly doubles the number of\n"
        "vertices, one or two passes are usually enough.",
    "Вершины, отстоящие меньше этой величины, считаются одной.\n"
    "Нужно, когда соседи записаны с разной точностью координат.\n"
    "Это не допуск упрощения, задавать метры здесь не следует.":
        "Vertices closer than this value count as one. Needed when neighbours\n"
        "are stored with different coordinate precision. This is not the\n"
        "simplification tolerance, do not set metres here.",
    "Границы объектов разных групп общими не считаются.\n"
    "Нужно, когда в одном слое лежат несколько покрытий.":
        "Borders between features of different groups do not count as shared.\n"
        "Needed when several coverages lie in one layer.",
    "Прореживание идёт по плановым координатам, отметка переносится\n"
    "с оставшихся вершин.":
        "Thinning works on plan coordinates, the elevation is carried over\n"
        "from the remaining vertices.",
    "Новый слой с упрощённой геометрией и атрибутами исходного.":
        "A new layer with the simplified geometry and the attributes of the\n"
        "source.",
    "Полигональный слой покрытия. Слой не изменяется.":
        "The polygon coverage layer. The layer is not modified.",
    "Значение этого поля у обоих соседей попадёт в атрибуты линии.\n"
    "Для геологических границ это пласт слева и пласт справа.":
        "The value of this field on both neighbours goes into the attributes\n"
        "of the line. For geological borders this is the seam on the left and\n"
        "the seam on the right.",
    "Вершина, лежащая на ребре соседа ближе этой величины, получает\n"
    "узел перед разбором. Без этого общая граница не опознаётся.\n"
    "У соседей разная вершинность, и участок выходит двумя линиями.\n"
    "Вершины при этом не двигаются. Ноль отключает.":
        "A vertex lying on a neighbour's edge closer than this value gets a\n"
        "node before the analysis. Without it the shared border is not\n"
        "recognised. The neighbours have different vertices, and the segment\n"
        "comes out as two lines. Vertices do not move. Zero switches it off.",
    "Координаты соседей могут быть записаны с разной точностью.\n"
    "Величина нужна, чтобы такие вершины считались одной. Это не допуск.\n"
    "Увеличивать её до метров не следует.":
        "Neighbour coordinates may be stored with different precision. The\n"
        "value makes such vertices count as one. It is not a tolerance. Do\n"
        "not raise it to metres.",
    "Линейный слой границ. Общая граница двух соседей\n"
    "выходит одной линией.":
        "A line layer of borders. The shared border of two neighbours comes\n"
        "out as one line.",
    "Узлы достраиваются перед разбором, иначе общая граница\n"
    "не опознаётся. Вершины при этом не двигаются.":
        "Nodes are added before the analysis, otherwise the shared border is\n"
        "not recognised. Vertices do not move.",
    "Слой точек узлов покрытия. Узел - это конец дуги.":
        "A point layer of coverage nodes. A node is an end of an arc.",
    "Линейный слой дуг. Дуга - участок границы между двумя узлами\n"
    "с одними и теми же соседями слева и справа.":
        "A line layer of arcs. An arc is a border segment between two nodes\n"
        "with the same neighbours on the left and on the right.",
    "Максимальное расстояние, на которое разрешено сдвинуть вершину.\n"
    "Он же радиус поиска соседних рёбер для вставки узлов.\n"
    "Берите чуть больше реальной величины расхождений и заметно меньше\n"
    "длины самого короткого осмысленного ребра.":
        "The maximum distance a vertex is allowed to move. It is also the\n"
        "search radius for neighbouring edges when inserting nodes. Take a\n"
        "little more than the real size of the discrepancies and clearly less\n"
        "than the length of the shortest meaningful edge.",
    "Полная сшивка закрывает зазоры и согласует узлы.\n"
    "Только вставка узлов не меняет ни одной существующей координаты,\n"
    "это безопасный первый проход для контроля объёма правок.":
        "Full snapping closes gaps and reconciles nodes. Node insertion only\n"
        "does not change any existing coordinate, it is a safe first pass for\n"
        "checking the amount of edits.",
    "Слой, который трогать нельзя. Его вершины становятся опорными,\n"
    "входной слой подтягивается к ним. Сам эталон не изменяется.":
        "A layer that must not be touched. Its vertices become anchors, and\n"
        "the input layer is pulled to them. The reference itself is not\n"
        "modified.",
    "Определяет, чьи вершины остаются на месте при слиянии.\n"
    "Обычно на месте оставляют крупный объект,\n"
    "а мелкий подтянуть к нему.":
        "Defines whose vertices stay in place when merging. Usually the large\n"
        "feature stays in place and the small one is pulled to it.",
    "Интерполяция сохраняет форму ребра в разрезе.\n"
    "Второй вариант нужен, когда узлы должны совпасть и по высоте.":
        "Interpolation keeps the shape of the edge in section. The second\n"
        "option is needed when nodes must match in height too.",
    "Нужно для перехлёстов, где рёбра пересекаются крест-накрест,\n"
    "а общих вершин нет. Вставка узлов по вершинам такой случай\n"
    "не закрывает, потому что вставлять там нечего.":
        "Needed for crossings where edges cross each other and have no shared\n"
        "vertices. Node insertion by vertices does not close such a case,\n"
        "because there is nothing to insert there.",
    "У объекта, чья ширина меньше допуска, противоположные берега\n"
    "слиплись бы, и он схлопнулся бы сам в себя. С этой галочкой он\n"
    "остаётся нетронутым и служит опорой. Соседи подтягиваются к нему.\n"
    "Без неё такие объекты теряются целиком.":
        "A feature narrower than the tolerance would have its opposite banks\n"
        "stuck together, and it would collapse into itself. With this\n"
        "checkbox it stays untouched and serves as an anchor. The neighbours\n"
        "are pulled to it. Without it such features are lost entirely.",
    "Слияние вершин выворачивает форму, если объект уже допуска.\n"
    "Противоположные берега слипаются. Первый вариант пробует исправить,\n"
    "а если правка съедает больше четверти площади, возвращает объект\n"
    "в исходный вид. Второй сразу возвращает исходный, тогда границы\n"
    "такого объекта останутся несогласованными. Третий пишет как вышло.":
        "Vertex merging turns the shape inside out if a feature is narrower\n"
        "than the tolerance. The opposite banks stick together. The first\n"
        "option tries to repair, and if the repair takes more than a quarter\n"
        "of the area, it restores the feature to its original state. The\n"
        "second restores the original at once, and the borders of such a\n"
        "feature stay inconsistent. The third writes the result as it came\n"
        "out.",
    "Считает количество некорректных геометрий на входе и на выходе.\n"
    "На больших слоях проверка занимает заметное время.":
        "Counts invalid geometries at the input and at the output. On large\n"
        "layers the check takes noticeable time.",
    "Новый слой со сшитой геометрией и атрибутами исходного.":
        "A new layer with the snapped geometry and the attributes of the\n"
        "source.",
    "Точка на месте каждой правки. Поле kind называет вид правки,\n"
    "поле dist хранит смещение.":
        "A point at the place of each edit. The kind field names the kind of\n"
        "edit, the dist field holds the displacement.",
    "Источник узлов для входного слоя. Не изменяется и в результат\n"
    "не попадает. Нужен, когда вершины одного слоя лежат на рёбрах другого.":
        "The source of nodes for the input layer. It is not modified and does\n"
        "not go into the result. Needed when the vertices of one layer lie on\n"
        "the edges of another.",
    "Защита от ложных срабатываний, а не допуск поиска.\n"
    "Узел ставится, только если вершина лежит на ребре ближе\n"
    "этой величины. Значение отвечает точности координат.\n"
    "Задавать метры здесь не следует.":
        "Protection against false positives, not a search tolerance. A node\n"
        "is placed only when a vertex lies on an edge closer than this value.\n"
        "The value matches the coordinate precision. Do not set metres here.",
    "Точка пересечения лежит на обоих рёбрах, поэтому такая вставка\n"
    "тоже не меняет ни формы, ни площади.":
        "The crossing point lies on both edges, so such an insertion does not\n"
        "change the shape or the area either.",
    "Вставленный узел сам иногда ложится на ребро третьего объекта,\n"
    "поэтому проходы повторяются, пока узлы находятся. На согласованном\n"
    "покрытии хватает двух-трёх. Если предел достигнут, значит слой\n"
    "не является покрытием. Причина обычно в наложении объектов.":
        "An inserted node sometimes lands on an edge of a third feature\n"
        "itself, so the passes repeat while nodes are found. On a consistent\n"
        "coverage two or three are enough. If the limit is reached, the layer\n"
        "is not a coverage. The usual cause is overlapping features.",
    "Новый слой со вставленными узлами и атрибутами исходного.\n"
    "Вставка узлов не меняет ни форму, ни площадь.":
        "A new layer with the inserted nodes and the attributes of the\n"
        "source. Node insertion changes neither the shape nor the area.",
    "Точка на месте каждого вставленного узла.\n"
    "Поле dist хранит отклонение вершины от ребра.":
        "A point at the place of each inserted node. The dist field holds the\n"
        "offset of the vertex from the edge.",
}
