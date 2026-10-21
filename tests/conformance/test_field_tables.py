"""Conformance of every real field table, across ``model`` and ``qrcode``.

The whole design rests on one structural invariant: a shape's declared keys are
the keys it actually uses, because every key belongs to a row. These tests check
that of each table, and that each table agrees with the model it describes.
"""

import json
from typing import Any

import pytest

from pyxctsk import Task
from pyxctsk.model.shape import (
    Shape,
)
from pyxctsk.model.task import TASK_SHAPE
from pyxctsk.model.task_parts import (
    GOAL_SHAPE,
    SSS_SHAPE,
    TAKEOFF_SHAPE,
    TURNPOINT_SHAPE,
    WAYPOINT_SHAPE,
)
from pyxctsk.model.time_of_day import TimeOfDay
from pyxctsk.qrcode.models import (
    QR_GOAL_SHAPE,
    QR_SSS_SHAPE,
    QR_TAKEOFF_SHAPE,
    QR_TURNPOINT_SHAPE,
    QR_WAYPOINT_TURNPOINT_SHAPE,
)
from pyxctsk.qrcode.task import QR_TASK_SHAPE, QR_WAYPOINTS_TASK_SHAPE
from tests.corpus import reference_tasks

ALL_SHAPES = [
    ("Task", TASK_SHAPE),
    ("Turnpoint", TURNPOINT_SHAPE),
    ("Waypoint", WAYPOINT_SHAPE),
    ("Takeoff", TAKEOFF_SHAPE),
    ("SSS", SSS_SHAPE),
    ("Goal", GOAL_SHAPE),
    ("QRCodeTask", QR_TASK_SHAPE),
    ("QRCodeTask/waypoints", QR_WAYPOINTS_TASK_SHAPE),
    ("QRCodeTurnpoint", QR_TURNPOINT_SHAPE),
    ("QRCodeTurnpoint/waypoints", QR_WAYPOINT_TURNPOINT_SHAPE),
    ("QRCodeTakeoff", QR_TAKEOFF_SHAPE),
    ("QRCodeSSS", QR_SSS_SHAPE),
    ("QRCodeGoal", QR_GOAL_SHAPE),
]


class TestEveryKeyBelongsToARow:
    """The invariant the whole design rests on.

    If a shape can write a key its table does not declare, the derived
    allow-list is wrong again and the passthrough will treat that key as
    unknown on the way back in — reading it into ``unknown`` *and* writing it
    from its own row, or worse, letting a carried key shadow it. Rendering the
    whole corpus and checking every emitted key against the shape that emitted
    it is what makes a bespoke row's undeclared key fail here rather than in a
    round-trip nobody runs.
    """

    def _emitted_keys(self, obj: Any, shape: Shape) -> set[str]:
        written = shape.write(obj)
        carried = set(getattr(obj, "unknown", {}))
        return set(written) - carried

    @pytest.mark.parametrize("name, shape", ALL_SHAPES, ids=[n for n, _ in ALL_SHAPES])
    def test_no_shape_declares_a_key_it_cannot_reach(self, name, shape):
        """Every declared key is one some row owns, by construction."""
        owned = {key for f in shape.fields for key in f.keys}
        extra = shape.keys - owned - shape.ignored_keys

        assert extra <= {shape.ext_key} - {None}, f"{name} declares stray {extra}"

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_nothing_a_reference_task_emits_falls_outside_its_shape(self, reference):
        """Rendered both ways, every key at every level is a declared one."""
        task = reference.task

        assert self._emitted_keys(task, TASK_SHAPE) <= TASK_SHAPE.keys
        for turnpoint in task.turnpoints:
            assert (
                self._emitted_keys(turnpoint, TURNPOINT_SHAPE) <= TURNPOINT_SHAPE.keys
            )
            assert (
                self._emitted_keys(turnpoint.waypoint, WAYPOINT_SHAPE)
                <= WAYPOINT_SHAPE.keys
            )

        qr = task.to_qr_code_task()
        assert self._emitted_keys(qr, QR_TASK_SHAPE) <= QR_TASK_SHAPE.keys
        assert (
            self._emitted_keys(qr.as_waypoints(), QR_WAYPOINTS_TASK_SHAPE)
            <= QR_WAYPOINTS_TASK_SHAPE.keys
        )
        for qr_turnpoint in qr.turnpoints:
            assert (
                self._emitted_keys(qr_turnpoint, QR_TURNPOINT_SHAPE)
                <= QR_TURNPOINT_SHAPE.keys
            )
            assert (
                self._emitted_keys(qr_turnpoint, QR_WAYPOINT_TURNPOINT_SHAPE)
                <= QR_WAYPOINT_TURNPOINT_SHAPE.keys
            )

    def test_the_takeoff_row_declares_both_of_its_keys(self):
        """The regression this class is shaped to catch, stated directly."""
        from pyxctsk.qrcode.models import QRCodeTakeoff
        from pyxctsk.qrcode.task import QRCodeTask

        task = QRCodeTask(takeoff=QRCodeTakeoff(time_open=TimeOfDay(9, 0, 0)))

        assert set(QR_TASK_SHAPE.write(task)) <= QR_TASK_SHAPE.keys


class TestTablesAndModelsAgree:
    """A row names an attribute the class actually has.

    ``Shape.read`` ends in ``cls(**kwargs)``, so a misspelled ``attr`` is a
    ``TypeError`` at the moment something parses — which for a row the corpus
    does not exercise could be a long way from here.
    """

    @pytest.mark.parametrize("name, shape", ALL_SHAPES, ids=[n for n, _ in ALL_SHAPES])
    def test_every_row_names_a_field_of_its_class(self, name, shape):
        """Checked for the rows that declare one attribute.

        The handful spanning several write their own names, and the corpus
        covers those.
        """
        fields = set(shape.cls.__dataclass_fields__)

        for row in shape.fields:
            attr = getattr(row, "attr", None)
            if attr is not None:
                assert attr in fields, f"{name}: no attribute {attr!r}"

    @pytest.mark.parametrize("name, shape", ALL_SHAPES, ids=[n for n, _ in ALL_SHAPES])
    def test_a_shape_carries_unknown_only_if_its_class_can(self, name, shape):
        """The one shape that is not an object on the wire has no ``unknown``."""
        has_field = "unknown" in shape.cls.__dataclass_fields__

        assert shape.carries_unknown == has_field, name


def test_the_derived_key_sets_match_the_spec_fields():
    """A last check that deriving them changed none of them.

    The allow-lists were hand-written before the tables existed; these are the
    same sets, which is the evidence that the tables describe the format rather
    than a new reading of it.
    """
    assert Task.KNOWN_KEYS == frozenset(
        {
            "taskType",
            "version",
            "earthModel",
            "turnpoints",
            "takeoff",
            "sss",
            "goal",
            "extensions",
        }
    )
    assert json.loads(Task.from_json(_MINIMAL).to_json())["taskType"] == "CLASSIC"


_MINIMAL = json.dumps(
    {
        "taskType": "CLASSIC",
        "version": 1,
        "turnpoints": [
            {
                "radius": 400,
                "waypoint": {"name": "A", "lat": 46.5, "lon": 8.1, "altSmoothed": 100},
            }
        ],
    }
)
