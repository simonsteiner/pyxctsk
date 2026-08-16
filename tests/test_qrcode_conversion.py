"""Tests for the Task <-> QRCodeTask translation tables.

The conversion itself is exercised end-to-end by the reference round-trips in
``test_qrcode.py`` and ``test_distance_reference.py``. What those cannot catch
is a value added to one enum and mapped in only one direction, so the tables'
symmetry is pinned here.
"""

import pytest

from pyxctsk.qrcode_conversion import (
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
from pyxctsk.qrcode_enums import (
    QRCodeDirection,
    QRCodeEarthModel,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTaskType,
)
from pyxctsk.task import Direction, EarthModel, GoalType, SSSType, TaskType

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
