# -*- coding: utf-8 -*-
"""
Тесты округления величин и псевдонимов полей.

Округление проверяется на величинах, ради которых оно и заведено: на хвосте
двоичного представления, на площади в микроны и на количестве, которое трогать
нельзя.

Псевдонимы проверяются на полноту. Каждое поле выходного слоя обязано иметь
подпись, иначе в таблице атрибутов останется латинское имя без объяснения.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
sys.path.insert(0, PLUGIN)

import field_aliases  # noqa: E402
import qgis_helpers  # noqa: E402
import i18n  # noqa: E402
from rounding import DIGITS, fmt, nice  # noqa: E402

try:
    from osgeo import ogr  # noqa: F401
    HAS_GDAL = True
except ImportError:  # сборка без GDAL
    HAS_GDAL = False


class TestNice(unittest.TestCase):

    def test_binary_tail_is_cut(self):
        self.assertEqual(nice(0.0300000000000011), 0.03)

    def test_small_value_keeps_significant_digits(self):
        """Площадь в микроны не должна превращаться в ноль."""
        self.assertEqual(nice(3.8234567890123e-06), 3.823e-06)
        self.assertNotEqual(nice(3.8234567890123e-06), 0.0)

    def test_large_value_loses_meaningless_digits(self):
        self.assertEqual(nice(1234.5678), 1235.0)

    def test_integer_is_untouched(self):
        """В поле value попадает количество, и его округлять нельзя."""
        self.assertEqual(nice(12345), 12345.0)
        self.assertEqual(nice(1234567), 1234567.0)

    def test_negative_value(self):
        self.assertEqual(nice(-0.0300000000000011), -0.03)

    def test_zero_and_none(self):
        self.assertEqual(nice(0.0), 0.0)
        self.assertIsNone(nice(None))

    def test_text_passes_through(self):
        self.assertEqual(nice("не число"), "не число")

    def test_significant_digits_are_kept(self):
        """Лишних цифр не добавляется, целая часть не теряется."""
        for value in (0.001234567, 12.345678, 8.123456789, 98765.4321):
            text = fmt(value).replace("-", "").replace(".", "").lstrip("0")
            whole = len("%d" % abs(int(value)))
            self.assertLessEqual(len(text), max(DIGITS, whole),
                                 "%r дало %r" % (value, fmt(value)))


class TestFmt(unittest.TestCase):

    def test_no_trailing_zeros(self):
        self.assertEqual(fmt(0.5), "0.5")
        self.assertEqual(fmt(2.0), "2")

    def test_small_value_is_readable(self):
        self.assertEqual(fmt(3.8234567890123e-06), "0.000003823")

    def test_no_exponent_form(self):
        """Показатель степени в подписи на карте читать неудобно."""
        self.assertNotIn("e", fmt(3.8e-09))

    def test_none_gives_empty_string(self):
        self.assertEqual(fmt(None), "")


class TestAliases(unittest.TestCase):

    def tearDown(self):
        i18n.set_language("ru")

    def fields_of(self, name):
        """Имена полей выходного слоя, взятые из кода алгоритмов."""
        pattern = re.compile(r'(?<![\w])%s\.append\(QgsField\("(\w+)"' % name)
        found = []
        for fname in os.listdir(PLUGIN):
            if not fname.endswith(".py"):
                continue
            with open(os.path.join(PLUGIN, fname), encoding="utf-8") as fh:
                found += pattern.findall(fh.read())
        return found

    def test_findings_alias_for_every_field(self):
        names = set(self.fields_of("fields"))
        aliases = set(field_aliases.findings())
        self.assertTrue(names)
        self.assertEqual(sorted(names - aliases - set(field_aliases.borders())
                                - {"dist", "ring"}), [])

    def test_coverage_aliases_cover_their_layers(self):
        nodes = set(self.fields_of("node_fields"))
        arcs = set(self.fields_of("arc_fields"))
        self.assertEqual(sorted(nodes - set(field_aliases.coverage_nodes())), [])
        self.assertEqual(sorted(arcs - set(field_aliases.coverage_arcs())), [])

    def test_no_empty_alias(self):
        for maker in (field_aliases.findings, field_aliases.edits,
                      field_aliases.inserted_nodes, field_aliases.coverage_nodes,
                      field_aliases.coverage_arcs, field_aliases.borders):
            for name, alias in maker().items():
                self.assertTrue(alias.strip(), "%s без подписи" % name)

    def test_aliases_follow_the_interface_language(self):
        i18n.set_language("ru")
        russian = field_aliases.coverage_arcs()
        i18n.set_language("en")
        english = field_aliases.coverage_arcs()
        self.assertNotEqual(russian, english)
        self.assertEqual(sorted(russian), sorted(english))

    def test_every_alias_has_a_translation(self):
        i18n.set_language("ru")
        for maker in (field_aliases.findings, field_aliases.edits,
                      field_aliases.inserted_nodes, field_aliases.coverage_nodes,
                      field_aliases.coverage_arcs, field_aliases.borders):
            for name, alias in maker().items():
                self.assertIn(alias, i18n.EN, "%s без перевода" % name)


class TestGpkgTarget(unittest.TestCase):
    """Разбор ссылки на результат. Псевдоним в файл умеет только GeoPackage."""

    def test_path_with_layer_name(self):
        self.assertEqual(
            qgis_helpers.gpkg_target("C:/данные/файл.gpkg|layername=узлы"),
            ("C:/данные/файл.gpkg", "узлы"))

    def test_bare_path(self):
        self.assertEqual(qgis_helpers.gpkg_target("C:/данные/файл.gpkg"),
                         ("C:/данные/файл.gpkg", None))

    def test_upper_case_extension(self):
        self.assertEqual(qgis_helpers.gpkg_target("C:/файл.GPKG"),
                         ("C:/файл.GPKG", None))

    def test_other_formats_are_skipped(self):
        for ref in ("C:/файл.shp", "memory:вывод", "", None, 17,
                    "TEMPORARY_OUTPUT"):
            self.assertIsNone(qgis_helpers.gpkg_target(ref), repr(ref))


@unittest.skipUnless(HAS_GDAL, "нет GDAL")
class TestBakeAliases(unittest.TestCase):
    """Запись псевдонимов в сам файл."""

    def setUp(self):
        from osgeo import ogr
        self.folder = tempfile.mkdtemp(prefix="topoliner_")
        self.path = os.path.join(self.folder, "проба.gpkg")
        driver = ogr.GetDriverByName("GPKG")
        source = driver.CreateDataSource(self.path)
        layer = source.CreateLayer("дуги", geom_type=ogr.wkbLineString)
        for name, kind in (("arc_id", ogr.OFTInteger),
                           ("left_fid", ogr.OFTInteger64)):
            layer.CreateField(ogr.FieldDefn(name, kind))
        source = None

    def tearDown(self):
        shutil.rmtree(self.folder, ignore_errors=True)

    def aliases_in_file(self):
        from osgeo import gdal
        source = gdal.OpenEx(self.path, gdal.OF_VECTOR)
        definition = source.GetLayerByName("дуги").GetLayerDefn()
        found = {}
        for i in range(definition.GetFieldCount()):
            field = definition.GetFieldDefn(i)
            found[field.GetName()] = field.GetAlternativeName()
        source = None
        return found

    def test_alias_survives_without_a_project(self):
        written = qgis_helpers._write_to_gpkg(
            self.path, "дуги",
            {"arc_id": "Номер дуги", "left_fid": "Объект слева"})
        self.assertEqual(written, 2)
        self.assertEqual(self.aliases_in_file(),
                         {"arc_id": "Номер дуги", "left_fid": "Объект слева"})

    def test_foreign_field_is_not_touched(self):
        qgis_helpers._write_to_gpkg(self.path, "дуги", {"arc_id": "Номер дуги"})
        self.assertEqual(self.aliases_in_file()["left_fid"], "")

    def test_no_python_warning_escapes(self):
        """
        Предупреждение Python из этого кода роняет QGIS, см. AGENTS.md.

        Проверка идёт в отдельном процессе, потому что предупреждение
        библиотеки выдаётся один раз за процесс. В том же процессе его
        мог бы вызвать любой предыдущий тест, и сторож ничего не поймал бы.
        """
        code = (
            "import sys; sys.path.insert(0, %r);"
            "import qgis_helpers;"
            "qgis_helpers._write_to_gpkg(%r, 'дуги', {'arc_id': 'Номер дуги'})"
            % (PLUGIN, self.path))
        done = subprocess.run([sys.executable, "-W", "error::FutureWarning",
                               "-W", "error::DeprecationWarning", "-c", code],
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-800:])

    def test_missing_file_is_silent(self):
        self.assertEqual(
            qgis_helpers._write_to_gpkg(os.path.join(self.folder, "нет.gpkg"),
                                        None, {"arc_id": "Номер дуги"}), 0)

    def test_targets_are_remembered_and_written(self):
        """Заявка копится на алгоритме, запись идёт после прогона."""
        class Fake(object):
            pass

        alg = Fake()
        qgis_helpers.set_field_aliases(
            alg, None, self.path + "|layername=дуги", {"arc_id": "Номер дуги"})
        self.assertEqual(len(alg._alias_targets), 1)
        qgis_helpers.write_field_aliases(alg)
        self.assertEqual(self.aliases_in_file()["arc_id"], "Номер дуги")


if __name__ == "__main__":
    unittest.main(verbosity=2)
