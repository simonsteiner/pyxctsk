"""What a turnpoint is to the distance subsystem.

:class:`TaskTurnpoint` — a centre and a cylinder radius — and
:class:`TurnpointGeometry`, the seam the route optimizer depends on. Nothing
else: what is *done* to a turnpoint lives with the module doing it.
Projecting one into the plane and correcting a planar solution back onto its
boundary are two steps of route optimization, and are in
:mod:`~pyxctsk.distance.route_optimization`; the polyline through the centres
is the primitive under :mod:`~pyxctsk.distance.center_distance`, and is there.

This file used to be the largest in the library and held four subjects under a
name that covers one; after the split it still held the projection and
correction helpers, so reading one optimizer pass meant visiting six modules.
The others are :mod:`~pyxctsk.distance.earth`, :mod:`~pyxctsk.distance.plane`
and :mod:`~pyxctsk.distance.solver`.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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
