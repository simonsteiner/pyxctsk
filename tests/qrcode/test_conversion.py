"""Tests for the Task <-> QRCodeTask crossing and the QR wire integers.

The conversion itself is exercised end-to-end by the reference round-trips in
``test_codec.py``. What those cannot catch is an enum member with no wire
integer, so each table's totality is pinned here.
"""

from typing import Any

import pytest

from pyxctsk.model.shape import wire_int_codec
from pyxctsk.model.task import (
    Direction,
    EarthModel,
    GoalType,
    SSSType,
    TaskType,
    TurnpointType,
)
from pyxctsk.qrcode.models import (
    DIRECTION_WIRE,
    GOAL_TYPE_WIRE,
    SSS_TYPE_WIRE,
    TURNPOINT_TYPE_WIRE,
    QRCodeTurnpoint,
)
from pyxctsk.qrcode.task import EARTH_MODEL_WIRE, QRCodeTask
from tests.corpus import reference_task


@pytest.mark.parametrize(
    "enum, table",
    [
        (EarthModel, EARTH_MODEL_WIRE),
        (Direction, DIRECTION_WIRE),
        (SSSType, SSS_TYPE_WIRE),
        (GoalType, GOAL_TYPE_WIRE),
    ],
    ids=["earth model", "direction", "SSS type", "goal type"],
)
def test_every_value_has_a_wire_integer(enum, table):
    """A new enum member must not silently fall through to a default.

    This is the totality the twelve translation tables used to be tested for,
    now asked of the one table each field has.
    """
    assert set(enum) == set(table)


def test_every_turnpoint_role_has_a_wire_integer():
    """``TurnpointType.NONE`` is the one without: the format writes no ``t``.

    A new role used to become ``NONE`` going out and ``None`` coming back,
    silently. Now it has no wire integer, which this test turns into a failure.
    """
    assert set(TurnpointType) - set(TURNPOINT_TYPE_WIRE) == {TurnpointType.NONE}


@pytest.mark.parametrize(
    "table",
    [
        EARTH_MODEL_WIRE,
        DIRECTION_WIRE,
        SSS_TYPE_WIRE,
        GOAL_TYPE_WIRE,
        TURNPOINT_TYPE_WIRE,
    ],
)
def test_every_wire_integer_reads_back(table):
    """Each table is one-to-one, so reading is the inverse of writing."""
    codec = wire_int_codec(table)

    assert all(codec.from_wire(codec.to_wire(value)) is value for value in table)


def test_an_unknown_wire_integer_is_refused():
    """A value outside the table is an error, not a default."""
    with pytest.raises(ValueError, match="99 is not one of"):
        wire_int_codec(GOAL_TYPE_WIRE).from_wire(99)


def test_a_json_boolean_is_not_the_integer_one():
    """``True == 1`` in Python; ``true`` on the wire is not a goal type."""
    with pytest.raises(ValueError):
        wire_int_codec(GOAL_TYPE_WIRE).from_wire(True)


def test_a_zero_turnpoint_type_is_an_ordinary_turnpoint():
    """The format's "no type" reads as no type, as ``"type": ""`` does."""
    from pyxctsk.qrcode.encoding import encode_competition_turnpoint

    z = encode_competition_turnpoint(8.0, 46.5, 1000, 400)
    tp = QRCodeTurnpoint.from_dict({"n": "A", "z": z, "t": 0})

    assert tp.type is None


def test_both_formats_hold_the_same_enums():
    """Crossing the seam copies values; there is nothing left to translate."""
    task = reference_task("task_bevo").task
    qr = task.to_qr_code_task()

    assert qr.task_type is task.task_type is TaskType.CLASSIC
    assert [tp.type for tp in qr.turnpoints] == [tp.type for tp in task.turnpoints]


