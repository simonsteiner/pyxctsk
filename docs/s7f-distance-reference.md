# Task distances under FAI S7F: what the code defines, and what it leaves to us

**Status:** findings for discussion with instrument and scoring vendors
**Date:** 2026-08-18
**Reference implementation:** [pyxctsk](https://github.com/simonsteiner/pyxctsk), MIT-licensed,
audited against [FAI Sporting Code S7F 2026 V1.0](https://www.fai.org/sites/default/files/2026-05/Sporting%20Code%20S7%20F%20-%20XC%20Scoring%202026_V1.0.pdf)
(`sha256:6a0f400b…`, effective 1 May 2026) in
[`arch-review/2026-08-18-s7f-2026-conformance-audit.md`](arch-review/2026-08-18-s7f-2026-conformance-audit.md).

---

## Why this document exists

Competition task boards publish two numbers for every task: **distance through centres**
and **optimized distance**. Which numbers appear depends on which device or program the
task-setting committee happened to use. Pilots plan against them, and they do not always
agree between vendors.

pyxctsk is offered as an **open-source reference implementation** of the S7F distance
calculations, so that "what should this task's distance be?" has an answer anyone can
run, read and disagree with in public. It is deliberately faithful to the Sporting Code
rather than to any one implementation, including where that makes it disagree with a
widely used one.

This document reports three findings. The second is, we think, the more consequential of
the two headline ones, and it is not about anybody's optimizer.

---

## Finding 1 — S7F defines one of the two published numbers, and not the other

§7.2 is the whole of what the Sporting Code says a task's distance is:

> *"Task distance is defined as the distance of the optimized path from launch to goal.
> Speed section distance is defined as the distances of the optimized path from launch to
> ESS, minus the distance of the pre-start portion."*

Both are given as formulas, built on an algorithm chain the code specifies in unusual
detail — a localized Transverse Mercator projection with a fixed scale factor (§7.1.2),
the Ding–Xie–Jiang "touring n circles" path finder at ε = 0.1 m (§7.1.3), Karney/Thomas/
Vincenty geodesics (§7.1.4–7.1.5), a two-pass task-area centre (§7.1.6) and a projection
correction back onto the control-zone boundaries (§7.1.7). Two implementations that
follow it should agree to within millimetres.

**"Distance through centres" appears nowhere in the 2026 edition.** Not in §7, not in the
definitions of §3, not in the task-setting rules of §6. Searching the document for it
returns nothing. It is a display convention that every vendor has invented independently.

That matters because the convention is genuinely ambiguous. Three readings, each
defensible, on the corpus task with the widest spread:

| reading | `task_pepi` |
| --- | ---: |
| Every turnpoint centre, launch through goal | 321.4 km |
| …ending at the goal cylinder boundary (minus the goal radius) | 321.2 km |
| From the SSS rather than from launch | **281.6 km** |

**39.9 km apart**, on a task whose *optimized* distance is 92 km. Nothing in S7F prefers
one. Further defensible variations exist and are not tabulated here: measuring on the FAI
sphere rather than the WGS84 ellipsoid, and whether consecutive duplicate turnpoints
contribute a leg.

pyxctsk implements the first reading — every centre, launch to goal, geodesic on the
task's declared earth model, with consecutive duplicate turnpoints contributing their
(zero-length) leg like any other. On the 22 reference tasks that carry a published value
it agrees to within **49 m**, which is inside the 0.1 km display rounding. That agreement
is by convention, not by specification, and it is exactly the kind of agreement that
breaks silently when a new vendor arrives.

The reading is now stated in one place — `src/pyxctsk/distance/center_distance.py` — and
the alternatives are kept beside it and reported by `pyxctsk distances`, for exactly one
purpose: **if your board disagrees with ours, you can tell in one command whether the
cause is a different reading or a different bug.**

**What we would ask of CIVL and of vendors:** either S7F should define this number, or
task boards should stop publishing it as though it were defined. If it is to be defined,
the reading above is the one we propose, and we would rather be argued out of it now than
discover the disagreement on a task board.

---

## Finding 2 — on the optimized distance, the remaining disagreement is concentrated in giant cylinders

pyxctsk's optimized distance against the published values of the 22 reference tasks. The
published values are XCTrack's displayed figures, rounded to 0.1 km, so every row carries
±50 m of quantization; the provenance and the earlier round of this analysis are in
[`arch-review/2026-07-07-optimized-distance-findings.md`](arch-review/2026-07-07-optimized-distance-findings.md).
`r_max` is the task's largest cylinder radius, and the table is sorted by it.

| task | lat | r_max km | published km | pyxctsk km | Δ m | Δ % |
|---|---:|---:|---:|---:|---:|---:|
| `gibe` | 46.6 | 1.0 | 174.5 | 174.487 | -13.1 | -0.008 |
| `piga_line` | 42.5 | 5.5 | 35.4 | 35.359 | -41.4 | -0.117 |
| `quno_line` | 42.5 | 8.0 | 49.9 | 49.978 | +78.2 | +0.157 |
| `nohe` | 4.5 | 10.0 | 96.3 | 96.379 | +79.5 | +0.083 |
| `xise` | 46.5 | 10.0 | 58.9 | 59.252 | +351.8 | +0.597 |
| `wovi` | 4.4 | 11.0 | 95.6 | 95.491 | -109.0 | -0.114 |
| `fobe_line` | 46.3 | 14.7 | 47.4 | 47.830 | +429.7 | +0.907 |
| `nife` | 46.3 | 15.5 | 74.0 | 74.257 | +256.8 | +0.347 |
| `vocu` | 46.3 | 15.5 | 65.6 | 65.864 | +263.7 | +0.402 |
| `xiga` | 4.4 | 16.0 | 78.3 | 78.000 | -299.6 | -0.383 |
| `qavu` | 44.0 | 18.0 | 81.9 | 81.906 | +5.7 | +0.007 |
| `bevo` | 4.2 | 21.0 | 94.1 | 94.028 | -71.7 | -0.076 |
| `motu_line` | 46.3 | 22.0 | 60.7 | 60.967 | +266.6 | +0.439 |
| `mega` | 4.4 | 25.0 | 110.6 | 110.625 | +24.9 | +0.022 |
| `gimi` | 4.5 | 26.0 | 87.6 | 87.230 | -370.2 | -0.423 |
| `naxe` | 4.1 | 30.0 | 122.3 | 122.347 | +46.6 | +0.038 |
| `qoga_line` | 46.3 | 32.0 | 54.8 | 55.134 | +334.3 | +0.610 |
| `duna` | 4.5 | 35.5 | 81.1 | 81.190 | +89.7 | +0.111 |
| `lorili` | 4.3 | 51.5 | 100.8 | 100.022 | -778.2 | -0.772 |
| `nubu` | 4.5 | 58.0 | 91.2 | 90.471 | -728.5 | -0.799 |
| `pepi` | 4.6 | 66.6 | 92.9 | 92.002 | -898.4 | -0.967 |
| `waku` | 4.4 | 66.6 | 91.9 | 91.548 | -351.5 | -0.383 |

- **17 of 22** differ by more than the 50 m display quantization; the largest is 898 m
  (0.97 %).
- Tasks with `r_max ≥ 26 km` average **450 m** of disagreement; those below it average
  **164 m**. The published values run *high* on the giant-cylinder tasks and are mixed
  elsewhere.

**Where pyxctsk is lower, we can prove the published number is not the optimum.** Every
point of a pyxctsk route sits on its cylinder boundary, in order — that is asserted for
all 22 tasks in `tests/conformance/test_spec_conformance.py::
TestRouteOptimizerConformance::test_every_route_point_touches_its_cylinder`. A shorter
route that touches every control zone in order is, by §7.2, the task distance. On `pepi`,
`nubu` and `lorili` the published figure is 0.7–0.9 km above a demonstrably feasible path.

**Where pyxctsk is higher we make no such claim.** We hold the other implementation's
number, not its route. It may have found something shorter, or it may be measuring legs
differently; without its path points the two cannot be separated. This is the single most
useful thing a vendor could contribute to this comparison: **not the total, but the route
points.** Two implementations that publish their crossing coordinates can settle any
disagreement in one diff.

The earlier round of this work implemented and ruled out five hypotheses that might have
explained the deviations as a convention difference rather than an optimizer difference —
route starting on the takeoff boundary, ending at the goal centre, FAI-sphere distances,
haversine leg summation, and flat-earth per-leg approximation. None explains them
coherently; the table in the 2026-07-07 document records what each did.

---

## Finding 3 — a local optimum is easy to mistake for the shortest path

This one is about our own implementation, and is offered because it is a trap any
S7F implementation can fall into.

§7.1.3 tells you to use Ding–Xie–Jiang, which alternately fixes odd- and even-indexed
route points and re-solves each against its neighbours. The method converges to a *local*
optimum, and which one it reaches depends entirely on where the points start. The obvious
initialization — every point at its cylinder's centre — is a place that, for any non-zero
radius, can never be an answer.

On `task_bevo` that cost 98.6 m: the shipped route was that much longer than an equally
legal one touching all ten cylinders in order, and nothing separated the two but where
the projection happened to be centred. Sweeping the projection centre over a grid found
the shorter route; the convergence threshold was not the problem, and tightening ε from
0.1 m to 1e-9 did not close it.

pyxctsk now runs the sweep from three deterministic starting configurations — the centres,
and chains built forward and backward along the boundaries — and keeps the shortest.
Measured over the corpus against 49 projection centres, the worst route a shifted plane
can find that the shipped one misses fell from **98.6 m to 10 mm**.

If your implementation seeds the sweep only from the cylinder centres, it is worth
checking whether a different projection centre finds you a shorter route. If it does, the
number you publish is your projection's, not the task's.

---

## What pyxctsk implements, precisely

So that disagreements can be attributed rather than guessed at.

| S7F | implemented | note |
| --- | --- | --- |
| §4.1, §4.2 geodesics on the WGS84 ellipsoid | ✅ | Karney (2013) via `pyproj` |
| §7.1.2 LTM projection, k₀ = 0.99994 (latitude-dependent above 55°) | ✅ | |
| §7.1.3 Ding–Xie–Jiang path finder, ε = 0.1 m | ✅ | plus multi-start, see Finding 3 |
| §7.1.6 task-area centre: bounding box, two passes, antimeridian-aware | ✅ | |
| §7.1.7 projection correction onto the control-zone boundaries | ✅ | |
| §7.2 task distance | ✅ | route to the goal boundary; equal to the code's "centre minus radius" formulation to 1.1 mm across the corpus |
| §7.2 speed section distance | ✅ | a *separate* `taskToESS` optimization, not a prefix of the task route |
| §6.2.3.1 goal line, oriented from the optimized route point | ✅ | the 2025 change; the 2024 rule is still selectable |
| §6.2.3.2 elevated goal, 0–1000 m, implicitly the ESS | ✅ | validated, not silently accepted |
| §6.2.1 control-zone altitude limits | ❌ | XCTrack's task format has no keys for them |
| §6.2.2 general line control zones | ❌ | same; only the goal line exists in the format |
| §8, §9 tracklog evaluation; §10–16 scoring | ❌ | out of scope — pyxctsk reads no tracklogs and awards no points |
| "distance through centres" | ⚠️ | **S7F does not define it.** One stated convention, with the alternatives kept for diagnosis — `distance/center_distance.py` |

Two deliberate divergences worth naming:

- **`earthModel: FAI_SPHERE`.** XCTrack's task format carries this field and pyxctsk
  honours it throughout. S7F §4.1/§4.2 admit the WGS84 ellipsoid alone, so a task
  declaring the FAI sphere produces numbers no CIVL competition can be scored on. It is
  not rejected, because the field is valid in the format being read.
- **Goal-line orientation.** S7F 2025 changed §6.2.3.1 from the previous turnpoint's
  *centre* to the *optimized route point*. pyxctsk defaults to the current rule. On one
  reference task the two differ by 152° — the goal there sits inside the preceding 3 km
  ESS cylinder, so the route arrives from the opposite side to the one the centre
  suggests. Any implementation still on the 2024 rule will draw that control zone facing
  away from the approach.

---

## Reproducing all of this

```bash
git clone https://github.com/simonsteiner/pyxctsk && cd pyxctsk
uv sync --all-extras
uv run pytest                       # the conformance suite, including the assertions cited above
```

**One command gives you everything in this document for your own task file:**

```console
$ pyxctsk distances your-task.xctsk --format text
pyxctsk 0.5.0  |  FAI S7F 2026 V1.0  |  earth model: WGS84

  task distance (§7.2)            92.002 km
  speed section (§7.2)            86.761 km
  through centres                321.440 km   [LAUNCH_TO_GOAL]

  'through centres' is NOT defined by S7F. Other readings of it:
    LAUNCH_TO_GOAL                321.440 km
    LAUNCH_TO_GOAL_BOUNDARY       321.240 km
    START_TO_GOAL                 281.568 km

  optimized route:
     0 D01        TAKEOFF  r=     0 m    4.476050  -76.153519     0.000 km
     1 X09        SSS      r= 37000 m    4.502847  -76.137677     3.446 km
     ...
     8 G02                 r=   200 m    4.589699  -75.967881    92.002 km
```

Drop `--format text` for JSON, which is what to exchange: it carries the library
version, the S7F edition, the earth model, every reading of the centre distance, and
**the optimized crossing point for every turnpoint**. Reads stdin, writes with `-o`, so a
whole corpus goes through it in a loop.

From Python, if you prefer:

```python
from pathlib import Path
from pyxctsk import parse_task
from pyxctsk.distance import optimized_distance, center_distance, task_to_turnpoints, SpeedSection

task = parse_task(Path("your-task.xctsk").read_text())
print(optimized_distance(task_to_turnpoints(task)))  # S7F §7.2 task distance, metres
print(center_distance(task))                         # the convention S7F does not define
print(SpeedSection.from_task(task).distance_m)       # S7F §7.2 speed section distance
```

The 22 tasks are in `tests/data/reference_tasks/`, each as a `.xctsk` alongside the
published values it is compared against. They are real competition tasks.

---

## What would help

1. **Route points, not totals.** A total tells us two implementations disagree; the
   crossing coordinates tell us why, in one diff. `pyxctsk distances task.xctsk` prints
   ours, alongside the numbers, in a form built to be diffed.
2. **A definition of "distance through centres", or its retirement from task boards.**
   Finding 1 is the one that can put 39.9 km between two vendors, and it is entirely a
   documentation problem.
3. **Counter-examples.** If a task exists where pyxctsk's route is not the shortest one
   touching every control zone in order, that is a bug and we want the file. The corpus
   is 22 tasks and skews toward Colombia and the European Alps.
4. **Corrections to this document.** It is version-controlled; issues and pull requests
   are the preferred form of disagreement.
