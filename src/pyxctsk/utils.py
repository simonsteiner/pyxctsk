"""Utility functions for XCTrack tasks."""

from .task import Task

# Optional QR code dependencies
try:
    import qrcode
    from PIL import Image

    QR_CODE_SUPPORT = True
except ImportError:
    QR_CODE_SUPPORT = False


def generate_qr_code(data: str, size: int = 1024):
    """
    Generate a QR code image from string data.

    Args:
        data: String data to encode
        size: Size of the generated QR code image

    Returns:
        PIL Image containing the QR code

    Raises:
        ImportError: If QR code dependencies are not available
    """
    if not QR_CODE_SUPPORT:
        raise ImportError("QR code support requires 'qrcode' and 'Pillow' packages")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Resize to requested size
    img = img.resize((size, size), Image.LANCZOS)
    return img


def task_to_kml(task: Task) -> str:
    """
    Convert a Task to KML format.

    Args:
        task: Task to convert

    Returns:
        KML string representation
    """
    coordinates = []
    for turnpoint in task.turnpoints:
        coord_str = f"{turnpoint.waypoint.lon},{turnpoint.waypoint.lat},{turnpoint.waypoint.alt_smoothed}"
        coordinates.append(coord_str)

    coordinates_str = " ".join(coordinates)

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Folder>
      <Placemark>
        <LineString>
          <coordinates>{coordinates_str}</coordinates>
        </LineString>
      </Placemark>
    </Folder>
  </Document>
</kml>"""

    return kml
