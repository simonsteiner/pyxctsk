"""What the KML and GeoJSON writers both need to draw a task.

Four questions, each answered once so the two writers cannot answer them
differently: which turnpoints to draw, where the optimized route runs, what
colour a turnpoint is, and which turnpoint is the goal. Plus the polygon that
approximates a cylinder.

The circle approximation here is planar — a fixed metres-per-degree constant,
not a geodesic — because it draws a decorative outline, not a measured shape.
Anything a distance depends on is computed properly in
:mod:`pyxctsk.distance.turnpoint` and :mod:`pyxctsk.distance.goal_line`, and
this module must not grow a second opinion about task geometry.
"""

import math

from ..distance.goal_line import GoalLine
from ..distance.route_optimization import optimized_route_coordinates
from ..distance.task_distances import task_to_turnpoints
from ..model.task import Task, Turnpoint, TurnpointType

# Constants for visualization
CIRCLE_POINTS = 64  # Number of points to approximate circle
METERS_PER_DEGREE = 111320.0  # 1 degree ≈ 111.32 km at equator


def get_turnpoints_to_render(task: Task) -> list[Turnpoint]:
    """Get the list of turnpoints that should be rendered for visualization.

    Derived from the one answer to whether the task has a goal line: a goal
    line replaces the last turnpoint, so the turnpoint is dropped exactly when
    there is a line to draw in its place. Deciding this independently is what
    let a LINE goal with no usable approach direction lose its goal from the
    output — dropped here, and not drawn as a line either.

    Args:
        task: The Task object containing turnpoints.

    Returns:
        List of turnpoints to render.
    """
    if GoalLine.from_task(task) is not None:
        return task.turnpoints[:-1]
    return task.turnpoints


def get_optimized_route_coordinates(task: Task) -> list[tuple[float, float]] | None:
    """Get optimized route coordinates for the task.

    Args:
        task: The Task object.

    Returns:
        List of (lat, lon) coordinate tuples for the optimized route, or None if not available.
    """
    task_turnpoints = task_to_turnpoints(task)
    return optimized_route_coordinates(task_turnpoints)


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


def is_goal_turnpoint(
    turnpoint: Turnpoint,
    all_turnpoints: list[Turnpoint],
    task: Task | None = None,
) -> bool:
    """Check if a turnpoint is the goal (last) turnpoint.

    Compares identity, not value. A task may legitimately end by flying the
    same turnpoint twice — same name, coordinates, radius and type — and
    ``Turnpoint`` is a plain dataclass, so searching by value would find the
    earlier occurrence and report the goal as an ordinary turnpoint. The
    callers pass the task's own turnpoint objects, so identity is exact.

    Args:
        turnpoint: The turnpoint to check.
        all_turnpoints: List of all turnpoints in the task.
        task: Optional Task object to check if it has a goal defined.

    Returns:
        True if this is the goal turnpoint and the task has a goal defined.
    """
    # If task is provided, check if it actually has a goal
    if task is not None and task.goal is None:
        return False

    return bool(all_turnpoints) and turnpoint is all_turnpoints[-1]
