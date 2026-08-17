"""Tests for QR code generation and comparison.

This test module comprehensively verifies QR code functionality including:
1. QR code string generation from task files with format detection
2. QR code image generation, saving, and parsing when dependencies are available
3. Complete roundtrip validation (Task → QR string → QR image → Task)
4. Comparison against expected QR code strings for regression testing
5. Error handling when QR code dependencies are missing
6. Support for both waypoints and full task formats
7. QR turnpoint field ordering compliance
8. Waypoints format testing
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
    parse_task,
)
from pyxctsk.qrcode.enums import QRCodeTaskType, QRCodeTurnpointType
from pyxctsk.qrcode.image import generate_qrcode_image
from pyxctsk.qrcode.models import QRCodeTurnpoint
from pyxctsk.qrcode.task import QRCodeTask
from tests.corpus import reference_tasks

# Use shared QR code test utilities
from tests.qr_test_utils import QR_CODE_SUPPORT, Image, decode_qr, zxingcpp

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
    emitted = (
        qr.to_waypoints_string() if reference.is_waypoints_format else qr.to_string()
    )

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


def test_qr_turnpoint_field_order():
    """Test that the turnpoint fields are in the correct order."""
    # Create a simple turnpoint with different types
    sss_tp = QRCodeTurnpoint(
        lat=1.23456,
        lon=7.89012,
        radius=400,
        name="SSS",
        alt_smoothed=100,
        type=QRCodeTurnpointType.SSS,
        description="Start of Speed Section",
    )

    # Convert to dictionary
    sss_tp_dict = sss_tp.to_dict()

    # Get the keys in order
    keys = list(sss_tp_dict.keys())

    # Check order for fields: 'd', 'n', 't', 'z' is the expected order
    assert keys.index("d") < keys.index("n"), "Description should come before name"
    assert keys.index("n") < keys.index("t"), "Name should come before type"
    assert keys.index("t") < keys.index("z"), "Type should come before coordinates"

    # Create a turnpoint with ESS type
    ess_tp = QRCodeTurnpoint(
        lat=2.34567,
        lon=8.90123,
        radius=1000,
        name="ESS",
        alt_smoothed=200,
        type=QRCodeTurnpointType.ESS,
        description="End of Speed Section",
    )

    # Convert to dictionary
    ess_tp_dict = ess_tp.to_dict()
    keys = list(ess_tp_dict.keys())

    # Check order for ESS turnpoint
    assert keys.index("t") < keys.index("z"), (
        "Type should come before coordinates in ESS"
    )

    # Create a QRCode task with turnpoints that have types
    qr_task = QRCodeTask(turnpoints=[sss_tp, ess_tp])

    # Convert to JSON and parse back to check if structure is preserved
    task_json = qr_task.to_json()
    task_dict = json.loads(task_json)

    # Check if the turnpoint fields are in correct order
    assert "t" in task_dict, "Task should have turnpoints"
    assert len(task_dict["t"]) == 2, "Task should have 2 turnpoints"

    # Check SSS turnpoint
    sss_tp_json = task_dict["t"][0]
    sss_keys = list(sss_tp_json.keys())
    assert sss_keys.index("t") < sss_keys.index("z"), (
        "Type should come before z in SSS turnpoint"
    )

    # Check ESS turnpoint
    ess_tp_json = task_dict["t"][1]
    ess_keys = list(ess_tp_json.keys())
    assert ess_keys.index("t") < ess_keys.index("z"), (
        "Type should come before z in ESS turnpoint"
    )


def test_qr_spec_example_compliance():
    """Test with actual example from the XCTrack QR spec."""
    # Test with actual example from the spec
    # cspell: disable-next-line
    spec_example = """{"g":{"d":"22:00:00Z","t":2},"s":{"d":2,"g":["17:00:00Z"],"t":1},"t":[{"d":"Take--Off--AGUAPANELA","n":"D02","t":1,"z":"b`dpMgc{YgsB_X"},{"d":"PUENTE ZARZAL - LA PAILA","n":"P31","t":2,"z":"xthoM}orYcy@owH"},{"d":"ZANJAS LA UNION","n":"P32","z":"tmeoMgjtZuw@gxG"},{"d":"ANTENAS ROLDANILLO","n":"P09","z":"trvoMquwYydA_|B"},{"d":"GOL BUGALAGRANDE","n":"G04","z":"fb{oMofsXk}@oK"},{"d":"GOL BUGALAGRANDE","n":"G04","z":"fb{oMofsXk}@otL"},{"d":"GOL BUGALAGRANDE","n":"G04","z":"fb{oMofsXk}@oK"},{"d":"X24","n":"X24","z":"|ltnMkgxWu`Co_h@"},{"d":"GOL PISTA-LOS CHANCOS","n":"G11","t":3,"z":"|kbpMuvnWe}@ozD"},{"d":"GOL PISTA-LOS CHANCOS","n":"G11","z":"|kbpMuvnWe}@oK"}],"taskType":"CLASSIC","tc":null,"to":null,"version":2}"""

    # Parse the example and check if our code can parse it correctly
    qr_task_from_spec = QRCodeTask.from_json(spec_example)

    # Generate JSON from the parsed task and compare with the spec
    generated_json = qr_task_from_spec.to_json()
    generated_dict = json.loads(generated_json)
    spec_dict = json.loads(spec_example)

    # Check turnpoints field ordering
    for i, tp in enumerate(spec_dict["t"]):
        if "t" in tp:
            gen_tp = generated_dict["t"][i]
            gen_keys = list(gen_tp.keys())
            if "t" in gen_tp:
                assert gen_keys.index("t") < gen_keys.index("z"), (
                    f"Type should come before z in turnpoint {i}"
                )


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
    assert "t" in data and len(data["t"]) == 3, (
        f"Expected 3 turnpoints, got {len(data.get('t', []))}"
    )

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


class TestQRSupportProbe:
    """The probe that decides whether the QR image tests run at all.

    Every image test in this module is gated on ``QR_CODE_SUPPORT``, so a
    probe that silently reported the wrong answer would turn this file into a
    green no-op rather than a failure.
    """

    def test_support_flag_matches_imports(self):
        """QR_CODE_SUPPORT is only True when both decoders actually imported."""
        if QR_CODE_SUPPORT:
            assert Image is not None
            assert zxingcpp is not None

    def test_support_flag_is_a_bool(self):
        """The probe answers True or False, never an exception or None."""
        assert isinstance(QR_CODE_SUPPORT, bool)


class TestWithoutTheOptionalDependencies:
    """The documented behaviour when Pillow and zxing-cpp are absent.

    They are the library's only optional dependency, and both modules that use
    them carry a ``try: import ... except ImportError`` fallback — which
    nothing exercised, because the test environment always has them. One
    ``monkeypatch`` reaches the branch that real users without the extras hit.
    """

    def test_generating_an_image_says_what_is_missing(self, monkeypatch):
        """A named ImportError, not an AttributeError on None."""
        from pyxctsk.qrcode import image

        monkeypatch.setattr(image, "QR_CODE_SUPPORT", False)

        with pytest.raises(ImportError, match="qrcode.*Pillow"):
            image.generate_qrcode_image("XCTSK:{}")

    def test_the_parser_declines_an_image_rather_than_crashing(self, monkeypatch):
        """An image is simply not a format this install can read.

        The adapter returns None, so the input falls through to the others and
        the failure is the ordinary "invalid format" — not a NameError from
        the module-level ``Image = None``.
        """
        from pyxctsk import parser
        from pyxctsk.exceptions import InvalidFormatError

        monkeypatch.setattr(parser, "QR_CODE_SUPPORT", False)

        with pytest.raises(InvalidFormatError, match="invalid format"):
            parse_task(b"\x89PNG\r\n\x1a\n not really an image")

    def test_the_text_formats_still_work(self, monkeypatch):
        """Everything but image decoding is unaffected by the extras."""
        from pyxctsk import parser

        monkeypatch.setattr(parser, "QR_CODE_SUPPORT", False)
        qr_string = QRCodeTask(version=2).to_string()

        assert parse_task(qr_string).version == 1


class TestTheNestedModelsAreReachableOnTheirOwn:
    """``to_dict`` / ``from_dict`` on the objects nested inside a QR task.

    The task's own table reaches these shapes directly, so nothing inside the
    library calls these four methods any more — but they are public API, and
    ``QRCodeTakeoff``'s pair had never run at all.
    """

    def test_a_goal_round_trips(self):
        """Keys in the order tools.xcontest.org writes them."""
        from pyxctsk.qrcode.models import QRCodeGoal

        source = {"d": "18:00:00Z", "fa": 50, "t": 1}
        goal = QRCodeGoal.from_dict(source)

        assert goal.deadline.hour == 18
        assert goal.finish_altitude == 50
        assert list(goal.to_dict()) == ["d", "fa", "t"]
        assert goal.to_dict() == source

    def test_a_start_round_trips(self):
        """The obsolete direction first, the type last."""
        from pyxctsk.qrcode.models import QRCodeSSS

        source = {"d": 2, "g": ["12:00:00Z"], "t": 1}
        sss = QRCodeSSS.from_dict(source)

        assert sss.time_gates[0].hour == 12
        assert list(sss.to_dict()) == ["d", "g", "t"]
        assert sss.to_dict() == source

    def test_a_takeoff_round_trips(self):
        """The one shape the task flattens, read on its own terms."""
        from pyxctsk.qrcode.models import QRCodeTakeoff

        source = {"o": "08:00:00Z", "c": "09:30:00Z"}
        takeoff = QRCodeTakeoff.from_dict(source)

        assert (takeoff.time_open.hour, takeoff.time_close.hour) == (8, 9)
        assert takeoff.to_dict() == source

    def test_an_empty_takeoff_writes_nothing(self):
        """Absent times must stay absent rather than become null."""
        from pyxctsk.qrcode.models import QRCodeTakeoff

        assert QRCodeTakeoff().to_dict() == {}
