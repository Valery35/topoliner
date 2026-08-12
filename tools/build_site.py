# -*- coding: utf-8 -*-
"""
Собирает страницу Topoliner для сайта.

Страница самодостаточная: схемы встраиваются в неё как base64, поэтому файл
можно открыть как есть, положить на хостинг или вставить кодом на страницу
сайта. Внешних запросов нет, кроме шрифтов.

    python tools/build_site.py

Результат: site/topoliner_landing.html

Оформление держится того же семейства, что и страница Isoliner: одна палитра
и те же шрифты, чтобы два продукта читались как один набор.
"""

import base64
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURES = os.path.join(ROOT, "doc", "figures")
OUT_DIR = os.path.join(ROOT, "site")
OUT = os.path.join(OUT_DIR, "topoliner_landing.html")


def figure(name, language):
    """Схема как data-URL, чтобы страница осталась самодостаточной."""
    path = os.path.join(FIGURES, "%s_%s.png" % (name, language))
    with open(path, "rb") as fh:
        data = base64.b64encode(fh.read()).decode()
    return "data:image/png;base64," + data


def figure_pair(name):
    """
    Обе версии схемы для переключателя языка.

    Подписи внутри схем нарисованы, а не выведены текстом, поэтому картинка
    меняется вместе с языком: иначе на английской странице остаются русские
    рисунки.
    """
    return (' data-fig-ru="%s" data-fig-en="%s" src="%s"'
            % (figure(name, "ru"), figure(name, "en"), figure(name, "ru")))


def read_version():
    path = os.path.join(ROOT, "topoliner", "metadata.txt")
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("version="):
                return line.split("=", 1)[1].strip()
    return ""


