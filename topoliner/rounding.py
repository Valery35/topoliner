# -*- coding: utf-8 -*-
"""
rounding
--------
Округление измеренных величин до значащих цифр.

Величины приходят из геометрии и несут весь хвост двоичного представления.
Смещение вершины выглядит как 0.0300000000000011, площадь микродыры как
3.8234567890123e-06. В атрибутах и в отчёте такой хвост только мешает.

Округление идёт по значащим цифрам, а не по знакам после запятой. Фиксированное
количество знаков одинаково плохо работает на разных масштабах. Величина 0.0001
при четырёх знаках превращается в ноль, а 12345.6789 сохраняет знаки, которых
в исходных данных нет.

Целые величины не округляются вовсе. В поле value наряду с площадью и смещением
попадает количество, и 12345 вершин обязаны остаться числом 12345.

Чистый Python, без QGIS.
"""

import math

__all__ = ["nice", "fmt", "DIGITS"]

# Четыре значащие цифры. Точность оцифровки редко бывает выше, а прочитать
# результат с таким количеством цифр можно без усилия.
DIGITS = 4

# Предел на количество знаков после запятой. Ниже этого уровня величина
# уже не отличима от погрешности вычислений с двойной точностью.
MAX_PLACES = 12


def places_for(value, digits=DIGITS):
    """Количество знаков после запятой для заданного количества значащих цифр."""
    if value is None:
        return 0
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(value) or value == 0.0:
        return 0
    exponent = math.floor(math.log10(abs(value)))
    return max(0, min(MAX_PLACES, digits - 1 - int(exponent)))


def nice(value, digits=DIGITS):
    """
    Округлённая величина.

    Целые и нечисловые значения возвращаются как есть, остальные округляются
    до заданного количества значащих цифр.
    """
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(value):
        return value
    if value == int(value):
        return float(int(value))
    return round(value, places_for(value, digits))


def fmt(value, digits=DIGITS):
    """
    Величина строкой, без хвостовых нулей.

    Применяется в пояснениях к находкам и в отчёте, где число стоит внутри
    предложения и лишние нули читаются как точность, которой нет.
    """
    if value is None:
        return ""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if not math.isfinite(value):
        return str(value)
    if value == int(value):
        return "%d" % int(value)
    text = "%.*f" % (places_for(value, digits), value)
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
