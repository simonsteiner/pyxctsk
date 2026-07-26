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
(pyxctsk: 96.38 km). See `docs/XCTrack-Optimized-Distance-Findings.md`.

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
- A takeoff inside the SSS cylinder, nested start cylinders, and overlapping cylinders
  all route through segment–circle intersections without spurious detours (covered in
  `tests/test_distance.py::TestCrossingCase`).
