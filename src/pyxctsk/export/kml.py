"""Task to KML conversion."""

import re
from typing import assert_never

import simplekml  # type: ignore

from ..model.task import Task
from .common import (
    Color,
    ControlZoneFeature,
    CylinderFeature,
    GoalLineFeature,
    RouteFeature,
    TaskDrawing,
)

# Constants. Both alphas are opacity bytes, 0x00 transparent to 0xFF opaque, in
# one radix so they can be compared at a glance.
FILL_ALPHA = 0x64  # Cylinder and control-zone fills, 39% opaque
ROUTE_ALPHA = 0xE6  # Course line, 90% opaque

# Both are metres above ground, and both are presentation choices: the
# cylinders are extruded high enough to read as volumes, the goal line low
# enough to sit inside them rather than above. The second used to be a bare
# `500` at the call site with a comment, beside a named constant for the first.
TURNPOINT_ALTITUDE = 5000
GOAL_LINE_ALTITUDE = 500

#: Every character XML 1.0 has no way to spell, not even as a character
#: reference: the C0 controls but tab, newline and carriage return, the
#: surrogates, and U+FFFE/U+FFFF (XML 1.0 §2.2, ``Char``).
_NOT_XML_CHAR = re.compile(
    "[^\t\n\r\u0020-\ud7ff\ue000-\N{REPLACEMENT CHARACTER}\U00010000-\U0010ffff]"
)


def _xml_text(text: str) -> str:
    r"""Return ``text`` with each character XML cannot carry replaced by U+FFFD.

    A name may hold any character JSON and UTF-8 can — the reader keeps
    ``"a\u0001"`` as text, because the full and QR formats both carry it — but
    KML is XML 1.0, and simplekml raised ``xml.parsers.expat.ExpatError`` on
    one, outside the library's error hierarchy. Replaced rather than refused, so
    one stray control character costs a glyph rather than the whole map; and
    replaced rather than dropped, so the name still shows that something was
    there. Only KML needs this: GeoJSON is JSON.

    Args:
        text: User text bound for the document.

    Returns:
        The text, safe to hand to simplekml.
    """
    return _NOT_XML_CHAR.sub("\N{REPLACEMENT CHARACTER}", text)


def _create_turnpoint_style(color: Color) -> simplekml.Style:
    """Create the style for a turnpoint cylinder in the given colour.

    Args:
        color: The cylinder's colour.

    Returns:
        A configured simplekml.Style object.
    """
    style = simplekml.Style()
    style.linestyle.width = 4
    style.polystyle.outline = 1
    style.linestyle.color = color.kml()
    style.polystyle.color = color.kml(FILL_ALPHA)

    return style


def _add_cylinder(kml: simplekml.Kml, cylinder: CylinderFeature) -> None:
    """Add a cylinder's polygon and its centre point."""
    altitude = TURNPOINT_ALTITUDE
    lon, lat = cylinder.centre
    label = _xml_text(cylinder.name)

    polygon = kml.newpolygon(
        name=label,
        description=cylinder.description,
        outerboundaryis=[(lon, lat, altitude) for lon, lat in cylinder.outline()],
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    style = _create_turnpoint_style(cylinder.color)
    polygon.style = style

    # The centre point is in the same colour as its cylinder.
    center_point = kml.newpoint(name=f"{label} Center", coords=[(lon, lat, altitude)])
    center_point.style.iconstyle.scale = 0.5
    center_point.style.iconstyle.color = style.linestyle.color


def _add_route(kml: simplekml.Kml, route: RouteFeature) -> None:
    """Add the course line, clamped to the ground, in the route colour."""
    course_line = kml.newlinestring(
        name=route.name,
        description=route.description,
        coords=list(route.points),
        altitudemode=simplekml.AltitudeMode.clamptoground,
    )
    course_line.style.linestyle.color = route.color.kml(ROUTE_ALPHA)
    course_line.style.linestyle.width = 4


def _add_goal_line(kml: simplekml.Kml, goal_line: GoalLineFeature) -> None:
    """Add the goal line, at the goal-line altitude."""
    altitude = GOAL_LINE_ALTITUDE
    (lon1, lat1), (lon2, lat2) = goal_line.ends()
    placemark = kml.newlinestring(
        name=goal_line.name,
        description=goal_line.description,
        coords=[(lon1, lat1, altitude), (lon2, lat2, altitude)],
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    placemark.style.linestyle.color = goal_line.color.kml()
    placemark.style.linestyle.width = 5


def _add_control_zone(kml: simplekml.Kml, zone: ControlZoneFeature) -> None:
    """Add the control zone polygon, at the goal-line altitude."""
    altitude = GOAL_LINE_ALTITUDE
    polygon = kml.newpolygon(
        name=zone.name,
        description=zone.description,
        outerboundaryis=[(lon, lat, altitude) for lon, lat in zone.outline()],
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    polygon.style.linestyle.color = zone.edge_color.kml()
    polygon.style.linestyle.width = 2
    polygon.style.polystyle.color = zone.fill_color.kml(FILL_ALPHA)
    polygon.style.polystyle.outline = 1


def task_to_kml(task: Task) -> str:
    """Convert a Task object to a KML format string for visualization.

    Creates a KML document containing:
    - Circular turnpoint zones with type-based styling
    - Center points for precise turnpoint locations
    - Course line connecting turnpoints (optimized route if available)
    - Goal line and control zone for LINE type goals

    Args:
        task: The Task object containing turnpoints and related data.

    Returns:
        A string containing the KML representation of the task.
    """
    return drawing_to_kml(TaskDrawing.from_task(task))


def drawing_to_kml(drawing: TaskDrawing) -> str:
    """Convert an already-derived task drawing to KML.

    Use this to render one drawing in both formats without optimizing the route
    twice::

        drawing = TaskDrawing.from_task(task)
        kml, geojson = drawing_to_kml(drawing), drawing_to_geojson(drawing)

    Args:
        drawing: The task drawing to render.

    Returns:
        A string containing the KML representation of the task.
    """
    kml = simplekml.Kml()

    for feature in drawing.features:
        match feature:
            case CylinderFeature():
                _add_cylinder(kml, feature)
            case RouteFeature():
                _add_route(kml, feature)
            case GoalLineFeature():
                _add_goal_line(kml, feature)
            case ControlZoneFeature():
                _add_control_zone(kml, feature)
            case _:
                assert_never(feature)

    return str(kml.kml())
