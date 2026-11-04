# Topoliner 0.13.3, тексты для площадок

## Русский пост (ВК, Telegram, Facebook)

Topoliner 0.13.3 - модуль QGIS для топологии полигональных и линейных покрытий.

Модуль находит нарушения топологии и отделяет технический мусор от возможного смысла. Мусор исправляется в новый слой. Всё, что крупнее заданных порогов, попадает в слой оставшихся проблем с пояснением. Исходный слой не изменяется никогда.

В модуле одиннадцать инструментов Processing.
- Проверка топологии полигонов и линий выдаёт слой находок и сводку.
- Очистка исправляет щели, перекрытия и висячие концы мельче допуска.
- Сшивка согласует узлы и вершины соседей. Вставка достраивает недостающие узлы и не меняет форму.
- Контроль сборки проверяет, собираются ли группы по атрибуту в целое тело.
- Ввод контуров врезает новый контур в покрытие. Кромка разреза достаётся обеим сторонам одинаковой.
- Топологическое упрощение прореживает общую границу один раз для обоих соседей.
- Модель покрытия разбирает его на узлы и дуги.

Что нового в 0.13.
- QGIS 3.38-3.44 больше не падает при запуске инструментов.
- Слой с некорректной геометрией читается при любых настройках Processing. Причина ошибки названа словами GEOS.
- Инструмент 1.08 вводит контуры в покрытие в трёх режимах наложения.
- В окне «О модуле» появилась ссылка «Поддержать разработку».

Модуль работает в QGIS 3.16 и новее, включая QGIS 4. Он бесплатный и открытый, лицензия GPL 3.

Каталог QGIS: https://plugins.qgis.org/plugins/topoliner/
Выпуск и исходники: https://github.com/Valery35/topoliner/releases/tag/0.13.3

## Английский пост (LinkedIn, OSGeo Discourse)

Topoliner 0.13.3, a QGIS plugin for the topology of polygon and line coverages.

The plugin finds topology errors and separates technical debris from what may carry meaning. Debris is fixed into a new layer. Anything larger than the set thresholds goes to a layer of remaining issues with a note. The source layer is never changed.

Eleven Processing tools.
- Polygon and line topology checks produce a layer of findings and a summary.
- Cleanup fixes gaps, overlaps and dangles smaller than the tolerance.
- Snapping matches the nodes and vertices of neighbours. Node insertion adds missing nodes without changing the shape.
- Assembly check tests whether groups by attribute assemble into one body.
- Contour input cuts a new contour into a coverage, both sides get the same cut edge.
- Topological simplification thins a shared boundary once for both neighbours.
- The coverage model splits a coverage into nodes and arcs.

New in 0.13.
- QGIS 3.38-3.44 no longer crashes when a tool starts.
- A layer with invalid geometry is read with any Processing setting, and the error reason comes from GEOS.
- Tool 1.08 puts contours into a coverage in three overlay modes.

Works in QGIS 3.16 and later, including QGIS 4. Free and open source, GPL 3.

QGIS plugin repository: https://plugins.qgis.org/plugins/topoliner/
Release and source: https://github.com/Valery35/topoliner/releases/tag/0.13.3

## X

Topoliner 0.13.3, a free QGIS plugin for polygon and line coverage topology. Finds overlaps, gaps and missing nodes, fixes debris into a new layer, never touches the source. QGIS 3.38-3.44 crash fixed. #QGIS #GIS #opensource https://plugins.qgis.org/plugins/topoliner/

## Mastodon

Topoliner 0.13.3, a free QGIS plugin for the topology of polygon and line coverages.

It finds overlaps, gaps, dangles and missing nodes, fixes technical debris into a new layer and leaves larger issues for a human with a note. The source layer is never changed.

New: no more crash on QGIS 3.38-3.44, a contour input tool with three overlay modes.

https://plugins.qgis.org/plugins/topoliner/

#QGIS #GIS #OpenSource

## linux.org.ru

Заголовок - Вышел Topoliner 0.13.3, модуль QGIS для топологии покрытий

Topoliner - свободный модуль QGIS для проверки и исправления топологии полигональных и линейных покрытий. Лицензия GPL 3.

Модуль находит перекрытия, щели, висячие концы и недостающие узлы. Нарушения мельче заданного допуска исправляются в новый слой, крупные остаются человеку в отдельном слое с пояснением. Исходный слой не изменяется. Одиннадцать инструментов работают в панели Processing, в моделях и в пакетном режиме.

Изменения в 0.13:
- QGIS 3.38-3.44 больше не падает при запуске инструментов. Устаревший вызов давал предупреждение в фоновом потоке.
- Слой с некорректной геометрией читается при любых настройках Processing.
- Новый инструмент 1.08 вводит контуры в покрытие в трёх режимах наложения.

Модуль работает в QGIS от 3.16 до 4.

## Reddit r/QGIS, r/gis

Title (r/QGIS, r/gis): Topoliner 0.13.3, a free QGIS plugin to check and clean polygon and line coverage topology

Topoliner 0.13.3, a QGIS plugin for the topology of polygon and line coverages.

The plugin finds topology errors and separates technical debris from what may carry meaning. Debris is fixed into a new layer. Anything larger than the set thresholds goes to a layer of remaining issues with a note. The source layer is never changed.

Eleven Processing tools.
- Polygon and line topology checks produce a layer of findings and a summary.
- Cleanup fixes gaps, overlaps and dangles smaller than the tolerance.
- Snapping matches the nodes and vertices of neighbours. Node insertion adds missing nodes without changing the shape.
- Assembly check tests whether groups by attribute assemble into one body.
- Contour input cuts a new contour into a coverage, both sides get the same cut edge.
- Topological simplification thins a shared boundary once for both neighbours.
- The coverage model splits a coverage into nodes and arcs.

New in 0.13.
- QGIS 3.38-3.44 no longer crashes when a tool starts.
- A layer with invalid geometry is read with any Processing setting, and the error reason comes from GEOS.
- Tool 1.08 puts contours into a coverage in three overlay modes.

Works in QGIS 3.16 and later, including QGIS 4. Free and open source, GPL 3.

QGIS plugin repository: https://plugins.qgis.org/plugins/topoliner/
Release and source: https://github.com/Valery35/topoliner/releases/tag/0.13.3
