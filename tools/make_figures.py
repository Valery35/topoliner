# -*- coding: utf-8 -*-
"""
Рисует иллюстрации для руководства.

Это не снимки экрана, а схемы: они объясняют понятие, а не показывают окно.
Снимки устаревают с каждой правкой интерфейса, схемы живут дольше и читаются
на печати.

    python tools/make_figures.py

Картинки складываются в doc/figures. Оттуда их берёт сборка руководства.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon as MplPolygon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "doc", "figures")

# Подписи внутри схем. Картинка не переключается на лету, поэтому каждая
# схема рисуется дважды: имя_ru.png и имя_en.png. Иначе на английской
# странице получаются английские тексты с русскими рисунками.
WORDS = {
    "before":      ("до сшивки", "before snapping"),
    "after":       ("после", "after"),
    "gap":         ("зазор", "gap"),
    "no_node":     ("узла нет", "no node"),
    "node_added":  ("узел вставлен", "node inserted"),
    "neighbour":   ("здесь стыкуются два правых полигона,\nа у левого узла нет",
                    "the two right polygons meet here,\nthe left one has no node"),
    "undershoot":  ("недовод", "undershoot"),
    "overshoot":   ("перелёт", "overshoot"),
    "dangle":      ("висячий конец", "dangle"),
    "fixed":       ("чинится", "fixed"),
    "operator":    ("решает человек", "operator decides"),
    "to_lines":    ("перевод в линии: две линии",
                    "polygons to lines: two lines"),
    "tool_202":    ("инструмент 2.02: одна", "tool 2.02: one"),
    "two_lines":   ("две линии\nодна поверх другой",
                    "two lines,\none on top of the other"),
    "kind_shared": ("kind = shared\nfid_a, fid_b",
                    "kind = shared\nfid_a, fid_b"),
    "separate":    ("по отдельности:", "separately:"),
    "became_two":  ("одна граница стала двумя", "one border became two"),
    "topological": ("топологическое:", "topological:"),
    "thinned_once":("граница прорежена один раз", "border thinned once"),
    "one_body":    ("одно тело", "one body"),
    "split":       ("разрыв", "break"),
    "two_bodies":  ("два тела: смотреть note", "two bodies: see note"),
    "narrow_strip":("узкая полоса: мусор, вычитается",
                    "narrow strip: debris, subtracted"),
    "wide_strip":  ("шире допуска: решает человек",
                    "wider than the tolerance: operator decides"),
    "width_less":  ("ширина меньше допуска", "width below the tolerance"),
    "kept_anchor": ("не изменяется, служит опорой",
                    "left unchanged, serves as an anchor"),
    "would_collapse": ("без защиты схлопнулся бы",
                       "without protection it would collapse"),
    "to_zero_area":("в линию нулевой площади", "into a line of zero area"),
}

LANG = "ru"


def W(key):
    """Подпись на текущем языке."""
    return WORDS[key][0 if LANG == "ru" else 1]

# Единая палитра: спокойные заливки, тёмный контур, красный для дефекта.
FILL_A = "#cfe3f2"
FILL_B = "#f6ddc0"
FILL_C = "#d8ead3"
EDGE = "#2b3d52"
BAD = "#c0392b"
GOOD = "#1e7a3c"
GREY = "#8b98a5"


def new_axes(width=5.2, height=2.6):
    fig, ax = plt.subplots(figsize=(width, height))
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax


def poly(ax, points, fill, alpha=1.0, lw=1.6, edge=EDGE):
    ax.add_patch(MplPolygon(points, closed=True, facecolor=fill,
                            edgecolor=edge, linewidth=lw, alpha=alpha,
                            zorder=1))


def line(ax, points, color=EDGE, lw=1.8, style="-", zorder=3):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    ax.plot(xs, ys, color=color, linewidth=lw, linestyle=style, zorder=zorder,
            solid_capstyle="round")


def dots(ax, points, color=EDGE, size=34, zorder=5):
    ax.scatter([p[0] for p in points], [p[1] for p in points],
               s=size, c=color, zorder=zorder, edgecolors="white", linewidths=0.8)


def caption(ax, x, y, text, color=EDGE, size=8.5, ha="center"):
    ax.text(x, y, text, color=color, fontsize=size, ha=ha, va="center",
            zorder=6)


def save(fig, name):
    """Кладёт схему с суффиксом языка: snap_ru.png, snap_en.png."""
    os.makedirs(OUT, exist_ok=True)
    stem, ext = os.path.splitext(name)
    path = os.path.join(OUT, "%s_%s%s" % (stem, LANG, ext))
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ────────────────────────────────────────────────────────────────────────────
# Схемы
# ────────────────────────────────────────────────────────────────────────────

def fig_snap_leader():
    """Слияние вершин по лидеру: гарантия по смещению."""
    fig, ax = new_axes(5.6, 2.4)
    for shift, title, done in ((0, W("before"), False), (7.2, W("after"), True)):
        left = [(0.2 + shift, 0), (3 + shift, 0), (3 + shift, 2.2),
                (0.2 + shift, 2.2)]
        gap = 0.0 if done else 0.45
        right = [(3 + gap + shift, 0), (5.8 + shift, 0), (5.8 + shift, 2.2),
                 (3 + gap + shift, 2.2)]
        poly(ax, left, FILL_A)
        poly(ax, right, FILL_B)
        if not done:
            # Зазор мелкий, поэтому подпись выносится в сторону с выноской.
            ax.annotate(W("gap"), xy=(3.22 + shift, 1.1),
                        xytext=(3.22 + shift, 3.1), color=BAD, fontsize=8.5,
                        ha="center",
                        arrowprops=dict(arrowstyle="-", color=BAD, lw=1.0))
        else:
            dots(ax, [(3 + shift, 0), (3 + shift, 2.2)], GOOD)
        caption(ax, 3 + shift, -0.5, title, GREY)
    ax.set_xlim(-0.3, 13.3)
    ax.set_ylim(-1.0, 3.5)
    return save(fig, "snap.png")


def fig_missing_node():
    """
    Т-образный стык: слева один полигон, справа два.

    Именно этот случай встречается на данных. Точка стыка двух правых
    полигонов лежит на ребре левого, и вершины там у левого нет: справа
    граница разбита на две, слева она одна сплошная. Пока узла нет,
    объединение по атрибуту оставляет в этом месте волосяную щель.
    """
    fig, ax = new_axes(5.8, 2.6)
    for shift, title, done in ((0, W("no_node"), False),
                               (7.4, W("node_added"), True)):
        left = [(0.2 + shift, 0), (3 + shift, 0), (3 + shift, 2.2),
                (0.2 + shift, 2.2)]
        upper = [(3 + shift, 1.1), (5.8 + shift, 1.1), (5.8 + shift, 2.2),
                 (3 + shift, 2.2)]
        lower = [(3 + shift, 0), (5.8 + shift, 0), (5.8 + shift, 1.1),
                 (3 + shift, 1.1)]
        poly(ax, left, FILL_A)
        poly(ax, upper, FILL_B)
        poly(ax, lower, FILL_C)

        # Углы, общие для всех трёх
        dots(ax, [(3 + shift, 0), (3 + shift, 2.2)], EDGE, size=22)
        # Точка стыка двух правых на ребре левого
        dots(ax, [(3 + shift, 1.1)], GOOD if done else BAD)
        caption(ax, 3 + shift, -0.5, title, GREY)

        if not done:
            ax.annotate(W("neighbour"), xy=(3 + shift, 1.1),
                        xytext=(3.5 + shift, 3.15), color=BAD, fontsize=8,
                        ha="left",
                        arrowprops=dict(arrowstyle="-", color=BAD, lw=1.0))
    ax.set_xlim(-0.3, 14.0)
    ax.set_ylim(-1.0, 3.7)
    return save(fig, "missing_node.png")


def fig_line_ends():
    """Недовод, перелёт, висячий конец."""
    fig, ax = new_axes(6.4, 2.3)
    line(ax, [(0.2, 1.0), (11.8, 1.0)], EDGE, 2.0)
    # недовод
    line(ax, [(2.0, 2.0), (2.0, 1.28)], BAD, 1.8)
    dots(ax, [(2.0, 1.28)], BAD)
    caption(ax, 2.0, 2.25, W("undershoot"), BAD)
    caption(ax, 2.0, 0.62, W("fixed"), GOOD, 7.5)
    # перелёт
    line(ax, [(5.5, 2.0), (5.5, 0.55)], BAD, 1.8)
    dots(ax, [(5.5, 0.55)], BAD)
    caption(ax, 5.5, 2.25, W("overshoot"), BAD)
    caption(ax, 5.5, 0.22, W("fixed"), GOOD, 7.5)
    # висячий конец
    line(ax, [(9.2, 2.0), (9.2, 1.0)], EDGE, 1.8)
    dots(ax, [(9.2, 2.0)], GREY)
    caption(ax, 9.2, 2.28, W("dangle"), GREY)
    caption(ax, 9.2, 0.62, W("operator"), GREY, 7.5)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 2.6)
    return save(fig, "line_ends.png")


def fig_shared_border():
    """Общая граница один раз против двух совпадающих линий."""
    fig, ax = new_axes(5.8, 2.5)
    for shift, title in ((0, W("to_lines")),
                         (7.0, W("tool_202"))):
        poly(ax, [(0.2 + shift, 0), (2.8 + shift, 0), (2.8 + shift, 2.2),
                  (0.2 + shift, 2.2)], FILL_A, alpha=0.35)
        poly(ax, [(2.8 + shift, 0), (5.4 + shift, 0), (5.4 + shift, 2.2),
                  (2.8 + shift, 2.2)], FILL_B, alpha=0.35)
        if shift == 0:
            line(ax, [(2.72 + shift, 0), (2.72 + shift, 2.2)], BAD, 2.2)
            line(ax, [(2.88 + shift, 0), (2.88 + shift, 2.2)], BAD, 2.2)
            caption(ax, 3.9 + shift, 1.1, W("two_lines"),
                    BAD, 8, "left")
        else:
            line(ax, [(2.8 + shift, 0), (2.8 + shift, 2.2)], GOOD, 2.2)
            caption(ax, 4.0 + shift, 1.1, W("kind_shared"),
                    GOOD, 8, "left")
        caption(ax, 2.8 + shift, -0.5, title, GREY)
    ax.set_xlim(-0.3, 15.4)
    ax.set_ylim(-1.0, 2.6)
    return save(fig, "shared_border.png")


def fig_simplify():
    """Упрощение по отдельности разводит общую границу."""
    fig, ax = new_axes(6.0, 2.8)

    # Извилистая общая граница и её два разных упрощения
    detailed = [(0.0, 0.0), (0.5, 0.5), (-0.4, 1.0), (0.6, 1.5), (0.0, 2.2)]
    thin_a = [(0.0, 0.0), (0.5, 0.5), (0.0, 2.2)]        # так упростил левый
    thin_b = [(0.0, 0.0), (0.6, 1.5), (0.0, 2.2)]        # так упростил правый

    def block(shift, left_line, right_line, torn):
        left = [(-2.4 + shift, 0)] + [(x + shift, y) for x, y in left_line] + \
               [(-2.4 + shift, 2.2)]
        right = [(2.6 + shift, 0), (2.6 + shift, 2.2)] + \
                [(x + shift, y) for x, y in reversed(right_line)]
        poly(ax, left, FILL_A)
        poly(ax, right, FILL_C)
        if torn:
            # Показываем расхождение: две разные линии на месте одной границы
            line(ax, [(x + shift, y) for x, y in left_line], BAD, 2.0)
            line(ax, [(x + shift, y) for x, y in right_line], BAD, 2.0, "--")
        else:
            line(ax, [(x + shift, y) for x, y in left_line], GOOD, 2.2)

    block(0.0, thin_a, thin_b, True)
    caption(ax, 0.1, -0.6, W("separate"), BAD)
    caption(ax, 0.1, -1.05, W("became_two"), BAD, 8)

    block(7.0, detailed, detailed, False)
    caption(ax, 7.1, -0.6, W("topological"), GOOD)
    caption(ax, 7.1, -1.05, W("thinned_once"), GOOD, 8)

    ax.set_xlim(-2.8, 10.0)
    ax.set_ylim(-1.5, 2.6)
    return save(fig, "simplify.png")


def fig_assembly():
    """Контроль сборки: группа собирается или распадается."""
    fig, ax = new_axes(5.8, 2.4)
    # собирается
    poly(ax, [(0.2, 0), (1.6, 0), (1.6, 2.2), (0.2, 2.2)], FILL_C)
    poly(ax, [(1.6, 0), (3.2, 0), (3.2, 2.2), (1.6, 2.2)], FILL_C)
    caption(ax, 1.7, -0.5, W("one_body"), GOOD)
    # распадается
    poly(ax, [(5.4, 0), (6.8, 0), (6.8, 2.2), (5.4, 2.2)], FILL_C)
    poly(ax, [(7.3, 0), (8.9, 0), (8.9, 2.2), (7.3, 2.2)], FILL_C)
    ax.annotate("", xy=(7.3, 1.1), xytext=(6.8, 1.1),
                arrowprops=dict(arrowstyle="<->", color=BAD, lw=1.4))
    caption(ax, 7.05, 1.5, W("split"), BAD)
    caption(ax, 7.15, -0.5, W("two_bodies"), BAD)
    ax.set_xlim(-0.2, 9.3)
    ax.set_ylim(-1.0, 2.6)
    return save(fig, "assembly.png")


def fig_overlap_width():
    """Перекрытие оценивается шириной, а не площадью."""
    fig, ax = new_axes(6.0, 2.5)
    poly(ax, [(0.2, 0.9), (5.4, 0.9), (5.4, 2.1), (0.2, 2.1)], FILL_A, alpha=0.6)
    poly(ax, [(0.2, 0.75), (5.4, 0.75), (5.4, 1.05), (0.2, 1.05)], FILL_B, alpha=0.9)
    caption(ax, 2.8, 0.35, W("narrow_strip"), GOOD, 8.5)
    poly(ax, [(7.0, 1.4), (11.6, 1.4), (11.6, 2.4), (7.0, 2.4)], FILL_A, alpha=0.6)
    poly(ax, [(7.0, 0.5), (11.6, 0.5), (11.6, 1.9), (7.0, 1.9)], FILL_B, alpha=0.6)
    caption(ax, 9.3, 0.1, W("wide_strip"), BAD, 8.5)
    ax.set_xlim(0, 11.8)
    ax.set_ylim(-0.2, 2.7)
    return save(fig, "overlap_width.png")


def fig_narrow_object():
    """Объект уже допуска схлопывается при сшивке."""
    fig, ax = new_axes(5.6, 2.2)
    poly(ax, [(0.2, 0.9), (4.6, 0.9), (4.6, 1.25), (0.2, 1.25)], FILL_B)
    ax.annotate("", xy=(0.2, 1.6), xytext=(4.6, 1.6),
                arrowprops=dict(arrowstyle="<->", color=GREY, lw=1.0))
    caption(ax, 2.4, 1.85, W("width_less"), GREY, 8)
    caption(ax, 2.4, 0.45, W("kept_anchor"), GOOD, 8.5)
    line(ax, [(7.0, 1.05), (11.4, 1.05)], BAD, 2.4)
    caption(ax, 9.2, 1.55, W("would_collapse"), BAD, 8.5)
    caption(ax, 9.2, 0.45, W("to_zero_area"), BAD, 8)
    ax.set_xlim(0, 11.6)
    ax.set_ylim(0.1, 2.2)
    return save(fig, "narrow.png")


FIGURES = [fig_snap_leader, fig_missing_node, fig_line_ends, fig_shared_border,
           fig_simplify, fig_assembly, fig_overlap_width, fig_narrow_object]


def main():
    global LANG
    made = []
    for language in ("ru", "en"):
        LANG = language
        for func in FIGURES:
            made.append(func())
    LANG = "ru"
    print("Схем нарисовано: %d" % len(made))
    for path in made:
        size = os.path.getsize(path) / 1024.0
        print("  %-22s %6.1f КБ" % (os.path.basename(path), size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
