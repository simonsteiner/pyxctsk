"""GeoJSON generation utilities for XCTrack task visualization.

This module provides functions to convert pyxctsk task objects into GeoJSON FeatureCollections for mapping and visualization.

Features:
- Turnpoints as GeoJSON Point features with styling for type (takeoff, SSS, ESS, goal, etc.)
- Optimized route as a LineString feature (if available)
- Goal line and control zone (for LINE type goals) as LineString and Polygon features

All features include geometry and properties suitable for web map display, including color, opacity, and descriptive metadata.

Intended for use in web-based or desktop mapping tools to visualize XCTrack competition tasks.
"""

from .goal_line import get_goal_line_data
from .visualization_common import (
    get_optimized_route_coordinates,
    get_turnpoint_color_hex,
    get_turnpoints_to_render,
    is_goal_turnpoint,
)


def _create_turnpoint_feature(
    turnpoint, index: int, all_turnpoints: list, task=None
) -> dict:
    """Create a GeoJSON feature for a turnpoint.

    Args:
        turnpoint: The turnpoint object to create a feature for.
        index: The index of the turnpoint in the task.
        all_turnpoints: List of all turnpoints in the task.
        task: Optional Task object to check if it has a goal defined.

    Returns:
        GeoJSON feature dictionary for the turnpoint.
    """
    is_goal = is_goal_turnpoint(turnpoint, all_turnpoints, task)
    color = get_turnpoint_color_hex(turnpoint.type, is_goal)

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [turnpoint.waypoint.lon, turnpoint.waypoint.lat],
        },
        "properties": {
            "name": turnpoint.waypoint.name or f"TP{index+1}",
            "type": "cylinder",
            "radius": turnpoint.radius,
            "description": f"Radius: {turnpoint.radius}m",
            "turnpoint_index": index,
            "tp_type": getattr(turnpoint, "type", None),
            "color": color,
            "fillColor": color,
            "fillOpacity": 0.1,
            "weight": 2,
            "opacity": 0.7,
        },
    }


def _create_optimized_route_feature(task_or_coords) -> dict | None:
    """Create a GeoJSON feature for the optimized route."""
    # Handle both old API (list of coordinates) and new API (Task object)
    if isinstance(task_or_coords, list):
        # Old API for testing - coords is a list of (lat, lon) tuples
        opt_coords = task_or_coords  # type: list[tuple[float, float]] | None
    else:
        # New API - task_or_coords is a Task object
        opt_coords = get_optimized_route_coordinates(task_or_coords)

    if not opt_coords or len(opt_coords) < 2:
        return None

    # Convert from (lat, lon) to [lon, lat] format for GeoJSON
    opt_coordinates = [[coord[1], coord[0]] for coord in opt_coords]

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": opt_coordinates,
        },
        "properties": {
            "name": "Optimized Route",
            "type": "optimized_route",
            "color": "#ff4136",
            "weight": 3,
            "opacity": 0.8,
            "arrowheads": True,
            "arrow_color": "#ff4136",
            "arrow_size": 8,
            "arrow_spacing": 100,  # meters between arrows
        },
    }


def _create_goal_line_features(task) -> list[dict]:
    """Create goal line and control zone features for LINE type goals."""
    goal_data = get_goal_line_data(task)
    if goal_data is None:
        return []

    (lon1, lat1), (lon2, lat2), goal_line_length, control_zone_coords = goal_data
    features = []

    # Create goal line feature
    goal_line_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon1, lat1], [lon2, lat2]],
        },
        "properties": {
            "name": "Goal Line",
            "type": "goal_line",
            "length": goal_line_length,
            "description": f"Goal line length: {goal_line_length:.0f}m",
            "stroke": "#00ff00",
            "stroke-width": 4,
            "stroke-opacity": 1.0,
        },
    }
    features.append(goal_line_feature)

    # Create goal line control zone (semi-circle in front of the goal line)
    control_zone_radius = goal_line_length / 2

    # Convert control zone coordinates to GeoJSON format [lon, lat]
    control_zone_geojson_coords = [
        [coord[0], coord[1]] for coord in control_zone_coords
    ]

    control_zone_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [control_zone_geojson_coords],
        },
        "properties": {
            "name": "Goal Control Zone",
            "type": "goal_control_zone",
            "radius": control_zone_radius,
            "description": f"Goal control zone radius: {control_zone_radius:.0f}m",
            "fill": "#4ecdc4",
            "fill-opacity": 0.3,
            "stroke": "#00bcd4",
            "stroke-width": 2,
            "stroke-opacity": 0.8,
        },
    }
    features.append(control_zone_feature)

    return features


def generate_task_geojson(task) -> dict:
    """Generate GeoJSON data from pyxctsk task object."""
    features = []

    # Add turnpoints as point features with cylinders
    # Skip the last turnpoint if it's a LINE type goal (goal line replaces it)
    turnpoints_to_render = get_turnpoints_to_render(task)

    # Create turnpoint features
    for i, tp in enumerate(turnpoints_to_render):
        features.append(_create_turnpoint_feature(tp, i, task.turnpoints, task))

    # Add optimized route if available
    opt_route_feature = _create_optimized_route_feature(task)
    if opt_route_feature:
        features.append(opt_route_feature)

    # Add goal line features for LINE type goals
    goal_features = _create_goal_line_features(task)
    features.extend(goal_features)

    return {"type": "FeatureCollection", "features": features}
