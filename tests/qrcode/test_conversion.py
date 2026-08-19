"""Tests for the Task <-> QRCodeTask translation tables.

The conversion itself is exercised end-to-end by the reference round-trips in
``test_qrcode.py`` and ``test_distance_reference.py``. What those cannot catch
is a value added to one enum and mapped in only one direction, so the tables'
symmetry is pinned here.
"""

import pytest

from pyxctsk.model.task import (
    OBSOLETE_DIRECTION_DEFAULT,
    Direction,
    EarthModel,
    GoalType,
    SSSType,
    TaskType,
)
from pyxctsk.qrcode.conversion import (
    _FROM_QR_DIRECTION,
    _FROM_QR_EARTH_MODEL,
    _FROM_QR_GOAL_TYPE,
    _FROM_QR_SSS_TYPE,
    _FROM_QR_TASK_TYPE,
    _FROM_QR_TURNPOINT_TYPE,
    _TO_QR_DIRECTION,
    _TO_QR_EARTH_MODEL,
    _TO_QR_GOAL_TYPE,
    _TO_QR_SSS_TYPE,
    _TO_QR_TASK_TYPE,
    _TO_QR_TURNPOINT_TYPE,
)
from pyxctsk.qrcode.enums import (
    QR_OBSOLETE_DIRECTION_DEFAULT,
    QRCodeDirection,
    QRCodeEarthModel,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTaskType,
)
from tests.corpus import reference_task

TABLE_PAIRS = [
    ("task type", _TO_QR_TASK_TYPE, _FROM_QR_TASK_TYPE),
    ("earth model", _TO_QR_EARTH_MODEL, _FROM_QR_EARTH_MODEL),
    ("turnpoint type", _TO_QR_TURNPOINT_TYPE, _FROM_QR_TURNPOINT_TYPE),
    ("direction", _TO_QR_DIRECTION, _FROM_QR_DIRECTION),
    ("SSS type", _TO_QR_SSS_TYPE, _FROM_QR_SSS_TYPE),
    ("goal type", _TO_QR_GOAL_TYPE, _FROM_QR_GOAL_TYPE),
]


@pytest.mark.parametrize("name, to_qr, from_qr", TABLE_PAIRS)
def test_tables_are_mutual_inverses(name, to_qr, from_qr):
    """Every mapping must round-trip, in both directions."""
    assert {v: k for k, v in to_qr.items()} == from_qr, f"{name} tables disagree"


@pytest.mark.parametrize(
    "enum, table",
    [
        # TurnpointType.NONE has no QR counterpart: the QR format's own NONE is
        # the default for anything unmapped, so it is deliberately absent here.
        (TaskType, _TO_QR_TASK_TYPE),
        (EarthModel, _TO_QR_EARTH_MODEL),
        (Direction, _TO_QR_DIRECTION),
        (SSSType, _TO_QR_SSS_TYPE),
        (GoalType, _TO_QR_GOAL_TYPE),
    ],
)
def test_every_domain_value_is_mapped(enum, table):
    """A new enum member must not silently fall through to a default."""
    assert set(enum) == set(table)


@pytest.mark.parametrize(
    "enum, table",
    [
        (QRCodeTaskType, _FROM_QR_TASK_TYPE),
        (QRCodeEarthModel, _FROM_QR_EARTH_MODEL),
        (QRCodeDirection, _FROM_QR_DIRECTION),
        (QRCodeSSSType, _FROM_QR_SSS_TYPE),
        (QRCodeGoalType, _FROM_QR_GOAL_TYPE),
    ],
)
def test_every_qr_value_is_mapped(enum, table):
    """The same, coming back the other way."""
    assert set(enum) == set(table)


def test_the_two_obsolete_direction_defaults_agree():
    """Each layer names the fallback beside its own enum; they must match.

    ``sss.direction`` is obsolete and ignored on read, so both readers invent a
    value when a task omits it. If they invented different ones, the same task
    would export differently depending on which format it arrived in.
    """
    assert _TO_QR_DIRECTION[OBSOLETE_DIRECTION_DEFAULT] == QR_OBSOLETE_DIRECTION_DEFAULT


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
        from pyxctsk.qrcode.task import QRCodeTask

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
        from pyxctsk.qrcode.task import QRCodeTask

        waypoints = QRCodeTask.from_string(reference_task("task_dami_route").qr_string)

        assert waypoints.task_type is QRCodeTaskType.WAYPOINTS
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
        library write a version its own validator rejects.
        """
        import pyxctsk
        from pyxctsk.model.validation import FULL_FORMAT_VERSION

        assert pyxctsk.VERSION is FULL_FORMAT_VERSION
        assert self._payload(1, 2, 3).to_task().version == FULL_FORMAT_VERSION
