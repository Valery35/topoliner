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

import os
import warnings

try:  # внутри плагина QGIS
    from qgis.core import QgsProcessingLayerPostProcessorInterface
except ImportError:  # headless-тесты
    QgsProcessingLayerPostProcessorInterface = object

__all__ = ["fields_from", "set_field_aliases", "write_field_aliases"]

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


def set_field_aliases(algorithm, context, destination, aliases):
    """
    Назначить псевдонимы полей выходному слою.

    Делает две вещи. Ставит псевдоним слою, который загружается в проект,
    и запоминает, куда лёг результат, чтобы после прогона записать подписи
    в сам файл. Запись в файл выполняет write_field_aliases.
    """
    if not destination or not aliases:
        return
    targets = getattr(algorithm, "_alias_targets", None)
    if targets is None:
        targets = []
        algorithm._alias_targets = targets
    targets.append((destination, aliases))
    try:
        if not context.willLoadLayerOnCompletion(destination):
            return
        processor = _AliasPostProcessor(aliases)
        _KEEP_ALIVE.append(processor)
        context.layerToLoadOnCompletionDetails(destination).setPostProcessor(
            processor)
    except (AttributeError, KeyError, RuntimeError, TypeError):
        return


def gpkg_target(reference):
    """
    Путь и имя слоя для ссылки на GeoPackage, иначе None.

    Ссылка приходит в двух видах. От загрузки в проект с именем слоя,
    `C:/путь/файл.gpkg|layername=x`. От приёмника результата одним путём,
    и тогда имя слоя разбирает тот, кто открывает файл. Память, shapefile
    и прочее сюда не попадают, потому что псевдоним в файл умеет только
    GeoPackage.
    """
    if not isinstance(reference, str) or not reference:
        return None
    path, separator, tail = reference.partition("|layername=")
    if not path.lower().endswith(".gpkg"):
        return None
    if not separator:
        return (path, None)
    name = tail.split("|")[0].strip()
    return (path, name or None)


def _layer_of(source, path, layer_name):
    """Слой GeoPackage по имени, а без имени по имени файла."""
    if layer_name:
        return source.GetLayerByName(layer_name)
    stem = os.path.splitext(os.path.basename(path))[0]
    found = source.GetLayerByName(stem)
    if found is not None:
        return found
    return source.GetLayer(0) if source.GetLayerCount() == 1 else None


def _write_to_gpkg(path, layer_name, aliases):
    """
    Пишет псевдонимы в сам файл. Возвращает количество полей.

    Работа с GDAL идёт с погашенными предупреждениями Python. Библиотека
    предупреждает о будущем переходе на исключения при первом обращении,
    а обработчик предупреждений QGIS роняет программу. По той же причине
    обойдён parameterAsFields, см. начало файла.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from osgeo import gdal, ogr
        if not hasattr(ogr, "ALTER_ALTERNATIVE_NAME_FLAG"):
            return 0  # GDAL до 3.7 второго имени поля не знает
        source = gdal.OpenEx(path, gdal.OF_UPDATE | gdal.OF_VECTOR)
        if source is None:
            return 0
        layer = _layer_of(source, path, layer_name)
        if layer is None:
            return 0
        definition = layer.GetLayerDefn()
        done = 0
        for index in range(definition.GetFieldCount()):
            old = definition.GetFieldDefn(index)
            alias = aliases.get(old.GetName())
            if not alias:
                continue
            if old.GetAlternativeName() == alias:
                done += 1
                continue
            fresh = ogr.FieldDefn(old.GetName(), old.GetType())
            fresh.SetSubType(old.GetSubType())
            fresh.SetAlternativeName(alias)
            if layer.AlterFieldDefn(index, fresh,
                                    ogr.ALTER_ALTERNATIVE_NAME_FLAG) == 0:
                done += 1
        return done


def write_field_aliases(algorithm, feedback=None):
    """
    Записать псевдонимы в сами файлы результатов.

    Псевдоним, поставленный слою, живёт в проекте. Слой, открытый файлом
    из другого проекта, показывал бы латинские имена. GeoPackage хранит
    второе имя поля рядом с самим полем, и QGIS читает его при любом
    открытии.

    Записывается язык интерфейса на момент прогона. Вызывается после
    прогона, когда приёмник уже закрыл файл.
    """
    seen = set()
    for destination, aliases in getattr(algorithm, "_alias_targets", []):
        target = gpkg_target(destination)
        if target is None or target in seen:
            continue
        seen.add(target)
        try:
            _write_to_gpkg(target[0], target[1], aliases)
        except (ImportError, AttributeError, RuntimeError, TypeError) as why:
            if feedback is not None:
                feedback.pushDebugInfo(
                    "Псевдонимы в файл не записаны: %s" % why)


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
