"""Route optimization for XCTrack tasks via the Ding–Xie–Jiang touring-n-circles algorithm.

This module computes the shortest route through a sequence of task turnpoint
cylinders per FAI Sporting Code S7F 2026 §7 (task distance = shortest path from
launch to goal touching each cylinder or goal line in order), following the
algorithm the spec cites: Ding, Xie & Jiang, "An Efficient Algorithm for
Touring n Circles" (MATEC Web of Conferences 232, 03027, EITCE 2018).

The implementation:

- projects all turnpoint centers into a local Transverse Mercator plane centred
  on the task area (§7.1.2),
- initializes one route point per turnpoint and then alternately fixes the
  odd- and even-indexed points, updating each free point with the exact planar
  GetOptPi solution (crossing vs. reflection case) between its two neighbours,
- iterates until a full sweep changes the total path length by less than
  ε = 0.1 m (§7.1.3) or the sweep limit is reached,
- converts the points back to geographic coordinates and snaps each onto the
  true cylinder boundary at radius r on the selected earth model
  ("ProjectionCorrection", §7.1.7),
- sums the leg distances geodesically (WGS84 ellipsoid by default, great
  circles on the FAI sphere R = 6 371 000 m when the task specifies it).

The route starts at the takeoff *center* and each subsequent turnpoint circle
must be touched on its boundary, matching XCTrack's displayed optimized
distance (including mandatory "out and back" legs between concentric
cylinders of different radii).

The main entry point is `calculate_iteratively_refined_route`, which returns an
`OptimizedRoute` carrying the points *and* the per-leg distances it measured.
`optimized_distance` is kept beside it for the common case of wanting only the
number; anything else — the points, the legs, a cumulative distance — is a field
or method on the route rather than another function here.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate

from pyproj import Transformer

from .config import CONVERGENCE_EPSILON_M, DEFAULT_NUM_ITERATIONS
from .turnpoint import (
    TurnpointGeometry,
    geod_for_earth_model,
    local_tm_transformers,
    plane_optimal_point,
    snap_to_boundary,
)

#: A planar circle: (x, y, radius) in the local Transverse Mercator plane.
PlaneCircle = tuple[float, float, float]

#: Two circles closer than this in both center and radius are the same circle.
#: Identical turnpoints project through the same transformer to bit-identical
#: coordinates, so this only guards against float noise, not real geometry —
#: concentric cylinders of *different* radii stay distinct (see ADR 0002).
_SAME_CIRCLE_TOLERANCE_M = 1e-6


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
    earth_model: object = None

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


def _plane_circles(
    turnpoints: Sequence[TurnpointGeometry], earth_model: object
) -> tuple[list[PlaneCircle], Transformer]:
    """Project turnpoint cylinders into a local Transverse Mercator plane.

    The plane is centred on the mean of the turnpoint centers (the task area,
    §7.1.2). A LINE goal contributes a zero-radius circle: the goal line is
    perpendicular to the final approach and centred on the goal, so its
    optimal crossing point is the goal center itself.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): The task turnpoints.
        earth_model: Earth model selector (None means WGS84).

    Returns:
        Tuple of (planar circles, inverse transformer back to geographic
        coordinates).
    """
    lat0 = sum(tp.center[0] for tp in turnpoints) / len(turnpoints)
    lon0 = sum(tp.center[1] for tp in turnpoints) / len(turnpoints)
    to_plane, to_geo = local_tm_transformers(lat0, lon0, earth_model)

    circles: list[PlaneCircle] = []
    for tp in turnpoints:
        x, y = to_plane.transform(tp.center[1], tp.center[0])
        radius = 0.0 if tp.goal_type == "LINE" else float(tp.radius)
        circles.append((x, y, radius))
    return circles, to_geo


def _closest_circle_point(
    point: tuple[float, float], circle: PlaneCircle
) -> tuple[float, float]:
    """Return the planar circle-boundary point nearest to ``point``.

    Used for the final turnpoint, which has no successor: the shortest way to
    touch its circle from the previous route point is the radially nearest
    boundary point (regardless of whether the previous point lies inside or
    outside the circle).

    Args:
        point: (x, y) of the previous route point.
        circle: (x, y, radius) of the final circle.

    Returns:
        (x, y) of the nearest boundary point, or the center for radius 0.
    """
    cx, cy, radius = circle
    if radius <= 0.0:
        return (cx, cy)
    dx, dy = point[0] - cx, point[1] - cy
    dist = math.hypot(dx, dy)
    if dist == 0.0:
        return (cx + radius, cy)
    return (cx + radius * dx / dist, cy + radius * dy / dist)


def _same_circle(a: PlaneCircle, b: PlaneCircle) -> bool:
    """Return True if two planar circles are the same circle."""
    return (
        math.hypot(a[0] - b[0], a[1] - b[1]) <= _SAME_CIRCLE_TOLERANCE_M
        and abs(a[2] - b[2]) <= _SAME_CIRCLE_TOLERANCE_M
    )


def _collapse_duplicate_circles(
    circles: Sequence[PlaneCircle],
) -> tuple[list[PlaneCircle], list[int]]:
    """Collapse runs of consecutive identical circles into one.

    Touching a circle and then touching the same circle again is satisfied by
    a single touch, so duplicated turnpoints must contribute a zero-length
    leg. Optimizing them as separate points instead creates a spurious local
    minimum: once two route points on one circle coincide, moving either adds
    length to the leg between them exactly as fast as it saves on the
    neighbouring leg, so the alternating sweep freezes wherever it happens to
    be rather than at the true optimum. Collapsing first removes the
    degeneracy; the duplicate points are restored afterwards.

    Index 0 is never collapsed: the route starts at the takeoff *center*, not
    on its boundary, so a turnpoint repeating the takeoff circle is a real
    center-to-boundary leg.

    Concentric circles of *different* radii are left alone — their
    out-and-back leg is required (ADR 0002).

    Args:
        circles: Planar circles (x, y, radius) in turnpoint order.

    Returns:
        Tuple of (deduplicated circles, index into that list for each input
        circle).
    """
    unique: list[PlaneCircle] = [circles[0]]
    index_of: list[int] = [0]
    for i, circle in enumerate(circles[1:], start=1):
        # ``i > 1``: index 1 is never collapsed into index 0, per the takeoff
        # rule above. Every later circle may merge into its predecessor.
        collapsible = i > 1 and _same_circle(unique[-1], circle)
        if not collapsible:
            unique.append(circle)
        index_of.append(len(unique) - 1)
    return unique, index_of


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    """Total planar length of a polyline given as (x, y) points."""
    return sum(
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
    )


def _optimize_plane_points(
    circles: Sequence[PlaneCircle],
    max_sweeps: int,
    epsilon: float = CONVERGENCE_EPSILON_M,
    show_progress: bool = False,
) -> list[tuple[float, float]]:
    """Run the Ding–Xie–Jiang alternating optimization in the plane.

    One route point is kept per circle, initialized at the circle centers.
    Each sweep first updates all odd-indexed points (even ones fixed), then
    all even-indexed points (odd ones fixed); every update places the point
    with the exact GetOptPi solution between its two neighbours. The start
    point (index 0, the takeoff center) stays fixed; the final point, having
    no successor, is the boundary point nearest its predecessor. Sweeps stop
    once the total path length changes by less than ``epsilon``.

    Consecutive identical circles are optimized as one point and duplicated
    back afterwards (see :func:`_collapse_duplicate_circles`), so the returned
    list always has one point per input circle.

    Args:
        circles: Planar circles (x, y, radius) in turnpoint order.
        max_sweeps: Upper bound on alternating sweeps.
        epsilon: Convergence threshold on total length change, in meters.
        show_progress: Whether to print per-sweep progress.

    Returns:
        The optimized (x, y) route points, one per input circle.
    """
    if not circles:
        return []

    circles, index_of = _collapse_duplicate_circles(circles)

    n = len(circles)
    points: list[tuple[float, float]] = [(c[0], c[1]) for c in circles]
    if n < 2:
        return [points[j] for j in index_of]

    previous_length = _polyline_length(points)
    for sweep in range(max_sweeps):
        for parity in (1, 0):
            for i in range(1, n):
                if i % 2 != parity:
                    continue
                cx, cy, radius = circles[i]
                if i == n - 1:
                    points[i] = _closest_circle_point(points[i - 1], circles[i])
                else:
                    points[i] = plane_optimal_point(
                        points[i - 1], points[i + 1], (cx, cy), radius
                    )
        current_length = _polyline_length(points)
        if show_progress:
            print(f"    🔄 Sweep {sweep + 1}: {current_length / 1000.0:.4f}km")
        if abs(previous_length - current_length) < epsilon:
            break
        previous_length = current_length

    return [points[j] for j in index_of]


def calculate_iteratively_refined_route(
    turnpoints: Sequence[TurnpointGeometry],
    num_iterations: int | None = None,
    show_progress: bool = False,
    earth_model: object = None,
) -> OptimizedRoute:
    """Calculate the optimized route with the alternating point-circle-point method.

    Optimization runs in a local Transverse Mercator plane (§7.1.2) until the
    total length converges below ε = 0.1 m (§7.1.3); the resulting points are
    snapped onto the true cylinder boundaries (§7.1.7) and the legs measured
    geodesically on the task's earth model.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): The task turnpoints.
        num_iterations (Optional[int]): Maximum number of alternating sweeps.
        show_progress (bool): Whether to show progress indicators.
        earth_model: Earth model selector (``EarthModel`` member, its string
            value, or None). None falls back to the first turnpoint's
            ``earth_model`` attribute, defaulting to WGS84.

    Returns:
        OptimizedRoute: The route points, its per-leg distances, and the earth
        model they were measured on.
    """
    max_sweeps = (
        num_iterations if num_iterations is not None else DEFAULT_NUM_ITERATIONS
    )
    if earth_model is None and turnpoints:
        earth_model = getattr(turnpoints[0], "earth_model", None)

    if len(turnpoints) < 2:
        return OptimizedRoute(
            points=tuple((tp.center[0], tp.center[1]) for tp in turnpoints),
            legs=(),
            earth_model=earth_model,
        )

    if show_progress and turnpoints[-1].goal_type == "LINE":
        print("    🏁 Task has a goal line finish")

    circles, to_geo = _plane_circles(turnpoints, earth_model)
    plane_points = _optimize_plane_points(
        circles,
        max_sweeps=max_sweeps,
        show_progress=show_progress,
    )

    g = geod_for_earth_model(earth_model)
    route: list[tuple[float, float]] = []
    for i, ((x, y), (_, _, radius), tp) in enumerate(
        zip(plane_points, circles, turnpoints)
    ):
        if i == 0 or radius <= 0.0:
            # Takeoff start point and zero-radius circles (including LINE
            # goals) sit exactly on the turnpoint center.
            route.append((tp.center[0], tp.center[1]))
            continue
        # ProjectionCorrection (§7.1.7): re-place the planar solution at
        # exactly radius r on the earth model along the center→point azimuth.
        route.append(
            snap_to_boundary(to_geo.transform(x, y), tp.center, radius, earth_model)
        )

    legs = []
    for i in range(len(route) - 1):
        _, _, leg = g.inv(route[i][1], route[i][0], route[i + 1][1], route[i + 1][0])
        legs.append(float(leg))

    optimized = OptimizedRoute(
        points=tuple(route), legs=tuple(legs), earth_model=earth_model
    )

    if show_progress:
        print(f"    ✅ Optimized route: {optimized.total_m / 1000.0:.3f}km")

    return optimized


def optimized_distance(
    turnpoints: Sequence[TurnpointGeometry],
    show_progress: bool = False,
    num_iterations: int | None = None,
    earth_model: object = None,
) -> float:
    """Compute the fully optimized task distance through the turnpoints.

    This finds the shortest route starting at the takeoff center and touching
    every turnpoint cylinder (and goal line) in order, per FAI Sporting Code
    S7F §7, using the Ding–Xie–Jiang alternating optimization.

    Args:
        turnpoints: The task turnpoints.
        show_progress: Whether to show progress indicators.
        num_iterations: Maximum number of alternating sweeps.
        earth_model: Earth model selector (None uses the turnpoints' model,
            defaulting to WGS84).

    Returns:
        Optimized distance in meters.
    """
    return calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        show_progress=show_progress,
        earth_model=earth_model,
    ).total_m
