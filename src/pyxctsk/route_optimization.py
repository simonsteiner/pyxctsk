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

The main entry point is `calculate_iteratively_refined_route`; `optimized_distance`
and `optimized_route_coordinates` are thin wrappers over it.
"""

import math
from collections.abc import Sequence

from .optimization_config import CONVERGENCE_EPSILON_M, get_optimization_config
from .turnpoint import (
    TurnpointGeometry,
    geod_for_earth_model,
    local_tm_transformers,
    plane_optimal_point,
)

#: A planar circle: (x, y, radius) in the local Transverse Mercator plane.
PlaneCircle = tuple[float, float, float]


def _plane_circles(
    turnpoints: Sequence[TurnpointGeometry], earth_model: object
) -> tuple[list[PlaneCircle], object]:
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

    Args:
        circles: Planar circles (x, y, radius) in turnpoint order.
        max_sweeps: Upper bound on alternating sweeps.
        epsilon: Convergence threshold on total length change, in meters.
        show_progress: Whether to print per-sweep progress.

    Returns:
        The optimized (x, y) route points, one per circle.
    """
    n = len(circles)
    points: list[tuple[float, float]] = [(c[0], c[1]) for c in circles]
    if n < 2:
        return points

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

    return points


def calculate_iteratively_refined_route(
    turnpoints: Sequence[TurnpointGeometry],
    num_iterations: int | None = None,
    angle_step: int | None = None,
    show_progress: bool = False,
    beam_width: int | None = None,
    earth_model: object = None,
) -> tuple[float, list[tuple[float, float]]]:
    """Calculate the optimized route with the alternating point-circle-point method.

    Optimization runs in a local Transverse Mercator plane (§7.1.2) until the
    total length converges below ε = 0.1 m (§7.1.3); the resulting points are
    snapped onto the true cylinder boundaries (§7.1.7) and the legs summed
    geodesically on the task's earth model.

    Args:
        turnpoints (Sequence[TurnpointGeometry]): The task turnpoints.
        num_iterations (Optional[int]): Maximum number of alternating sweeps.
        angle_step (Optional[int]): Deprecated, ignored (kept for API compatibility).
        show_progress (bool): Whether to show progress indicators.
        beam_width (Optional[int]): Deprecated, ignored (kept for API compatibility).
        earth_model: Earth model selector (``EarthModel`` member, its string
            value, or None). None falls back to the first turnpoint's
            ``earth_model`` attribute, defaulting to WGS84.

    Returns:
        Tuple[float, List[Tuple[float, float]]]: Tuple of (optimized_distance_meters, route_coordinates).
    """
    config = get_optimization_config(angle_step, beam_width, num_iterations)
    if len(turnpoints) < 2:
        return 0.0, [(tp.center[0], tp.center[1]) for tp in turnpoints]

    if earth_model is None:
        earth_model = getattr(turnpoints[0], "earth_model", None)

    if show_progress and turnpoints[-1].goal_type == "LINE":
        print("    🏁 Task has a goal line finish")

    circles, to_geo = _plane_circles(turnpoints, earth_model)
    plane_points = _optimize_plane_points(
        circles,
        max_sweeps=config["num_iterations"],
        show_progress=show_progress,
    )

    g = geod_for_earth_model(earth_model)
    route: list[tuple[float, float]] = []
    for i, ((x, y), (cx, cy, radius), tp) in enumerate(
        zip(plane_points, circles, turnpoints)
    ):
        if i == 0 or radius <= 0.0:
            # Takeoff start point and zero-radius circles (including LINE
            # goals) sit exactly on the turnpoint center.
            route.append((tp.center[0], tp.center[1]))
            continue
        # ProjectionCorrection (§7.1.7): re-place the planar solution at
        # exactly radius r on the earth model along the center→point azimuth.
        azimuth = math.degrees(math.atan2(x - cx, y - cy))
        lon, lat, _ = g.fwd(tp.center[1], tp.center[0], azimuth, radius)
        route.append((lat, lon))

    distance = 0.0
    for i in range(len(route) - 1):
        _, _, leg = g.inv(route[i][1], route[i][0], route[i + 1][1], route[i + 1][0])
        distance += float(leg)

    if show_progress:
        print(f"    ✅ Optimized route: {distance / 1000.0:.3f}km")

    return distance, route


def optimized_distance(
    turnpoints: Sequence[TurnpointGeometry],
    angle_step: int | None = None,
    show_progress: bool = False,
    beam_width: int | None = None,
    num_iterations: int | None = None,
    earth_model: object = None,
) -> float:
    """Compute the fully optimized task distance through the turnpoints.

    This finds the shortest route starting at the takeoff center and touching
    every turnpoint cylinder (and goal line) in order, per FAI Sporting Code
    S7F §7, using the Ding–Xie–Jiang alternating optimization.

    Args:
        turnpoints: The task turnpoints.
        angle_step: Deprecated, ignored (kept for API compatibility).
        show_progress: Whether to show progress indicators.
        beam_width: Deprecated, ignored (kept for API compatibility).
        num_iterations: Maximum number of alternating sweeps.
        earth_model: Earth model selector (None uses the turnpoints' model,
            defaulting to WGS84).

    Returns:
        Optimized distance in meters.
    """
    distance, _ = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        angle_step=angle_step,
        show_progress=show_progress,
        beam_width=beam_width,
        earth_model=earth_model,
    )
    return distance


def optimized_route_coordinates(
    turnpoints: Sequence[TurnpointGeometry],
    task_turnpoints: object | None = None,  # Kept for backward compatibility
    angle_step: int | None = None,
    beam_width: int | None = None,
    num_iterations: int | None = None,
    earth_model: object = None,
) -> list[tuple[float, float]]:
    """Compute the fully optimized route coordinates through the turnpoints.

    Args:
        turnpoints: The task turnpoints.
        task_turnpoints: Unused; kept for backward compatibility.
        angle_step: Deprecated, ignored (kept for API compatibility).
        beam_width: Deprecated, ignored (kept for API compatibility).
        num_iterations: Maximum number of alternating sweeps.
        earth_model: Earth model selector (None uses the turnpoints' model,
            defaulting to WGS84).

    Returns:
        List of (lat, lon) tuples representing the optimized route coordinates.
    """
    _, route_coordinates = calculate_iteratively_refined_route(
        turnpoints,
        num_iterations=num_iterations,
        angle_step=angle_step,
        show_progress=False,
        beam_width=beam_width,
        earth_model=earth_model,
    )
    return route_coordinates
