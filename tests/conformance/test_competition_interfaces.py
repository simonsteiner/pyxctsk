"""XCTrack Competition Interfaces conformance regressions.

Derived from docs/arch-review/2026-08-16-competition-interfaces-audit.md.
Each test keeps the finding and specification provenance that it pins.
"""

import json

import pytest

from pyxctsk import (
    Direction,
    SSSType,
    Task,
    parse_task,
)
from pyxctsk.distance.goal_line import (
    GoalLine,
    goal_line_length_from_turnpoints,
)
from tests.conformance._support import BASE_TASK, task_json
from tests.corpus import reference_task

# Polyline-encoded "z" literals below are opaque tokens, not words.
# cspell:ignore Fligr


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
        from pyxctsk.model.task import OBSOLETE_DIRECTION_DEFAULT
        from pyxctsk.qrcode.enums import QRCodeDirection
        from pyxctsk.qrcode.models import QRCodeSSS

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
        converted = qr.to_task()
        assert converted.goal is not None
        assert converted.goal.finish_altitude == 50

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
        """Dropping it from the model must not drop the geometry it fed."""
        goal = {"type": "LINE", "deadline": "18:00:00Z"}
        task = Task.from_json(task_json(goal=goal))

        # Twice the last turnpoint's radius, which the spec says is half the line.
        assert goal_line_length_from_turnpoints(task.turnpoints) == (
            task.turnpoints[-1].radius * 2
        )
        line = GoalLine.from_task(task)
        assert line is not None
        assert line.length == task.turnpoints[-1].radius * 2

    def test_legacy_line_length_is_ignored(self):
        """Files written by older pyxctsk versions must still parse.

        The key carried nothing the turnpoints did not already say, so it is
        read past rather than stored — and never echoed back on output.
        """
        goal = {"type": "LINE", "deadline": "18:00:00Z", "lineLength": "800.0"}
        task = Task.from_json(task_json(goal=goal))

        assert task.goal is not None
        assert "lineLength" not in json.loads(task.to_json())["goal"]
        # The geometry comes from the radius, not from the discarded key.
        line = GoalLine.from_task(task)
        assert line is not None
        assert line.length == task.turnpoints[-1].radius * 2


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
        from pyxctsk.model.rounding import round_half_up

        assert round_half_up(value) == expected


