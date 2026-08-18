# FAI Sporting Code S7F 2026 conformance audit

**Date:** 2026-08-18
**Spec:** FAI Sporting Code, Section 7F — XC Scoring, **2026 Edition V1.0**, effective 1 May 2026
(document history: 2026-04-17, Jörg Ewald)
**Source:** [`Sporting Code S7 F - XC Scoring 2026_V1.0.pdf`](https://www.fai.org/sites/default/files/2026-05/Sporting%20Code%20S7%20F%20-%20XC%20Scoring%202026_V1.0.pdf),
listed on [fai.org/civl-documents](https://www.fai.org/civl-documents).
56 pages, `sha256:6a0f400bf8970c1199f5366ad40c53430be340da42455b1b11b7008ed7b4458e`.
**Also read:** the [2024 edition](https://www.fai.org/sites/default/files/civl/documents/sporting_code_s7_f_-_xc_scoring_2024.pdf)
(64 pages, `sha256:c9f4a5dd37477ffefded6679711b2e314d532ca268d78f74cc41f99c628756ae`), which
parts of the library were written against — see [Spec lineage](#spec-lineage).
**Code audited:** `main` at `8522ea7`. Test suite green (18 skips, all in
`tests/distance/test_xctrack_accuracy.py`, concentric-turnpoint cases).
**Predecessor:** [2026-07-07 route-optimization audit](./2026-07-07-route-optimization-audit.md),
resolved by PR [#8](https://github.com/simonsteiner/pyxctsk/pull/8). This audit re-checks
everything that one raised and covers the sections it did not.

---

## Open issues

Status values: **open**, **in progress**, **fixed** (name the PR/commit), **won't fix** (say why).
Edit the table in place; the finding sections below keep the reproduction as first written,
so a fixed finding still says what it was and how it was measured.

**All eight actionable issues are fixed.** S7F-09 is not actionable in this library.

| ID | § | Severity | Status | Summary |
| --- | --- | --- | --- | --- |
| [S7F-01](#s7f-01--the-goal-line-still-follows-the-2024-orientation-rule) | 6.2.3.1 | **High** | **fixed** `2800429` | Goal line now oriented from the optimized route point; the 2024 rule stays reachable as `GoalLineOrientation.TURNPOINT_CENTERS` |
| [S7F-02](#s7f-02--speed-section-distance-is-not-computed) | 7.2 | Medium | **fixed** `5ec661a` | `SpeedSection` — its own `taskToESS` optimization, since the ESS route is not a prefix of the task route |
| [S7F-03](#s7f-03--the-task-area-centre-is-not-findtaskareacentre) | 7.1.6 | Medium | **fixed** `50dae97`, `278ab2b` | Bounding-box centre with §7.1.6.1 antimeridian handling, and the second pass that re-centres on the corrected path |
| [S7F-04](#s7f-04--the-optimizer-can-settle-in-a-local-optimum) | 7 | Low | **fixed** `278ab2b` | Multi-start from three deterministic placements. Worst projection sensitivity across the corpus: 98.6 m → 10 mm |
| [S7F-05](#s7f-05--the-ltm-scale-factor-is-1-not-099994) | 7.1.2 | Low | **fixed** `17ce2de` | `ltm_scale_factor` applies k₀ = 0.99994, latitude-dependent above 55°, written as `+k_0` |
| [S7F-06](#s7f-06--the-elevated-goal-ceiling-is-not-validated) | 6.2.3.2 | Low | **fixed** `e71b3de` | `FINISH_ALTITUDE_OUT_OF_RANGE`, checked in both formats |
| [S7F-07](#s7f-07--an-elevated-goal-implicitly-is-the-ess) | 6.2.3.2 | Low | **fixed** `e71b3de` | `ELEVATED_GOAL_IS_NOT_ESS` reports the contradiction; `is_ess_goal()` deliberately unchanged |
| [S7F-08](#s7f-08--fai_sphere-distances-are-not-s7f-task-distances) | 4.1, 4.2 | Info | **fixed** | Recorded in `distance/__init__.py`; deliberately not a validation rule |
| [S7F-09](#s7f-09--shapes-the-xctrack-format-cannot-carry) | 6.2.1, 6.2.2 | Info | **won't fix** — not ours to fix | The XCTrack format defines no keys for either, so they cannot become model fields without inventing spec. What *is* in our hands is pinned: a producer's own keys survive both round trips uninterpreted |

---

## Scope

S7F is a **scoring** code. pyxctsk is a task-format library with a task-distance
calculator; it reads no tracklogs and awards no points. The audit therefore covers the
sections that describe the task and its geometry, and states the rest as out of scope:

| S7F section | In scope | Why |
| --- | --- | --- |
| 3 Definitions, 4 Measurements | ✅ | Position, distance, earth model |
| 5 Competition Parameters | ❌ | Nominal/minimum distance, FTV — scoring inputs |
| 6 Task Setting | ✅ | Control zones, goal, elevated goal, task types |
| 7 Task and flight distance calculations | ✅ | The whole of `distance/` |
| 8 Flying a task, 9 Task evaluation | ❌ | Needs tracklogs: crossings, tolerances, validation times |
| 10–16 Validity, points, ranking, FTV | ❌ | Scoring |
| Annex A (projection), Annex B (lines in PathFinder) | ✅ | Cited by §7 |

One structural note that shapes everything below: pyxctsk implements **XCTrack's task
format**, not S7F's task model. Where the two disagree about what a task can express
(§6.2.1 altitude limits, §6.2.2 line control zones), the format wins and the gap is
recorded rather than treated as a defect — see [S7F-09](#s7f-09--shapes-the-xctrack-format-cannot-carry).

---

## Spec lineage

**As audited, pyxctsk implemented two different editions of S7F at once**, and knowing
which is which explains most of the findings below. The optimizer was migrated from the
2024 edition to the 2026 one by PR [#8](https://github.com/simonsteiner/pyxctsk/pull/8);
the goal line was not, and still implemented 2024.

> **Since resolved.** `2800429` moved the goal line to 2026, so the library is on one
> edition throughout. The 2024 rule is still reachable as
> `GoalLineOrientation.TURNPOINT_CENTERS` — see [S7F-01](#s7f-01--the-goal-line-still-follows-the-2024-orientation-rule).

The 2025 edition (§2.1.1.14) is where the geometry rules changed. Its own change list,
filtered to what this library does:

| 2025 change | § | in pyxctsk |
| --- | --- | --- |
| 7. *"Orientation of Goal Line: Follow optimized route, instead of turnpoint centres."* | 6.2.3.1 | ✅ `2800429` — [S7F-01](#s7f-01--the-goal-line-still-follows-the-2024-orientation-rule), the finding this audit opened with |
| 9. *"Define projection algorithm for planar calculations"* | 7.1.2 | ✅ PR #8, completed by `17ce2de` ([S7F-05](#s7f-05--the-ltm-scale-factor-is-1-not-099994)) and `50dae97`+`278ab2b` ([S7F-03](#s7f-03--the-task-area-centre-is-not-findtaskareacentre)) |
| 10. *"New definition of algorithm for route optimization"* | 7.1.3 | ✅ PR #8; `278ab2b` made it find the *shortest* path rather than a local optimum ([S7F-04](#s7f-04--the-optimizer-can-settle-in-a-local-optimum)) |
| 11. *"Define algorithm for geodesic calculations"* | 7.1.4, 7.1.5 | ✅ PR #8 |
| 8. Rename "Race to Goal" → "Race", "Elapsed Time" → "Time Trial" | 6.2.3.2 | n/a — `SSSType` spells XCTrack's `RACE` / `ELAPSED-TIME`, which is the format's vocabulary, not S7F's |

Items 9, 10 and 11 are between them the first four findings of the 2026-07-07 audit, and
they are done. Item 7 is the one left behind — and that audit had already spotted it,
noting under "2024 vs 2026 differences" that *"2025/2026 added: goal-line orientation
follows the optimized route"*, then filing the goal line itself as its lowest-priority
finding on the strength of a guess. It was the only geometry rule from that list still
outstanding when this audit was written.

Two more rules are **new in 2026** (§2.1.1.15), so nothing predating this year could have
implemented them:

| 2026 change | § | in pyxctsk |
| --- | --- | --- |
| 1. *"Introduces Elevated Goal"* | 6.2.3.2 | ✅ `e71b3de` — the field round-trips and both of §6.2.3.2's constraints are now checked ([S7F-06](#s7f-06--the-elevated-goal-ceiling-is-not-validated), [S7F-07](#s7f-07--an-elevated-goal-implicitly-is-the-ess)) |
| 3. *"Introduces upper and lower limits for control zones"* | 6.2.1, 6.2.2 | ❌ [S7F-09](#s7f-09--shapes-the-xctrack-format-cannot-carry) — no representation in the XCTrack format, so not ours to add |

---

## What is conformant

Verified against the code and, where a number is claimed, by running the library over
the 24-task reference corpus.

- **§4.1/§4.2, §7.1.4, §7.1.5 — distances on the WGS84 ellipsoid.** Every leg is
  measured with `pyproj.Geod(ellps="WGS84").inv`, i.e. Karney (2013) — one of the three
  algorithms §7.1.4 names, and the one §7.1.5 asks for when only the distance is needed.
  `distance/turnpoint.py:geodesic_distance`.
- **§7.1.3 — PathFinder is the algorithm the spec cites.** `plane_optimal_point`
  implements Ding–Xie–Jiang GetOptPi with both branches: the *crossing* case (segment
  meets the boundary, including the one-neighbour-inside case of their Theorem 1) and the
  *reflection* point-circle-point case. `_optimize_plane_points` alternates odd- and
  even-indexed sweeps. The 2026-07-07 audit's findings 1 and 3 are resolved.
- **§7.1.3 — ε = 0.1 m, and it is actually converged.** `CONVERGENCE_EPSILON_M = 0.1`.
  Tightening it to 1e-9 with 5000 sweeps moves `task_bevo` by 9 mm
  (94 028.282 m → 94 028.273 m), so the shipped threshold is not cutting the iteration
  short. The 2026-07-07 audit's finding 4 is resolved.
- **§7.1.2 / §7.1.7 — the plane and the correction exist.** Optimization runs in a local
  Transverse Mercator plane and each point is re-placed at exactly *r* along the
  centre→point geodesic before the legs are measured
  (`snap_to_boundary`, `route_optimization.py`). The 2026-07-07 audit's finding 2 is
  resolved. Two details of the plane remain off-spec — [S7F-03](#s7f-03--the-task-area-centre-is-not-findtaskareacentre)
  and [S7F-05](#s7f-05--the-ltm-scale-factor-is-1-not-099994).
- **§7.2 — the speed section.** `SpeedSection` (`5ec661a`) optimizes S7F's separate
  `taskToESS` route and reports all three of §7.2's numbers as projections of it. It is
  emphatically not a prefix of the task route — see
  [S7F-02](#s7f-02--speed-section-distance-is-not-computed).
- **§7.2 — the task-distance formula, in a different but equivalent formulation.** S7F
  routes to `goal.centre` and subtracts `goal.radius`; pyxctsk routes to the goal
  *boundary*. Because the boundary point is placed at exactly `radius` along the geodesic
  from the centre toward the previous point, the two are the same number: over every
  cylinder-goal task in the corpus the worst difference in the final leg is **1.1 mm**.
  Prefer the shipped formulation — it stays correct where S7F's subtraction would go
  negative, namely a previous control zone lying inside the goal cylinder.
- **§6.2.3.1 — goal-line geometry.** Perpendicular to the approach, centred on the goal,
  total length `2 × radius`, semicircular control zone of radius `l/2` on the far side
  from the approach. All of that is unchanged between the 2024 and 2026 editions and all
  of it is correct — except *which point* defines the approach, which the 2025 edition
  changed and pyxctsk did not follow:
  [S7F-01](#s7f-01--the-goal-line-still-follows-the-2024-orientation-rule).
- **§7.2 / Annex B.1.2 — a LINE goal collapses to the goal centre.** `plane_circle`
  gives a LINE goal radius 0. Correct: the line is built perpendicular to the p→c
  azimuth, so the closest point on it from p is c itself, which is what B.1.2 asks for.
- **§7.2 — the route starts at the launch point.** Index 0 is never snapped to a
  boundary, matching S7F's `task` list, which opens with `launch` as a bare point.
- **§7.1.2 — the 100 km validity radius is respected in practice.** The farthest any
  corpus turnpoint sits from its projection centre is 81.3 km (`task_pepi`). There is no
  guard in the code, but no reference task needs one.

---

## Findings

### S7F-01 — the goal line still follows the 2024 orientation rule

**This is a superseded-edition implementation, not a misreading.** The rule changed in the
2025 edition, and pyxctsk implements the one before it — faithfully.

**S7F 2024 §6.2.3.1:** *"The goal line control zone consists of the semi-circle with radius
l/2 behind the goal line, when coming from **the last turn point that is different from the
goal line centre**."*

**S7F 2026 §6.2.3.1:** *"The previous point p is defined as **the optimized route point on
the last control zone before goal**. This point is obtained as part of the task distance
calculation, see chapter 7.2."*

**S7F 2025 §2.1.1.14, change 7:** *"Orientation of Goal Line: Follow optimized route,
instead of turnpoint centres. (6.2.3.1)"*

`_find_previous_turnpoint` (`src/pyxctsk/distance/goal_line.py:50`) walks backwards from
the goal for the first turnpoint whose coordinates differ from it, and
`GoalLine.from_task` (`:208`) sets `approach_from` to that turnpoint's **centre**. That is
a line-by-line implementation of the 2024 sentence, down to the "different from the goal
line centre" clause — which is also why the coincident-turnpoint guard exists. Against
2024 the code is correct; against 2026 it is one edition behind. The 2026-07-07 audit
called it "plausibly correct, but should be tested against a known goal-line task" (its
finding 7) and separately noted that the 2025 change had moved the rule; PR #8 picked up
the optimizer changes from that same list but not this one.

The optimized route point on that cylinder's *boundary* is never consulted. Every
LINE-goal task in the corpus is affected. Azimuth error and the resulting
displacement of each goal-line endpoint (all five lines are 200 m long):

| task | previous TP radius | azimuth used (2024) | azimuth per 2026 §6.2.3.1 | Δ | endpoint shift |
| --- | ---: | ---: | ---: | ---: | ---: |
| `task_piga_line` | 2 000 m | 103.431° | 103.805° | 0.37° | 0.7 m |
| `task_motu_line` | 400 m | 162.112° | 161.379° | 0.73° | 1.3 m |
| `task_fobe_line` | 600 m | 162.115° | 159.415° | 2.70° | 4.7 m |
| `task_quno_line` | 1 500 m | 103.430° | 106.454° | 3.02° | 5.3 m |
| `task_qoga_line` | 3 000 m | 71.385° | −137.039° | **151.58°** | **47.6 m** |

`task_qoga_line` is the case that shows the shape of the divergence rather than its size. Its
goal (`A30`, r = 100 m) sits 2 259 m from the centre of the ESS cylinder (`B02`,
r = 3 000 m) — the goal is *inside* the previous control zone. The optimized route
therefore touches `B02` on the far side and approaches the goal from azimuth −137°, while
pyxctsk draws the line for an approach from +71°. The line is nearly parallel to the real
approach instead of perpendicular to it, and the semicircular control zone faces away
from the direction pilots actually arrive from.

The optimized *distance* is unaffected — a LINE goal is a zero-radius circle at the goal
centre either way — but both writers render the wrong shape:

```bash
uv run python -c "
from pathlib import Path
from pyxctsk import parse_task
from pyxctsk.distance.goal_line import GoalLine
from pyxctsk.distance.route_optimization import calculate_iteratively_refined_route as opt
from pyxctsk.distance.task_distances import task_to_turnpoints
from pyxctsk.distance.turnpoint import geod_for_earth_model
t = parse_task(Path('tests/data/reference_tasks/xctsk/task_qoga_line.xctsk').read_text())
gl, r = GoalLine.from_task(t), opt(task_to_turnpoints(t))
g = geod_for_earth_model(t.earth_model)
print('used  :', g.inv(gl.approach_from[1], gl.approach_from[0], gl.center[1], gl.center[0])[0])
print('S7F   :', g.inv(r.points[-2][1], r.points[-2][0], gl.center[1], gl.center[0])[0])
"
```

**Fix shape.** `GoalLine.from_task` needs the optimized route, not just the task. The
route is already computed once per drawing (`TaskDrawing.from_task`), so the natural move
is a second constructor taking the `OptimizedRoute` and reading `route.points[-2]`, with
`from_task` optimizing for callers that have no route yet. `_find_previous_turnpoint`'s
coincident-coordinates guard stays: a previous *route point* coincident with the goal
still leaves no approach direction.

**Before fixing, decide which edition the library targets**, because this is the one place
the two editions give different answers and the rest of the code has already moved to
2026. If pyxctsk is meant to mirror XCTrack's *displayed* geometry rather than the current
scoring code, the 2024 rule may be the right answer and this becomes *won't fix* with a
comment in `goal_line.py` saying so — but that should be a recorded decision, not the
current silence. Whichever way it goes, the module docstring should name the edition it
implements, the way the optimizer's docstrings name §7.

---

### S7F-02 — speed-section distance is not computed

**§7.2** defines two numbers. pyxctsk produces one.

```
distanceSpeedSection = pathToESSdistance − preStartSectionDistance
```

where `pathToESS` is the route optimized over `launch … SSS … ESS.centre` with
`ESS.radius` subtracted, and `preStartSectionDistance` is the sum of that route's legs up
to the SSS index. `calculate_task_distances` returns `center_distance_km`,
`optimized_distance_km` and per-turnpoint cumulative distances; there is no speed-section figure
and no public function that could produce one.

`distance/sss.py` was deleted in `c3fdd26` as dead code, correctly — every function in it
failed the deletion test and none of them computed this. The gap predates that commit;
the 2026-07-07 audit raised it as finding 6 ("unverified") and it is now confirmed absent.

Note that the number is *not* a prefix of the task route: §7.2 optimizes a **separate**
route that ends at the ESS, because the optimizer treats the last circle it is handed as
the finish. `OptimizedRoute.cumulative_m()` at the ESS index is a different quantity —
which is exactly the distinction `docs/arch-review/2026-08-17-deepening-candidates.md`
records for cumulative distances. A speed-section implementation must run its own
`calculate_iteratively_refined_route` over the truncated turnpoint list.

Whether pyxctsk *should* produce this number is a scope call, not a defect: it is a
scoring input, and the library does not score. Recorded so the decision is explicit.

---

### S7F-03 — the task-area centre is not `FindTaskAreaCentre`

**§7.1.6** specifies the projection centre precisely, and pyxctsk uses a different rule in
three ways.

`LocalPlane.around` (`src/pyxctsk/distance/turnpoint.py:360`) takes the arithmetic **mean**
of the turnpoint centres, once. §7.1.6 asks for:

1. the **centre of the bounding box** of the task's points — not their mean;
2. a **second pass**: project, run PathFinder, correct, take the bounding box of the
   *corrected path*, and re-centre on that;
3. **antimeridian handling** (§7.1.6.1): sort the normalized longitudes, find the largest
   gap, and if it exceeds 180° take the box across the seam.

Measured effects, over the 24-task corpus:

- **Bounding-box vs. mean centre**: the optimized total moves by up to **98.6 m**
  (`task_bevo`, 94 028.282 m → 94 126.909 m). Three tasks move at all; the other 21 are
  bit-identical. No task changes at the 0.1 km rounding the reports use. The size of the
  shift is out of proportion to the 6.4 km between the two centres — it is
  [S7F-04](#s7f-04--the-optimizer-can-settle-in-a-local-optimum) showing through, not
  projection distortion.
- **Antimeridian**: a task straddling ±180° gets a projection centre roughly 120° of
  longitude away. Constructed cases:

  ```
  Fiji, 3 turnpoints:  mean-of-longitudes centre = -59.67°  (task is at ~180°)
  ```

  The snapping and geodesic measurement absorb most of the distortion — the totals differ
  from a correctly-centred run by 0.3 m (3 turnpoints) and 3.6 m (5 turnpoints with
  15–25 km radii) — but the deviation is unbounded in principle and there is no guard.
  For comparison, the spec's own reference converter (Annex A.2) rejects a centre latitude
  outside [−80, 80] and counts "wrong usage" beyond 2.2° from the central meridian.

The second pass is the least consequential of the three and the most invasive to add.
The bounding-box rule and the antimeridian handling are both local changes to
`LocalPlane.around`.

---

### S7F-04 — the optimizer can settle in a local optimum

**§7** asks for *the* shortest path. The alternating point-circle-point method is only
locally convergent, and pyxctsk initializes every route point at its circle's centre, so
which optimum it reaches depends on the projection.

Sweeping the projection centre over a 31 × 31 grid (±0.75° in each axis, 961 runs per
task) and taking the shortest route found:

| task | shipped | best found | gap | as % |
| --- | ---: | ---: | ---: | ---: |
| `task_duna` | 81 230.830 m | 81 189.700 m | **41.130 m** | 0.051 % |
| `task_bevo` | 94 028.282 m | 94 028.282 m | 0 | — |

Only `task_duna` is affected, and the gap does not survive the 0.1 km rounding of the
distance report (both round to 81.2 km; XCTrack publishes 81.1 km for this task, so the
corpus already tolerates a 0.1 km spread here). This is not a convergence-threshold
problem: driving ε from 0.1 m to 1e-9 with 5000 sweeps does not close it
(see [What is conformant](#what-is-conformant)).

Fixing it properly means multiple starts or a better initialization, which is a real cost
for 41 m on one task in 24. Recorded as a known limit of the method rather than a bug to
rush. It is, however, the reason [S7F-03](#s7f-03--the-task-area-centre-is-not-findtaskareacentre)
measures a 98.6 m sensitivity to a 6.4 km shift in the projection centre — the two
findings should be read together, and any change to the projection centre should be
re-measured against this grid rather than against a single task.

---

### S7F-05 — the LTM scale factor is 1, not 0.99994

**§7.1.2** fixes the scale factor of the localized Transverse Mercator projection:

```
scaling = { centre.lat ≤ 55°:  0.99994
            centre.lat > 55°:  0.99994 + (centre.lat − 55)/60 × 1.3e-4 }
```

`_cached_tm_transformers` (`src/pyxctsk/distance/turnpoint.py:95,101`) builds both CRSs
with `+k=1`.

**Measured effect: 2.1 mm**, worst case over the corpus (`task_duna`, 81 230.830 m →
81 230.828 m). The scale factor only shifts where a point is *placed* in the plane; the
point is then snapped onto the true boundary and the legs are measured geodesically, so
a uniform 6e-5 scaling almost entirely cancels. Fix it because the spec states a number
and the code states a different one, not because the answer is wrong.

Two details worth carrying into the fix: the spec's formula uses **|lat|**
(`double la = abs(refLat)` in both Annex A samples), and the 2026 edition's own document
history records the correction *"parameter `+k_0` instead of deprecated `+k`"* — so the
replacement should be `+k_0=…`, not `+k=…`.

---

### S7F-06 — the elevated-goal ceiling is not validated

**§6.2.3.2:** *"The elevation above goal is by default 300 m but can be increased up to
1000 m for each task."*

`model/validation.py` checks turnpoint roles, negative radii, the declared version and
extension ordering. It does not check this ceiling: `goal.finishAltitude = 5000` validates
clean.

```bash
uv run python -c "
from pathlib import Path
from pyxctsk import parse_task
t = parse_task(Path('tests/data/reference_tasks/elevated-goal/xcontest-conformant.xctsk').read_text())
t.goal.finish_altitude = 5000.0
print(t.validate() or 'no issues reported')
"
```

One new `ValidationRule` member and one function beside `_radius_issues`; `TaskStructure`
gains a `finish_altitude` field, presented by both format adapters (the QR format carries
it as `g.fa`).

**No goal-line length bound applies.** An earlier draft of this audit claimed one, reading
§6.2.2's *"length must lie between 0.1 and 50.0 km"* onto the goal line. That is wrong
twice over: §6.2.2 governs the **general line control zone**, which §6.2.3.1 does not
reference — the goal line is defined independently by *c*, *l* and *p* with no stated
bounds — and the two sections do not even mean the same thing by *l*. In §6.2.2 it is the
half-length (*"the distance between c and e1 and e2, respectively"*, total = 2*l*); in
§6.2.3.1 it is the total (*"extends by l/2 meters from c in each direction"*). pyxctsk's
`length = 2 × radius` with a control zone of `length / 2` matches §6.2.3.1's convention,
and the 2024 edition's default of 400 m confirms *l* is the total there too.

---

### S7F-07 — an elevated goal implicitly *is* the ESS

**§6.2.3.2:** *"When an elevated goal is declared, it implicitly also serves as the End of
Speed Section (ESS): the point where a pilot's race time is taken."*

`Task.is_ess_goal()` (`src/pyxctsk/model/task.py:560`) answers by looking for a turnpoint
typed `ESS` and comparing it to the last one. A task that sets `goal.finishAltitude` and
marks ESS on an *earlier* turnpoint is contradictory under S7F, and pyxctsk reports
`is_ess_goal() == False` for it without comment.

The corpus does not contain such a task — `elevated-goal/xcontest-conformant.xctsk` sets
`finishAltitude = 300` with ESS on the last of its three turnpoints, so the two agree.
The gap is that nothing enforces the agreement. Two possible responses, and they are not
exclusive: a validation rule flagging the combination, and `is_ess_goal()` returning True
whenever `goal.finish_altitude` is set.

Related, and deliberately left alone: SeeYou Navigator's non-spec root `o.fa` also
declares an elevated goal, in absolute AMSL rather than AGL. Per
`tests/data/reference_tasks/elevated-goal/README.md` that key is preserved and never
interpreted, which is right — reading it as an elevated goal here would import the same
~1 km datum error the passthrough rule exists to prevent.

---

### S7F-08 — `FAI_SPHERE` distances are not S7F task distances

**§4.1:** coordinates are *"always given as WGS84 coordinates, based on the WGS84
ellipsoid."* **§4.2:** distances *"are calculated on the WGS84 ellipsoid."* S7F 2026 offers
no spherical option anywhere; paragliding left the FAI sphere in 2018.

`earthModel: "FAI_SPHERE"` is an XCTrack format field, and pyxctsk honours it correctly
(ADR 0003) — routes, cylinder snapping and goal-line geometry all move to the sphere
together. That is the right behaviour for a library that implements the XCTrack format.

The gap is that a task declaring the FAI sphere produces numbers that are not S7F task
distances, and nothing in the API or the CLI says so. XCTrack's own documentation puts
the divergence at 200–300 m on a 50 km cylinder. A note in
`distance/__init__.py` and a line in the CLI's output would close it; a validation rule
would over-reach, since the field is valid in the format being validated.

---

### S7F-09 — shapes the XCTrack format cannot carry

Recorded so the absence is a decision, not an oversight. Neither is actionable in this
library.

- **§6.2.1 turnpoint altitude limits.** S7F allows an optional upper and lower altitude
  limit in metres AMSL on every turnpoint cylinder, and §9.2.1 makes a crossing valid only
  within them. XCTrack's format has no key for either, so a task using them cannot be
  expressed as `.xctsk` at all. Any such value arriving in a turnpoint object lands in
  `unknown` and is carried back out verbatim, which is the correct handling.
- **§6.2.2 general line control zones.** S7F defines a line control zone anywhere in a
  task, parameterized by a waypoint *w*, a signed distance *d*, an orientation *o* in
  multiples of 2.5° or as a cardinal direction, and a half-length *l*. XCTrack has a goal
  line only, derived from the last turnpoint's radius and the approach direction. Annex
  B.1.1 (a line in the *middle* of a task: intersection, reflection, or nearer endpoint)
  is consequently unreachable code for this format — pyxctsk implements only B.1.2, the
  line-at-the-end case, and that is all it can ever need.

---

## Reproducing this audit

The PDFs are not fetchable by tooling that does not send a browser user agent — both
`fai.org/civl-documents` and the PDF URLs return 403 to a plain request. What worked:

```bash
UA="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
curl -sSL -A "$UA" -o s7f2026.pdf \
  "https://www.fai.org/sites/default/files/2026-05/Sporting%20Code%20S7%20F%20-%20XC%20Scoring%202026_V1.0.pdf"
curl -sSL -A "$UA" -o s7f2024.pdf \
  "https://www.fai.org/sites/default/files/civl/documents/sporting_code_s7_f_-_xc_scoring_2024.pdf"
uv run --with pypdf python -c "
import sys
from pypdf import PdfReader
print('\n'.join(p.extract_text() for p in PdfReader(sys.argv[1]).pages))" s7f2026.pdf > s7f2026.txt
```

The 2024 extraction contains a byte that makes GNU grep treat the file as binary and
suppress its output entirely — pass `grep -a`, or searches silently return nothing.

The formulae extract as mojibake — the PDF's maths font maps most Latin letters onto a
single glyph, so `goal.type = line` comes out as a run of repeated characters. The prose,
the section numbering, the code samples in Annex A and the numeric constants all extract
cleanly. Where a formula mattered (§7.2, §9.1.1) it was read from the rendered page.

Every measurement above was taken by running the library over
`tests/data/reference_tasks/xctsk/` at `8522ea7`, patching one thing at a time
(`LocalPlane.around`, `_cached_tm_transformers`, `_optimize_plane_points`'s epsilon) and
comparing against the unpatched result.
