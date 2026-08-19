"""Task to KML conversion."""

import simplekml  # type: ignore

from ..model.task import Task
from .common import (
    CONTROL_ZONE_EDGE_COLOR,
    CONTROL_ZONE_FILL_COLOR,
    GOAL_LINE_COLOR,
    ROUTE_COLOR,
    Color,
    TaskDrawing,
    generate_circle_coordinates_3d,
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


def _create_turnpoint_style(color: Color) -> simplekml.Style:
    """Create the style for a turnpoint cylinder in the given colour.

    Args:
        color: The turnpoint's colour, from :meth:`TaskDrawing.color_of`.

    Returns:
        A configured simplekml.Style object.
    """
    style = simplekml.Style()
    style.linestyle.width = 4
    style.polystyle.outline = 1
    style.linestyle.color = color.kml()
    style.polystyle.color = color.kml(FILL_ALPHA)

    return style


def _create_turnpoint_elements(
    kml: simplekml.Kml,
    drawing: TaskDrawing,
    task_altitude: int,
) -> None:
    """Create turnpoint circles and center points in the KML.

    Args:
        kml: The KML document to add elements to.
        drawing: The task drawing, which knows both which turnpoints to draw
            and which of them is the goal.
        task_altitude: Unified altitude for the task.
    """
    for i, turnpoint in enumerate(drawing.turnpoints):
        coord = (turnpoint.waypoint.lon, turnpoint.waypoint.lat, task_altitude)

        # Generate circle coordinates
        circle_coords = generate_circle_coordinates_3d(
            turnpoint.waypoint.lat,
            turnpoint.waypoint.lon,
            turnpoint.radius,
            task_altitude,
        )

        # Create turnpoint circle as polygon
        circle_polygon = kml.newpolygon(
            name=drawing.label_of(turnpoint, i),
            description=drawing.description_of(turnpoint),
            outerboundaryis=circle_coords,
            extrude=1,
            altitudemode=simplekml.AltitudeMode.relativetoground,
        )

        # The drawing answers what colour this turnpoint is, goal included.
        style = _create_turnpoint_style(drawing.color_of(turnpoint))
        circle_polygon.style = style

        # Add turnpoint center point, in the same colour as its cylinder.
        center_point = kml.newpoint(
            name=f"{drawing.label_of(turnpoint, i)} Center",
            coords=[coord],
        )
        center_point.style.iconstyle.scale = 0.5
        center_point.style.iconstyle.color = style.linestyle.color


def _create_course_line(kml: simplekml.Kml, drawing: TaskDrawing) -> None:
    """Create the course line along the optimized route, if there is one.

    Fewer than two points is not a line: a task with one turnpoint used to emit
    a one-coordinate ``<LineString>``, and an empty task a phantom one at
    0°N 0°E, because simplekml writes an empty coordinate list as a single zero
    point. GeoJSON omits the route feature in that case and KML now agrees.

    Args:
        kml: The KML document to add elements to.
        drawing: The task drawing, carrying the optimized route.
    """
    route_coordinates = drawing.route_coordinates_lon_lat()
    if route_coordinates is None:
        return

    # Create the course line
    course_line = kml.newlinestring(
        name=drawing.route_label(),
        description=(
            f"XCTrack task course with {len(drawing.task.turnpoints)} turnpoints"
        ),
        coords=route_coordinates,
        altitudemode=simplekml.AltitudeMode.clamptoground,
    )

    # Style the course line: the shared route colour, 90% opaque.
    course_line.style.linestyle.color = ROUTE_COLOR.kml(ROUTE_ALPHA)
    course_line.style.linestyle.width = 4


def _create_goal_line_elements(
    kml: simplekml.Kml, drawing: TaskDrawing, altitude: int
) -> None:
    """Create goal line and control zone for LINE type goals.

    Args:
        kml: The KML document to add elements to.
        drawing: The task drawing, carrying the goal line if there is one.
        altitude: altitude for the line.
    """
    goal_line = drawing.goal_line
    if goal_line is None:
        return

    (lon1, lat1), (lon2, lat2), _ = goal_line.endpoints()

    # Create goal line
    goal_line_placemark = kml.newlinestring(
        name=drawing.goal_line_label(),
        description=drawing.goal_line_description(),
        coords=[(lon1, lat1, altitude), (lon2, lat2, altitude)],
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    goal_line_placemark.style.linestyle.color = GOAL_LINE_COLOR.kml()
    goal_line_placemark.style.linestyle.width = 5

    # Create control zone polygon
    control_zone_coords_3d = [
        (lon, lat, altitude) for lon, lat in goal_line.control_zone()
    ]

    control_zone = kml.newpolygon(
        name=drawing.control_zone_label(),
        description=drawing.control_zone_description(),
        outerboundaryis=control_zone_coords_3d,
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    control_zone.style.linestyle.color = CONTROL_ZONE_EDGE_COLOR.kml()
    control_zone.style.linestyle.width = 2
    control_zone.style.polystyle.color = CONTROL_ZONE_FILL_COLOR.kml(FILL_ALPHA)
    control_zone.style.polystyle.outline = 1


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

    _create_turnpoint_elements(kml, drawing, TURNPOINT_ALTITUDE)
    # The course line is clamped to the ground; the goal line is not.
    _create_course_line(kml, drawing)
    _create_goal_line_elements(kml, drawing, GOAL_LINE_ALTITUDE)

    return str(kml.kml())
