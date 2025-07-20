"""Task to KML conversion."""

from typing import List, Optional, Tuple

import simplekml  # type: ignore

from .goal_line import get_goal_line_data
from .task import Task, Turnpoint, TurnpointType
from .visualization_common import (
    generate_circle_coordinates_3d,
    get_optimized_route_coordinates,
    get_turnpoint_color_hex,
    get_turnpoints_to_render,
    is_goal_turnpoint,
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
    turnpoints: List[Turnpoint],
    task_altitude: int,
    original_turnpoints: List[Turnpoint],
    task: Optional[Task] = None,
) -> List[Tuple[float, float, int]]:
    """Create turnpoint circles and center points in the KML.

    Args:
        kml: The KML document to add elements to.
        turnpoints: List of turnpoints to render.
        task_altitude: Unified altitude for the task.
        original_turnpoints: Original task turnpoints for goal detection.
        task: Optional Task object for goal validation.

    Returns:
        List of coordinates for the turnpoints.
    """
    coordinates = []

    for i, turnpoint in enumerate(turnpoints):
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
            name=turnpoint.waypoint.name or f"TP{i+1}",
            description=f"Type: {turnpoint.type}, Radius: {turnpoint.radius}m",
            outerboundaryis=circle_coords,
            extrude=1,
            altitudemode=simplekml.AltitudeMode.relativetoground,
        )

        # Determine if this is the goal turnpoint
        is_goal = is_goal_turnpoint(turnpoint, original_turnpoints, task)
        turnpoint_type = turnpoint.type or TurnpointType.NONE
        circle_polygon.style = _create_turnpoint_style(turnpoint_type, is_goal)

        # Add turnpoint center point
        center_point = kml.newpoint(
            name=f"{turnpoint.waypoint.name or f'TP{i+1}'} Center",
            coords=[coord],
        )
        center_point.style.iconstyle.scale = 0.5
        center_point.style.iconstyle.color = _create_turnpoint_style(
            turnpoint_type, is_goal
        )

    return coordinates


def _create_course_line(
    kml: simplekml.Kml,
    task: Task,
    coordinates: List[Tuple[float, float, int]],
) -> None:
    """Create the course line connecting all turnpoints.

    Args:
        kml: The KML document to add elements to.
        task: The Task object.
        coordinates: Fallback coordinates if optimized route is not available.
        altitude: altitude for the line.
    """
    # Get optimized route coordinates
    opt_route_coords = get_optimized_route_coordinates(task)

    # Use optimized route if available, otherwise fallback to direct coordinates
    if opt_route_coords and len(opt_route_coords) >= 2:
        # Convert from (lat, lon) to (lon, lat) format (no altitude)
        route_coordinates = [(lon, lat) for lat, lon in opt_route_coords]
    else:
        route_coordinates = [(lon, lat) for (lon, lat, _alt) in coordinates]

    # Create the course line
    course_line = kml.newlinestring(
        name="Course Line",
        description=f"XCTrack task course with {len(task.turnpoints)} turnpoints",
        coords=route_coordinates,
        altitudemode=simplekml.AltitudeMode.clamptoground,
    )

    # Style the course line
    # Set color to red with 90% transparency (alpha=26 in KML AABBGGRR format)
    course_line.style.linestyle.color = "E64136ff"  # Red, 90% transparent
    course_line.style.linestyle.width = 4


def _create_goal_line_elements(kml: simplekml.Kml, task: Task, altitude: int) -> None:
    """Create goal line and control zone for LINE type goals.

    Args:
        kml: The KML document to add elements to.
        task: The Task object.
        altitude: altitude for the line.
    """
    goal_data = get_goal_line_data(task)
    if goal_data is None:
        return

    (lon1, lat1), (lon2, lat2), goal_line_length, control_zone_coords = goal_data

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
    kml = simplekml.Kml()
    altitude = DEFAULT_ALTITUDE  # Default altitude for KML elements

    # Determine which turnpoints to render
    # Skip the last turnpoint if it's a LINE type goal (goal line replaces it)
    turnpoints_to_render = get_turnpoints_to_render(task)

    # Create turnpoint elements and get coordinates
    coordinates = _create_turnpoint_elements(
        kml, turnpoints_to_render, altitude, task.turnpoints, task
    )

    # Create course line
    # line is created with clampToGround mode
    _create_course_line(kml, task, coordinates)

    # Create goal line elements if applicable
    # goal line elements are created 500m above the ground
    _create_goal_line_elements(kml, task, 500)

    return str(kml.kml())
