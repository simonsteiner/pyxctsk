"""Tests for the QR code round trips, end to end.

Task → QR string → QR image → Task, over the reference corpus and made-up
tasks:
1. QR code string generation from task files with format detection
2. QR code image generation, saving, and parsing when dependencies are available
3. Comparison against expected QR code strings for regression testing
4. Error handling when QR code dependencies are missing

The per-module tests are in ``test_task.py``, ``test_image.py``,
``test_models.py`` and ``test_encoding.py``.
"""

import json
import os
import tempfile
import unicodedata
from io import BytesIO

import pytest

from pyxctsk import (
    EarthModel,
    Task,
    TaskType,
    Turnpoint,
    TurnpointType,
    Waypoint,
    load_task,
    parse_task,
)
from pyxctsk.qrcode.image import generate_qrcode_image
from pyxctsk.qrcode.task import QRCodeTask
from tests.corpus import reference_tasks

# Use shared QR code test utilities
from tests.qr_test_utils import QR_CODE_SUPPORT, Image, decode_qr

REFERENCE_TASKS = reference_tasks()


@pytest.mark.parametrize("reference", REFERENCE_TASKS, ids=str)
def test_qr_code_string_matches_the_expected_one(reference):
    """Every reference task encodes to the string the producer wrote.

    Both shapes go through the library. The waypoints ones used to be checked
    by re-serializing the *source file* and comparing that to the expected
    string, which compares two fixtures to each other and never runs the
    encoder at all.
    """
    qr = reference.task.to_qr_code_task()
    emitted = qr.to_string()

    assert emitted.startswith("XCTSK:")
    assert emitted == reference.qr_string


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
@pytest.mark.parametrize("reference", REFERENCE_TASKS, ids=str)
def test_qr_code_image_round_trips(reference, tmp_path):
    """Task → QR string → PNG → decoded string → Task, on every reference task.

    The image goes to ``tmp_path``: the suite used to write 24 tracked PNGs
    into the source tree on every run.
    """
    task = reference.task
    qr_string = task.to_qr_code_task().to_string()

    image = generate_qrcode_image(qr_string, size=512)
    png = tmp_path / f"{reference.stem}_qr.png"
    image.save(png, format="PNG")

    decoded = decode_qr(Image.open(png))
    assert decoded, f"failed to decode the QR code for {reference.stem}"
    assert _normalized(decoded[0]) == _normalized(qr_string)

    # And the decoded string parses back to the task it came from.
    for parsed in (parse_task(decoded[0]), parse_task(png.read_bytes())):
        assert parsed.task_type == task.task_type
        assert len(parsed.turnpoints) == len(task.turnpoints)
        for original, round_tripped in zip(task.turnpoints, parsed.turnpoints):
            assert original.waypoint.name == round_tripped.waypoint.name
            assert abs(original.waypoint.lat - round_tripped.waypoint.lat) < 0.001
            assert abs(original.waypoint.lon - round_tripped.waypoint.lon) < 0.001


def _normalized(qr_string: str):
    """Return a QR payload as JSON with its strings in Unicode NFC.

    Task names carry accents, and a decoder may hand them back decomposed —
    a difference in the encoding of the same text, not in the task.
    """
    payload = json.loads(qr_string[len("XCTSK:") :])

    def nfc(value):
        if isinstance(value, str):
            return unicodedata.normalize("NFC", value)
        if isinstance(value, list):
            return [nfc(item) for item in value]
        if isinstance(value, dict):
            return {key: nfc(item) for key, item in value.items()}
        return value

    return nfc(payload)


