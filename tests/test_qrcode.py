"""Tests for QR code functionality."""

import os
import tempfile
from io import BytesIO

import pytest

from pyxctsk import Task, TaskType, Turnpoint, Waypoint, parse_task
from pyxctsk.qrcode_task import QRCodeTask
from pyxctsk.utils import generate_qr_code

try:
    from PIL import Image
    from pyzbar import pyzbar

    QR_CODE_SUPPORT = True
except ImportError:
    QR_CODE_SUPPORT = False


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
def test_qr_code_roundtrip():
    """Test complete QR code roundtrip: Task -> QR string -> QR image -> Task."""
    # Create a simple task
    original_task = Task(
        task_type=TaskType.CLASSIC,
        version=1,
        turnpoints=[
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(name="TP01", lat=46.5, lon=8.0, alt_smoothed=1000),
            ),
            Turnpoint(
                radius=1500,
                waypoint=Waypoint(name="TP02", lat=46.6, lon=8.1, alt_smoothed=1200),
            ),
        ],
    )

    # Convert to QR code string
    qr_task = original_task.to_qr_code_task()
    qr_string = qr_task.to_string()

    # Generate QR code image
    qr_image = generate_qr_code(qr_string, size=512)

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        qr_image.save(tmp_path, format="PNG")

    try:
        # Parse back from image file
        parsed_task = parse_task(tmp_path)

        # Verify the roundtrip
        assert parsed_task.task_type == original_task.task_type
        assert parsed_task.version == original_task.version
        assert len(parsed_task.turnpoints) == len(original_task.turnpoints)

        for orig_tp, parsed_tp in zip(original_task.turnpoints, parsed_task.turnpoints):
            assert orig_tp.waypoint.name == parsed_tp.waypoint.name
            assert abs(orig_tp.waypoint.lat - parsed_tp.waypoint.lat) < 0.001
            assert abs(orig_tp.waypoint.lon - parsed_tp.waypoint.lon) < 0.001
            assert orig_tp.radius == parsed_tp.radius

    finally:
        # Clean up
        os.unlink(tmp_path)


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
def test_qr_code_string_parsing():
    """Test parsing QR code string directly."""
    # Create QR task
    qr_task = QRCodeTask(version=2)
    qr_string = qr_task.to_string()

    # Parse from string
    parsed_task = parse_task(qr_string)
    # Note: QR code tasks always convert to regular tasks with version 1
    assert parsed_task.version == 1


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
def test_qr_code_image_bytes():
    """Test parsing QR code from image bytes."""
    # Create a simple task
    task = Task(
        task_type=TaskType.CLASSIC,
        version=1,
        turnpoints=[
            Turnpoint(
                radius=500,
                waypoint=Waypoint(name="Test", lat=47.0, lon=8.5, alt_smoothed=800),
            )
        ],
    )

    # Convert to QR code and generate image
    qr_task = task.to_qr_code_task()
    qr_string = qr_task.to_string()
    qr_image = generate_qr_code(qr_string, size=256)

    # Convert to bytes
    image_buffer = BytesIO()
    qr_image.save(image_buffer, format="PNG")
    image_bytes = image_buffer.getvalue()

    # Parse from bytes
    parsed_task = parse_task(image_bytes)

    assert parsed_task.task_type == TaskType.CLASSIC
    assert len(parsed_task.turnpoints) == 1
    assert parsed_task.turnpoints[0].waypoint.name == "Test"


def test_qr_code_without_dependencies():
    """Test QR code functionality gracefully handles missing dependencies."""
    # This test ensures the module doesn't crash when QR code deps are missing
    # Even if they're installed, we can test the import error handling

    # Create a simple QR task
    qr_task = QRCodeTask(version=1)
    qr_string = qr_task.to_string()

    # This should work regardless of QR code dependencies
    assert qr_string.startswith("XCTSK:")

    # Parsing the string should also work
    parsed_task = parse_task(qr_string)
    assert parsed_task.version == 1
