"""SSS (Start Speed Section) specific calculations."""

from typing import Any, Dict, List, Optional, Tuple
from geopy.distance import geodesic

from .turnpoint import TaskTurnpoint
from .optimization_config import get_optimization_config


def calculate_optimal_sss_entry_point(
    sss_turnpoint: TaskTurnpoint,
    takeoff_center: Tuple[float, float],
    first_tp_after_sss_point: Tuple[float, float],
    angle_step: Optional[int] = None,
) -> Tuple[float, float]:
    """Calculate the optimal entry point for an SSS (Start Speed Section) turnpoint.

    This function finds the point on the SSS cylinder perimeter that minimizes the
    total distance from takeoff to the first turnpoint after SSS, passing through
    the SSS entry point.

    Args:
        sss_turnpoint: TaskTurnpoint object representing the SSS cylinder
        takeoff_center: (lat, lon) tuple of takeoff center coordinates
        first_tp_after_sss_point: (lat, lon) tuple of the target point on first TP after SSS
        angle_step: Angle step in degrees for perimeter point generation

    Returns:
        Tuple of (lat, lon) representing the optimal SSS entry point
    """
    config = get_optimization_config(angle_step)
    # Generate perimeter points for the SSS turnpoint
    sss_perimeter = sss_turnpoint.perimeter_points(config["angle_step"])

    # Find the point that minimizes total distance: takeoff -> SSS entry -> first TP after SSS
    best_sss_point = min(
        sss_perimeter,
        key=lambda p: geodesic(takeoff_center, p).meters
        + geodesic(p, first_tp_after_sss_point).meters,
    )

    return best_sss_point


def _find_sss_turnpoint(task_turnpoints) -> Optional[Tuple[int, Any]]:
    """Find the SSS turnpoint in a task.

    Args:
        task_turnpoints: List of task turnpoints

    Returns:
        Tuple of (index, turnpoint) or None if not found
    """
    for i, tp in enumerate(task_turnpoints):
        if hasattr(tp, "type") and tp.type and tp.type.value == "SSS":
            return i, tp
    return None


def _get_first_tp_after_sss_point(
    task_turnpoints, sss_index: int, route_coordinates: List[Tuple[float, float]]
) -> Optional[Tuple[Dict[str, float], Tuple[float, float]]]:
    """Get the first turnpoint after SSS and its route point.

    Args:
        task_turnpoints: List of task turnpoints
        sss_index: Index of the SSS turnpoint
        route_coordinates: List of route coordinates

    Returns:
        Tuple of (turnpoint_dict, route_point) or None if not available
    """
    if sss_index + 1 >= len(task_turnpoints):
        return None

    next_tp = task_turnpoints[sss_index + 1]
    next_tp_dict = {
        "lat": next_tp.waypoint.lat,
        "lon": next_tp.waypoint.lon,
    }

    # Determine the optimal point on the first TP after SSS from the route
    route_point = None
    if len(route_coordinates) > 1:
        # Route starts with takeoff, then first TP after SSS
        route_point = route_coordinates[1]
    else:
        # Fallback to center coordinates
        route_point = (next_tp_dict["lat"], next_tp_dict["lon"])

    return next_tp_dict, route_point


def calculate_sss_info(
    task_turnpoints,
    route_coordinates: List[Tuple[float, float]],
    angle_step: Optional[int] = None,
) -> Dict[str, Any]:
    """Calculate SSS (Start Speed Section) information for a task.

    This function analyzes a task to find SSS turnpoints and calculates the optimal
    entry point and related information for display and route planning.

    Args:
        task_turnpoints: List of task turnpoints with type information
        route_coordinates: List of (lat, lon) tuples representing the optimized route
        angle_step: Angle step in degrees for perimeter point generation

    Returns:
        Dictionary containing SSS information or None if no SSS found:
        {
            'sss_center': {'lat': float, 'lon': float, 'radius': float},
            'optimal_entry_point': {'lat': float, 'lon': float},
            'first_tp_after_sss': {'lat': float, 'lon': float},
            'takeoff_center': {'lat': float, 'lon': float}
        }
    """
    config = get_optimization_config(angle_step)
    if not task_turnpoints or len(task_turnpoints) < 2:
        return None

    # Get takeoff center
    takeoff_center = (task_turnpoints[0].waypoint.lat, task_turnpoints[0].waypoint.lon)

    # Find SSS turnpoint
    sss_result = _find_sss_turnpoint(task_turnpoints)
    if not sss_result:
        return None

    sss_index, tp = sss_result

    # Extract SSS center and radius
    sss_tp = {
        "lat": tp.waypoint.lat,
        "lon": tp.waypoint.lon,
        "radius": tp.radius,
    }

    # Get first turnpoint after SSS
    next_tp_result = _get_first_tp_after_sss_point(
        task_turnpoints, sss_index, route_coordinates
    )
    if not next_tp_result:
        return None

    first_tp_after_sss, first_tp_after_sss_route_point = next_tp_result

    # Calculate optimal SSS entry point using the centralized function
    sss_task_tp = TaskTurnpoint(tp.waypoint.lat, tp.waypoint.lon, tp.radius)
    best_sss_point = calculate_optimal_sss_entry_point(
        sss_task_tp,
        takeoff_center,
        first_tp_after_sss_route_point,
        config["angle_step"],
    )

    optimal_sss_point = {"lat": best_sss_point[0], "lon": best_sss_point[1]}

    return {
        "sss_center": sss_tp,
        "optimal_entry_point": optimal_sss_point,
        "first_tp_after_sss": first_tp_after_sss,
        "takeoff_center": {
            "lat": takeoff_center[0],
            "lon": takeoff_center[1],
        },
    }
