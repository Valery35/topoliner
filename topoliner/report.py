# -*- coding: utf-8 -*-
"""
report
------
Текстовый отчёт о находках.

Слой точек хорош, чтобы увидеть место на карте, но плох, чтобы передать
результат человеку, который данные готовил. Ему нужен список: номер, что
не так, у каких объектов, где именно. По номеру находка ищется в слое,
по идентификатору объекта - в исходных данных.

Предложение Ивана Иванова после публикации на GIS-Lab: нумерованный список
найденного и слой с отметками, чтобы автор данных мог посмотреть и оригинал,
и результат.

Чистый Python, без QGIS.
"""

try:  # внутри плагина QGIS
    from .i18n import is_russian
    from .rounding import fmt
    from . import topo_checks as tc
except ImportError:  # headless-тесты
    from i18n import is_russian
    from rounding import fmt
    import topo_checks as tc

__all__ = ["build_report"]


def build_report(findings, summary, header=None, tolerance=None,
                 area_threshold=None, hint=None):
    """
    Собирает отчёт как список строк.

    findings  находки с проставленными номерами
    summary   сводка по типам
    header    название слоя и прочее, что стоит записать сверху
    hint      подсказка по допуску, если считалась

    Возвращает текст одной строкой.
    """
    lines = []
    russian = is_russian()

    def line(text=""):
        lines.append(text)

    line(header or ("Topoliner. Отчёт о проверке топологии" if russian
                    else "Topoliner. Topology check report"))
    line("=" * 70)
    line()

    if tolerance is not None:
        line((("Допуск: %s" if russian else "Tolerance: %s") % fmt(tolerance)))
    if area_threshold is not None:
        line((("Порог площади: %s" if russian else "Area threshold: %s")
              % fmt(area_threshold)))
    line()

    if not findings:
        line("Нарушений не найдено." if russian else "No violations found.")
        return "\n".join(lines)

    # ── Сводка по типам ──────────────────────────────────────────────────
    line("Сводка" if russian else "Summary")
    line("-" * 70)
    order = sorted(summary.items(),
                   key=lambda kv: -(kv[1]["auto"] + kv[1]["review"]))
    for kind, slot in order:
        total = slot["auto"] + slot["review"]
        line("%-44s %6d  %s %d  %s %d"
             % (tc.label_of(kind), total,
                "чинится" if russian else "auto", slot["auto"],
                "решать" if russian else "review", slot["review"]))
    line()

    if hint:
        line("Расхождения вершин с рёбрами соседей" if russian
             else "Discrepancies between vertices and neighbour edges")
        line("-" * 70)
        line(("медиана %s, 95 процентиль %s, максимум %s" if russian
              else "median %s, 95th percentile %s, maximum %s")
             % (fmt(hint["median"]), fmt(hint["p95"]), fmt(hint["max"])))
        if hint.get("gap_at"):
            line(("разрыв в распределении около %s" if russian
                  else "break in the distribution around %s")
                 % fmt(hint["gap_at"]))
        if hint.get("ceiling"):
            line(("выше %s допуск брать не следует" if russian
                  else "the tolerance should not exceed %s")
                 % fmt(hint["ceiling"]))
        line()

    # ── Разбор человеком ─────────────────────────────────────────────────
    review = [f for f in findings if f["severity"] == tc.SEVERITY_REVIEW]
    auto = [f for f in findings if f["severity"] == tc.SEVERITY_AUTO]

    if review:
        line("Решать человеку" if russian else "Left to the operator")
        line("-" * 70)
        for f in review:
            line(_describe(f, russian))
        line()

    if auto:
        line("Чинится автоматически" if russian else "Fixed automatically")
        line("-" * 70)
        for f in auto:
            line(_describe(f, russian))
        line()

    line("-" * 70)
    line(("Всего %d, из них решать человеку %d" if russian
          else "Total %d, of which left to the operator %d")
         % (len(findings), len(review)))
    return "\n".join(lines)


def _describe(finding, russian):
    """Одна строка списка: номер, тип, объекты, координаты, пояснение."""
    parts = ["%5d" % finding.get("num", 0), "%-34s" % tc.label_of(finding["type"])]

    who = []
    if finding.get("fid") is not None:
        who.append(str(finding["fid"]))
    if finding.get("fid_b") is not None:
        who.append(str(finding["fid_b"]))
    parts.append(("объекты " if russian else "objects ") + ", ".join(who)
                 if who else "")

    if finding.get("x") is not None:
        parts.append("%.2f %.2f" % (finding["x"], finding["y"]))

    note = finding.get("note") or ""
    if note:
        parts.append(note)
    return "  ".join(p for p in parts if p)
