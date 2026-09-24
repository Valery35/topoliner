# -*- coding: utf-8 -*-
"""
qgis_helpers
------------
Обходы особенностей QGIS, не относящиеся к топологии.

Здесь два обхода. Чтение списка полей из параметра и установка псевдонимов
полей выходному слою.

Метод parameterAsFields в некоторых сборках QGIS выдаёт предупреждение
Python. Само по себе оно безобидно, но обработчик предупреждений QGIS
собирает стек вызовов, а вызванный из фонового потока Processing он роняет
программу целиком с нарушением доступа. Замечено на QGIS 3.44.10 LTR при
проверке топологии геологической карты.

Падает при этом не наш код, а реакция QGIS на него, поэтому чинится
единственным доступным способом. Предупреждение не порождается.

Псевдоним поля, поставленный приёмнику до записи, QGIS встречает
предупреждением о несовместимости с временными слоями. Поэтому псевдонимы
ставятся слою после загрузки, обработчиком завершения.
"""

import warnings

try:  # внутри плагина QGIS
    from qgis.core import QgsProcessingLayerPostProcessorInterface
except ImportError:  # headless-тесты
    QgsProcessingLayerPostProcessorInterface = object

__all__ = ["fields_from", "set_field_aliases"]

# Обработчик должен пережить вызов processAlgorithm, иначе QGIS получит
# ссылку на уничтоженный объект. Список держит его до конца сеанса.
_KEEP_ALIVE = []


class _AliasPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Ставит псевдонимы полей загруженному слою."""

    def __init__(self, aliases):
        super().__init__()
        self.aliases = aliases

    def postProcessLayer(self, layer, context, feedback):
        try:
            fields = layer.fields()
        except (AttributeError, RuntimeError):
            return
        for name, alias in self.aliases.items():
            index = fields.indexOf(name)
            if index >= 0:
                layer.setFieldAlias(index, alias)


def set_field_aliases(context, destination, aliases):
    """
    Назначить псевдонимы полей выходному слою после загрузки.

    Молча ничего не делает, если слой не загружается в проект. При выгрузке
    в файл псевдонимы теряются вместе с проектом, это свойство формата,
    а не пропущенный случай.
    """
    if not destination or not aliases:
        return
    try:
        if not context.willLoadLayerOnCompletion(destination):
            return
        processor = _AliasPostProcessor(aliases)
        _KEEP_ALIVE.append(processor)
        context.layerToLoadOnCompletionDetails(destination).setPostProcessor(
            processor)
    except (AttributeError, KeyError, RuntimeError, TypeError):
        return


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
