# ADR 0003: Honor the task's earthModel (WGS84 default, FAI sphere R = 6371 km)

Date: 2026-07-07 · Status: Accepted

## Context

XCTrack's `.xctsk` format carries an `earthModel` field ("WGS84" default or
"FAI_SPHERE"). pyxctsk previously ignored it and always measured on the WGS84 ellipsoid.
Per XCTrack's competition tutorial, on a 50 km cylinder radius the difference between the
FAI-sphere and WGS84 formulas can be 200–300 m — enough to make or miss a cylinder in
scoring. The distance subsystem needed one consistent way to select the model in leg
measurement, boundary-point placement, and the optimization projection.

## Decision

- One selector, accepted everywhere as `earth_model` (an `EarthModel` enum member, its
  string value, or `None` = WGS84): `geod_for_earth_model()` returns a shared pyproj
  `Geod` — `Geod(ellps="WGS84")` or a sphere `Geod(a=R, b=R)` with
  `FAI_SPHERE_RADIUS_M = 6_371_000.0`, on which Karney's solver yields exact great
  circles. `geodesic_distance(p1, p2, earth_model)` is the shared distance helper.
- The local Transverse Mercator projection (ADR 0001) is built on the same model
  (`+ellps=WGS84` vs `+R=6371000`), as is `snap_to_boundary`.
- `TaskTurnpoint` carries an `earth_model` attribute; `_task_to_turnpoints` fills it from
  `task.earth_model`. Public distance functions take an optional `earth_model` parameter
  and fall back to the first turnpoint's attribute, so existing call sites (CLI,
  KML/GeoJSON visualization) pick up the task's model without signature churn.

## Consequences

- Distances honor the task's declared model end to end; a meridian degree measures
  111 194.93 m on the FAI sphere vs ~110 574 m on WGS84 at the equator (asserted in
  `tests/distance/test_distance.py::TestEarthModel`).
- geopy was dropped from the distance subsystem in favour of pyproj (both use Karney's
  algorithm; pyproj parameterizes the sphere cleanly and provides fwd/inv in one object).
- All 22 reference tasks declare WGS84, so reference accuracy is unchanged by this
  decision. Notably, computing them on the FAI sphere does *not* reproduce XCTrack's
  displayed values either (ruled out in `docs/arch-review/2026-07-07-optimized-distance-findings.md`).

## Amendment (2026-09-27): the earth model is the route's, not each turnpoint's

The decision stands; the per-turnpoint mechanism in the third bullet is withdrawn.
`TaskTurnpoint.earth_model` copied a property of the task onto every turnpoint and the
optimizer read it off the first, so a misspelled model on any other turnpoint was
silently ignored and a list mixing the two earths measured 278 m differently depending
on which came first. The reason for the mechanism — no signature churn for the CLI and
the writers — no longer applied: all of them reach the optimizer through
`MeasuredTask.from_task`. `calculate_iteratively_refined_route`, `optimized_distance`
and `distance_through_centers` now take `earth_model` as an argument (None = WGS84) with
no fallback, `MeasuredTask` and `SpeedSection` pass the task's, and `TurnpointGeometry`
is a centre and a radius. Every distance report and KML output is byte-identical across
the reference corpus on both earth models.
