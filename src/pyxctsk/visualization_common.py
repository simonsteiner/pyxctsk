"""Common functionality for task visualization modules (KML and GeoJSON).

This module provides shared utilities for generating visual representations of XCTrack tasks,
including turnpoint filtering, route coordinate generation, and styling helpers.
"""

import math
from typing import List, Optional, Tuple

from .distance import optimized_route_coordinates
from .goal_line import should_skip_last_turnpoint
from .task import Task, Turnpoint, TurnpointType
from .task_distances import _task_to_turnpoints

# Constants for visualization
CIRCLE_POINTS = 64  # Number of points to approximate circle
METERS_PER_DEGREE = 111320.0  # 1 degree ≈ 111.32 km at equator


def get_turnpoints_to_render(task: Task) -> List[Turnpoint]:
    """Get the list of turnpoints that should be rendered for visualization.

    Skips the last turnpoint if it's a LINE type goal (goal line replaces it).

    Args:
        task: The Task object containing turnpoints.

    Returns:
        List of turnpoints to render.
    """
    if should_skip_last_turnpoint(task):
        return task.turnpoints[:-1]
    return task.turnpoints


def get_optimized_route_coordinates(task: Task) -> Optional[List[Tuple[float, float]]]:
    """Get optimized route coordinates for the task.

    Args:
        task: The Task object.

    Returns:
        List of (lat, lon) coordinate tuples for the optimized route, or None if not available.
    """
    task_turnpoints = _task_to_turnpoints(task)
    return optimized_route_coordinates(task_turnpoints, task.turnpoints)


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
) -> List[Tuple[float, float]]:
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
) -> List[Tuple[float, float, int]]:
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
    turnpoint: Turnpoint, all_turnpoints: List[Turnpoint], task: Optional[Task] = None
) -> bool:
    """Check if a turnpoint is the goal (last) turnpoint.

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

    try:
        index = all_turnpoints.index(turnpoint)
        return index == len(all_turnpoints) - 1
    except ValueError:
        return False


def calculate_unified_altitude(task: Task) -> int:
    """Calculate unified altitude for the entire task.

    Args:
        task: The Task object containing turnpoints.

    Returns:
        Average altitude of all turnpoints in meters, or 0 if no turnpoints.
    """
    if not task.turnpoints:
        return 0
    return sum(tp.waypoint.alt_smoothed for tp in task.turnpoints) // len(
        task.turnpoints
    )


def get_route_coordinates_with_fallback(
    task: Task, fallback_coordinates: List[Tuple[float, float]]
) -> List[Tuple[float, float]]:
    """Get route coordinates with fallback to direct coordinates.

    Args:
        task: The Task object.
        fallback_coordinates: Fallback coordinates if optimized route is not available.

    Returns:
        List of (lat, lon) coordinate tuples for the route.
    """
    opt_route_coords = get_optimized_route_coordinates(task)

    if opt_route_coords and len(opt_route_coords) >= 2:
        return opt_route_coords
    return fallback_coordinates
