"""Task to KML conversion."""

import simplekml  # type: ignore

from .task import Task


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
    coordinates = []
    for i, turnpoint in enumerate(task.turnpoints):
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

    # Create the course line connecting all turnpoints
    course_line = kml.newlinestring(
        name="Course Line",
        description=f"XCTrack task course with {len(task.turnpoints)} turnpoints",
        coords=coordinates,
        extrude=1,
        altitudemode=simplekml.AltitudeMode.relativetoground,
    )

    # Style the course line
    course_line.style.linestyle.color = simplekml.Color.blue
    course_line.style.linestyle.width = 3

    return str(kml.kml())
