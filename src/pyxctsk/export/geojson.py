"""GeoJSON generation utilities for XCTrack task visualization.

This module provides functions to convert pyxctsk task objects into GeoJSON FeatureCollections for mapping and visualization.

Features:
- Turnpoints as GeoJSON Point features with styling for type (takeoff, SSS, ESS, goal, etc.)
- Optimized route as a LineString feature (if available)
- Goal line and control zone (for LINE type goals) as LineString and Polygon features

All features include geometry and properties suitable for web map display, including color, opacity, and descriptive metadata.

Intended for use in web-based or desktop mapping tools to visualize XCTrack competition tasks.
"""

from typing import Any

from ..model.task import Task, Turnpoint
from .common import (
    CONTROL_ZONE_EDGE_COLOR,
    CONTROL_ZONE_FILL_COLOR,
    GOAL_LINE_COLOR,
    ROUTE_COLOR,
    TaskDrawing,
)


def _create_turnpoint_feature(
    drawing: TaskDrawing, turnpoint: Turnpoint, index: int
) -> dict[str, Any]:
    """Create a GeoJSON feature for a turnpoint.

    Args:
        drawing: The task drawing, which knows which turnpoint is the goal.
        turnpoint: The turnpoint object to create a feature for.
        index: The index of the turnpoint in the task.

    Returns:
        GeoJSON feature dictionary for the turnpoint.
    """
    color = drawing.color_of(turnpoint).hex

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [turnpoint.waypoint.lon, turnpoint.waypoint.lat],
        },
        "properties": {
            "name": drawing.label_of(turnpoint, index),
            "type": "cylinder",
            "radius": turnpoint.radius,
            "description": drawing.description_of(turnpoint),
            "turnpoint_index": index,
            # ``.value``, not the member: every sibling accessor on the
            # drawing returns a rendered primitive, and this is a JSON
            # document. It worked only because ``TurnpointType`` subclasses
            # ``str``, so the enum leaked into the output undetected.
            "tp_type": drawing.role_of(turnpoint).value,
            "color": color,
            "fillColor": color,
            "fillOpacity": 0.1,
            "weight": 2,
            "opacity": 0.7,
        },
    }


def _create_optimized_route_feature(drawing: TaskDrawing) -> dict[str, Any] | None:
    """Create a GeoJSON feature for the optimized route.

    Args:
        drawing: The task drawing, carrying the route.

    Returns:
        The route feature, or None when there is no line to draw.
    """
    opt_coords = drawing.route_coordinates_lon_lat()
    if opt_coords is None:
        return None

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [list(point) for point in opt_coords],
        },
        "properties": {
            "name": drawing.route_label(),
            "type": "optimized_route",
            "color": ROUTE_COLOR.hex,
            "weight": 3,
            "opacity": 0.8,
            "arrowheads": True,
            "arrow_color": ROUTE_COLOR.hex,
            "arrow_size": 8,
            "arrow_spacing": 100,  # meters between arrows
        },
    }


def _create_goal_line_features(drawing: TaskDrawing) -> list[dict[str, Any]]:
    """Create goal line and control zone features for LINE type goals.

    Args:
        drawing: The task drawing, carrying the goal line if there is one.

    Returns:
        The goal-line and control-zone features, or an empty list.
    """
    goal_line = drawing.goal_line
    if goal_line is None:
        return []

    (lon1, lat1), (lon2, lat2), _ = goal_line.endpoints()
    features: list[dict[str, Any]] = []

    # Create goal line feature
    goal_line_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon1, lat1], [lon2, lat2]],
        },
        "properties": {
            "name": drawing.goal_line_label(),
            "type": "goal_line",
            "length": goal_line.length,
            "description": drawing.goal_line_description(),
            "stroke": GOAL_LINE_COLOR.hex,
            "stroke-width": 4,
            "stroke-opacity": 1.0,
        },
    }
    features.append(goal_line_feature)

    # Convert control zone coordinates to GeoJSON format [lon, lat]
    control_zone_geojson_coords = [[lon, lat] for lon, lat in goal_line.control_zone()]

    control_zone_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [control_zone_geojson_coords],
        },
        "properties": {
            "name": drawing.control_zone_label(),
            "type": "goal_control_zone",
            "radius": goal_line.control_zone_radius,
            "description": drawing.control_zone_description(),
            "fill": CONTROL_ZONE_FILL_COLOR.hex,
            "fill-opacity": 0.3,
            "stroke": CONTROL_ZONE_EDGE_COLOR.hex,
            "stroke-width": 2,
            "stroke-opacity": 0.8,
        },
    }
    features.append(control_zone_feature)

    return features


def generate_task_geojson(task: Task) -> dict[str, Any]:
    """Generate GeoJSON data from pyxctsk task object.

    Args:
        task: The Task object to render.

    Returns:
        A GeoJSON FeatureCollection.
    """
    return drawing_to_geojson(TaskDrawing.from_task(task))


def drawing_to_geojson(drawing: TaskDrawing) -> dict[str, Any]:
    """Generate GeoJSON from an already-derived task drawing.

    Use this to render one drawing in both formats without optimizing the route
    twice — see :func:`pyxctsk.export.kml.drawing_to_kml`.

    Args:
        drawing: The task drawing to render.

    Returns:
        A GeoJSON FeatureCollection.
    """
    features: list[dict[str, Any]] = []

    # Create turnpoint features. The drawing has already dropped the last
    # turnpoint if a goal line replaces it.
    for i, tp in enumerate(drawing.turnpoints):
        features.append(_create_turnpoint_feature(drawing, tp, i))

    # Add optimized route if available
    opt_route_feature = _create_optimized_route_feature(drawing)
    if opt_route_feature:
        features.append(opt_route_feature)

    # Add goal line features for LINE type goals
    features.extend(_create_goal_line_features(drawing))

    return {"type": "FeatureCollection", "features": features}
