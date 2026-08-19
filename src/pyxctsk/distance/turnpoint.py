"""What a turnpoint is to the distance subsystem.

:class:`TaskTurnpoint` — a centre, a cylinder radius, and the earth they are
measured on — plus :class:`TurnpointGeometry`, the seam the route optimizer
depends on, and the two things done to a turnpoint that are not the optimizer's
own: projecting it into a plane (:func:`plane_circle`) and measuring the
polyline through a list of centres (:func:`distance_through_centers`).

This file used to be the largest in the library and held four subjects under a
name that covers one. The other three are now:

- :mod:`~pyxctsk.distance.earth` — the two earth models and geodesic distance
- :mod:`~pyxctsk.distance.plane` — the local Transverse Mercator projection
- :mod:`~pyxctsk.distance.solver` — the planar GetOptPi primitive
"""

from typing import Protocol, runtime_checkable

from .earth import EarthModelLike, geodesic_distance, snap_to_boundary
from .plane import LocalPlane
from .solver import plane_optimal_point


@runtime_checkable
class TurnpointGeometry(Protocol):
    """The geometry seam the route optimizer depends on.

    Route optimization needs three things from a turnpoint: where its center
    is, how large its cylinder is, and which earth the first two are measured
    on. Everything else (goal-line length, the goal's type, geodesic math) is
    outside this interface.

    **It is exactly what the implementation reads, in both directions.**
    ``earth_model`` is here because ``calculate_iteratively_refined_route``
    reads it off the first turnpoint to pick the model for the whole route; it
    used to do that through ``getattr(turnpoints[0], "earth_model", None)``
    while the protocol declared three attributes and its docstring said "only
    three things", so a fake that satisfied ``isinstance`` got a different
    distance for identical geometry, depending on an attribute the interface
    denied having. ``goal_type`` went the other way and is now gone from the
    concrete class too: it was declared because :func:`plane_circle` read it to
    collapse a LINE goal to a zero-radius circle, but that rule belongs to —
    and is applied only by — ``task_to_turnpoints``, which is where the
    cylinders are built. A LINE goal arrives here already carrying
    ``radius = 0``, which is the same fact losslessly, and is what
    ``center_distance`` reads. An interface declaring a value nothing reads
    misleads a caller just as an interface omitting one does; leaving the
    attribute on ``TaskTurnpoint`` after removing it from the protocol left the
    constructor taking four things where the interface declares three.

    Depending on this protocol instead of the concrete ``TaskTurnpoint`` lets
    the optimization core be exercised with lightweight fakes and lets new
    turnpoint kinds be added without editing the optimizer.

    Attributes:
        center: (lat, lon) of the turnpoint center.
        radius: Cylinder radius in meters (0 collapses to the center).
        earth_model: The model this turnpoint's geometry is measured on. Read
            from the first turnpoint when the caller names none.
    """

    center: tuple[float, float]
    radius: float
    earth_model: EarthModelLike


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


class TaskTurnpoint:
    """Turnpoint class for distance calculations."""

    def __init__(
        self,
        lat: float,
        lon: float,
        radius: float = 0,
        earth_model: EarthModelLike = None,
    ):
        """Initialize a task turnpoint.

        Args:
            lat (float): Latitude in degrees.
            lon (float): Longitude in degrees.
            radius (float): Cylinder radius in meters. A LINE goal is built
                with 0 here — see ``task_to_turnpoints``, which owns that rule.
            earth_model: Earth model the turnpoint's task uses (``EarthModel``
                member, its string value, or None for the WGS84 default).
        """
        self.center = (lat, lon)
        self.radius = radius
        self.earth_model = earth_model

    def optimal_point(
        self,
        prev_point: tuple[float, float],
        next_point: tuple[float, float],
        plane: LocalPlane | None = None,
    ) -> tuple[float, float]:
        """Find the optimal point on this turnpoint's cylinder or goal line.

        The point is placed with the exact planar GetOptPi solution (crossing
        vs. reflection case per Ding, Xie & Jiang) in a local Transverse
        Mercator plane, then snapped back onto the true cylinder boundary at
        radius ``r`` on the selected earth model.

        Args:
            prev_point (Tuple[float, float]): (lat, lon) of previous point in route.
            next_point (Tuple[float, float]): (lat, lon) of next point in route.
            plane: The plane to solve in. Defaults to one centred on this
                turnpoint. Pass the task's own plane — the one
                :func:`~pyxctsk.distance.route_optimization.calculate_iteratively_refined_route`
                builds — to get the answer the route optimizer would give:
                the projection is the only thing the two ever differed by.

        Returns:
            Tuple[float, float]: (lat, lon) of optimal point on cylinder perimeter or goal line.
        """
        if plane is None:
            plane = LocalPlane.around([self.center], self.earth_model)

        cx, cy, radius = plane_circle(self, plane)
        if radius == 0.0:
            return self.center

        xy = plane_optimal_point(
            plane.xy(prev_point), plane.xy(next_point), (cx, cy), radius
        )
        # Snap on the plane's own model, so the projection and the boundary it
        # is corrected onto cannot be measured on different earths.
        return snap_to_boundary(
            plane.lon_lat(xy), self.center, self.radius, plane.earth_model
        )


def distance_through_centers(
    turnpoints: list[TaskTurnpoint], earth_model: EarthModelLike = None
) -> float:
    """Sum the geodesic legs between consecutive turnpoint centers.

    The primitive, not the published number. **S7F defines no "distance
    through centres"**, so which points to include and where to stop is a
    convention — see :mod:`~pyxctsk.distance.center_distance`, which owns that
    decision and calls this. A caller producing a figure for a task board
    wants ``center_distance(task)``; a caller who already knows exactly which
    turnpoints it means wants this.

    Args:
        turnpoints (List[TaskTurnpoint]): List of TaskTurnpoint objects.
        earth_model: Earth model selector (``EarthModel`` member, its string
            value, or None). None falls back to the first turnpoint's
            ``earth_model`` attribute, defaulting to WGS84.

    Returns:
        float: Distance through centers in meters.
    """
    if len(turnpoints) < 2:
        return 0.0

    if earth_model is None:
        # A plain attribute read, not `getattr(..., "earth_model", None)`:
        # every TaskTurnpoint has one, and the defensive lookup is the exact
        # shape `TurnpointGeometry` documents as the bug that let an interface
        # deny having a value its implementation read.
        earth_model = turnpoints[0].earth_model

    total = 0.0
    for i in range(len(turnpoints) - 1):
        total += geodesic_distance(
            turnpoints[i].center, turnpoints[i + 1].center, earth_model
        )
    return total
