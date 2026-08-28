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

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import accumulate

from .earth import EarthModelLike, geod_for_earth_model
from .plane import LocalPlane
from .solver import CONVERGENCE_EPSILON_M as CONVERGENCE_EPSILON_M
from .solver import optimize_plane_route
from .turnpoint import TurnpointGeometry, plane_circle, point_on_boundary

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
    plane_points = optimize_plane_route(circles, max_sweeps=max_sweeps)

    path: list[tuple[float, float]] = []
    for i, (xy, (_, _, radius), tp) in enumerate(
        zip(plane_points, circles, turnpoints)
    ):
        # The takeoff start point sits on the centre whatever its radius: the
        # takeoff cylinder is not touched (ADR 0002). Everything else goes
        # through ProjectionCorrection (§7.1.7), which owns the zero-radius
        # case — a LINE goal included.
        if i == 0:
            path.append((tp.center[0], tp.center[1]))
            continue
        path.append(point_on_boundary(tp, plane, xy, radius))
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
