"""Utility functions for XCTrack tasks.

This module provides helper functions for working with XCTrack task data, including:
- QR code generation (if dependencies are available)
- Conversion of Task objects to KML format

See project documentation for details on usage and requirements.
"""

import simplekml  # type: ignore

from .task import Task

# Optional QR code dependencies
try:
    import qrcode
    from PIL import Image

    QR_CODE_SUPPORT = True
except ImportError:
    qrcode = None  # type: ignore
    Image = None  # type: ignore
    QR_CODE_SUPPORT = False


def generate_qr_code(data: str, size: int = 1024):
    """Generate a QR code image from string data.

    Args:
        data (str): String data to encode.
        size (int): Size of the generated QR code image.

    Returns:
        Image: PIL Image containing the QR code.

    Raises:
        ImportError: If QR code dependencies are not available.
    """
    if not QR_CODE_SUPPORT:
        raise ImportError("QR code support requires 'qrcode' and 'Pillow' packages")

    qr = qrcode.QRCode(  # type: ignore
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # type: ignore
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Resize to requested size
    try:
        # Try new Pillow API first
        img = img.resize((size, size), Image.Resampling.LANCZOS)  # type: ignore
    except AttributeError:
        # Fall back to old API for older Pillow versions
        img = img.resize((size, size), Image.LANCZOS)  # type: ignore
    return img


def task_to_kml(task: Task) -> str:
    """Convert a Task object to KML format string.

    Args:
        task (Task): Task object.

    Returns:
        str: KML string.
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
