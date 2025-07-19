"""Task to KML conversion."""

import simplekml  # type: ignore

from .distance import optimized_route_coordinates
from .goal_line import get_goal_line_data, should_skip_last_turnpoint
from .task import Task
from .task_distances import _task_to_turnpoints


def task_to_kml(task: Task) -> str:
    """Converts a Task object to a KML format string for visualization.

    Args:
        task (Task): The Task object containing turnpoints and related data.

    Returns:
        str: A string containing the KML representation of the task, including turnpoint zones and course line.
    """
    import math

    kml = simplekml.Kml()

    # Create style for turnpoint circles
    circle_style = simplekml.Style()
    circle_style.linestyle.color = simplekml.Color.red
    circle_style.linestyle.width = 4
    circle_style.polystyle.color = simplekml.Color.changealphaint(
        100, simplekml.Color.green
    )
    circle_style.polystyle.outline = 1

    # Create coordinates list and individual turnpoint circles
    # Skip the last turnpoint if it's a LINE type goal (goal line replaces it)
    turnpoints_to_render = task.turnpoints
    if should_skip_last_turnpoint(task):
        turnpoints_to_render = task.turnpoints[:-1]

    coordinates = []
    for i, turnpoint in enumerate(turnpoints_to_render):
        coord = (
            turnpoint.waypoint.lon,
            turnpoint.waypoint.lat,
            turnpoint.waypoint.alt_smoothed,
        )
        coordinates.append(coord)

        # Create circular turnpoint zone
        circle_coords = []
        num_points = 64  # Number of points to approximate circle

        # Convert radius from meters to degrees (rough approximation)
        radius_deg = turnpoint.radius / 111320.0  # 1 degree ≈ 111.32 km at equator

        for j in range(num_points + 1):  # +1 to close the circle
            angle = 2 * math.pi * j / num_points
            lat = turnpoint.waypoint.lat + radius_deg * math.sin(angle)
            lon = turnpoint.waypoint.lon + radius_deg * math.cos(angle) / math.cos(
                math.radians(turnpoint.waypoint.lat)
            )
            circle_coords.append((lon, lat, turnpoint.waypoint.alt_smoothed))

        # Create turnpoint circle as polygon
        circle_polygon = kml.newpolygon(
            name=turnpoint.waypoint.name or f"TP{i+1}",
            description=f"Type: {turnpoint.type}, Radius: {turnpoint.radius}m",
            outerboundaryis=circle_coords,
            extrude=1,
            altitudemode=simplekml.AltitudeMode.relativetoground,
        )

        # Apply style
        circle_polygon.style = circle_style

        # Add turnpoint center as a point placemark to ensure exact coordinates appear in KML
        center_point = kml.newpoint(
            name=f"{turnpoint.waypoint.name or f'TP{i+1}'} Center",
            coords=[
                (
                    turnpoint.waypoint.lon,
                    turnpoint.waypoint.lat,
                    turnpoint.waypoint.alt_smoothed,
                )
            ],
        )
        center_point.style.iconstyle.scale = 0.5  # Make it smaller
        center_point.style.iconstyle.color = simplekml.Color.red

    # Generate optimized route coordinates
    task_turnpoints = _task_to_turnpoints(task)
    opt_route_coords = optimized_route_coordinates(task_turnpoints, task.turnpoints)

    # Convert optimized route coordinates to KML format with altitude
    # opt_route_coords are in (lat, lon) format, convert to (lon, lat, alt)
    if opt_route_coords and len(opt_route_coords) >= 2:
        # Use optimized route coordinates
        route_coordinates = []
        for i, (lat, lon) in enumerate(opt_route_coords):
            # For altitude, interpolate between turnpoints or use a default
            if i < len(task.turnpoints):
                alt = task.turnpoints[i].waypoint.alt_smoothed
            else:
                # Use last turnpoint altitude for any extra points
                alt = task.turnpoints[-1].waypoint.alt_smoothed
            route_coordinates.append((lon, lat, alt))
    else:
        # Fallback to direct turnpoint coordinates if optimized route is not available
        route_coordinates = coordinates

    # Create the course line connecting all points
    course_line = kml.newlinestring(
        name="Course Line",
        description=f"XCTrack task course with {len(task.turnpoints)} turnpoints",
        coords=route_coordinates,
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )

    # Style the course line
    course_line.style.linestyle.color = simplekml.Color.blue
    course_line.style.linestyle.width = 3

    # Add goal line and control zone for LINE type goals
    goal_data = get_goal_line_data(task)
    if goal_data is not None:
        (lon1, lat1), (lon2, lat2), goal_line_length, control_zone_coords = goal_data

        # Get altitude for goal line (use last turnpoint altitude)
        goal_alt = task.turnpoints[-1].waypoint.alt_smoothed

        # Create goal line
        goal_line = kml.newlinestring(
            name="Goal Line",
            description=f"Goal line length: {goal_line_length:.0f}m",
            coords=[(lon1, lat1, goal_alt), (lon2, lat2, goal_alt)],
            extrude=1,
            altitudemode=simplekml.AltitudeMode.relativetoground,
        )
        goal_line.style.linestyle.color = simplekml.Color.green
        goal_line.style.linestyle.width = 5

        # Create control zone polygon
        control_zone_coords_3d = [
            (coord[0], coord[1], goal_alt) for coord in control_zone_coords
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
            100, simplekml.Color.cyan
        )
        control_zone.style.polystyle.outline = 1

    return str(kml.kml())
