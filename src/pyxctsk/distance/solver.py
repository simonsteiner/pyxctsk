"""The planar GetOptPi primitive from Ding, Xie & Jiang.

"An Efficient Algorithm for Touring n Circles" (MATEC Web of Conferences 232,
03027, EITCE 2018), Algorithm 1: the optimal point on a circle between two
fixed neighbours, distinguishing the *crossing* case — the segment between the
neighbours meets the circle — from the *reflection* (point-circle-point) case.

Pure planar geometry. It knows nothing about turnpoints, tasks or the earth:
the caller projects into a plane, calls this, and projects back. That is why
it is its own module rather than part of ``turnpoint.py``, where it used to sit
beside three other subjects.
"""

import math


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
