# Topoliner. Design notes

[Русская версия](DETAILS.md)

## Classification of topology violations

An "do everything" button is only possible with an honest split: only what is
certainly technical debris gets fixed silently. Anything that may carry meaning
is reported and never touched under any settings.

The line is drawn by two thresholds: a **tolerance** in length units and
an **area threshold**.

| Violation | What it is | Decision |
|---|---|---|
| Repeated vertices | Zero-length segments, a digitising trace | Auto: removed |
| Spike | The line turns back on itself at one vertex | Auto: removed by angle |
| Vertex on a neighbour edge without a node | Borders coincide geometrically but not by vertices | Auto: a node is inserted |
| Edges crossing without shared vertices | Edges cross each other | Auto: nodes at the intersections |
| Vertex discrepancy below the tolerance | A gap or overlap from manual digitising | Auto: vertices are merged |
| Tiny hole | A hole smaller than the area threshold | Auto: filled |
| Tiny part | A part of a multipolygon below the threshold | Auto: removed |
| Invalid geometry | Self-intersection, loop, hole outside the shell | Auto with control: the edit is cancelled if more than a quarter of the area is lost |
| Narrow overlap | A strip narrower than the tolerance | Auto: subtracted from the loser by the priority rule |
| Small gap | A closed hole in the coverage below the threshold | Auto: goes to the neighbour with the longest shared border |
| Wide overlap | Two objects disputing real area | Operator: a meaningful conflict, not debris |
| Large gap | An unmapped area | Operator: there may genuinely be no data there |
| Duplicate object | Fully coincident geometries | Operator: the attributes may differ |
| Nested object | One polygon entirely inside another | Operator: an enclave can be legitimate |
| Sliver polygon | Effective width below the tolerance with noticeable area | Operator: it can also be a real narrow body |
| Tiny object | The whole object is below the threshold | Operator by default: deleting it destroys its attributes |
| Ring self-touch | A ring touches itself at a point | Operator: the resolution is ambiguous |
| Lost object | The object vanished during repair | Operator: reported as a separate warning |

### What the button cannot do in principle

Automation cannot know which of two disputed borders is correct. It can only
tell scale: a centimetre overlap is certainly an error, a hectare one is
a disagreement between sources. Wide overlaps, large gaps, duplicates and
nested objects therefore always stay with the operator.

### The gap limitation

Gaps are found as holes in the union of the coverage. A gap reaching the outer
edge of the coverage is not a hole and is not found this way. Such gaps are
closed by vertex snapping when their width is below the tolerance. This is
pinned by the test `test_open_gap_is_not_a_hole` and closed by
`test_open_gap_is_closed_by_snapping`.

---

## 1.01 Topology check

The layer is not modified. The output is a point layer with the fields `type`,
`label`, `severity`, `fid_a`, `fid_b`, `value`, `note`, `grp`, plus a summary
in the Processing panel. The `severity` field takes the values `auto` and
`review` according to the table above.

The tool answers the main question before cleaning: how much will go silently
and how much has to be looked at by hand.

---

## 1.02 Topology cleanup (all at once)

The order of steps is fixed:

1. removal of repeated vertices and spikes,
2. removal of tiny parts and filling of tiny holes,
3. snapping: merging close vertices and inserting missing nodes,
4. repair of invalid geometry with area loss control,
5. subtraction of narrow overlaps by the priority rule,
6. handing small gaps to the neighbour with the longest shared border.

Step 3 comes after vertex cleaning on purpose: otherwise spikes and duplicates
turn into false nodes and get spread across neighbours. Step 4 comes after
snapping, because snapping can itself produce a self-intersection. Steps 5
and 6 come last, as they work on an already reconciled coverage.

### Guarantees

- No vertex moves further than the tolerance.
- An edit taking more than a quarter of an object's area is cancelled; the
  object stays as it was and goes into the remaining problems.
- A repeat run over the result changes nothing.
- Attributes are preserved. Objects are never deleted without permission.

