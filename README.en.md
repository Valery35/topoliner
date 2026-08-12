# Topoliner

[Русская версия](README.md)

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
| 1.01 Topology check | Finds violations, produces a point layer and a summary | No |
| 1.02 Topology cleanup (all at once) | Fixes what is technical debris | Yes, into a new layer |
| 1.03 Topology snap (nodes and vertices) | Brings borders to an exact match | Yes, into a new layer |
| 1.04 Assembly check by attribute | Checks whether groups assemble into one body | No |
| 1.05 Insert missing nodes | Adds nodes without changing shape or area | Yes, into a new layer |
| 2.01 Topology-preserving simplify | Thins vertices without tearing shared borders | Yes, into a new layer |

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

Short manual: [MANUAL.en.md](MANUAL.en.md).
Design notes and the classification of violations: [DETAILS.en.md](DETAILS.en.md).

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
