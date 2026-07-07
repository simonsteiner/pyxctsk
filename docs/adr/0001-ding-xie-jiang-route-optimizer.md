# ADR 0001: Use the Ding–Xie–Jiang alternating point-circle-point optimizer

Date: 2026-07-07 · Status: Accepted

## Context

pyxctsk's optimized task distance was computed by a dynamic program with beam search and
iterative "look-ahead" refinement — a heuristic that could prune the optimal path and had
no principled convergence criterion. FAI Sporting Code S7F 2026 §7 specifies the
algorithm to use: run the shortest-path search in a localized Transverse Mercator plane
(§7.1.2) using the "PathFinder" method it cites — Ding, Xie & Jiang, *"An Efficient
Algorithm for Touring n Circles"* ([MATEC Web of Conferences 232, 03027, EITCE 2018](https://www.matec-conferences.org/articles/matecconf/pdf/2018/91/matecconf_eitce2018_03027.pdf))
— converge at ε = 0.1 m (§7.1.3), transform back to WGS84, snap each point onto its
control-zone boundary ("ProjectionCorrection", §7.1.7), and only then measure distances
on the ellipsoid. See `docs/Audit-of-pyxctsk-Route-Optimization.md`.

## Decision

Replace the DP/beam-search core in `route_optimization.py` with the spec's pipeline:

1. Project all turnpoint centers into a local Transverse Mercator plane centred on the
   mean of the centers (`local_tm_transformers` in `turnpoint.py`); a LINE goal becomes a
   zero-radius circle (see ADR 0002).
2. Keep one route point per circle, initialized at the centers; the start point (takeoff
   center) stays fixed.
3. Sweep alternately over odd- then even-indexed points, updating each free point with
   the exact planar GetOptPi solution (`plane_optimal_point`): the *crossing* case
   (segment–circle intersection — always when exactly one neighbour is inside the
   circle, per the paper's Theorem 1, or when the segment passes through it) or the
   *reflection* (point-circle-point) case, solved by a coarse 64-point scan plus bounded
   scalar minimization. The final point, having no successor, is the boundary point
   nearest its predecessor.
4. Stop when a full sweep changes the total planar length by less than
   `CONVERGENCE_EPSILON_M = 0.1` (or after `DEFAULT_NUM_ITERATIONS = 100` sweeps).
5. Convert the points back to geographic coordinates, snap each onto the true cylinder
   boundary along the geodesic center→point azimuth (`snap_to_boundary`), and sum the
   legs geodesically on the task's earth model (ADR 0003).

GetOptPi minimizes over the *disk* interpretation only in the crossing case; combined
with boundary snapping this makes each local update the exact minimizer, so the
coordinate-descent sweeps converge monotonically.

## Consequences

- The optimizer finds the true geometric optimum (the old heuristic already came close on
  the reference tasks but with no guarantee), and is roughly an order of magnitude
  faster — the full test suite dropped from minutes to ~10 s.
- Accuracy against XCTrack's displayed values is limited by *XCTrack's own* optimizer,
  not by pyxctsk — see `docs/XCTrack-Optimized-Distance-Findings.md`. Acceptance tests
  assert 0.1 %/50 m (plus 50 m display rounding) on well-conditioned tasks and 1 %
  overall.
- The DP internals (`_run_dp`, look-ahead strategies, beam width) are gone; the
  `TurnpointGeometry` protocol now exposes the attributes the optimizer needs
  (`center`, `radius`, `goal_type`) instead of an `optimal_point` method (see ADR 0004
  for the API removals).
