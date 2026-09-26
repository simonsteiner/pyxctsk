"""What a turnpoint is to the distance subsystem.

:class:`TaskTurnpoint` — a centre and a cylinder radius — plus :class:`TurnpointGeometry`, the seam the route optimizer
depends on, and the two things done to a turnpoint that are not the optimizer's
own: projecting it into a plane (:func:`plane_circle`) and measuring the
polyline through a list of centres (:func:`distance_through_centers`).

This file used to be the largest in the library and held four subjects under a
name that covers one. The other three are now:

- :mod:`~pyxctsk.distance.earth` — the two earth models and geodesic distance
- :mod:`~pyxctsk.distance.plane` — the local Transverse Mercator projection
- :mod:`~pyxctsk.distance.solver` — the planar GetOptPi primitive
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .earth import EarthModelLike, geodesic_distance, snap_to_boundary
from .plane import LocalPlane
from .solver import plane_optimal_point


@runtime_checkable
class TurnpointGeometry(Protocol):
    """The geometry seam the route optimizer depends on.

    Route optimization needs two things from a turnpoint: where its center is
    and how large its cylinder is. Everything else (goal-line length, the
    goal's type, which earth to measure on) is outside this interface.

    **It is exactly what the implementation reads, in both directions.**
    ``earth_model`` used to be a third attribute, because
    ``calculate_iteratively_refined_route`` read it off the *first* turnpoint
    to pick the model for the whole route — a property of the task copied onto
    every turnpoint and read from one. A misspelled model on any other
    turnpoint was silently ignored, and a list mixing the two earths measured
    278 m differently depending on which came first. The earth model is now an
    argument of the optimizer, supplied once by ``MeasuredTask`` from the task.
    ``goal_type`` went the same way earlier: the LINE-goal rule belongs to
    ``task_to_turnpoints``, and a LINE goal arrives here already carrying
    ``radius = 0``. An interface declaring a value nothing reads misleads a
    caller just as an interface omitting one does.

    Depending on this protocol instead of the concrete ``TaskTurnpoint`` lets
    the optimization core be exercised with lightweight fakes and lets new
    turnpoint kinds be added without editing the optimizer.

    Attributes:
        center: (lat, lon) of the turnpoint center.
        radius: Cylinder radius in meters (0 collapses to the center).
    """

    center: tuple[float, float]
    radius: float


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


@dataclass(init=False)
class TaskTurnpoint:
    """A turnpoint as the distance subsystem sees it: a centre and a radius.

    A value: two turnpoints with the same centre and radius are equal. It
    carries no earth model — that is the task's, and a route is measured on
    one — so ``calculate_iteratively_refined_route`` takes it as an argument.

    Attributes:
        center: (lat, lon) in degrees.
        radius: Cylinder radius in meters. A LINE goal is built with 0 here —
            see ``task_to_turnpoints``, which owns that rule.
    """

    center: tuple[float, float]
    radius: float

    def __init__(self, lat: float, lon: float, radius: float = 0):
        """Initialize a task turnpoint.

        Args:
            lat (float): Latitude in degrees.
            lon (float): Longitude in degrees.
            radius (float): Cylinder radius in meters.
        """
        self.center = (lat, lon)
        self.radius = radius


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


def distance_through_centers(
    turnpoints: Sequence[TurnpointGeometry], earth_model: EarthModelLike = None
) -> float:
    """Sum the geodesic legs between consecutive turnpoint centers.

    The primitive, not the published number. **S7F defines no "distance
    through centres"**, so which points to include and where to stop is a
    convention — see :mod:`~pyxctsk.distance.center_distance`, which owns that
    decision and calls this. A caller producing a figure for a task board
    wants ``center_distance(task)``; a caller who already knows exactly which
    turnpoints it means wants this.

    Args:
        turnpoints: The turnpoints whose centres to join.
        earth_model: Earth model selector (``EarthModel`` member, its string
            value, or None for WGS84).

    Returns:
        float: Distance through centers in meters.
    """
    if len(turnpoints) < 2:
        return 0.0

    total = 0.0
    for i in range(len(turnpoints) - 1):
        total += geodesic_distance(
            turnpoints[i].center, turnpoints[i + 1].center, earth_model
        )
    return total