class TestTaskTypeValue:
    """Finding 10 — ``taskType`` in the competition format is only "CLASSIC".

    Spec: the v2 competition format defines ``"taskType": "CLASSIC"``. An
    XC/Waypoints task is signalled by ``"T": "W"`` in the simplified format,
    so "WAYPOINTS" is not a value either format defines.
    """

    @pytest.mark.parametrize("stem", ["task_noha_route", "task_dami_route"])
    def test_waypoints_task_serializes_as_the_simplified_format(self, stem):
        """to_string() on a waypoints task must produce XCTrack's own form."""
        reference = reference_task(stem)
        task = parse_task(reference.qr_string)

        assert task.to_qr_code_task().to_string() == reference.qr_string

    def test_waypoints_value_is_never_emitted(self):
        """The non-spec "WAYPOINTS" value must not appear anywhere."""
        task = parse_task(reference_task("task_noha_route").qr_string)
        emitted = json.loads(task.to_qr_code_task().to_json())

        assert "taskType" not in emitted
        assert emitted["T"] == "W"

    def test_classic_still_says_classic(self):
        """The competition format is untouched."""
        task = parse_task(reference_task("task_bevo").qr_string)

        assert json.loads(task.to_qr_code_task().to_json())["taskType"] == "CLASSIC"

    def test_format_is_identified_by_its_task_type_key_alone(self):
        """A waypoints payload missing ``V`` is still a waypoints payload.

        The discriminator used to require both ``T`` and ``V``, so a payload
        with only ``T`` fell through to the competition reader: the task type
        came out unset and ``T`` was swallowed as an unknown key, which then
        re-serialized in the wrong shape.
        """
        from pyxctsk.qrcode.enums import QRCodeTaskType
        from pyxctsk.qrcode.task import QRCodeTask

        qr = QRCodeTask.from_dict({"T": "W", "t": [{"n": "A", "z": "|dz~FligrB?"}]})

        assert qr.task_type == QRCodeTaskType.WAYPOINTS
        assert qr.unknown == {}
        assert json.loads(qr.to_json()) == {
            "T": "W",
            "V": 2,
            "t": [{"n": "A", "z": "|dz~FligrB?"}],
        }

    def test_serialized_shape_follows_task_type_alone(self):
        """There is one source of truth for the shape, not a flag beside it."""
        qr = parse_task(reference_task("task_bevo").qr_string).to_qr_code_task()

        assert json.loads(qr.to_json())["taskType"] == "CLASSIC"
        assert json.loads(qr.as_waypoints().to_json())["T"] == "W"

    def test_as_waypoints_keeps_only_what_the_format_can_represent(self):
        """Reducing to waypoints must match what reading the payload back gives.

        ``as_waypoints()`` used to flip the task type and nothing else, so the
        in-memory copy kept radii, turnpoint types and the timing sections that
        the simplified payload has nowhere to store. Serialized output was
        right either way, but ``.as_waypoints().to_task()`` and
        ``parse_task(.to_waypoints_string())`` described different tasks.
        """
        qr = parse_task(reference_task("task_bevo").qr_string).to_qr_code_task()

        direct = qr.as_waypoints().to_task()
        round_tripped = parse_task(qr.to_waypoints_string())

        assert direct.to_json() == round_tripped.to_json()
        assert all(tp.radius == 0 for tp in direct.turnpoints)
        assert all(tp.type is None for tp in direct.turnpoints)
        assert direct.sss is None

    def test_both_waypoints_entry_points_agree(self):
        """from_task_waypoints() and to_waypoints_string() are one definition."""
        from pyxctsk.qrcode.task import QRCodeTask

        task = parse_task(reference_task("task_bevo").qr_string)

        assert (
            QRCodeTask.from_task_waypoints(task).to_string()
            == task.to_qr_code_task().to_waypoints_string()
        )

    def test_as_waypoints_does_not_mutate_the_original(self):
        """Downgrading to waypoints returns a copy, so the source is reusable."""
        qr = parse_task(reference_task("task_bevo").qr_string).to_qr_code_task()

        before = qr.to_json()
        qr.to_waypoints_json()

        assert qr.to_json() == before


class TestTurnpointCoordinatesAreNeverInvented:
    """A malformed ``z`` is an error, not a turnpoint at 0°N 0°E.

    Both QR formats require ``z``. Defaulting the coordinates to zero produced
    a valid-looking turnpoint in the Gulf of Guinea and reported the task as
    read successfully — a silent fallback papering over malformed input.
    """

    def _from_dict(self, data):
        from pyxctsk.qrcode.models import QRCodeTurnpoint

        return QRCodeTurnpoint.from_dict(data)

    def test_missing_z_raises(self):
        """No coordinates at all is malformed input."""
        with pytest.raises(KeyError):
            self._from_dict({"n": "TP"})

    @pytest.mark.parametrize("count", [0, 1, 2, 5])
    def test_wrong_number_count_raises(self, count):
        """Only the 3- and 4-number forms are defined."""
        from pyxctsk.qrcode.encoding import encode_num

        z = "".join(encode_num(n) for n in range(count))
        with pytest.raises(ValueError, match="3 or 4 numbers"):
            self._from_dict({"n": "TP", "z": z})

    def test_the_error_reaches_the_parser_as_a_format_error(self):
        """Raising here must surface as a descriptive parse failure."""
        from pyxctsk.exceptions import InvalidFormatError

        with pytest.raises(InvalidFormatError, match="could not be parsed"):
            parse_task('XCTSK:{"taskType":"CLASSIC","version":2,"t":[{"n":"TP"}]}')
