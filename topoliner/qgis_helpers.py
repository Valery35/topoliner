# -*- coding: utf-8 -*-
"""
qgis_helpers
------------
Обходы особенностей QGIS, не относящиеся к топологии.

Пока здесь одно: чтение списка полей из параметра.

Метод parameterAsFields в некоторых сборках QGIS выдаёт предупреждение
Python. Само по себе оно безобидно, но обработчик предупреждений QGIS
собирает стек вызовов, а вызванный из фонового потока Processing он роняет
программу целиком с нарушением доступа. Замечено на QGIS 3.44.10 LTR при
проверке топологии геологической карты.

Падает при этом не наш код, а реакция QGIS на него, поэтому чинится
единственным доступным способом: предупреждение не порождается.
"""

import warnings

__all__ = ["fields_from"]


def fields_from(algorithm, parameters, name, context):
    """
    Имена полей из параметра, без побочных предупреждений.

    Сперва обычный вызов с погашенными предупреждениями. Если он почему-то
    не сработал, значение читается из параметров напрямую: для параметра
    полей это либо строка, либо список строк.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return algorithm.parameterAsFields(parameters, name, context)
    except (TypeError, AttributeError, KeyError):
        return _raw_fields(parameters, name)


def _raw_fields(parameters, name):
    value = parameters.get(name)
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    try:
        return [str(item) for item in value if str(item)]
    except TypeError:
        return [str(value)]