---

## 1.03 Topology snap (nodes and vertices)

Replaces the manual routine of snapping a layer to itself with vertex
insertion, followed by a dissolve without attributes as a check.

**Node insertion.** A vertex of one object lies on the edge of another and
there is no node there. A node is inserted; existing vertices stay in place.
It is exactly the absence of such nodes that makes a dissolve leave hairline
slivers.

**Vertex merging.** Vertices closer than the tolerance are brought to a single
point. Clustering is greedy by leader: vertices are traversed in a fixed order,
the first free one becomes the leader and never moves again, and the others
within the tolerance are attracted to it.

### The displacement guarantee

No vertex moves further than the tolerance. This follows from the leader
scheme: the leader is chosen once and stays put, so chains of the form
"A pulled B, B pulled C" that drag geometry beyond the tolerance are
impossible. A classical snap of a layer to itself gives no such guarantee.

### Objects narrower than the tolerance

Such an object would have its opposite banks stick together and would collapse
into itself. By default it is left untouched and serves as an anchor: the
neighbours are pulled towards it. Advising a smaller tolerance would not help,
because a tolerance below the narrowest object stops closing real
discrepancies.

---

## 1.04 Assembly check by attribute

The union of objects sharing an attribute value must give exactly one part
without interior rings. The tool checks this across all groups at once and
replaces the manual union followed by staring at the result.

It finds what a coverage-wide gap search cannot see: a gap reaching the outer
edge is not a hole in the union, yet it cuts the group in two during assembly.
Pinned by the test `test_open_gap_splits_the_group`.

The `note` field of a finding holds the distance to the nearest part of the
group, which is exactly the tolerance that was missing.

Parts are grouped into bodies by connectivity: two parts belong to one body
if the distance between them is not greater than the **maximum gap** parameter.
Only a split within a body counts as a break; separate bodies are legitimate.
Zero means the group must be whole, which is the mode for zones, blocks
and panels.

---

## 1.05 Insert missing nodes

Only insertion. No existing vertex is moved or deleted, so the total area stays
exactly the same rather than approximately the same. A node is placed at the
projection of the point onto the edge, that is strictly on the line of that
edge, so the shape does not change and a self-intersection has nowhere to come
from.

Several passes may be required: an inserted node sometimes lands on the edge
of a third object. On a real kriging polygon layer the passes produced 136,
56 and 10 nodes, after which the findings were exhausted.

---

## 2.01 Topology-preserving simplify

Rings are broken into edges; an edge is identified by its pair of ends
regardless of direction, so the same edge of two neighbours yields a single
record. Edges are glued into arcs: a chain continues while exactly two edges
with the same owner set meet at a vertex, and breaks at a branch node. Each arc
is thinned exactly once, so both neighbours receive the same result. Arc ends
are fixed, so the nodes where three polygons meet do not move.

Measured on a zone layer of 341 objects with a tolerance of 5: independent
simplification gives 46 overlaps, 25 gaps and 189 mismatched nodes, while the
topological one gives none.

---

## Structure

```
topoliner/
  topo_core.py          snapping core, plain Python, no QGIS dependency
  topo_checks.py        checks and the cleanup pipeline
  topo_simplify.py      arcs and Douglas-Peucker thinning
  geom_backend.py       geometry adapter: QGIS in production, Shapely in tests
  topo_algorithm.py     Processing wrappers for 1.03 and 1.05
  audit_algorithms.py   Processing wrappers for 1.01, 1.02 and 1.04
  simplify_algorithm.py Processing wrapper for 2.01
  i18n.py               interface translation
  help_texts.py         tool help in two languages
  provider.py           algorithm registration
  tests/                tests
```

Tests:

```
cd topoliner
python -m unittest discover -s tests -v
```

QGIS is not needed: the core works with plain coordinate lists, and the
intersection operations go through an adapter that has a Shapely
implementation. Shapely uses the same GEOS as QGIS, so the behaviour matches
production.
