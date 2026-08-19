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

from .turnpoint import (
    EarthModelLike,
    LocalPlane,
    TurnpointGeometry,
    geod_for_earth_model,
    plane_circle,
    plane_optimal_point,
    snap_to_boundary,
)

#: How many alternating sweeps to allow before giving up. A safety bound, not
#: an accuracy setting — convergence normally stops far earlier — and the one
#: genuinely tunable number here: it is what ``num_iterations`` defaults to on
#: :func:`calculate_iteratively_refined_route` and :func:`optimized_distance`.
DEFAULT_NUM_ITERATIONS = 100

#: The convergence threshold the spec fixes: iteration stops once a full sweep
#: changes the total path length by less than this (FAI Sporting Code S7F
#: §7.1.3: ε = 0.1 m).
#:
#: **Not a tuning knob.** ADR 0004 settled that "precision is governed by the
#: spec's ε = 0.1 m, not by a sampling knob", which is why no public entry
#: point forwards it. It is named rather than inlined because the citation is
#: the payload — the same reason ``model/rounding.py`` exists. It lived in a
#: module called ``config.py`` beside the tunable above, which said
#: *configuration* about a value the spec settles.
CONVERGENCE_EPSILON_M = 0.1

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


def _boundary_toward(
    circle: PlaneCircle, target: tuple[float, float]
) -> tuple[float, float]:
    """Return the point of ``circle`` nearest ``target``, in the plane."""
    cx, cy, radius = circle
    if radius <= 0.0:
        return (cx, cy)
    dx, dy = target[0] - cx, target[1] - cy
    distance = math.hypot(dx, dy)
    if distance == 0.0:
        return (cx + radius, cy)
    return (cx + radius * dx / distance, cy + radius * dy / distance)


def _place_at_centers(circles: Sequence[PlaneCircle]) -> list[tuple[float, float]]:
    """Start every point at its circle's center."""
    return [(c[0], c[1]) for c in circles]


def _place_chained_forward(
    circles: Sequence[PlaneCircle],
) -> list[tuple[float, float]]:
    """Start each point at the boundary nearest its predecessor."""
    points = [(circles[0][0], circles[0][1])]
    for circle in circles[1:]:
        points.append(_boundary_toward(circle, points[-1]))
    return points


def _place_chained_backward(
    circles: Sequence[PlaneCircle],
) -> list[tuple[float, float]]:
    """Start each point at the boundary nearest its successor."""
    points: list[tuple[float, float]] = [(0.0, 0.0)] * len(circles)
    points[-1] = (circles[-1][0], circles[-1][1])
    for i in range(len(circles) - 2, -1, -1):
        points[i] = _boundary_toward(circles[i], points[i + 1])
    points[0] = (circles[0][0], circles[0][1])
    return points


#: The starting configurations every optimization is run from, shortest wins.
#:
#: The alternating method converges to a *local* optimum — Ding et al. say so —
#: and which one depends entirely on where the points start. Starting at the
#: circle centers alone left ``task_bevo`` 98.6 m above a route that touches
#: every one of its cylinders just as legitimately, so a single start does not
#: deliver the shortest path §7 asks for. The two chained placements are what
#: reach it: they begin on the boundaries, where the answer lives, rather than
#: at the centers, where it never does.
#:
#: Deterministic and ordered, so the same task always yields the same route.
#: Adding a placement costs one planar sweep and cannot make the result longer.
_INITIAL_PLACEMENTS = (
    _place_at_centers,
    _place_chained_forward,
    _place_chained_backward,
)


def _sweep_to_convergence(
    circles: Sequence[PlaneCircle],
    points: list[tuple[float, float]],
    max_sweeps: int,
    epsilon: float,
) -> list[tuple[float, float]]:
    """Alternate odd/even sweeps from ``points`` until the length settles.

    Each sweep first updates all odd-indexed points (even ones fixed), then
    all even-indexed points (odd ones fixed); every update places the point
    with the exact GetOptPi solution between its two neighbours. The start
    point (index 0, the takeoff center) stays fixed; the final point, having
    no successor, is the boundary point nearest its predecessor.

    Args:
        circles: Planar circles (x, y, radius), already deduplicated.
        points: One starting point per circle; mutated in place.
        max_sweeps: Upper bound on alternating sweeps.
        epsilon: Convergence threshold on total length change, in meters.

    Returns:
        The settled points — the same list that was passed in.
    """
    n = len(circles)
    previous_length = _polyline_length(points)
    for _ in range(max_sweeps):
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
        if abs(previous_length - current_length) < epsilon:
            break
        previous_length = current_length
    return points


def _optimize_plane_points(
    circles: Sequence[PlaneCircle],
    max_sweeps: int,
    epsilon: float = CONVERGENCE_EPSILON_M,
) -> list[tuple[float, float]]:
    """Run the Ding–Xie–Jiang alternating optimization in the plane.

    One route point is kept per circle. The sweep runs once from each of
    :data:`_INITIAL_PLACEMENTS` and the shortest result wins, because the
    method finds a local optimum and the starting configuration decides which
    one. Sweeps stop once the total path length changes by less than
    ``epsilon``.

    The winner is chosen on *planar* length, which is where the choice belongs:
    §7.1.3's PathFinder selects a path in Cartesian space and §7.1.8 only then
    measures it on the ellipsoid. Picking here also means the snapping and the
    geodesic legs are paid for once rather than once per placement.

    Consecutive identical circles are optimized as one point and duplicated
    back afterwards (see :func:`_collapse_duplicate_circles`), so the returned
    list always has one point per input circle.

    Args:
        circles: Planar circles (x, y, radius) in turnpoint order.
        max_sweeps: Upper bound on alternating sweeps, per placement.
        epsilon: Convergence threshold on total length change, in meters.

    Returns:
        The optimized (x, y) route points, one per input circle.
    """
    if not circles:
        return []

    circles, index_of = _collapse_duplicate_circles(circles)

    if len(circles) < 2:
        return [_place_at_centers(circles)[j] for j in index_of]

    best: list[tuple[float, float]] | None = None
    best_length = math.inf
    for place in _INITIAL_PLACEMENTS:
        points = _sweep_to_convergence(circles, place(circles), max_sweeps, epsilon)
        length = _polyline_length(points)
        if length < best_length:
            best, best_length = points, length

    assert best is not None  # _INITIAL_PLACEMENTS is never empty
    return [best[j] for j in index_of]


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
    plane_points = _optimize_plane_points(circles, max_sweeps=max_sweeps)

    path: list[tuple[float, float]] = []
    for i, ((x, y), (_, _, radius), tp) in enumerate(
        zip(plane_points, circles, turnpoints)
    ):
        if i == 0 or radius <= 0.0:
            # Takeoff start point and zero-radius circles (including LINE
            # goals) sit exactly on the turnpoint center.
            path.append((tp.center[0], tp.center[1]))
            continue
        # ProjectionCorrection (§7.1.7): re-place the planar solution at
        # exactly radius r on the earth model along the center→point azimuth.
        path.append(
            snap_to_boundary(
                plane.lon_lat((x, y)), tp.center, radius, plane.earth_model
            )
        )
    return path


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
        # Declared on TurnpointGeometry, so this is a protocol attribute now
        # rather than a getattr against an interface that denied having it.
        earth_model = turnpoints[0].earth_model

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
        earth_model: Earth model selector (None uses the turnpoints' model,
            defaulting to WGS84).

    Returns:
        Optimized distance in meters.
    """
    return calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        earth_model=earth_model,
    ).total_m
