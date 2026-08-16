"""Regression tests for the XCTrack Competition Interfaces conformance audit.

These tests encode the findings from the spec-conformance audit
(docs/spec-conformance/2026-08-16-competition-interfaces-audit.md). Each test
names the finding it pins, so a failure points straight at the spec clause it
violates.

The reference corpus in ``tests/data/reference_tasks/`` only covers the fields
tools.xcontest.org exports, which is why these gaps survived a green suite. The
tests here deliberately exercise the optional half of the spec instead.
"""

import json
from pathlib import Path

import pytest

from pyxctsk import Direction, SSSType, Task, parse_task

REFERENCE_QR = Path(__file__).parent / "data" / "reference_tasks" / "qrcode_string"

# A spec-valid CLASSIC task, used as the base for targeted mutations.
BASE_TASK = {
    "taskType": "CLASSIC",
    "version": 1,
    "turnpoints": [
        {
            "type": "SSS",
            "radius": 1000,
            "waypoint": {"name": "A", "lat": 46.5, "lon": 8.1, "altSmoothed": 1000},
        },
        {
            "type": "ESS",
            "radius": 2000,
            "waypoint": {"name": "B", "lat": 46.6, "lon": 8.2, "altSmoothed": 1200},
        },
        {
            "radius": 400,
            "waypoint": {"name": "G", "lat": 46.7, "lon": 8.3, "altSmoothed": 600},
        },
    ],
    "sss": {"type": "RACE", "direction": "EXIT", "timeGates": ["12:00:00Z"]},
    "goal": {"type": "CYLINDER", "deadline": "18:00:00Z"},
}


def task_json(**overrides) -> str:
    """Return BASE_TASK as JSON with top-level keys replaced by ``overrides``."""
    data = json.loads(json.dumps(BASE_TASK))
    data.update(overrides)
    return json.dumps(data)


class TestObsoleteSSSDirection:
    """Finding 4 — ``sss.direction`` is obsolete and must be ignored on read.

    Spec: "this has been obsolete. Devices must ignore this field when reading a
    task and should produce some value when exporting a task in order to stay
    compatible with older devices."
    """

    def test_task_without_direction_parses(self):
        """A task omitting the obsolete field must parse, not raise KeyError."""
        sss = {"type": "RACE", "timeGates": ["12:00:00Z"]}
        task = Task.from_json(task_json(sss=sss))

        assert task.sss is not None
        assert task.sss.type == SSSType.RACE
        assert task.sss.time_gates[0].hour == 12

    def test_omitted_direction_still_exported(self):
        """Export must carry *some* direction so older devices keep working."""
        sss = {"type": "RACE", "timeGates": ["12:00:00Z"]}
        task = Task.from_json(task_json(sss=sss))

        exported = json.loads(task.to_json())["sss"]
        assert exported["direction"] == Direction.EXIT.value

    def test_explicit_direction_is_preserved(self):
        """Ignoring the field on read must not mean discarding it."""
        sss = {"type": "RACE", "direction": "ENTER", "timeGates": ["12:00:00Z"]}
        task = Task.from_json(task_json(sss=sss))

        assert task.sss is not None
        assert task.sss.direction == Direction.ENTER
        assert json.loads(task.to_json())["sss"]["direction"] == "ENTER"

    @pytest.mark.parametrize("empty", [None, ""])
    def test_null_or_empty_direction_falls_back(self, empty):
        """A present-but-empty value is as absent as a missing key."""
        sss = {"type": "RACE", "direction": empty, "timeGates": ["12:00:00Z"]}
        task = Task.from_json(task_json(sss=sss))

        assert task.sss is not None
        assert task.sss.direction == Direction.EXIT

    def test_both_readers_agree_on_the_fallback(self):
        """The QR reader and the full-JSON reader must not diverge here."""
        from pyxctsk.qrcode_enums import QRCodeDirection
        from pyxctsk.qrcode_models import QRCodeSSS
        from pyxctsk.task import OBSOLETE_DIRECTION_DEFAULT

        qr_fallback = QRCodeSSS.from_dict({"t": 1, "g": ["12:00:00Z"]}).direction

        assert qr_fallback == QRCodeDirection.EXIT
        assert OBSOLETE_DIRECTION_DEFAULT == Direction.EXIT
        assert qr_fallback.name == OBSOLETE_DIRECTION_DEFAULT.name