# Тексты страницы. Ключ, русский, английский.
# Хранятся в одном месте, чтобы версии не разъезжались: страница переключается
# на лету, без перезагрузки, как это сделано у Isoliner.
TEXTS = {
"title":      ("Topoliner - топология для QGIS · Информ++",
               "Topoliner - topology for QGIS · Inform++"),
"desc":       ("Topoliner приводит полигональные и линейные слои QGIS в порядок: "
               "находит нарушения топологии, чинит технический мусор и не трогает "
               "то, что может нести смысл.",
               "Topoliner brings QGIS polygon and line layers into order: it finds "
               "topology violations, fixes technical debris and leaves alone "
               "anything that may carry meaning."),
"brand.sub":  ("для QGIS", "for QGIS"),
"nav.idea":   ("Идея", "Idea"),
"nav.tools":  ("Инструменты", "Tools"),
"nav.cases":  ("Примеры", "Examples"),
"nav.docs":   ("Документация", "Documentation"),

"hero.eyebrow": ("Плагин QGIS · Processing", "QGIS plugin · Processing"),
"hero.h1":    ("Топология покрытия без ручной правки границ",
               "Coverage topology without editing borders by hand"),
"hero.lead":  ("Знакомая картина: границы соседних участков совпадают на глаз, "
               "а при объединении вылезают волосяные щели. Обычно это правят "
               "руками и каждый раз заново. Topoliner делает то же самое "
               "воспроизводимо, с числовым отчётом и с гарантиями.",
               "A familiar picture: the borders of neighbouring areas look "
               "identical, yet a dissolve leaves hairline slivers behind. "
               "Usually this is fixed by hand, over and over. Topoliner does "
               "the same thing reproducibly, with a numeric report "
               "and with guarantees."),
"cta.install":("Установить в QGIS", "Install in QGIS"),
"cta.code":   ("Исходный код", "Source code"),
"cta.code2":  ("Исходный код и релизы", "Source code and releases"),

"idea.eyebrow":("Как принимается решение", "How the decision is made"),
"idea.h2":    ("Автоматика не знает, какая из двух спорящих границ верна",
               "Automation cannot know which of two disputed borders is correct"),
"idea.sub":   ("Зато она различает масштаб. Сантиметровый нахлёст это погрешность "
               "оцифровки, гектарный это разногласие между источниками. Поэтому "
               "поведение задают два порога, допуск и порог площади. Всё, что "
               "мельче, чинится молча. Всё, что крупнее, показывается и не "
               "трогается ни при каких настройках.",
               "What it can tell is scale. A centimetre overlap is a digitising "
               "error, a hectare one is a disagreement between sources. Behaviour "
               "is therefore set by two thresholds, a tolerance and an area "
               "threshold. Anything smaller is fixed silently. Anything larger "
               "is reported and never touched under any settings."),
"idea.c1.h":  ("Чинится молча", "Fixed silently"),
"idea.c1.p":  ("Повторяющиеся вершины и иглы, вершины на ребре соседа без узла, "
               "расхождения меньше допуска, микродыры и микрочасти, некорректная "
               "геометрия, узкие перекрытия, мелкие щели.",
               "Repeated vertices and spikes, vertices on a neighbour edge without "
               "a node, discrepancies below the tolerance, tiny holes and parts, "
               "invalid geometry, narrow overlaps, small gaps."),
"idea.c2.h":  ("Остаётся человеку", "Left to the operator"),
"idea.c2.p":  ("Широкие перекрытия, крупные щели, дубликаты и вложенные объекты, "
               "волосяные полигоны, висячие концы линий. Всё это попадает "
               "в отдельный слой с пояснением, что именно не так.",
               "Wide overlaps, large gaps, duplicates and nested objects, sliver "
               "polygons, line dangles. All of it goes into a separate layer with "
               "an explanation of what exactly is wrong."),
"idea.fig":   ("Полоса шириной с допуск набирает сотню квадратных единиц, "
               "оставаясь следствием смещения вершин. Поэтому перекрытие "
               "оценивается шириной, а не площадью.",
               "A strip as wide as the tolerance collects a hundred square units "
               "while remaining a consequence of vertex movement. An overlap is "
               "therefore judged by width, not by area."),

"tools.eyebrow":("Девять инструментов", "Nine tools"),
"tools.h2":   ("Порядок в панели повторяет рабочий процесс",
               "The order in the panel follows the workflow"),
"tools.sub":  ("Проверить, почистить, при необходимости сшить отдельно, "
               "проконтролировать сборку. Пары проверки и очистки стоят рядом: "
               "полигоны и линии.",
               "Check, clean, snap separately if needed, verify the assembly. "
               "The check and cleanup pairs stand together: polygons and lines."),
"g1":         ("1. Топология", "1. Topology"),
"g2":         ("2. Генерализация", "2. Generalisation"),
"t101.h":     ("Проверка топологии полигонов", "Polygon topology check"),
"t101.p":     ("Слой точек с находками и сводка. Слой не изменяется.",
               "A point layer with the findings and a summary. The layer is not "
               "modified."),
"t102.h":     ("Проверка топологии линий", "Line topology check"),
"t102.p":     ("Недоводы, перелёты, висячие концы, псевдоузлы, пересечения "
               "без узла.",
               "Undershoots, overshoots, dangles, pseudo nodes, crossings without "
               "a node."),
"t103.h":     ("Очистка топологии полигонов", "Polygon topology cleanup"),
"t103.p":     ("Конвейер с фиксированным порядком шагов и гарантиями по смещению "
               "и потере площади.",
               "A pipeline with a fixed order of steps and guarantees on "
               "displacement and area loss."),
"t104.h":     ("Очистка топологии линий", "Line topology cleanup"),
"t104.p":     ("Обрезка перелётов, дотягивание недоводов, вставка узлов.",
               "Trimming overshoots, closing undershoots, inserting nodes."),
"t105.h":     ("Сшивка узлов и вершин", "Node and vertex snapping"),
"t105.p":     ("Слияние близких вершин с гарантией по смещению и вставка "
               "недостающих узлов.",
               "Merging close vertices with a displacement guarantee and "
               "inserting missing nodes."),
"t106.h":     ("Вставка недостающих узлов", "Insertion of missing nodes"),
"t106.p":     ("Только вставка. Форма и площадь не меняются вовсе.",
               "Insertion only. Shape and area do not change at all."),
"t107.h":     ("Контроль сборки по атрибуту", "Assembly check by attribute"),
"t107.p":     ("Собирается ли группа объектов в одно тело. Блоки, панели, стволы, "
               "водотоки.",
               "Whether a group of objects assembles into one body. Blocks, "
               "panels, shafts, watercourses."),
"t201.h":     ("Топологическое упрощение", "Topology-preserving simplification"),
"t201.p":     ("Общая граница прореживается один раз и остаётся общей. Полигоны "
               "и линии.",
               "A shared border is thinned once and stays shared. Polygons "
               "and lines."),
"t202.h":     ("Границы полигонов линиями", "Polygon borders as lines"),
"t202.p":     ("Каждая граница один раз, с признаком того, с чем граничит.",
               "Each border once, with a mark of what it borders on."),

"cases.eyebrow":("Что это даёт на данных", "What it gives on real data"),
"cases.h2":   ("Три случая, ради которых инструмент и появился",
               "Three cases the tool was made for"),
"cases.f1":   ("Недовод это след оцифровки, он чинится. Перелёт тоже. Висячий "
               "конец у гидросети или сети выработок это устье или тупик, поэтому "
               "решение остаётся человеку.",
               "An undershoot is a digitising trace and it is fixed. So is an "
               "overshoot. A dangle in a stream network or a set of mine workings "
               "is an outlet or a dead end, so the decision is left to the "
               "operator."),
"cases.f2":   ("Обычное упрощение обрабатывает каждый полигон отдельно, и одна "
               "граница прореживается дважды по-разному. На слое зон из 341 "
               "объекта это дало 46 перекрытий и 25 щелей. Топологическое "
               "упрощение не даёт ни одного.",
               "Ordinary simplification processes each polygon separately, and one "
               "border is thinned twice in different ways. On a zone layer of 341 "
               "objects that produced 46 overlaps and 25 gaps. The topological one "
               "produces none."),
"cases.f3":   ("Обычный перевод полигонов в линии выдаёт общую границу дважды: две "
               "совпадающие линии одна поверх другой, стиль ложится на обе. "
               "Инструмент 2.02 выдаёт её один раз и говорит, с чем она граничит.",
               "The usual conversion of polygons to lines outputs a shared border "
               "twice: two coincident lines stacked on each other, and the style "
               "lands on both. Tool 2.02 outputs it once and says what it borders "
               "on."),
"fact1":      ("вершин лежали точно на рёбрах соседей без узла на слое полигонов "
               "кригинга. После вставки узлов проверка не находит ничего, "
               "а суммарная площадь не изменилась.",
               "vertices lay exactly on neighbour edges without a node on a kriging "
               "polygon layer. After node insertion the check finds nothing and the "
               "total area is unchanged."),
"fact2":      ("находок на слое геомеханических зон после группировки по пласту. "
               "Три четверти были межпластовыми наложениями, то есть замыслом, "
               "а не ошибкой.",
               "findings on a geomechanical zone layer after grouping by seam. "
               "Three quarters were inter-seam overlaps, that is design rather "
               "than error."),
"fact3":      ("потерянных объектов при очистке. Правка, отнимающая больше "
               "четверти площади, отменяется, а объект уже допуска не изменяется "
               "и служит опорой для соседей.",
               "objects lost during cleanup. An edit taking more than a quarter of "
               "the area is cancelled, and an object narrower than the tolerance "
               "stays unchanged and serves as an anchor for its neighbours."),

"docs.eyebrow":("Документация", "Documentation"),
"docs.h2":    ("Руководство в комплекте, на двух языках",
               "The manual ships with the plugin, in two languages"),
"docs.sub":   ("Кнопка <b>Справка</b> в диалоге инструмента открывает PDF на языке "
               "интерфейса и работает без сети. Интерфейс двуязычный, язык берётся "
               "из локали QGIS. Все инструменты работают в моделях и в пакетном "
               "режиме, исходный слой не изменяется никогда.",
               "The <b>Help</b> button in a tool dialog opens the PDF in the "
               "interface language and works without a network. The interface is "
               "bilingual, the language comes from the QGIS locale. All tools work "
               "in models and in batch mode, and the input layer is never "
               "modified."),
"docs.fig":   ("Т-образный стык: справа два полигона сходятся в точке на ребре "
               "левого, а вершины там у левого нет. Границы совпадают "
               "геометрически, отрисовке это не мешает и на глаз не видно, "
               "но объединение по атрибуту оставляет в этом месте волосяную "
               "щель.",
               "A T-junction: two polygons on the right meet at a point on the "
               "left polygon edge, and the left one has no vertex there. The "
               "borders coincide geometrically, this does not affect rendering "
               "and is invisible to the eye, but a dissolve by attribute leaves "
               "a hairline sliver in that spot."),

"ftr.line1":  ("лицензия GNU GPL v3 или новее · QGIS 3.16 и новее",
               "GNU GPL v3 or later · QGIS 3.16 and newer"),
"ftr.line2":  ("Разработано ООО «Информ++»", "Developed by Inform++ LLC"),
"ftr.line3":  ("Плагин развивается на задачах реальных предприятий. Если вашему "
               "производству не хватает функции, напишите нам.",
               "The plugin grows on the tasks of real enterprises. If your "
               "operation is missing a feature, write to us."),
}


