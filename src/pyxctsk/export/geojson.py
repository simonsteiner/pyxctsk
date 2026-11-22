"""GeoJSON generation utilities for XCTrack task visualization.

This module provides functions to convert pyxctsk task objects into GeoJSON FeatureCollections for mapping and visualization.

Features:
- Turnpoints as GeoJSON Point features with styling for type (takeoff, SSS, ESS, goal, etc.)
- Optimized route as a LineString feature (if available)
- Goal line and control zone (for LINE type goals) as LineString and Polygon features

All features include geometry and properties suitable for web map display, including color, opacity, and descriptive metadata.

Intended for use in web-based or desktop mapping tools to visualize XCTrack competition tasks.
"""

from typing import Any, assert_never

from ..model.task import Task
from .common import (
    ControlZoneFeature,
    CylinderFeature,
    GoalLineFeature,
    RouteFeature,
    TaskDrawing,
)


def _cylinder(cylinder: CylinderFeature) -> dict[str, Any]:
    """A cylinder as a GeoJSON Point feature."""
    color = cylinder.color.hex
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": list(cylinder.centre)},
        "properties": {
            "name": cylinder.name,
            "type": "cylinder",
            "radius": cylinder.radius,
            "description": cylinder.description,
            "turnpoint_index": cylinder.index,
            "tp_type": cylinder.role.value,
            "color": color,
            "fillColor": color,
            "fillOpacity": 0.1,
            "weight": 2,
            "opacity": 0.7,
        },
    }


def _route(route: RouteFeature) -> dict[str, Any]:
    """The optimized route as a GeoJSON LineString feature."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [list(point) for point in route.points],
        },
        "properties": {
            "name": route.name,
            "type": "optimized_route",
            "color": route.color.hex,
            "weight": 3,
            "opacity": 0.8,
            "arrowheads": True,
            "arrow_color": route.color.hex,
            "arrow_size": 8,
            "arrow_spacing": 100,  # meters between arrows
        },
    }


def _goal_line(goal_line: GoalLineFeature) -> dict[str, Any]:
    """The goal line as a GeoJSON LineString feature."""
    first, second = goal_line.ends()
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": [list(first), list(second)]},
        "properties": {
            "name": goal_line.name,
            "type": "goal_line",
            "length": goal_line.length,
            "description": goal_line.description,
            "stroke": goal_line.color.hex,
            "stroke-width": 4,
            "stroke-opacity": 1.0,
        },
    }


def _control_zone(zone: ControlZoneFeature) -> dict[str, Any]:
    """The control zone as a GeoJSON Polygon feature."""
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[lon, lat] for lon, lat in zone.outline()]],
        },
        "properties": {
            "name": zone.name,
            "type": "goal_control_zone",
            "radius": zone.radius,
            "description": zone.description,
            "fill": zone.fill_color.hex,
            "fill-opacity": 0.3,
            "stroke": zone.edge_color.hex,
            "stroke-width": 2,
            "stroke-opacity": 0.8,
        },
    }


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
    for feature in drawing.features:
        match feature:
            case CylinderFeature():
                features.append(_cylinder(feature))
            case RouteFeature():
                features.append(_route(feature))
            case GoalLineFeature():
                features.append(_goal_line(feature))
            case ControlZoneFeature():
                features.append(_control_zone(feature))
            case _:
                assert_never(feature)

    return {"type": "FeatureCollection", "features": features}
