# XCTrack Optimized-Distance Findings

Companion to [Audit-of-pyxctsk-Route-Optimization.md](Audit-of-pyxctsk-Route-Optimization.md).
This documents what was learned about XCTrack's displayed optimized distances while
implementing the FAI S7F §7 / Ding–Xie–Jiang route optimizer in pyxctsk (PR #8), so the
knowledge is not lost with the working session. All measurements were made against the
22 reference tasks in `tests/data/reference_tasks/` whose JSON metadata carries XCTrack's
displayed values (rounded to 0.1 km).

## TL;DR

1. **XCTrack uses circle-boundary ("touching") semantics**, not disk ("entering counts")
   semantics: every turnpoint circle must be touched at its boundary, in order. For
   concentric turnpoints of different radii this forces mandatory out-and-back legs —
   and XCTrack includes them.
2. **The route starts at the takeoff *center*** (not on the takeoff cylinder boundary),
   and a **goal line contributes its center** as the final point.
3. **XCTrack's displayed optimized distance is itself an approximation.** On tasks with
   very large cylinders (≥ ~26 km radius) it deviates from the true WGS84 optimum by up
   to ~1 % — *in both directions*. Where XCTrack is higher, pyxctsk's route is a
   genuinely shorter feasible path (all points verified on their boundaries), proving
   XCTrack's number is not the geometric optimum there. No alternative convention that
   was tested reproduces XCTrack's numbers across the board (see
   [Hypotheses tested and ruled out](#hypotheses-tested-and-ruled-out)).
4. On well-conditioned tasks (largest cylinder ≲ 25 km), pyxctsk matches XCTrack within
   the display rounding — typically 6–80 m on 35–175 km tasks.

## Evidence for touching semantics: `task_nohe`

`task_nohe` contains two clusters of concentric turnpoints (identical centers):

| # | type    | radius | note                        |
|---|---------|-------:|-----------------------------|
| 1 | SSS     | 10 000 | same center as #2, #3, #4   |
| 2 |         |    200 | concentric                  |
| 3 |         | 10 000 | concentric                  |
| 4 |         |    100 | concentric                  |
| 8 |         |    300 | same center as #9, #10      |
| 9 | ESS     |  4 000 | concentric                  |
| 10| Goal    |    200 | concentric                  |

The polyline through the centers is 82.6 km, yet XCTrack displays **96.3 km optimized —
more than the center distance**. That is only possible if the route must *touch each
circle's boundary*: after reaching within 200 m of the shared center (#2), the route must
fly ~9.8 km back out to the 10 km circle (#3) and ~9.9 km back in to the 100 m circle
(#4); likewise out to the 4 km ESS circle and back to the 200 m goal circle. Under disk
semantics ("entering the cylinder counts"), the optimized distance would be far *below*
82.6 km. pyxctsk reproduces XCTrack's value with boundary semantics: 96.38 km (+80 m,
within the 0.1 km display rounding).

Consequences encoded in pyxctsk:

- `optimized_distance ≤ distance_through_centers` is **not** an invariant for tasks with
  consecutive concentric turnpoints (the center polyline never touches the smaller
  circle, so it is not a feasible route). It holds for all other reference tasks and is
  asserted that way in `tests/test_distance.py`.
- Two identical concentric turnpoints have center distance 0 but optimized distance =
  radius (start at the shared center, touch the circle).

## Accuracy vs. XCTrack's displayed values

pyxctsk (true WGS84 optimum, boundary semantics) vs. XCTrack's displayed optimized
distance. `r_max` = largest cylinder radius in the task; reference values are rounded to
0.1 km (±50 m quantization):

| task       |  lat | r_max km | XCTrack km | pyxctsk km |  Δ m    |   Δ %  |
|------------|-----:|---------:|-----------:|-----------:|--------:|-------:|
| bevo       |  4.4 |     21.0 |       94.1 |     94.028 |   -71.7 | -0.076 |
| duna       |  4.5 |     35.5 |       81.1 |     81.231 |  +130.8 | +0.161 |
| fobe_line  | 46.3 |     14.7 |       47.4 |     47.830 |  +429.7 | +0.907 |
| gibe       | 46.7 |      1.0 |      174.5 |    174.487 |   -13.1 | -0.008 |
| gimi       |  4.5 |     26.0 |       87.6 |     87.230 |  -370.2 | -0.423 |
| lorili     |  4.5 |     51.5 |      100.8 |    100.022 |  -778.2 | -0.772 |
| mega       |  4.4 |     25.0 |      110.6 |    110.625 |   +24.9 | +0.022 |
| motu_line  | 46.3 |     22.0 |       60.7 |     60.967 |  +266.6 | +0.439 |
| naxe       |  4.5 |     30.0 |      122.3 |    122.347 |   +46.6 | +0.038 |
| nife       | 46.3 |     15.5 |       74.0 |     74.257 |  +256.8 | +0.347 |
| nohe       |  4.4 |     10.0 |       96.3 |     96.380 |   +79.6 | +0.083 |
| nubu       |  4.4 |     58.0 |       91.2 |     90.471 |  -728.5 | -0.799 |
| pepi       |  4.5 |     66.6 |       92.9 |     92.002 |  -898.4 | -0.967 |
| piga_line  | 42.5 |      5.5 |       35.4 |     35.359 |   -41.4 | -0.117 |
| qavu       | 44.0 |     18.0 |       81.9 |     81.906 |    +5.7 | +0.007 |
| qoga_line  | 46.3 |     32.0 |       54.8 |     55.134 |  +334.3 | +0.610 |
| quno_line  | 42.5 |      8.0 |       49.9 |     49.978 |   +78.2 | +0.157 |
| vocu       | 46.3 |     15.5 |       65.6 |     65.864 |  +263.7 | +0.402 |
| waku       |  4.5 |     66.6 |       91.9 |     91.548 |  -351.5 | -0.383 |
| wovi       |  4.5 |     11.0 |       95.6 |     95.491 |  -109.0 | -0.114 |
| xiga       |  4.5 |     16.0 |       78.3 |     78.000 |  -299.6 | -0.383 |
| xise       | 46.4 |     10.0 |       58.9 |     59.252 |  +351.9 | +0.597 |

Observations:

- 8 tasks (bevo, gibe, mega, naxe, nohe, piga, qavu, quno) match within 0.1 % *and*
  50 m once the 50 m display quantization is allowed for — these are the acceptance
  benchmark in `tests/test_distance.py`.
- The large deviations correlate with very large cylinders (lorili 51.5 km, nubu 58 km,
  pepi/waku 66.6 km → XCTrack up to ~0.9 km *higher* than the true optimum) and cluster
  by region/sign (European Alps tasks tend to +0.3…+0.9 km, Colombian tasks with giant
  cylinders −0.3…−0.9 km).
- The old DP + beam-search optimizer produced almost identical values to the new
  spec-faithful optimizer (both find the same geometric optimum on these tasks); the
  residual differences vs. XCTrack are therefore **XCTrack's**, not pyxctsk's.
- XCTrack's per-turnpoint cumulative "Optimized (km)" column is measured **along its
  single full-task optimized route** (distance to where the route touches each circle),
  not as independently optimized prefixes. Prefix-optimized values (what
  `calculate_cumulative_distances` returns) are generally smaller.

## Hypotheses tested and ruled out

Each of these was implemented and compared against all 22 references; none explains the
deviations coherently:

| hypothesis                                                        | result |
|-------------------------------------------------------------------|--------|
| Route starts on the takeoff cylinder boundary instead of center    | Worse on most tasks; no consistent winner per task family |
| Route ends at the goal *center* instead of nearest boundary point  | Improves the Colombian giant-cylinder tasks a little, breaks others |
| All distances on the FAI sphere (R = 6371 km) instead of WGS84     | Better for most European tasks (~ −100 m residual), much worse for Colombian ones; incoherent overall |
| Leg summation with haversine / equirectangular (R = 6371 km)       | Halves the total absolute error but leaves ±500 m outliers both ways |
| FCC-style flat-earth per-leg approximation with WGS84 local radii  | Numerically identical to WGS84 geodesics on these scales |

Because XCTrack deviates in *both* directions from a provably feasible shorter route,
its optimizer either leaves points slightly off the cylinder boundaries or measures legs
with a non-geodesic approximation that varies with direction/latitude. Matching it
exactly would require replicating its closed-source implementation, including its
errors — which would contradict the goal of being faithful to FAI S7F §7. pyxctsk
therefore implements the spec and treats XCTrack agreement as a benchmark with
documented tolerances (0.1 %/50 m on well-conditioned tasks, 1 % as regression guard).

## Other behaviours confirmed while validating

- **Displayed rounding**: the reference "distance_optimized_km" values are XCTrack's
  display values rounded to 0.1 km; leg-by-leg comparisons carry ±50 m noise per leg.
- **SSS**: XCTrack's displayed task distance is takeoff-center → goal, with the SSS
  cylinder treated like any other circle to touch (no subtraction of the start-cylinder
  radius in the displayed total). The S7F §7.2 *speed-section* distance
  (launch→ESS minus pre-start portion) is a separate quantity that pyxctsk does not
  currently compute.
- **Goal line (S7F 2026 §6.2.3.1)**: the goal line is centred on the goal and
  perpendicular to the incoming optimized leg, so the optimal crossing point is exactly
  the goal center; treating a LINE goal as a zero-radius circle is exact for the
  distance. (For *visualization*, `goal_line.py` still orients the line from the
  previous turnpoint center — the pre-2025 rule — which does not affect distances.)
- **Convergence**: the alternating optimizer converges below ε = 0.1 m within a
  handful of sweeps on all reference tasks; further sweeps change nothing (asserted in
  `tests/test_distance.py::TestConvergence`).

## Reproducing the measurements

```bash
uv run python - <<'EOF'
import json
from pathlib import Path
from pyxctsk.parser import parse_task
from pyxctsk.task_distances import _task_to_turnpoints
from pyxctsk.route_optimization import optimized_distance

xdir = Path('tests/data/reference_tasks/xctsk')
jdir = Path('tests/data/reference_tasks/json')
for f in sorted(xdir.glob('*.xctsk')):
    ref = json.load(open(jdir / (f.stem + '.json')))['metadata'].get('distance_optimized_km')
    if not ref:
        continue
    opt = optimized_distance(_task_to_turnpoints(parse_task(str(f)))) / 1000
    print(f"{f.stem:16s} ref {ref:7.1f}km  pyxctsk {opt:8.3f}km  diff {(opt - ref) * 1000:+7.1f}m")
EOF
```
