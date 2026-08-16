# ADR 0002: Circle-boundary ("touching") semantics for the optimized route

Date: 2026-07-07 · Status: Accepted

## Context

Two plausible readings of "shortest path touching each turnpoint cylinder in order"
exist:

- **Disk semantics** — entering a cylinder counts; a route point may lie anywhere inside
  the disk. Nested/concentric cylinders then cost nothing extra once the route is inside.
- **Boundary semantics** — each turnpoint's *circle* must be touched; with concentric
  turnpoints of different radii the route must fly back out to the larger circle and back
  in to the smaller one.

The reference task `task_nohe` (concentric 10 km/200 m/10 km/100 m turnpoints, and a
concentric 300 m/4 km/200 m ESS-goal cluster) settles which one XCTrack uses: XCTrack
displays an optimized distance of **96.3 km, more than the 82.6 km through the centers**
— impossible under disk semantics, and reproduced exactly by boundary semantics
(pyxctsk: 96.38 km). See `docs/arch-review/2026-07-07-optimized-distance-findings.md`.

## Decision

The optimized route uses boundary semantics with these endpoint rules:

- **Start**: the route starts at the takeoff *center* (matches XCTrack and the previous
  pyxctsk behaviour; the takeoff cylinder is not "touched").
- **Middle turnpoints**: GetOptPi on the circle — the crossing case adds no length when
  the leg already crosses the circle; when both neighbours are inside (concentric case)
  the reflection point on the boundary produces the mandatory out-and-back.
- **Goal cylinder**: the boundary point nearest the previous route point (also when the
  previous point is inside the circle).
- **Goal line**: contributes its *center*. Per S7F 2026 §6.2.3.1 the line is centred on
  the goal and perpendicular to the incoming optimized leg, so the perpendicular foot
  from the incoming point — the optimal crossing — is the center itself; a LINE goal is
  therefore modelled as a zero-radius circle.

## Consequences

- `optimized_distance ≤ distance_through_centers` is **not** an invariant when
  consecutive turnpoints are concentric (the center polyline is not a feasible touching
  route there). Tests assert the inequality only for non-concentric tasks and assert the
  `task_nohe` value explicitly.
- Two identical concentric turnpoints yield optimized distance = radius (not 0); the
  synthetic regression test was updated accordingly.
- **Consecutive *identical* circles (same center and same radius) are collapsed before
  optimizing** (`_collapse_duplicate_circles`, added 2026-08-16). Touching a circle and
  then touching the same circle again is satisfied by one touch, so the duplicate must
  cost zero. Optimizing the two points separately instead created a spurious local
  minimum — once they coincide, moving either adds length to the leg between them
  exactly as fast as it saves on the neighbouring leg, so the alternating sweep froze
  wherever it happened to be. On `tests/data/reference_tasks/ess-goal/task2` that left
  the final point at bearing 90.05° from the goal center instead of 170.16°, inflating
  the optimized distance by 168 m. Index 0 is exempt (the route starts at the takeoff
  *center*, so repeating the takeoff circle is a real center-to-boundary leg), and
  concentric circles of *different* radii are untouched — their out-and-back is
  required, per the rules above.
- A takeoff inside the SSS cylinder, nested start cylinders, and overlapping cylinders
  all route through segment–circle intersections without spurious detours (covered in
  `tests/distance/test_distance.py::TestCrossingCase`).