def dictionary():
    """Словарь для встраивания в страницу."""
    import json
    data = {"ru": {}, "en": {}}
    for key, (ru, en) in TEXTS.items():
        data["ru"][key] = ru
        data["en"][key] = en
    return json.dumps(data, ensure_ascii=False)


def tool_row(number, key):
    return ('<div class="tool"><div class="num">%s</div><div class="txt">'
            '<b data-i18n="%s.h"></b><span data-i18n="%s.p"></span>'
            '</div></div>' % (number, key, key))


PAGE = """<!-- ============================================================= -->
<!-- Topoliner - лендинг для www.informpp.ru                        -->
<!-- Самодостаточная двуязычная страница: схемы встроены в файл,    -->
<!-- переключатель языка работает без перезагрузки.                 -->
<!-- Собирается скриптом tools/build_site.py, править лучше его:    -->
<!-- тексты обоих языков лежат там в одном месте.                   -->
<!-- ============================================================= -->
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" data-i18n-attr="desc" content="">
<title data-i18n="title"></title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Bitter:wght@500;600;700\
&family=Golos+Text:wght@400;500;600&display=swap');

:root{
  --paper:#F1F3EE; --paper-2:#E7EBE3; --ink:#16221F; --ink-soft:#4C5A55;
  --teal:#0E7C66; --teal-deep:#0A5446; --amber:#C2622C;
  --line:rgba(22,34,31,.14); --r:14px; --maxw:1080px;
  --display:'Bitter',Georgia,serif; --body:'Golos Text','Segoe UI',system-ui,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
section[id],[id]{scroll-margin-top:74px}
body{margin:0;background:var(--paper);color:var(--ink);
  font-family:var(--body);font-size:17px;line-height:1.6;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 24px}
a{color:inherit}
h1,h2,h3{font-family:var(--display);font-weight:700;line-height:1.1;margin:0;
  letter-spacing:-.01em}
p{margin:0}
.eyebrow{font-size:13px;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:var(--teal-deep);margin-bottom:18px;
  display:inline-flex;gap:10px;align-items:center}
.eyebrow::before{content:"";width:26px;height:2px;background:var(--amber);
  display:inline-block}
.hdr{position:sticky;top:0;z-index:20;background:rgba(241,243,238,.86);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.hdr .wrap{display:flex;align-items:center;justify-content:space-between;
  height:62px;gap:18px}
.brand{display:flex;align-items:baseline;gap:10px;font-family:var(--display);
  font-weight:700;text-decoration:none;font-size:20px}
.brand span{font-family:var(--body);font-weight:500;font-size:13px;
  color:var(--ink-soft)}
.right{display:flex;align-items:center;gap:22px}
.nav{display:flex;gap:22px;font-size:15px}
.nav a{text-decoration:none;color:var(--ink-soft)}
.nav a:hover{color:var(--teal-deep)}
@media(max-width:860px){.nav{display:none}}
.lang{display:flex;border:1px solid var(--line);border-radius:10px;
  overflow:hidden;font-size:13px;font-weight:600}
.lang button{border:0;background:transparent;padding:6px 11px;cursor:pointer;
  font:inherit;color:var(--ink-soft)}
.lang button.on{background:var(--teal);color:#fff}
.hero{padding:74px 0 48px}
.hero h1{font-size:clamp(34px,5vw,56px);max-width:18ch}
.hero .lead{margin-top:22px;font-size:20px;max-width:64ch;color:var(--ink-soft)}
.cta{margin-top:34px;display:flex;gap:14px;flex-wrap:wrap}
.btn{display:inline-block;padding:13px 22px;border-radius:var(--r);
  text-decoration:none;font-weight:600;font-size:16px}
.btn-main{background:var(--teal);color:#fff}
.btn-main:hover{background:var(--teal-deep)}
.btn-ghost{border:1px solid var(--line);color:var(--ink)}
.btn-ghost:hover{border-color:var(--teal)}
section{padding:56px 0;border-top:1px solid var(--line)}
section h2{font-size:clamp(26px,3.3vw,38px);max-width:24ch}
section .sub{margin-top:16px;max-width:70ch;color:var(--ink-soft)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:34px}
@media(max-width:860px){.pair{grid-template-columns:1fr}}
.card{background:var(--paper-2);border:1px solid var(--line);
  border-radius:var(--r);padding:22px 24px}
.card h3{font-size:19px;margin-bottom:10px}
.card p{color:var(--ink-soft);font-size:16px}
figure{margin:30px 0 0}
figure img{width:100%;height:auto;display:block;border-radius:var(--r);
  border:1px solid var(--line);background:#fff}
figcaption{margin-top:10px;font-size:14px;color:var(--ink-soft)}
.tools{margin-top:34px;border:1px solid var(--line);border-radius:var(--r);
  overflow:hidden;background:#fff}
.tool{display:grid;grid-template-columns:88px 1fr;
  border-bottom:1px solid var(--line)}
.tool:last-child{border-bottom:none}
.tool .num{background:var(--paper-2);padding:16px 12px;font-weight:600;
  font-family:var(--display);color:var(--teal-deep);text-align:center}
.tool .txt{padding:16px 20px}
.tool .txt b{display:block;font-size:16px}
.tool .txt span{color:var(--ink-soft);font-size:15px}
.group{background:var(--paper-2);padding:10px 20px;font-size:13px;
  font-weight:600;letter-spacing:.1em;text-transform:uppercase;
  color:var(--teal-deep);border-bottom:1px solid var(--line)}
.facts{display:grid;grid-template-columns:repeat(3,1fr);gap:22px;margin-top:34px}
@media(max-width:860px){.facts{grid-template-columns:1fr}}
.fact{border-left:3px solid var(--amber);padding-left:16px}
.fact b{display:block;font-family:var(--display);font-size:30px;line-height:1.1}
.fact span{color:var(--ink-soft);font-size:15px}
.ftr{padding:40px 0 60px;border-top:1px solid var(--line);
  color:var(--ink-soft);font-size:15px}
.ftr a{color:var(--teal-deep)}
</style>

<header class="hdr">
  <div class="wrap">
    <a class="brand" href="#">Topoliner <span data-i18n="brand.sub"></span></a>
    <div class="right">
      <nav class="nav">
        <a href="#idea" data-i18n="nav.idea"></a>
        <a href="#tools" data-i18n="nav.tools"></a>
        <a href="#cases" data-i18n="nav.cases"></a>
        <a href="#docs" data-i18n="nav.docs"></a>
      </nav>
      <div class="lang">
        <button type="button" data-lang="ru">RU</button>
        <button type="button" data-lang="en">EN</button>
      </div>
    </div>
  </div>
</header>

<div class="wrap hero">
  <div class="eyebrow" data-i18n="hero.eyebrow"></div>
  <h1 data-i18n="hero.h1"></h1>
  <p class="lead" data-i18n="hero.lead"></p>
  <div class="cta">
    <a class="btn btn-main" data-i18n="cta.install"
       href="https://plugins.qgis.org/plugins/topoliner/"></a>
    <a class="btn btn-ghost" data-i18n="cta.code"
       href="https://github.com/Valery35/topoliner"></a>
  </div>
</div>

<section id="idea">
  <div class="wrap">
    <div class="eyebrow" data-i18n="idea.eyebrow"></div>
    <h2 data-i18n="idea.h2"></h2>
    <p class="sub" data-i18n="idea.sub"></p>
    <div class="pair">
      <div class="card"><h3 data-i18n="idea.c1.h"></h3>
        <p data-i18n="idea.c1.p"></p></div>
      <div class="card"><h3 data-i18n="idea.c2.h"></h3>
        <p data-i18n="idea.c2.p"></p></div>
    </div>
    <figure>
      <img alt=""__PAIR_overlap_width__>
      <figcaption data-i18n="idea.fig"></figcaption>
    </figure>
  </div>
</section>

<section id="tools">
  <div class="wrap">
    <div class="eyebrow" data-i18n="tools.eyebrow"></div>
    <h2 data-i18n="tools.h2"></h2>
    <p class="sub" data-i18n="tools.sub"></p>
    <div class="tools">
      <div class="group" data-i18n="g1"></div>
      __ROWS1__
      <div class="group" data-i18n="g2"></div>
      __ROWS2__
    </div>
  </div>
</section>

<section id="cases">
  <div class="wrap">
    <div class="eyebrow" data-i18n="cases.eyebrow"></div>
    <h2 data-i18n="cases.h2"></h2>
    <figure><img alt=""__PAIR_line_ends__>
      <figcaption data-i18n="cases.f1"></figcaption></figure>
    <figure><img alt=""__PAIR_simplify__>
      <figcaption data-i18n="cases.f2"></figcaption></figure>
    <figure><img alt=""__PAIR_shared_border__>
      <figcaption data-i18n="cases.f3"></figcaption></figure>
    <div class="facts">
      <div class="fact"><b>68</b><span data-i18n="fact1"></span></div>
      <div class="fact"><b>166 &rarr; 41</b><span data-i18n="fact2"></span></div>
      <div class="fact"><b>0</b><span data-i18n="fact3"></span></div>
    </div>
  </div>
</section>

<section id="docs">
  <div class="wrap">
    <div class="eyebrow" data-i18n="docs.eyebrow"></div>
    <h2 data-i18n="docs.h2"></h2>
    <p class="sub" data-i18n="docs.sub"></p>
    <figure><img alt=""__PAIR_missing_node__>
      <figcaption data-i18n="docs.fig"></figcaption></figure>
    <div class="cta">
      <a class="btn btn-main" data-i18n="cta.install"
         href="https://plugins.qgis.org/plugins/topoliner/"></a>
      <a class="btn btn-ghost" data-i18n="cta.code2"
         href="https://github.com/Valery35/topoliner"></a>
    </div>
  </div>
</section>

<footer class="ftr">
  <div class="wrap">
    Topoliner __VERSION__ &middot; <span data-i18n="ftr.line1"></span><br>
    <span data-i18n="ftr.line2"></span>,
    <a href="https://www.informpp.ru/">www.informpp.ru</a><br>
    <span data-i18n="ftr.line3"></span>
  </div>
</footer>

<script>
var TEXTS = __DICT__;

function apply(lang){
  var d = TEXTS[lang] || TEXTS.ru;
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(function(el){
    var value = d[el.getAttribute('data-i18n')];
    if (value !== undefined) el.innerHTML = value;
  });
  document.querySelectorAll('[data-i18n-attr]').forEach(function(el){
    var value = d[el.getAttribute('data-i18n-attr')];
    if (value !== undefined) el.setAttribute('content', value);
  });
  // Подписи внутри схем нарисованы, поэтому картинки меняются вместе с языком.
  document.querySelectorAll('img[data-fig-' + lang + ']').forEach(function(img){
    img.src = img.getAttribute('data-fig-' + lang);
  });
  document.querySelectorAll('.lang button').forEach(function(b){
    b.classList.toggle('on', b.getAttribute('data-lang') === lang);
  });
  try { localStorage.setItem('topoliner-lang', lang); } catch (e) {}
}

document.querySelectorAll('.lang button').forEach(function(b){
  b.addEventListener('click', function(){
    apply(b.getAttribute('data-lang'));
  });
});

// По умолчанию русский: страница живёт на русском сайте.
// Английский включается кнопкой, выбор запоминается.
var saved = null;
try { saved = localStorage.getItem('topoliner-lang'); } catch (e) {}
apply(saved || 'ru');
</script>
"""


def main():
    if not os.path.isdir(FIGURES):
        print("Нет doc/figures, сначала запустите tools/make_figures.py")
        return 1

    page = PAGE
    for name in ("overlap_width", "line_ends", "simplify",
                 "shared_border", "missing_node"):
        page = page.replace("__PAIR_%s__" % name, figure_pair(name))
    rows1 = "".join(tool_row(n, k) for n, k in (
        ("1.01", "t101"), ("1.02", "t102"), ("1.03", "t103"),
        ("1.04", "t104"), ("1.05", "t105"), ("1.06", "t106"),
        ("1.07", "t107")))
    rows2 = "".join(tool_row(n, k) for n, k in (
        ("2.01", "t201"), ("2.02", "t202")))
    page = page.replace("__ROWS1__", rows1)
    page = page.replace("__ROWS2__", rows2)
    page = page.replace("__DICT__", dictionary())
    page = page.replace("__VERSION__", read_version())

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(page)
    print("%-32s %7.1f КБ" % (os.path.relpath(OUT, ROOT),
                              os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