class TestGoalSerializedShape:
    """Findings 1 and 6 — the goal object's keys are type/deadline/finishAltitude.

    Spec: ``finishAltitude`` is "number, optional, meters AGL - elevated goal
    altitude". ``lineLength`` is not in the spec at all.
    """

    def test_finish_altitude_survives_json_roundtrip(self):
        """A scored competition parameter must not be dropped."""
        goal = {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": 50}
        task = Task.from_json(task_json(goal=goal))

        assert task.goal is not None
        assert task.goal.finish_altitude == 50
        assert json.loads(task.to_json())["goal"]["finishAltitude"] == 50

    def test_finish_altitude_survives_qr_roundtrip(self):
        """The QR format carries it as "fa"."""
        goal = {"type": "LINE", "deadline": "18:00:00Z", "finishAltitude": 50}
        task = Task.from_json(task_json(goal=goal))

        qr = task.to_qr_code_task()
        assert json.loads(qr.to_json())["g"]["fa"] == 50
        assert qr.to_task().goal.finish_altitude == 50

    def test_finish_altitude_omitted_when_absent(self):
        """An optional field must stay absent, not become null or zero."""
        goal = {"type": "CYLINDER", "deadline": "18:00:00Z"}
        task = Task.from_json(task_json(goal=goal))

        assert "finishAltitude" not in json.loads(task.to_json())["goal"]
        assert "fa" not in json.loads(task.to_qr_code_task().to_json())["g"]

    def test_goal_keys_are_spec_keys_only(self):
        """The non-spec ``lineLength`` key must not be written."""
        goal = {"type": "LINE", "deadline": "18:00:00Z", "finishAltitude": 50}
        task = Task.from_json(task_json(goal=goal))

        assert set(json.loads(task.to_json())["goal"]) <= {
            "type",
            "deadline",
            "finishAltitude",
        }

    def test_line_length_still_derived_for_geometry(self):
        """Dropping it from output must not drop it from the model."""
        goal = {"type": "LINE", "deadline": "18:00:00Z"}
        task = Task.from_json(task_json(goal=goal))

        # Twice the last turnpoint's radius, which the spec says is half the line.
        assert task.goal is not None
        assert task.goal.line_length == task.turnpoints[-1].radius * 2

    def test_legacy_line_length_is_still_read(self):
        """Files written by older pyxctsk versions must still parse."""
        goal = {"type": "CYLINDER", "deadline": "18:00:00Z", "lineLength": "800.0"}
        task = Task.from_json(task_json(goal=goal))

        assert task.goal is not None
        assert task.goal.line_length == 800.0


class TestNumericEdgeCases:
    """Findings 5 and 11 — numeric handling must match the reference.

    Spec: ``radius`` and ``altSmoothed`` are typed "number", not integer. The
    polyline reference implementation rounds with Java's ``Math.round``.
    """

    @pytest.mark.parametrize("radius", [400.0, 399.5, 400])
    def test_non_integer_radius_encodes(self, radius):
        """A float radius is valid JSON and must not raise TypeError."""
        turnpoints = json.loads(json.dumps(BASE_TASK["turnpoints"]))
        turnpoints[0]["radius"] = radius
        task = Task.from_json(task_json(turnpoints=turnpoints))

        assert task.turnpoints[0].radius == 400
        assert task.to_qr_code_task().to_string().startswith("XCTSK:")

    def test_non_integer_altitude_encodes(self):
        """Same for altSmoothed, which the spec also types as a number."""
        turnpoints = json.loads(json.dumps(BASE_TASK["turnpoints"]))
        turnpoints[0]["waypoint"]["altSmoothed"] = 1000.6
        task = Task.from_json(task_json(turnpoints=turnpoints))

        assert task.turnpoints[0].waypoint.alt_smoothed == 1001
        assert task.to_qr_code_task().to_string().startswith("XCTSK:")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [(612344.5, 612345), (612345.5, 612346), (-2.5, -2), (2.5, 3), (2.4, 2)],
    )
    def test_ties_round_like_java_math_round(self, value, expected):
        """floor(x + 0.5), not Python's banker's rounding."""
        from pyxctsk.qrcode_encoding import _round_half_up

        assert _round_half_up(value) == expected


