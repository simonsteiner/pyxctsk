"""What the KML and GeoJSON writers both need to draw a task.

:class:`TaskDrawing` is that answer, derived once per task: which turnpoints to
draw, which of them is the goal, whether there is a goal line, and the optimized
route. Both writers render the same value rather than each asking the same
questions again — which is not only cheaper (the optimizer ran once per format)
but the reason the answers cannot disagree. They did: the goal line's presence
and the decision to drop the last turnpoint were computed separately, and a LINE
goal with no usable approach direction lost its goal from both outputs. There is
no free function beside the drawing that answers any of those a second way.

Also here: what colour a turnpoint is, and the polygon that approximates a
cylinder. That circle is planar — a fixed metres-per-degree constant, not a
geodesic — because it draws a decorative outline, not a measured shape. Anything
a distance depends on is computed properly in
:mod:`pyxctsk.distance.turnpoint` and :mod:`pyxctsk.distance.goal_line`, and
this module must not grow a second opinion about task geometry.
"""

import math
from dataclasses import dataclass

from ..distance.goal_line import GoalLine
from ..distance.route_optimization import (
    OptimizedRoute,
    calculate_iteratively_refined_route,
)
from ..distance.task_distances import task_to_turnpoints
from ..model.task import Task, Turnpoint, TurnpointType

# Constants for visualization
CIRCLE_POINTS = 64  # Number of points to approximate circle
METERS_PER_DEGREE = 111320.0  # 1 degree ≈ 111.32 km at equator


@dataclass(frozen=True)
class TaskDrawing:
    """Everything both writers need to draw one task, derived once.

    Built by :meth:`from_task`, which runs the optimizer once. Rendering the
    same task in both formats therefore costs one route, not two, and — more
    importantly — the two formats cannot disagree about what the task looks
    like, because they are reading one value rather than each deriving their
    own.

    A drawing is a snapshot: it holds the turnpoints and route as they were
    when it was built, so build it after the task is final.

    Attributes:
        task: The task being drawn, for names, counts and descriptions.
        turnpoints: The turnpoints to draw, in order — the task's own, less the
            last one when a goal line replaces it.
        goal_line: The task's goal line, or None if it has none.
        route: The optimized route through the task's cylinders.
    """

    task: Task
    turnpoints: tuple[Turnpoint, ...]
    goal_line: GoalLine | None
    route: OptimizedRoute

    @classmethod
    def from_task(cls, task: Task) -> "TaskDrawing":
        """Derive the drawing for a task, optimizing its route once.

        Args:
            task: The task to draw.

        Returns:
            The drawing both writers render.
        """
        goal_line = GoalLine.from_task(task)
        # A goal line replaces the last turnpoint, so it is dropped exactly when
        # there is a line to draw in its place — one decision, made here.
        turnpoints = task.turnpoints[:-1] if goal_line else task.turnpoints
        return cls(
            task=task,
            turnpoints=tuple(turnpoints),
            goal_line=goal_line,
            route=calculate_iteratively_refined_route(task_to_turnpoints(task)),
        )

    def is_goal(self, turnpoint: Turnpoint) -> bool:
        """Whether this turnpoint is the task's goal.

        Compares identity, not value: a task may legitimately end by flying the
        same turnpoint twice, and ``Turnpoint`` is a plain dataclass, so
        searching by value would find the earlier occurrence and draw the goal
        as an ordinary turnpoint.

        Args:
            turnpoint: One of the task's turnpoints.

        Returns:
            True if this is the goal turnpoint and the task has a goal defined.
        """
        if self.task.goal is None:
            return False
        return bool(self.task.turnpoints) and turnpoint is self.task.turnpoints[-1]

    def route_coordinates(self) -> list[tuple[float, float]] | None:
        """The optimized route as (lat, lon) points, or None if there is no line.

        A route needs two points to be a line, so a task with fewer than two
        turnpoints has nothing to draw here.

        Returns:
            The route's (lat, lon) points, or None if there are fewer than two.
        """
        if len(self.route.points) < 2:
            return None
        return list(self.route.points)


def get_turnpoint_color_hex(
    turnpoint_type: TurnpointType, is_goal: bool = False
) -> str:
    """Get hex color for turnpoint based on its type.

    Args:
        turnpoint_type: The type of turnpoint.
        is_goal: Whether this is the goal (last) turnpoint.

    Returns:
        Hex color string for the turnpoint.
    """
    if is_goal:
        return "#ff0000"  # Red for goal

    color_mapping = {
        TurnpointType.TAKEOFF: "#204d74",  # Dark blue
        TurnpointType.SSS: "#ac2925",  # Dark red
        TurnpointType.ESS: "#ff8c00",  # Orange
    }

    return color_mapping.get(turnpoint_type, "#269abc")  # Default blue


def generate_circle_coordinates_2d(
    center_lat: float, center_lon: float, radius_meters: float
) -> list[tuple[float, float]]:
    """Generate 2D coordinates for a circular turnpoint zone.

    Args:
        center_lat: Latitude of the circle center.
        center_lon: Longitude of the circle center.
        radius_meters: Radius of the circle in meters.

    Returns:
        List of (longitude, latitude) tuples forming a circle.
    """
    coords = []
    radius_deg = radius_meters / METERS_PER_DEGREE

    for i in range(CIRCLE_POINTS + 1):  # +1 to close the circle
        angle = 2 * math.pi * i / CIRCLE_POINTS
        lat = center_lat + radius_deg * math.sin(angle)
        lon = center_lon + radius_deg * math.cos(angle) / math.cos(
            math.radians(center_lat)
        )
        coords.append((lon, lat))

    return coords


def generate_circle_coordinates_3d(
    center_lat: float, center_lon: float, radius_meters: float, altitude: int
) -> list[tuple[float, float, int]]:
    """Generate 3D coordinates for a circular turnpoint zone.

    Args:
        center_lat: Latitude of the circle center.
        center_lon: Longitude of the circle center.
        radius_meters: Radius of the circle in meters.
        altitude: Altitude for all points in meters.

    Returns:
        List of (longitude, latitude, altitude) tuples forming a circle.
    """
    coords_2d = generate_circle_coordinates_2d(center_lat, center_lon, radius_meters)
    return [(lon, lat, altitude) for lon, lat in coords_2d]
