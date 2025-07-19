"""GeoJSON generation utilities for XCTrack task visualization.

This module provides functions to convert pyxctsk task objects into GeoJSON FeatureCollections for mapping and visualization.

Features:
- Turnpoints as GeoJSON Point features with styling for type (takeoff, SSS, ESS, goal, etc.)
- Optimized route as a LineString feature (if available)
- Goal line and control zone (for LINE type goals) as LineString and Polygon features

All features include geometry and properties suitable for web map display, including color, opacity, and descriptive metadata.

Intended for use in web-based or desktop mapping tools to visualize XCTrack competition tasks.
"""

from typing import Dict, List, Optional, Tuple

from .distance import optimized_route_coordinates
from .goal_line import get_goal_line_data, should_skip_last_turnpoint
from .task_distances import _task_to_turnpoints


def _create_turnpoint_feature(turnpoint, index: int) -> Dict:
    """Create a GeoJSON feature for a turnpoint."""
    # Determine color based on turnpoint type
    tp_type = getattr(turnpoint, "type", None)

    if tp_type == "takeoff":
        color = "#204d74"  # takeoff
    elif tp_type in ["SSS", "ESS"]:
        color = "#ac2925"  # SSS and ESS
    elif tp_type == "goal":
        color = "#398439"  # goal
    else:
        color = "#269abc"  # default turnpoint

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
            "tp_type": tp_type,
            "color": color,
            "fillColor": color,
            "fillOpacity": 0.1,
            "weight": 2,
            "opacity": 0.7,
        },
    }


def _create_optimized_route_feature(
    opt_coords: List[Tuple[float, float]],
) -> Optional[Dict]:
    """Create a GeoJSON feature for the optimized route."""
    if len(opt_coords) < 2:
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


def _create_goal_line_features(task) -> List[Dict]:
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


def generate_task_geojson(task) -> Dict:
    """Generate GeoJSON data from pyxctsk task object."""
    features = []

    # Add turnpoints as point features with cylinders
    # Skip the last turnpoint if it's a LINE type goal (goal line replaces it)
    turnpoints_to_render = task.turnpoints
    if should_skip_last_turnpoint(task):
        turnpoints_to_render = task.turnpoints[:-1]

    # Create turnpoint features
    for i, tp in enumerate(turnpoints_to_render):
        features.append(_create_turnpoint_feature(tp, i))

    # Add optimized route if available
    task_turnpoints = _task_to_turnpoints(task)
    opt_coords = optimized_route_coordinates(task_turnpoints, task.turnpoints)

    opt_route_feature = _create_optimized_route_feature(opt_coords)
    if opt_route_feature:
        features.append(opt_route_feature)

    # Add goal line features for LINE type goals
    goal_features = _create_goal_line_features(task)
    features.extend(goal_features)

    return {"type": "FeatureCollection", "features": features}