class TestManufacturerExtensions:
    """Finding 2 — manufacturer extensions must survive verbatim.

    Spec: the root ``extensions`` list holds objects each with an obligatory
    ``id``; ``turnpoints[i].extensions`` must be "in the same order as the
    extensions field on the root object", with ``id`` not repeated. The QR
    format carries both as ``x``.
    """

    ROOT = [{"id": "XCT1", "v": "1"}, {"id": "ACME2", "k": "z"}]
    PER_TURNPOINT = [{"w": "3"}, {"k": "y"}]

    def _task_with_extensions(self) -> Task:
        turnpoints = json.loads(json.dumps(BASE_TASK["turnpoints"]))
        turnpoints[0]["extensions"] = self.PER_TURNPOINT
        return Task.from_json(
            task_json(turnpoints=turnpoints, extensions=self.ROOT),
        )

    def test_root_extensions_survive_json_roundtrip(self):
        """Opaque manufacturer data must be preserved, not interpreted."""
        task = self._task_with_extensions()

        assert task.extensions == self.ROOT
        assert json.loads(task.to_json())["extensions"] == self.ROOT

    def test_turnpoint_extensions_survive_json_roundtrip(self):
        """Per-turnpoint extensions belong to their turnpoint."""
        task = self._task_with_extensions()

        assert task.turnpoints[0].extensions == self.PER_TURNPOINT
        emitted = json.loads(task.to_json())["turnpoints"]
        assert emitted[0]["extensions"] == self.PER_TURNPOINT
        assert "extensions" not in emitted[1]

    def test_extensions_survive_qr_roundtrip(self):
        """Both levels travel through the QR format's "x" key."""
        qr = self._task_with_extensions().to_qr_code_task()

        as_dict = json.loads(qr.to_json())
        assert as_dict["x"] == self.ROOT
        assert as_dict["t"][0]["x"] == self.PER_TURNPOINT

        back = qr.to_task()
        assert back.extensions == self.ROOT
        assert back.turnpoints[0].extensions == self.PER_TURNPOINT

    def test_order_is_preserved(self):
        """The spec pins turnpoint extensions to the root list's order."""
        task = self._task_with_extensions()

        assert [e["id"] for e in json.loads(task.to_json())["extensions"]] == [
            "XCT1",
            "ACME2",
        ]

    def test_absent_extensions_emit_no_key(self):
        """An optional list must stay absent rather than become []."""
        task = Task.from_json(task_json())

        emitted = json.loads(task.to_json())
        assert "extensions" not in emitted
        assert all("extensions" not in tp for tp in emitted["turnpoints"])
        assert "x" not in json.loads(task.to_qr_code_task().to_json())

    def test_turnpoint_x_is_not_read_as_a_coordinate(self):
        """The ``x`` key means extensions, not longitude as it once did."""
        from pyxctsk.qrcode_encoding import encode_competition_turnpoint
        from pyxctsk.qrcode_models import QRCodeTurnpoint

        z = encode_competition_turnpoint(8.1, 46.5, 1234, 400)
        turnpoint = QRCodeTurnpoint.from_dict({"n": "X", "z": z, "x": [{"k": "v"}]})

        assert turnpoint.lon == pytest.approx(8.1)
        assert turnpoint.lat == pytest.approx(46.5)
        assert turnpoint.extensions == [{"k": "v"}]


class TestWaypointsTaskEncoding:
    """Findings 7 and 8 — the XC/Waypoints ``z`` carries three numbers.

    Spec: the XC/Waypoints task is a "simple route from waypoints without
    cylinders", and its ``z`` is "polyline encoded coordinates with altitude"
    — longitude, latitude, altitude. No radius.
    """

    def test_altitudes_survive_reading(self):
        """A three-number z must yield its altitude, not zero."""
        task = parse_task(str(REFERENCE_QR / "task_noha_route.txt"))

        altitudes = [tp.waypoint.alt_smoothed for tp in task.turnpoints[:4]]
        assert altitudes == [1149, 175, 606, 1450]

    def test_no_cylinder_is_invented(self):
        """A route "without cylinders" must not acquire a radius on read."""
        task = parse_task(str(REFERENCE_QR / "task_noha_route.txt"))

        assert all(tp.radius == 0 for tp in task.turnpoints)

    @pytest.mark.parametrize(
        "name", ["task_noha_route.txt", "task_dami_route.txt", "task_dami.txt"]
    )
    def test_roundtrip_is_byte_identical_to_xctrack(self, name):
        """Re-encoding an XCTrack waypoints QR must reproduce it exactly.

        These fixtures were decoded from QR codes generated by
        tools.xcontest.org, so they are ground truth rather than our own output.
        """
        expected = (REFERENCE_QR / name).read_text().strip()
        task = parse_task(str(REFERENCE_QR / name))

        assert task.to_qr_code_task().to_waypoints_string() == expected

    def test_competition_z_keeps_its_radius(self):
        """The four-number competition encoding must be left alone."""
        expected = (REFERENCE_QR / "task_bevo.txt").read_text().strip()
        task = parse_task(str(REFERENCE_QR / "task_bevo.txt"))

        assert task.to_qr_code_task().to_string() == expected
        assert task.turnpoints[0].radius == 400

    def test_z_length_selects_the_format(self):
        """Three numbers means waypoints, four means competition."""
        from pyxctsk.qrcode_encoding import (
            encode_competition_turnpoint,
            encode_waypoint_turnpoint,
        )
        from pyxctsk.qrcode_models import QRCodeTurnpoint

        waypoint_z = encode_waypoint_turnpoint(8.1, 46.5, 1234)
        competition_z = encode_competition_turnpoint(8.1, 46.5, 1234, 400)

        waypoint = QRCodeTurnpoint.from_dict({"n": "X", "z": waypoint_z})
        competition = QRCodeTurnpoint.from_dict({"n": "X", "z": competition_z})

        assert (waypoint.alt_smoothed, waypoint.radius) == (1234, 0)
        assert (competition.alt_smoothed, competition.radius) == (1234, 400)
        assert competition_z.startswith(waypoint_z)
