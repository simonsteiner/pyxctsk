"""Tests for the QR task: field order, the spec example, waypoints and the shape."""

import json

import pytest

from pyxctsk import (
    TaskType,
    TurnpointType,
)
from pyxctsk.qrcode.models import QRCodeTurnpoint
from pyxctsk.qrcode.task import QRCodeTask
from tests.corpus import reference_tasks

# Use shared QR code test utilities


def test_qr_turnpoint_field_order():
    """Test that the turnpoint fields are in the correct order."""
    # Create a simple turnpoint with different types
    sss_tp = QRCodeTurnpoint(
        lat=1.23456,
        lon=7.89012,
        radius=400,
        name="SSS",
        alt_smoothed=100,
        type=TurnpointType.SSS,
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
        type=TurnpointType.ESS,
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
        task_type=TaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )

    # Test simplified format
    simplified_json = task.as_waypoints().to_json()

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
        task_type=TaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )

    # Test round-trip conversion
    simplified_json = task.as_waypoints().to_json()
    parsed_task = QRCodeTask.from_json(simplified_json)

    assert parsed_task.task_type == TaskType.WAYPOINTS
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
        task_type=TaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )

    # Test URL format
    url_string = task.as_waypoints().to_string()
    assert url_string.startswith("XCTSK:"), "URL should start with XCTSK:"

    # Parse from URL
    parsed_from_url = QRCodeTask.from_string(url_string)
    assert len(parsed_from_url.turnpoints) == 3, "Should have 3 turnpoints from URL"
    assert parsed_from_url.task_type == TaskType.WAYPOINTS


class TestTheShapeIsDecidedOnce:
    """It used to be decided twice, on two different inputs.

    `from_dict` dispatched on the payload's keys and `to_dict` on
    `task_type`, and `_CompetitionTaskType` reads the legacy `"W"` spelling
    that the competition shape's `taskType` sometimes carried — so a payload
    read in one shape wrote itself in the other, and one round trip dropped
    the goal, the earth model, the takeoff window and every turnpoint radius,
    silently and with nothing to notice it by.
    """

    LEGACY = {
        "g": {"d": "22:00:00Z", "t": 2},
        "t": [{"n": "A", "z": "b`dpMgc{YgsB_X"}],
        "taskType": "W",
        "tc": None,
        "to": None,
        "version": 2,
        "e": 1,
    }

    def test_reading_is_idempotent_through_a_write(self):
        """The invariant that was broken: an object equals its own payload."""
        task = QRCodeTask.from_dict(self.LEGACY)
        payload = task.to_dict()

        assert QRCodeTask.from_dict(payload) == task
        assert QRCodeTask.from_dict(payload).to_dict() == payload

    def test_a_legacy_waypoints_spelling_is_reduced_where_it_is_documented(self):
        """`as_waypoints` is where "reduced to what the format can represent" lives."""
        task = QRCodeTask.from_dict(self.LEGACY)

        assert task.task_type is TaskType.WAYPOINTS
        # Not carried in the object either, so nothing can be lost between
        # holding it and writing it — which is what "silently" meant.
        assert task.goal is None and task.earth_model is None

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_every_corpus_payload_still_round_trips_in_its_own_shape(self, reference):
        """The competition shape must be untouched by the legacy branch."""
        qr = reference.task.to_qr_code_task()

        assert QRCodeTask.from_dict(qr.to_dict()).to_dict() == qr.to_dict()
        waypoints = qr.as_waypoints().to_dict()
        assert QRCodeTask.from_dict(waypoints).to_dict() == waypoints


class TestAnUnreadableSectionIsCarriedNotEaten:
    """`_A_DICT_OR_NOTHING` said so; the mechanism could not deliver it.

    `g` and `s` are declared keys, and the passthrough excludes every declared
    key by construction, so a section of the wrong shape was neither read nor
    carried — it was dropped, in the package whose docstring says the library
    hands back anything it cannot interpret.
    """

    def test_a_malformed_section_travels_back_out(self):
        """The docstring's claim, now true."""
        source = {
            "taskType": "CLASSIC",
            "version": 2,
            "t": [],
            "g": "nonsense",
            "s": 123,
            "tc": None,
            "to": None,
        }
        task = QRCodeTask.from_dict(source)

        assert task.goal is None and task.sss is None
        assert task.unknown == {"g": "nonsense", "s": 123}
        assert task.to_dict()["g"] == "nonsense"
        assert task.to_dict()["s"] == 123

    def test_a_malformed_turnpoint_list_travels_back_out(self):
        """The same rule for `_A_LIST_OR_NOTHING`."""
        task = QRCodeTask.from_dict(
            {"taskType": "CLASSIC", "version": 2, "t": "not a list"}
        )

        assert task.turnpoints == []
        assert task.to_dict()["t"] == "not a list"

    def test_a_null_section_is_absent_rather_than_unreadable(self):
        """Null is how the format says "not there"; it is not carried."""
        task = QRCodeTask.from_dict(
            {"taskType": "CLASSIC", "version": 2, "t": [], "g": None, "s": None}
        )

        assert task.unknown == {}
        assert "g" not in task.to_dict() and "s" not in task.to_dict()

    def test_a_row_that_reads_what_it_declares_carries_nothing(self):
        """The default, and why every other row is unaffected."""
        from pyxctsk.model.shape import NUMBER, OPTIONAL, Value

        assert Value("goal", "g", NUMBER, OPTIONAL).unread({"g": 7}) == ()