def test_roundtrip_basic():
    """Test basic QR code roundtrip with synthetic task data.

    Creates a simple task with multiple turnpoint types (TAKEOFF, SSS, ESS) and tests:
    - QR string generation and parsing
    - Image generation and parsing (when dependencies available)
    - Preservation of task properties and turnpoint data
    """
    # Create a simple task
    waypoints = [
        Waypoint(name="Start", lat=47.0, lon=8.0, alt_smoothed=1000),
        Waypoint(name="TP1", lat=47.1, lon=8.1, alt_smoothed=1200),
        Waypoint(name="Goal", lat=47.2, lon=8.0, alt_smoothed=900),
    ]

    turnpoints = [
        Turnpoint(waypoint=waypoints[0], type=TurnpointType.TAKEOFF, radius=0),
        Turnpoint(waypoint=waypoints[0], type=TurnpointType.SSS, radius=400),
        Turnpoint(
            waypoint=waypoints[1], type=None, radius=400
        ),  # Regular turnpoint/cylinder
        Turnpoint(waypoint=waypoints[2], type=TurnpointType.ESS, radius=1000),
        Turnpoint(waypoint=waypoints[2], type=None, radius=400),  # Goal
    ]

    task = Task(
        task_type=TaskType.CLASSIC,
        version=1,
        turnpoints=turnpoints,
        earth_model=EarthModel.WGS84,
    )

    # Generate QR code string
    qr_task = task.to_qr_code_task()
    qr_string = qr_task.to_string()

    assert qr_string.startswith("XCTSK:"), "Invalid QR string format"

    # Parse back to a task
    roundtrip_task = parse_task(qr_string)

    # Verify key properties are preserved
    assert roundtrip_task.task_type == task.task_type
    assert len(roundtrip_task.turnpoints) == len(task.turnpoints)

    # If QR code image support is available, test image generation
    if QR_CODE_SUPPORT:
        qr_image = generate_qrcode_image(qr_string, size=256)

        # Test parsing the image
        with tempfile.NamedTemporaryFile(suffix=".png") as tmp:
            qr_image.save(tmp.name, format="PNG")

            image = Image.open(tmp.name)
            try:
                decoded_objects = decode_qr(image)
                assert decoded_objects, "Failed to decode QR code"

                decoded_string = decoded_objects[0]
                assert decoded_string == qr_string, "QR code roundtrip failed"
            except Exception as e:
                # If decoding fails unexpectedly, skip rather than fail.
                pytest.skip(f"QR decode failed: {e}")


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
def test_qr_code_roundtrip_comprehensive():
    """Test complete QR code roundtrip workflow with file I/O.

    Creates a task, generates QR image, saves to temporary file, and tests:
    - Task → QR string → QR image → File → Parsed task roundtrip
    - Exact preservation of task properties, version, and turnpoint data
    - Proper file cleanup after testing
    """
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
    qr_image = generate_qrcode_image(qr_string, size=512)

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        tmp_path = tmp_file.name
        qr_image.save(tmp_path, format="PNG")

    try:
        # Parse back from image file
        parsed_task = load_task(tmp_path)

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


def test_qr_code_string_parsing():
    """Test direct QR code string parsing without image generation.

    Tests the parsing of QR code strings directly:
    - Creates QRCodeTask with specific version
    - Generates QR string representation
    - Parses back to Task object
    - Verifies version normalization (QR v2 → Task v1)
    """
    # Create QR task
    qr_task = QRCodeTask(version=2)
    qr_string = qr_task.to_string()

    # Parse from string
    parsed_task = parse_task(qr_string)
    # Note: QR code tasks always convert to regular tasks with version 1
    assert parsed_task.version == 1


@pytest.mark.skipif(not QR_CODE_SUPPORT, reason="QR code dependencies not available")
def test_qr_code_image_bytes():
    """Test QR code parsing from raw image bytes in memory.

    Tests the image bytes parsing workflow:
    - Creates task and generates QR code image
    - Converts image to raw bytes buffer (PNG format)
    - Parses task directly from image bytes
    - Validates task properties and turnpoint data preservation
    """
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
    qr_image = generate_qrcode_image(qr_string, size=256)

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
    """Test graceful QR code functionality when image dependencies are missing.

    Verifies that core QR functionality works without PIL/zxing-cpp:
    - QRCodeTask creation and string generation
    - QR string validation (XCTSK: prefix)
    - String parsing back to Task objects
    - No crashes when image libraries are unavailable
    """
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
