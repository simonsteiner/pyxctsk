"""Route optimization for XCTrack tasks via the Ding–Xie–Jiang touring-n-circles algorithm.

This module computes the shortest route through a sequence of task turnpoint
cylinders per FAI Sporting Code S7F 2026 §7 (task distance = shortest path from
launch to goal touching each cylinder or goal line in order), following the
algorithm the spec cites: Ding, Xie & Jiang, "An Efficient Algorithm for
Touring n Circles" (MATEC Web of Conferences 232, 03027, EITCE 2018).

The implementation:

- projects all turnpoint centers into a local Transverse Mercator plane centred
  on the task area (§7.1.2),
- initializes one route point per turnpoint — from each of three deterministic
  placements, keeping the shortest, because the alternating method finds a
  *local* optimum and the starting configuration decides which one — and then
  alternately fixes the odd- and even-indexed points, updating each free point
  with the exact planar GetOptPi solution (crossing vs. reflection case)
  between its two neighbours,
- iterates until a full sweep changes the total path length by less than
  ε = 0.1 m (§7.1.3) or the sweep limit is reached,
- converts the points back to geographic coordinates and snaps each onto the
  true cylinder boundary at radius r on the selected earth model
  ("ProjectionCorrection", §7.1.7),
- runs all of that twice (§7.1.6): the first pass centres its plane on the
  turnpoints' bounding box, the second on the bounding box of the corrected
  path the first found, which is the taskAreaCentre the spec defines,
- sums the leg distances geodesically (WGS84 ellipsoid by default, great
  circles on the FAI sphere R = 6 371 000 m when the task specifies it).

The route starts at the takeoff *center* and each subsequent turnpoint circle
must be touched on its boundary, matching XCTrack's displayed optimized
distance (including mandatory "out and back" legs between concentric
cylinders of different radii).

The two steps either side of the solver live here too: :func:`plane_circle`
projects a turnpoint into the plane and :func:`point_on_boundary` corrects a
planar solution back onto its cylinder. :func:`boundary_point` composes the
three for one circle with fixed neighbours — the single-circle answer beside
the joint one, which is how tests reach the solver through the earth.

The main entry point is `calculate_iteratively_refined_route`, which returns an
`OptimizedRoute` carrying the points *and* the per-leg distances it measured.
`optimized_distance` is kept beside it for the common case of wanting only the
number; anything else — the points, the legs, a cumulative distance — is a field
or method on the route rather than another function here.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate

from .earth import EarthModelLike, geod_for_earth_model, snap_to_boundary
from .plane import LocalPlane
from .solver import optimize_plane_route, plane_optimal_point
from .turnpoint import TurnpointGeometry

#: How many alternating sweeps to allow before giving up. A safety bound, not
#: an accuracy setting — convergence normally stops far earlier — and the one
#: genuinely tunable number here: it is what ``num_iterations`` defaults to on
#: :func:`calculate_iteratively_refined_route` and :func:`optimized_distance`.
DEFAULT_NUM_ITERATIONS = 100


@dataclass(frozen=True)
class OptimizedRoute:
    """The optimized route through a task's turnpoints, with its legs kept.

    The optimizer measures every leg on its way to the total, so the route it
    found is the only thing that can answer "how far along the route is
    turnpoint i". Keeping the legs is what makes
    :meth:`cumulative_m` a projection of the route rather than a second
    optimization over a truncated task — the two do not agree, and re-deriving
    the answer once cost n optimizer runs per task.

    Attributes:
        points: One (lat, lon) per turnpoint, in task order: the takeoff
            center, then each subsequent point snapped onto its cylinder
            boundary (§7.1.7).
        legs: Geodesic length of each leg in meters, ``len(points) - 1``
            entries, measured on ``earth_model``.
        earth_model: The model the legs were measured on (an ``EarthModel``
            member, its string value, or None for WGS84).
    """

    points: tuple[tuple[float, float], ...]
    legs: tuple[float, ...]
    earth_model: EarthModelLike = None

    @property
    def total_m(self) -> float:
        """Total optimized distance in meters."""
        return float(sum(self.legs))

    def cumulative_m(self) -> list[float]:
        """Distance along the route to each point, in meters.

        One entry per point, starting at 0.0 for the takeoff, so the last entry
        equals :attr:`total_m`. A route with no points has no entries — the
        ``initial=0.0`` seed would otherwise report a distance to a point that
        does not exist.

        Returns:
            Cumulative distances in meters, one per point.
        """
        if not self.points:
            return []
        return list(accumulate(self.legs, initial=0.0))


def plane_circle(
    turnpoint: "TurnpointGeometry", plane: LocalPlane
) -> tuple[float, float, float]:
    """Return a turnpoint as the circle the solver sees: (x, y, radius).

    A projection and nothing else. It used to also apply the rule that **a LINE
    goal is a zero-radius circle at the goal center** — but so does
    :func:`~pyxctsk.distance.measured_task.task_to_turnpoints`, which builds
    every cylinder the library measures, and each docstring claimed to be the
    only place that rule lived while a third module picked a side in prose. The
    rule now belongs to the constructor: a LINE goal arrives here already
    carrying ``radius=0``, which is also what
    :func:`~pyxctsk.distance.center_distance.center_distance` reads it as.

    Args:
        turnpoint: Anything with a center and a radius.
        plane: The plane to project into.

    Returns:
        (x, y, radius) with radius in meters; 0 collapses to the center.
    """
    x, y = plane.xy(turnpoint.center)
    return (x, y, float(turnpoint.radius))


def point_on_boundary(
    turnpoint: TurnpointGeometry,
    plane: LocalPlane,
    plane_point: tuple[float, float],
    radius: float,
) -> tuple[float, float]:
    """ProjectionCorrection (S7F §7.1.7): a planar solution put on the boundary.

    **The one spelling of the rule.** It had two — this one and the loop body
    of ``route_optimization._corrected_path`` — and they did not agree: one
    guarded ``radius == 0.0`` where the other guarded ``<= 0.0``, and one
    snapped against the turnpoint's own radius where the other snapped against
    the projected one. Identical answers today, and two places to change
    snapping policy, of which the product runs one.

    Args:
        turnpoint: The turnpoint whose circle the point belongs to.
        plane: The projection the point was solved in, which carries the earth
            model it is snapped back onto — so a planar solution and the
            boundary it is corrected onto cannot be measured on different
            earths.
        plane_point: The planar (x, y) solution.
        radius: The circle's radius in the plane. Zero collapses to the centre,
            which is what a LINE goal arrives here as.

    Returns:
        (lat, lon) on the true boundary, or the centre for a zero radius.
    """
    if radius <= 0.0:
        return turnpoint.center
    return snap_to_boundary(
        plane.lon_lat(plane_point), turnpoint.center, radius, plane.earth_model
    )


def boundary_point(
    turnpoint: TurnpointGeometry,
    prev_point: tuple[float, float],
    next_point: tuple[float, float],
    plane: LocalPlane,
) -> tuple[float, float]:
    """Where a route touches one circle, given fixed neighbours (GetOptPi).

    The single-circle answer, as against
    :func:`~pyxctsk.distance.route_optimization.calculate_iteratively_refined_route`,
    which solves every circle jointly and is what a task's route is measured
    with. Both project, solve and correct; only the solve differs.

    **The plane is required.** It used to default to one centred on this
    turnpoint — a projection no shipped code path ever builds — and the
    crossing-case tests took that default, so a fix to the projection the
    product does use could go green and ship nothing. ``plane.py`` records
    that failure as fixed; the default was the half of it left in place.

    Args:
        turnpoint: The circle to touch.
        prev_point: (lat, lon) of the previous point on the route.
        next_point: (lat, lon) of the next point on the route.
        plane: The projection to solve in — the task's own, from
            ``LocalPlane.around`` over every turnpoint centre, unless the
            caller means something else and says so.

    Returns:
        (lat, lon) on the cylinder boundary, or the centre for a LINE goal.
    """
    cx, cy, radius = plane_circle(turnpoint, plane)
    if radius <= 0.0:
        return turnpoint.center
    xy = plane_optimal_point(
        plane.xy(prev_point), plane.xy(next_point), (cx, cy), radius
    )
    return point_on_boundary(turnpoint, plane, xy, radius)


def _corrected_path(
    turnpoints: Sequence[TurnpointGeometry],
    plane: LocalPlane,
    max_sweeps: int,
) -> list[tuple[float, float]]:
    """Optimize in ``plane`` and correct the result back onto the boundaries.

    One turn of the §7.1.8 RouteOptimizer crank: project, run the alternating
    sweep, convert back, and apply ProjectionCorrection (§7.1.7). Separated out
    because §7.1.6 turns it twice — once to find the task area centre, once to
    use it.

    Args:
        turnpoints: The task turnpoints.
        plane: The projection to solve in, which carries the earth model its
            points are snapped back onto.
        max_sweeps: Upper bound on alternating sweeps, per placement.

    Returns:
        One (lat, lon) per turnpoint, each on its cylinder boundary.
    """
    circles = [plane_circle(tp, plane) for tp in turnpoints]
    # The takeoff is a point: the route starts at its centre whatever its
    # radius, because the takeoff cylinder is not touched (ADR 0002). Stated
    # once, here, as the circle the solver is handed — the solver has no rule
    # about its first circle, and ProjectionCorrection puts a zero-radius
    # solution back on the centre.
    x, y, _ = circles[0]
    circles[0] = (x, y, 0.0)
    plane_points = optimize_plane_route(circles, max_sweeps=max_sweeps)

    return [
        point_on_boundary(tp, plane, xy, radius)
        for xy, (_, _, radius), tp in zip(plane_points, circles, turnpoints)
    ]


def calculate_iteratively_refined_route(
    turnpoints: Sequence[TurnpointGeometry],
    num_iterations: int | None = None,
    earth_model: EarthModelLike = None,
) -> OptimizedRoute:
    """Calculate the optimized route with the alternating point-circle-point method.

    Optimization runs in a local Transverse Mercator plane (§7.1.2) until the
    total length converges below ε = 0.1 m (§7.1.3); the resulting points are
    snapped onto the true cylinder boundaries (§7.1.7) and the legs measured
    geodesically on the task's earth model.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): The task turnpoints.
        num_iterations (Optional[int]): Maximum number of alternating sweeps.
        earth_model: The earth to measure on (``EarthModel`` member, its
            string value, or None for WGS84). The whole route's, not any one
            turnpoint's — ``MeasuredTask.from_task`` passes the task's.

    Returns:
        OptimizedRoute: The route points, its per-leg distances, and the earth
        model they were measured on.

    Raises:
        UnmeasurableRouteError: If the local plane the route is solved in
            cannot represent a turnpoint or a route point (see
            :class:`~pyxctsk.distance.plane.LocalPlane`).
    """
    max_sweeps = (
        num_iterations if num_iterations is not None else DEFAULT_NUM_ITERATIONS
    )
    if len(turnpoints) < 2:
        return OptimizedRoute(
            points=tuple((tp.center[0], tp.center[1]) for tp in turnpoints),
            legs=(),
            earth_model=earth_model,
        )

    # §7.1.6 runs the whole thing twice. The first pass centres its plane on
    # the bounding box of the *turnpoints*; the second re-centres on the
    # bounding box of the corrected path the first produced, and that centre
    # is the taskAreaCentre the spec says to keep. The corrected path is a
    # tighter box than the turnpoint centers — its points sit on cylinder
    # boundaries, not at their middles — so the two differ whenever a large
    # cylinder pulls the turnpoint box wider than the route ever goes.
    plane = LocalPlane.around([tp.center for tp in turnpoints], earth_model)
    route = _corrected_path(turnpoints, plane, max_sweeps)
    plane = LocalPlane.around(route, earth_model)
    route = _corrected_path(turnpoints, plane, max_sweeps)

    g = geod_for_earth_model(earth_model)
    legs = []
    for i in range(len(route) - 1):
        _, _, leg = g.inv(route[i][1], route[i][0], route[i + 1][1], route[i + 1][0])
        legs.append(float(leg))

    return OptimizedRoute(
        points=tuple(route), legs=tuple(legs), earth_model=earth_model
    )


def optimized_distance(
    turnpoints: Sequence[TurnpointGeometry],
    num_iterations: int | None = None,
    earth_model: EarthModelLike = None,
) -> float:
    """Compute the fully optimized task distance through the turnpoints.

    This finds the shortest route starting at the takeoff center and touching
    every turnpoint cylinder (and goal line) in order, per FAI Sporting Code
    S7F §7, using the Ding–Xie–Jiang alternating optimization.

    Args:
        turnpoints: The task turnpoints.
        num_iterations: Maximum number of alternating sweeps.
        earth_model: Earth model selector (None for WGS84).

    Returns:
        Optimized distance in meters.

    Raises:
        UnmeasurableRouteError: As
            :func:`calculate_iteratively_refined_route` raises it.
    """
    return calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        earth_model=earth_model,
    ).total_m