class TestValidatingWhatArrived:
    """A QR payload can be checked without being converted first.

    Validation used to require a ``Task``, so QR input had to be converted —
    which invents a ``version``, a ``CLASSIC`` task type and a CYLINDER goal
    the payload never carried. "Check what actually arrived" was not
    expressible for the format most tasks are shared in.
    """

    def _payload(self, *types):
        """A competition QR task whose turnpoints carry these ``t`` values."""
        from pyxctsk.qrcode.encoding import encode_competition_turnpoint

        turnpoints = []
        for i, tp_type in enumerate(types):
            tp = {
                "n": f"TP{i}",
                "z": encode_competition_turnpoint(8.0 + i, 46.5, 1000, 400),
            }
            if tp_type is not None:
                tp["t"] = tp_type
            turnpoints.append(tp)
        return QRCodeTask.from_dict(
            {
                "taskType": "CLASSIC",
                "version": 2,
                "t": turnpoints,
                "tc": None,
                "to": None,
            }
        )

    def test_a_valid_payload_reports_nothing(self):
        """TAKEOFF first, then SSS, then ESS."""
        assert self._payload(1, 2, 3, None).validate() == []

    def test_the_rules_fire_on_the_payloads_own_turnpoints(self):
        """Two starts is two starts, in either format."""
        issues = self._payload(2, 2, 3).validate()

        assert [str(i) for i in issues] == ["SSS must appear exactly once, found 2"]

    def test_takeoff_must_still_be_first(self):
        """The rule set is the same one; only the adapter differs."""
        issues = self._payload(2, 1, 3).validate()

        assert any("TAKEOFF is only allowed on the first" in str(i) for i in issues)

    def test_a_waypoints_payload_is_exempt(self):
        """A route without cylinders has no speed section to constrain."""
        waypoints = QRCodeTask.from_string(reference_task("task_dami_route").qr_string)

        assert waypoints.task_type is TaskType.WAYPOINTS
        assert waypoints.validate() == []

    def test_nothing_is_invented_to_check_it(self):
        """Validating must not depend on what conversion would supply.

        The payload declares no version 1 and no CLASSIC task type; the
        converted task has both, which is why validation reads the payload.

        The goal used to be a third invention here and no longer is: neither
        this module nor ``Task`` fills one in, so a payload with no ``g``
        converts to a task with no goal. The default is
        ``Task.effective_goal``, derived where it is needed rather than stored
        where it would be written back out.
        """
        payload = self._payload(1, 2, 3, None)

        assert payload.goal is None
        assert payload.version == 2
        assert payload.validate() == []

        converted = payload.to_task()
        # Still invented, because the full format requires them:
        assert converted.version == 1
        assert converted.task_type is TaskType.CLASSIC
        # No longer invented:
        assert converted.goal is None
        assert converted.effective_goal is not None
        assert converted.effective_goal.type is GoalType.CYLINDER

    def test_the_new_rules_reach_the_qr_format_too(self):
        """Radius, version and extensions are all things a QR payload carries.

        The rules are stated over a ``TaskStructure``, so a format that can
        present one gets every rule rather than the subset someone remembered
        to wire up.
        """
        from pyxctsk.model.validation import ValidationRule

        payload = self._payload(1, 2, 3)
        payload.version = 99
        payload.turnpoints[0].radius = -1
        payload.turnpoints[0].extensions = [{"id": "ACME"}]

        rules = {issue.rule for issue in payload.validate()}

        assert rules == {
            ValidationRule.UNKNOWN_VERSION,
            ValidationRule.NEGATIVE_RADIUS,
            ValidationRule.EXTENSION_WITHOUT_ROOT,
            ValidationRule.EXTENSION_REPEATS_ID,
        }

    def test_the_qr_format_expects_its_own_version(self):
        """Version 2 here, version 1 in the full format — one rule, two facts."""
        payload = self._payload(1, 2, 3)

        assert payload.version == 2
        assert payload.validate() == []
        # The same task in the other format declares 1, and is equally valid.
        assert payload.to_task().version == 1
        assert payload.to_task().validate() == []

    def test_the_full_formats_version_is_declared_once(self):
        """The converter stamps the number the validator checks against.

        There used to be three independent literal ``1``s: this module's
        ``TASK_VERSION`` (stamped onto every converted task),
        ``validation.FULL_FORMAT_VERSION`` (what ``Task.validate()`` checks),
        and ``pyxctsk.VERSION``. Editing one of the three would have made the
        library write a version its own validator rejects. ``VERSION`` was an
        alias by then, and is gone: one number, one name.
        """
        import pyxctsk
        from pyxctsk.model.validation import FULL_FORMAT_VERSION

        assert pyxctsk.FULL_FORMAT_VERSION is FULL_FORMAT_VERSION
        assert not hasattr(pyxctsk, "VERSION")
        assert self._payload(1, 2, 3).to_task().version == FULL_FORMAT_VERSION


