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

import pytest

from pyxctsk import Direction, SSSType, Task

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
