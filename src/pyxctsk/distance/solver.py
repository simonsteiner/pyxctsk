"""Pure planar route optimization from Ding, Xie & Jiang.

"An Efficient Algorithm for Touring n Circles" (MATEC Web of Conferences 232,
03027, EITCE 2018). This module owns both Algorithm 1's optimal point on one
circle and Algorithm 2's alternating route optimization through many circles.

Pure planar geometry. It knows nothing about turnpoints, tasks or the earth:
the caller projects circles into a plane, calls :func:`optimize_plane_route`,
and projects the result back. The route-level function is the module seam; its
placement and sweep machinery stays private.
"""

import math
from collections.abc import Sequence

#: The convergence threshold fixed by FAI Sporting Code S7F §7.1.3.
CONVERGENCE_EPSILON_M = 0.1

#: A planar circle represented as (x, y, radius), all in the same units.
PlaneCircle = tuple[float, float, float]

#: Consecutive circles within this tolerance are treated as identical.
_SAME_CIRCLE_TOLERANCE_M = 1e-6


def _segment_circle_intersections(
    p1: tuple[float, float],
    p2: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> list[float]:
    """Find where the planar segment p1→p2 meets a circle boundary.

    Args:
        p1: Segment start (x, y).
        p2: Segment end (x, y).
        center: Circle center (x, y).
        radius: Circle radius (same units as coordinates).

    Returns:
        Sorted parameters ``t`` in [0, 1] (with the point at ``p1 + t*(p2-p1)``)
        where the segment crosses the circle; empty if it does not.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    fx, fy = p1[0] - center[0], p1[1] - center[1]
    a = dx * dx + dy * dy
    if a == 0.0:
        return []
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return []
    sqrt_disc = math.sqrt(disc)
    roots = ((-b - sqrt_disc) / (2.0 * a), (-b + sqrt_disc) / (2.0 * a))
    return sorted(t for t in roots if 0.0 <= t <= 1.0)


def _plane_point_at(
    center: tuple[float, float], radius: float, theta: float
) -> tuple[float, float]:
    """Return the boundary point of a planar circle at angle ``theta``."""
    return (center[0] + radius * math.cos(theta), center[1] + radius * math.sin(theta))


def _plane_pcp_point(
    p1: tuple[float, float],
    p2: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> tuple[float, float]:
    """Solve the reflection (point-circle-point) case in the plane.

    Finds the boundary point minimizing ``|p1 - x| + |x - p2|``. A coarse
    global scan brackets the minimum, then a bounded scalar minimization
    refines it — robust for every endpoint configuration (both neighbours
    outside, or both inside, the circle).

    Args:
        p1: Previous point (x, y).
        p2: Next point (x, y).
        center: Circle center (x, y).
        radius: Circle radius.

    Returns:
        The optimal boundary point (x, y).
    """
    # scipy.optimize is 297 ms of the 400 ms `import pyxctsk` used to cost,
    # and this is the only place in the library that needs it. Importing it
    # here means a caller that only parses, converts or draws a task never
    # pays for the optimizer's dependency tree; sys.modules caches it, so the
    # optimizer itself pays a dict lookup per call.
    from scipy.optimize import fminbound

    def total(theta: float) -> float:
        x, y = _plane_point_at(center, radius, theta)
        return math.hypot(x - p1[0], y - p1[1]) + math.hypot(x - p2[0], y - p2[1])

    scan = 64
    best_k = min(range(scan), key=lambda k: total(2.0 * math.pi * k / scan))
    lo = 2.0 * math.pi * (best_k - 1) / scan
    hi = 2.0 * math.pi * (best_k + 1) / scan
    theta_opt = float(fminbound(total, lo, hi, xtol=1e-12))
    return _plane_point_at(center, radius, theta_opt)


def plane_optimal_point(
    prev_point: tuple[float, float],
    next_point: tuple[float, float],
    center: tuple[float, float],
    radius: float,
) -> tuple[float, float]:
    """Optimal point on a planar circle between two fixed neighbours (GetOptPi).

    Implements Algorithm 1 (GetoptPi) of Ding, Xie & Jiang: if the segment
    between the neighbours crosses the circle boundary — which per their
    Theorem 1 is always the case when exactly one neighbour lies inside the
    circle — the optimal point is the segment-circle intersection (*crossing*
    case, adding no length). Otherwise (both neighbours outside with no
    intersection, or both inside) it is the *reflection* point-circle-point
    solution on the boundary.

    Args:
        prev_point: Previous fixed point (x, y) in the local plane.
        next_point: Next fixed point (x, y) in the local plane.
        center: Circle center (x, y).
        radius: Circle radius in plane units (meters).

    Returns:
        The optimal (x, y) point on the circle boundary (the center for a
        zero-radius circle).
    """
    if radius <= 0.0:
        return center

    prev_inside = (
        math.hypot(prev_point[0] - center[0], prev_point[1] - center[1]) < radius
    )
    next_inside = (
        math.hypot(next_point[0] - center[0], next_point[1] - center[1]) < radius
    )

    # Crossing case, stated once. It applies unless *both* neighbours are
    # inside: with exactly one inside the segment meets the boundary exactly
    # once (their Theorem 1), and with both outside it may or may not. Either
    # way the answer is where the segment leaves the region already covered,
    # which is the first intersection unless we start inside.
    #
    # This was written as two branches calling the same function on the same
    # arguments and returning the same interpolation, differing only in that
    # root choice — the module's most delicate function, duplicated. The
    # collapse is exact over 4000 randomized configurations spanning all four
    # inside/outside combinations.
    if not (prev_inside and next_inside):
        ts = _segment_circle_intersections(prev_point, next_point, center, radius)
        if ts:
            t = ts[-1] if prev_inside else ts[0]
            return (
                prev_point[0] + t * (next_point[0] - prev_point[0]),
                prev_point[1] + t * (next_point[1] - prev_point[1]),
            )

    # Reflection case (also the numerically-degenerate tangent fallback).
    return _plane_pcp_point(prev_point, next_point, center, radius)


def _same_circle(a: PlaneCircle, b: PlaneCircle) -> bool:
    """Return True if two planar circles are the same circle."""
    return (
        math.hypot(a[0] - b[0], a[1] - b[1]) <= _SAME_CIRCLE_TOLERANCE_M
        and abs(a[2] - b[2]) <= _SAME_CIRCLE_TOLERANCE_M
    )


def _collapse_duplicate_circles(
    circles: Sequence[PlaneCircle],
) -> tuple[list[PlaneCircle], list[int]]:
    """Collapse consecutive identical circles while retaining input indexes."""
    unique: list[PlaneCircle] = [circles[0]]
    index_of: list[int] = [0]
    for i, circle in enumerate(circles[1:], start=1):
        # Index 1 is never collapsed into index 0: the route starts at the
        # takeoff center, so touching its boundary remains a real leg.
        if not (i > 1 and _same_circle(unique[-1], circle)):
            unique.append(circle)
        index_of.append(len(unique) - 1)
    return unique, index_of


def _polyline_length(points: Sequence[tuple[float, float]]) -> float:
    """Return the total planar length of a polyline."""
    return sum(
        math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        for i in range(len(points) - 1)
    )


def _boundary_toward(
    circle: PlaneCircle, target: tuple[float, float]
) -> tuple[float, float]:
    """Return the point of ``circle`` nearest ``target``."""
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
    return [(circle[0], circle[1]) for circle in circles]


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


#: Deterministic starting configurations; the shortest settled route wins.
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
    """Alternate odd/even updates until the route length settles."""
    n = len(circles)
    previous_length = _polyline_length(points)
    for _ in range(max_sweeps):
        for parity in (1, 0):
            for i in range(1, n):
                if i % 2 != parity:
                    continue
                cx, cy, radius = circles[i]
                if i == n - 1:
                    points[i] = _boundary_toward(circles[i], points[i - 1])
                else:
                    points[i] = plane_optimal_point(
                        points[i - 1], points[i + 1], (cx, cy), radius
                    )
        current_length = _polyline_length(points)
        if abs(previous_length - current_length) < epsilon:
            break
        previous_length = current_length
    return points


def optimize_plane_route(
    circles: Sequence[PlaneCircle],
    max_sweeps: int,
    epsilon: float = CONVERGENCE_EPSILON_M,
) -> list[tuple[float, float]]:
    """Find the shortest planar route touching each circle in order.

    The first point is fixed at the first circle's center. Later points touch
    their circle boundaries. Three deterministic placements seed alternating
    odd/even sweeps, and the shortest converged route wins. Consecutive
    duplicate circles share one optimized point, except that the first
    boundary touch is never collapsed into the takeoff center.

    Args:
        circles: Planar circles as (x, y, radius), in route order.
        max_sweeps: Maximum alternating sweeps for each initial placement.
        epsilon: Route-length convergence threshold in plane units.

    Returns:
        Optimized (x, y) route points, one per input circle.
    """
    if not circles:
        return []

    unique_circles, index_of = _collapse_duplicate_circles(circles)
    if len(unique_circles) < 2:
        centers = _place_at_centers(unique_circles)
        return [centers[index] for index in index_of]

    best: list[tuple[float, float]] | None = None
    best_length = math.inf
    for place in _INITIAL_PLACEMENTS:
        points = _sweep_to_convergence(
            unique_circles,
            place(unique_circles),
            max_sweeps,
            epsilon,
        )
        length = _polyline_length(points)
        if length < best_length:
            best, best_length = points, length

    assert best is not None  # _INITIAL_PLACEMENTS is never empty
    return [best[index] for index in index_of]
