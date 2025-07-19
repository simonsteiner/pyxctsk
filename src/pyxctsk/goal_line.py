"""Goal line calculation utilities for LINE type goals.

This module provides common functionality for calculating goal line positions
and control zones that can be used by both GeoJSON and KML generation modules.
"""

from typing import List, Optional, Tuple

from pyproj import Geod

from .task import GoalType, Task

# Initialize WGS84 ellipsoid for geographical calculations
geod = Geod(ellps="WGS84")

# Constants for goal line visualization
GOAL_LINE_NUM_POINTS = 20
COORD_TOLERANCE = 1e-9


def _find_previous_turnpoint(turnpoints, last_tp):
    """Find the previous turnpoint with different coordinates from the goal center.

    Args:
        turnpoints: List of turnpoints to search through
        last_tp: The last turnpoint (goal center)

    Returns:
        The previous turnpoint with different coordinates, or None if not found
    """
    for i in range(len(turnpoints) - 2, -1, -1):
        candidate_tp = turnpoints[i]
        # Check if coordinates are different (with small tolerance for floating point comparison)
        if (
            abs(candidate_tp.waypoint.lon - last_tp.waypoint.lon) > COORD_TOLERANCE
            or abs(candidate_tp.waypoint.lat - last_tp.waypoint.lat) > COORD_TOLERANCE
        ):
            return candidate_tp
    return None


def calculate_goal_line_endpoints(
    last_tp, prev_tp, goal_line_length: float
) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
    """Calculate the endpoints of the goal line and return the forward azimuth.

    Args:
        last_tp: The last turnpoint (goal center)
        prev_tp: The previous turnpoint to determine approach direction
        goal_line_length: Length of the goal line in meters

    Returns:
        Tuple of ((lon1, lat1), (lon2, lat2), forward_azimuth)
    """
    # Calculate bearing from previous turnpoint to goal center
    forward_azimuth, _, _ = geod.inv(
        prev_tp.waypoint.lon,
        prev_tp.waypoint.lat,
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
    )

    # Goal line is perpendicular to the approach direction
    perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
    perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

    half_length = goal_line_length / 2

    lon1, lat1, _ = geod.fwd(
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
        perpendicular_azimuth_1,
        half_length,
    )
    lon2, lat2, _ = geod.fwd(
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
        perpendicular_azimuth_2,
        half_length,
    )

    return (lon1, lat1), (lon2, lat2), forward_azimuth


def generate_semicircle_arc(
    center_lon: float,
    center_lat: float,
    start_azimuth: float,
    end_azimuth: float,
    through_azimuth: float,
    radius: float,
) -> List[Tuple[float, float]]:
    """Generate arc points for a semi-circle.

    Args:
        center_lon: Center longitude
        center_lat: Center latitude
        start_azimuth: Starting azimuth in degrees
        end_azimuth: Ending azimuth in degrees
        through_azimuth: Intermediate azimuth to pass through
        radius: Radius in meters

    Returns:
        List of (lon, lat) coordinate tuples representing the arc
    """
    arc_points = []
    for i in range(GOAL_LINE_NUM_POINTS + 1):  # include endpoint
        if i <= GOAL_LINE_NUM_POINTS // 2:
            # First half: interpolate from start_azimuth to through_azimuth
            t = (i * 2) / GOAL_LINE_NUM_POINTS
            angle_diff = (through_azimuth - start_azimuth) % 360
            if angle_diff > 180:
                angle_diff -= 360
            angle = (start_azimuth + angle_diff * t) % 360
        else:
            # Second half: interpolate from through_azimuth to end_azimuth
            t = ((i - GOAL_LINE_NUM_POINTS // 2) * 2) / GOAL_LINE_NUM_POINTS
            angle_diff = (end_azimuth - through_azimuth) % 360
            if angle_diff > 180:
                angle_diff -= 360
            angle = (through_azimuth + angle_diff * t) % 360

        lon_arc, lat_arc, _ = geod.fwd(center_lon, center_lat, angle, radius)
        arc_points.append((lon_arc, lat_arc))
    return arc_points


def get_goal_line_data(
    task: Task,
) -> Optional[
    Tuple[Tuple[float, float], Tuple[float, float], float, List[Tuple[float, float]]]
]:
    """Get goal line data for LINE type goals.

    Args:
        task: The task object

    Returns:
        Tuple of (goal_line_start, goal_line_end, goal_line_length, control_zone_coords)
        or None if not a LINE type goal or insufficient data
    """
    if not (
        task.goal
        and task.goal.type == GoalType.LINE
        and task.turnpoints
        and len(task.turnpoints) >= 2
    ):
        return None

    last_tp = task.turnpoints[-1]
    prev_tp = _find_previous_turnpoint(task.turnpoints, last_tp)

    if prev_tp is None:
        return None

    # Determine goal line length
    goal_line_length = task.goal.line_length
    if goal_line_length is None:
        goal_line_length = float(last_tp.radius * 2)

    # Calculate goal line endpoints and approach direction
    (lon1, lat1), (lon2, lat2), forward_azimuth = calculate_goal_line_endpoints(
        last_tp, prev_tp, goal_line_length
    )

    # Create goal line control zone (semi-circle in front of the goal line)
    control_zone_radius = goal_line_length / 2
    perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
    perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

    front_arc_points = generate_semicircle_arc(
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
        perpendicular_azimuth_2,
        perpendicular_azimuth_1,
        forward_azimuth,
        control_zone_radius,
    )

    # Create control zone coordinates (closed polygon)
    control_zone_coords = (
        [(lon2, lat2)] + front_arc_points + [(lon1, lat1), (lon2, lat2)]
    )

    return (lon1, lat1), (lon2, lat2), goal_line_length, control_zone_coords


def should_skip_last_turnpoint(task: Task) -> bool:
    """Check if the last turnpoint should be skipped for LINE type goals.

    Args:
        task: The task object

    Returns:
        True if the last turnpoint should be skipped (for LINE goals)
    """
    return bool(
        task.goal
        and task.goal.type == GoalType.LINE
        and task.turnpoints
        and len(task.turnpoints) >= 2
    )
