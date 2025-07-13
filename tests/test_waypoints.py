"""Test module for XC/Waypoints simplified format."""

import json

from pyxctsk.qrcode_task import QRCodeTask, QRCodeTaskType, QRCodeTurnpoint


def test_waypoints_format():
    """Test the XC/Waypoints simplified format."""

    # Create a simple waypoints task
    turnpoints = [
        QRCodeTurnpoint(
            lat=46.3028,
            lon=13.8470,
            radius=1000,
            name="Start",
            alt_smoothed=1200,
        ),
        QRCodeTurnpoint(
            lat=46.3128,
            lon=13.8570,
            radius=1000,
            name="WP1",
            alt_smoothed=1300,
        ),
        QRCodeTurnpoint(
            lat=46.3228,
            lon=13.8670,
            radius=1000,
            name="Goal",
            alt_smoothed=1400,
        ),
    ]

    task = QRCodeTask(
        version=2,
        task_type=QRCodeTaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )

    # Test simplified format
    simplified_json = task.to_waypoints_json()

    # Parse the JSON to verify structure
    data = json.loads(simplified_json)

    # Verify expected structure
    assert "T" in data and data["T"] == "W", f"Expected T=W, got {data.get('T')}"
    assert "V" in data and data["V"] == 2, f"Expected V=2, got {data.get('V')}"
    assert (
        "t" in data and len(data["t"]) == 3
    ), f"Expected 3 turnpoints, got {len(data.get('t', []))}"

    # Verify turnpoint structure
    for i, tp in enumerate(data["t"]):
        assert "n" in tp, f"Turnpoint {i} missing name"
        assert "z" in tp, f"Turnpoint {i} missing encoded coordinates"
        assert len(tp) == 2, f"Turnpoint {i} has extra fields: {tp}"


def test_waypoints_round_trip():
    """Test round-trip conversion for waypoints format."""

    # Create a simple waypoints task
    turnpoints = [
        QRCodeTurnpoint(
            lat=46.3028,
            lon=13.8470,
            radius=1000,
            name="Start",
            alt_smoothed=1200,
        ),
        QRCodeTurnpoint(
            lat=46.3128,
            lon=13.8570,
            radius=1000,
            name="WP1",
            alt_smoothed=1300,
        ),
        QRCodeTurnpoint(
            lat=46.3228,
            lon=13.8670,
            radius=1000,
            name="Goal",
            alt_smoothed=1400,
        ),
    ]

    task = QRCodeTask(
        version=2,
        task_type=QRCodeTaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )

    # Test round-trip conversion
    simplified_json = task.to_waypoints_json()
    parsed_task = QRCodeTask.from_json(simplified_json)

    assert parsed_task.task_type == QRCodeTaskType.WAYPOINTS
    assert len(parsed_task.turnpoints) == 3

    # Verify turnpoints were parsed correctly
    for i, (original, parsed) in enumerate(zip(turnpoints, parsed_task.turnpoints)):
        assert original.name == parsed.name, f"Name mismatch at turnpoint {i}"

        # Check if coordinates are reasonably close (polyline encoding is lossy)
        lat_diff = abs(original.lat - parsed.lat)
        lon_diff = abs(original.lon - parsed.lon)
        assert lat_diff < 0.001, f"Lat difference too large: {lat_diff}"
        assert lon_diff < 0.001, f"Lon difference too large: {lon_diff}"


def test_waypoints_url_format():
    """Test URL format for waypoints."""

    # Create a simple waypoints task
    turnpoints = [
        QRCodeTurnpoint(
            lat=46.3028,
            lon=13.8470,
            radius=1000,
            name="Start",
            alt_smoothed=1200,
        ),
        QRCodeTurnpoint(
            lat=46.3128,
            lon=13.8570,
            radius=1000,
            name="WP1",
            alt_smoothed=1300,
        ),
        QRCodeTurnpoint(
            lat=46.3228,
            lon=13.8670,
            radius=1000,
            name="Goal",
            alt_smoothed=1400,
        ),
    ]

    task = QRCodeTask(
        version=2,
        task_type=QRCodeTaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )

    # Test URL format
    url_string = task.to_waypoints_string()
    assert url_string.startswith("XCTSK:"), "URL should start with XCTSK:"

    # Parse from URL
    parsed_from_url = QRCodeTask.from_string(url_string)
    assert len(parsed_from_url.turnpoints) == 3, "Should have 3 turnpoints from URL"
    assert parsed_from_url.task_type == QRCodeTaskType.WAYPOINTS
