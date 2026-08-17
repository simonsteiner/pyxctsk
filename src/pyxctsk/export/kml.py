"""Task to KML conversion."""

import simplekml  # type: ignore

from ..model.task import Task, TurnpointType
from .common import (
    TaskDrawing,
    generate_circle_coordinates_3d,
    get_turnpoint_color_hex,
)

# Constants
ALPHA_TRANSPARENCY = 100
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
    style = simplekml.Style()
    style.linestyle.width = 4
    style.polystyle.outline = 1

    # Get hex color and convert to simplekml color
    hex_color = get_turnpoint_color_hex(turnpoint_type, is_goal)

    # Convert hex to simplekml color (assuming hex format #RRGGBB)
    color_map = {
        "#ff0000": simplekml.Color.red,
        "#204d74": simplekml.Color.darkblue,
        "#ac2925": simplekml.Color.darkred,
        "#ff8c00": simplekml.Color.orange,
        "#269abc": simplekml.Color.blue,
    }

    color = color_map.get(hex_color, simplekml.Color.blue)

    style.linestyle.color = color
    style.polystyle.color = simplekml.Color.changealphaint(ALPHA_TRANSPARENCY, color)

    return style


def _create_turnpoint_elements(
    kml: simplekml.Kml,
    drawing: TaskDrawing,
    task_altitude: int,
) -> list[tuple[float, float, int]]:
    """Create turnpoint circles and center points in the KML.

    Args:
        kml: The KML document to add elements to.
        drawing: The task drawing, which knows both which turnpoints to draw
            and which of them is the goal.
        task_altitude: Unified altitude for the task.

    Returns:
        List of coordinates for the turnpoints.
    """
    coordinates = []

    for i, turnpoint in enumerate(drawing.turnpoints):
        coord = (turnpoint.waypoint.lon, turnpoint.waypoint.lat, task_altitude)
        coordinates.append(coord)

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
        circle_polygon.style = _create_turnpoint_style(turnpoint_type, is_goal)

        # Add turnpoint center point
        center_point = kml.newpoint(
            name=f"{turnpoint.waypoint.name or f'TP{i + 1}'} Center",
            coords=[coord],
        )
        center_point.style.iconstyle.scale = 0.5
        center_point.style.iconstyle.color = _create_turnpoint_style(
            turnpoint_type, is_goal
        )

    return coordinates


def _create_course_line(
    kml: simplekml.Kml,
    drawing: TaskDrawing,
    coordinates: list[tuple[float, float, int]],
) -> None:
    """Create the course line connecting all turnpoints.

    Args:
        kml: The KML document to add elements to.
        drawing: The task drawing, carrying the optimized route.
        coordinates: Fallback coordinates if optimized route is not available.
    """
    opt_route_coords = drawing.route_coordinates()

    # Use optimized route if available, otherwise fallback to direct coordinates
    if opt_route_coords is not None:
        # Convert from (lat, lon) to (lon, lat) format (no altitude)
        route_coordinates = [(lon, lat) for lat, lon in opt_route_coords]
    else:
        route_coordinates = [(lon, lat) for (lon, lat, _alt) in coordinates]

    # Create the course line
    course_line = kml.newlinestring(
        name="Course Line",
        description=(
            f"XCTrack task course with {len(drawing.task.turnpoints)} turnpoints"
        ),
        coords=route_coordinates,
        altitudemode=simplekml.AltitudeMode.clamptoground,
    )

    # Style the course line
    # Set color to red with 90% transparency (alpha=26 in KML AABBGGRR format)
    course_line.style.linestyle.color = "E64136ff"  # Red, 90% transparent
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
    if drawing.goal_line is None:
        return

    (lon1, lat1), (lon2, lat2), goal_line_length, control_zone_coords = (
        drawing.goal_line.data()
    )

    # Create goal line
    goal_line = kml.newlinestring(
        name="Goal Line",
        description=f"Goal line length: {goal_line_length:.0f}m",
        coords=[(lon1, lat1, altitude), (lon2, lat2, altitude)],
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )
    goal_line.style.linestyle.color = simplekml.Color.red
    goal_line.style.linestyle.width = 5

    # Create control zone polygon
    control_zone_coords_3d = [
        (coord[0], coord[1], altitude) for coord in control_zone_coords
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

    # Create turnpoint elements and get coordinates
    coordinates = _create_turnpoint_elements(kml, drawing, altitude)

    # Create course line
    # line is created with clampToGround mode
    _create_course_line(kml, drawing, coordinates)

    # Create goal line elements if applicable
    # goal line elements are created 500m above the ground
    _create_goal_line_elements(kml, drawing, 500)

    return str(kml.kml())
