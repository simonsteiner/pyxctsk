"""Task to KML conversion."""

import simplekml  # type: ignore

from ..model.task import Task, TurnpointType
from .common import (
    ROUTE_COLOR,
    TaskDrawing,
    generate_circle_coordinates_3d,
    turnpoint_color,
)

# Constants
ALPHA_TRANSPARENCY = 100  # Cylinder and control-zone fills, 0-255
ROUTE_ALPHA = 0xE6  # Course line, 90% opaque
DEFAULT_ALTITUDE = 5000  # Default altitude for KML elements


def _create_turnpoint_style(
    turnpoint_type: TurnpointType, is_goal: bool = False
) -> simplekml.Style:
    """Create style for turnpoint based on its type.

    Args:
        turnpoint_type: The type of turnpoint.
        is_goal: Whether this is the goal (last) turnpoint.

    Returns:
        A configured simplekml.Style object.
    """
    color = turnpoint_color(turnpoint_type, is_goal)

    style = simplekml.Style()
    style.linestyle.width = 4
    style.polystyle.outline = 1
    style.linestyle.color = color.kml()
    style.polystyle.color = color.kml(ALPHA_TRANSPARENCY)

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
            name=turnpoint.waypoint.name or f"TP{i + 1}",
            description=f"Type: {turnpoint.type}, Radius: {turnpoint.radius}m",
            outerboundaryis=circle_coords,
            extrude=1,
            altitudemode=simplekml.AltitudeMode.relativetoground,
        )

        # Determine if this is the goal turnpoint
        is_goal = drawing.is_goal(turnpoint)
        turnpoint_type = turnpoint.type or TurnpointType.NONE
        style = _create_turnpoint_style(turnpoint_type, is_goal)
        circle_polygon.style = style

        # Add turnpoint center point, in the same colour as its cylinder.
        center_point = kml.newpoint(
            name=f"{turnpoint.waypoint.name or f'TP{i + 1}'} Center",
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
    opt_route_coords = drawing.route_coordinates()
    if opt_route_coords is None:
        return

    # Convert from (lat, lon) to (lon, lat) format (no altitude)
    route_coordinates = [(lon, lat) for lat, lon in opt_route_coords]

    # Create the course line
    course_line = kml.newlinestring(
        name="Course Line",
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
    goal_line_length = goal_line.length

    # Create goal line
    goal_line_placemark = kml.newlinestring(
        name="Goal Line",
        description=f"Goal line length: {goal_line_length:.0f}m",
        coords=[(lon1, lat1, altitude), (lon2, lat2, altitude)],
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    goal_line_placemark.style.linestyle.color = simplekml.Color.red
    goal_line_placemark.style.linestyle.width = 5

    # Create control zone polygon
    control_zone_coords_3d = [
        (lon, lat, altitude) for lon, lat in goal_line.control_zone()
    ]

    control_zone = kml.newpolygon(
        name="Goal Control Zone",
        description=f"Goal control zone radius: {goal_line_length / 2:.0f}m",
        outerboundaryis=control_zone_coords_3d,
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    control_zone.style.linestyle.color = simplekml.Color.cyan
    control_zone.style.linestyle.width = 2
    control_zone.style.polystyle.color = simplekml.Color.changealphaint(
        ALPHA_TRANSPARENCY, simplekml.Color.cyan
    )
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
    altitude = DEFAULT_ALTITUDE  # Default altitude for KML elements

    # Create turnpoint elements
    _create_turnpoint_elements(kml, drawing, altitude)

    # Create course line
    # line is created with clampToGround mode
    _create_course_line(kml, drawing)

    # Create goal line elements if applicable
    # goal line elements are created 500m above the ground
    _create_goal_line_elements(kml, drawing, 500)

    return str(kml.kml())
