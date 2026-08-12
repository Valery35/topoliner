# Topoliner

[Русская версия](README.md) · **English**

[![Install in QGIS](https://img.shields.io/badge/Install%20in%20QGIS-blue.svg)](https://plugins.qgis.org/plugins/topoliner/)
[![Plugin page](https://img.shields.io/badge/Plugin%20page-0f766e.svg)](https://www.informpp.ru/)

A QGIS plugin for bringing polygon coverages into order: topology check,
automatic cleanup, border snapping, insertion of missing nodes, assembly check
by attribute and simplification that keeps shared borders shared.

All tools live in the Processing panel and work in models and in batch mode.
The input layer is never modified: every result goes to a new layer.

Interface in English and Russian, chosen by the QGIS locale.

## Why

The usual manual routine looks like this: snap a layer to itself with some
tolerance, then dissolve without attributes, then stare at the result looking
for scratches. It is well known, repeatable and done by hand every time.
The plugin does the same thing reproducibly, with a numeric report
and with guarantees.

## Tools

| Tool | What it does | Modifies the layer |
|---|---|---|
| 1.01 Polygon topology check | Finds violations, produces a point layer and a summary | No |
| 1.02 Line topology check | Undershoots, overshoots, dangles | No |
| 1.03 Polygon topology cleanup | Fixes what is technical debris | Yes, into a new layer |
| 1.04 Line topology cleanup | Fixes what is a digitising trace | Yes, into a new layer |
| 1.05 Node and vertex snapping | Brings borders to an exact match | Yes, into a new layer |
| 1.06 Insertion of missing nodes | Adds nodes without changing shape or area | Yes, into a new layer |
| 1.07 Assembly check by attribute | Checks whether groups assemble into one body | No |
| 2.01 Topology-preserving simplify | Thins vertices without tearing shared borders | Yes, into a new layer |
| 2.02 Polygon borders as lines | Outputs borders as separate lines, each one once | No |

## The main principle

Automation cannot know which of two disputed borders is correct. What it can
tell is scale: a centimetre overlap is a digitising error, a hectare one is
a disagreement between sources. Behaviour is therefore set by two thresholds,
a tolerance in length units and an area threshold. Anything above them is left
to the operator and is never fixed automatically under any settings.

## Guarantees

- No vertex moves further than the tolerance.
- An edit that takes more than a quarter of an object's area is cancelled.
- Objects narrower than the tolerance are left untouched and serve as anchors.
- A repeat run over the result changes nothing.
- Attributes are preserved; objects are never deleted without explicit permission.
- Insertion of missing nodes does not change the area at all.

## Installation

From the QGIS plugin repository, or from a ZIP file:
**Plugins - Manage and Install Plugins - Install from ZIP**.
Restarting QGIS is not required.

## Documentation

The manual in PDF ships with the plugin: `topoliner/doc/Topoliner_en.pdf`.
The **Help** button in a tool dialog opens it in the interface language.

Sources: [doc/MANUAL.en.md](doc/MANUAL.en.md), design notes and the
classification of violations - [doc/DETAILS.en.md](doc/DETAILS.en.md).

## Development

```
cd topoliner
python -m unittest discover -s tests -v
```

QGIS is not needed for the tests. The geometric logic is kept out of QGIS:
the core works with plain coordinate lists, and intersection operations go
through an adapter that has a Shapely implementation. Shapely uses the same
GEOS as QGIS, so the behaviour matches production.

Building the archives:

```
python tools/build_zip.py
```

## License

GNU GPL version 3 or later, see [LICENSE](LICENSE).
