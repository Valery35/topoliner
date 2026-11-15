# Topoliner 0.13.5

Статья для ВК и сайта, русская и английская.

## Русская статья

Topoliner 0.13.5 - модуль QGIS для топологии полигональных и линейных покрытий.

Модуль находит нарушения топологии и отделяет технический мусор от возможного смысла. Мусор исправляется в новый слой. Всё, что крупнее заданных порогов, попадает в слой оставшихся проблем с пояснением. Исходный слой не изменяется никогда.

Выпуск 0.13.5 посвящён крупным слоям.

**Девять миллионов вершин за 13 минут.** Слой муниципальных районов России, 2570 объектов и 9 миллионов вершин, проходит очистку 1.03 примерно за 13 минут. Пик памяти меньше 4 ГБ. Сшивка исправила 342 тысячи вершин и вставила 102 тысячи узлов. Ни одна вершина не сдвинулась дальше допуска в 1 м. Щели и перекрытие крупнее порога остались в слое проблем, решать их человеку.

**Нехватка памяти больше не роняет QGIS.** Если слою не хватит памяти, инструмент останавливается до начала шага и пишет, сколько памяти нужно, сколько доступно и что сделать. Это касается очистки, сшивки, вставки узлов, ввода контуров, границ и модели покрытия.

**Журнал называет ожидаемую память и время.** На слое от миллиона вершин инструменты 1.03-1.06 до начала сшивки пишут оценку и сравнивают её со свободной памятью. Если памяти может не хватить, журнал предупреждает, и прогон можно отменить. Шкала хода движется и во время сшивки.

**Градусы вместо метров.** Если слой в географической системе координат, а допуск или порог площади похожи на метры, журнал предупреждает. Величина переводится в километры по широте слоя. Допуск 2 в градусах - это около 200 км, и такая очистка сводит соседние вершины в одну.

Модуль работает в QGIS 3.16 и новее, включая QGIS 4. Он бесплатный и открытый, лицензия GPL 3.

Каталог QGIS - https://plugins.qgis.org/plugins/topoliner/
Выпуск и исходники - https://github.com/Valery35/topoliner/releases/tag/0.13.5

## English article

Topoliner 0.13.5 is a QGIS plugin for the topology of polygon and line coverages.

The plugin finds topology violations and separates technical debris from cases that may carry meaning. Debris is fixed into a new layer. Everything above the thresholds goes to a layer of remaining problems with an explanation. The source layer is never changed.

Release 0.13.5 is about large layers.

**Nine million vertices in 13 minutes.** A layer of Russian municipal districts, 2570 features and 9 million vertices, passes cleanup 1.03 in about 13 minutes. The memory peak stays under 4 GB. Snapping fixed 342 thousand vertices and inserted 102 thousand nodes. No vertex moved further than the 1 m tolerance. Gaps and an overlap above the threshold stayed in the problem layer for a person to decide.

**Running short of memory no longer crashes QGIS.** When a layer needs more memory than is available, the tool stops before the step starts and tells how much memory is needed, how much is available and what to do. This covers cleanup, snapping, node insertion, contour insertion, boundaries and the coverage model.

**The log gives the expected memory and time.** From one million vertices, tools 1.03-1.06 write an estimate before snapping and compare it with the free memory. If memory may run short, the log warns and the run can be cancelled. The progress bar moves during snapping.

**Degrees instead of metres.** When the layer is in a geographic coordinate system and the tolerance or the area threshold look like metres, the log warns. The value is converted to kilometres at the latitude of the layer. A tolerance of 2 in degrees is about 200 km, and such a cleanup merges neighbouring vertices into one.

Works in QGIS 3.16 and later, including QGIS 4. Free and open source, GPL 3.

QGIS plugin repository - https://plugins.qgis.org/plugins/topoliner/
Release and source - https://github.com/Valery35/topoliner/releases/tag/0.13.5