class TestEveryFieldCrossesTheSeam:
    """The last hand-written field mirror, and the guard it never had.

    `model/shape.py` exists to abolish "a hand-written to_dict sitting beside a
    hand-written from_dict, with nothing making the two agree", and it did — at
    the model↔wire seam, where `test_shape.py` pairs each table against its
    dataclass. The model↔*model* seam is still exactly that situation:
    `task_to_qr_code_task` and `qr_code_task_to_task` are two hand-written
    field-by-field constructors of ~65 lines each.

    So adding one spec field is six edits in four files, and only the first
    four are checked. Miss either constructor and mypy is silent, the corpus is
    silent — no reference task carries a field the spec has just gained — and
    the value vanishes on every QR round trip.

    These two tests close it from both ends: `NOT_CROSSING` says which fields
    deliberately have no counterpart and why, and the round trip says every
    other field survives. A new field must be populated (or declared), and must
    then come back.
    """

    #: Fields with no counterpart on the other side, and the reason. Anything
    #: not named here must survive the crossing in both directions.
    NOT_CROSSING = {
        # The QR format has no key for it: the compact SSS carries the open
        # time and the gates, not the close.
        ("SSS", "time_close"),
        # The QR format flattens the takeoff into two root keys, so there is
        # nothing to split its unknown keys apart by coming back; they stay in
        # the full format. Same reason a Waypoint's do.
        ("Takeoff", "unknown"),
        # A converted task always declares the full format's version, which is
        # the whole reason `--strict` validates what arrived rather than the
        # conversion: the QR payload's own version is a different number.
        ("Task", "version"),
    }

    #: Fields holding a shape that has its own entry. Compared there, so a
    #: child's exemption is not silently re-applied to the whole parent — a
    #: `Takeoff` compared inside a `Task` would drag `Takeoff.unknown` with it.
    NESTED = {
        ("Task", "turnpoints"),
        ("Task", "takeoff"),
        ("Task", "sss"),
        ("Task", "goal"),
        ("Turnpoint", "waypoint"),
    }

    def _populated(self) -> dict[str, Any]:
        """One fully populated instance per 1:1 pair, keyed by class name.

        Every field carries a value distinguishable from its default, so a
        field that fails to cross shows up as the default coming back.
        """
        from pyxctsk.model.task import SSS, Goal, Takeoff, Task, Turnpoint, Waypoint
        from pyxctsk.model.time_of_day import TimeOfDay

        parts: dict[str, Any] = {
            "Turnpoint": Turnpoint(
                radius=1234,
                waypoint=Waypoint(
                    name="TP", lat=46.5, lon=8.25, alt_smoothed=1100, description="d"
                ),
                type=TurnpointType.SSS,
                extensions=[{"id": "x", "k": 1}],
                unknown={"zz": 9},
            ),
            "SSS": SSS(
                type=SSSType.RACE,
                direction=Direction.EXIT,
                time_gates=[TimeOfDay(11, 30, 0)],
                time_close=TimeOfDay(13, 0, 0),
                unknown={"zz": 9},
            ),
            "Goal": Goal(
                type=GoalType.LINE,
                deadline=TimeOfDay(19, 45, 0),
                finish_altitude=321,
                unknown={"zz": 9},
            ),
            "Takeoff": Takeoff(
                time_open=TimeOfDay(8, 0, 0),
                time_close=TimeOfDay(9, 30, 0),
                unknown={"zz": 9},
            ),
        }
        parts["Task"] = Task(
            task_type=TaskType.CLASSIC,
            version=1,
            turnpoints=[parts["Turnpoint"], parts["Turnpoint"]],
            earth_model=EarthModel.FAI_SPHERE,
            takeoff=parts["Takeoff"],
            sss=parts["SSS"],
            goal=parts["Goal"],
            extensions=[{"id": "root", "k": 2}],
            unknown={"root_zz": 8},
        )
        return parts

    def test_every_field_of_every_pair_is_populated(self):
        """Otherwise the round trip below silently stops covering a new field."""
        from dataclasses import fields

        for name, obj in self._populated().items():
            unset = [
                f.name
                for f in fields(obj)
                if not getattr(obj, f.name)  # noqa: B009
            ]
            assert unset == [], f"{name}: add {unset} to the populated instance"

    def test_every_field_survives_the_crossing(self):
        """A missed line in either hand-written constructor shows up here."""
        from dataclasses import fields

        populated = self._populated()
        back = populated["Task"].to_qr_code_task().to_task()
        returned = {
            "Task": back,
            "Turnpoint": back.turnpoints[0],
            "SSS": back.sss,
            "Goal": back.goal,
            "Takeoff": back.takeoff,
        }

        for name, before in populated.items():
            after = returned[name]
            assert after is not None, f"{name} did not cross at all"
            for f in fields(before):
                if (name, f.name) in self.NOT_CROSSING | self.NESTED:
                    continue
                assert getattr(after, f.name) == getattr(before, f.name), (
                    f"{name}.{f.name} was lost crossing to the QR format and back — "
                    f"add it to qrcode/conversion.py, or to NOT_CROSSING with a reason"
                )

    def test_the_nested_waypoint_crosses_one_level_down(self):
        """`Turnpoint.waypoint` has no counterpart; its values still cross."""
        from pyxctsk.model.task import Task

        turnpoint = self._populated()["Turnpoint"]
        task = Task(
            task_type=TaskType.CLASSIC, version=1, turnpoints=[turnpoint, turnpoint]
        )

        back = task.to_qr_code_task().to_task().turnpoints[0].waypoint

        assert (back.name, back.lat, back.lon) == (
            turnpoint.waypoint.name,
            turnpoint.waypoint.lat,
            turnpoint.waypoint.lon,
        )
        assert back.description == turnpoint.waypoint.description
        assert back.alt_smoothed == turnpoint.waypoint.alt_smoothed

    def test_not_crossing_names_only_fields_that_exist(self):
        """A renamed field must not leave a stale exemption behind."""
        from dataclasses import fields

        for name, obj in self._populated().items():
            declared = {
                f for (cls, f) in self.NOT_CROSSING | self.NESTED if cls == name
            }
            assert declared <= {f.name for f in fields(obj)}
