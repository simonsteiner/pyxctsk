"""Unknown-key and manufacturer-extension conformance regressions.

Derived from docs/arch-review/2026-08-16-competition-interfaces-audit.md.
Each test keeps the finding and specification provenance that it pins.
"""

import json

import pytest

from pyxctsk import (
    Goal,
    GoalType,
    Task,
    parse_task,
)
from tests.conformance._support import BASE_TASK, task_json

# Polyline-encoded "z" literals below are opaque tokens, not words.
# cspell:ignore Fligr


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

    def test_legacy_p_key_round_trips_as_an_unknown_key(self):
        """The dead ``p`` field used to swallow the key and drop it on output.

        ``p`` was a pyxctsk-only polyline of the turnpoint coordinates. It sat
        on the KNOWN_KEYS allow-list, so an incoming ``p`` was captured into a
        field that ``to_dict`` never wrote — the exact round-trip loss the
        unknown-key passthrough exists to prevent, hidden by the allow-list.
        """
        from pyxctsk.qrcode.task import QRCodeTask

        source = json.loads(Task.from_json(task_json()).to_qr_code_task().to_json())
        source["p"] = "_p~iF~ps|U"

        qr = QRCodeTask.from_dict(source)

        assert qr.unknown["p"] == "_p~iF~ps|U"
        assert json.loads(qr.to_json())["p"] == "_p~iF~ps|U"

    def test_turnpoint_x_is_not_read_as_a_coordinate(self):
        """The ``x`` key means extensions, not longitude as it once did."""
        from pyxctsk.qrcode.encoding import encode_competition_turnpoint
        from pyxctsk.qrcode.models import QRCodeTurnpoint

        z = encode_competition_turnpoint(8.1, 46.5, 1234, 400)
        turnpoint = QRCodeTurnpoint.from_dict({"n": "X", "z": z, "x": [{"k": "v"}]})

        assert turnpoint.lon == pytest.approx(8.1)
        assert turnpoint.lat == pytest.approx(46.5)
        assert turnpoint.extensions == [{"k": "v"}]


class TestUnknownKeysNeverCrossIntoAForeignSlot:
    """A carried key may not occupy a key the other format defines.

    ``unknown`` means "a key the format it arrived in does not define", so it
    only means anything relative to that format. Copied across the seam it kept
    its spelling but changed namespace: a full-format turnpoint's ``t`` — a key
    that format spells ``type`` — landed in the QR format's *type* slot, and
    the payload written from it could not be read back at all.

    ``write_passthrough``'s never-shadow rule cannot catch this. ``t`` is
    emitted for SSS and ESS turnpoints only, so on a plain turnpoint the slot
    is free and the foreign key wins.
    """

    #: The goal turnpoint of BASE_TASK, which has no type — so no ``t``.
    PLAIN = 2

    def _task_with(self, **extras) -> Task:
        data = json.loads(task_json())
        data["turnpoints"][self.PLAIN].update(extras)
        return Task.from_json(json.dumps(data))

    def test_the_foreign_key_is_still_read_as_unknown(self):
        """Nothing changes in the format the key arrived in.

        ``t`` is not a key the full format defines, so it is carried there
        exactly as before.
        """
        task = self._task_with(t=99)

        assert task.turnpoints[self.PLAIN].unknown == {"t": 99}
        assert json.loads(task.to_json())["turnpoints"][self.PLAIN]["t"] == 99

    def test_it_does_not_reach_the_qr_payload(self):
        """The QR turnpoint defines ``t``, so the crossing drops it."""
        emitted = json.loads(self._task_with(t=99).to_qr_code_task().to_json())

        assert "t" not in emitted["t"][self.PLAIN]

    def test_the_qr_payload_can_be_read_back(self):
        """The point of the rule: what we emit, we can parse."""
        qr_string = self._task_with(t=99).to_qr_code_task().to_string()

        assert parse_task(qr_string).turnpoints[self.PLAIN].type is None

    def test_a_key_neither_format_defines_still_crosses(self):
        """Only colliding keys are dropped — SeeYou's extras must survive."""
        emitted = json.loads(self._task_with(zz="kept").to_qr_code_task().to_json())

        assert emitted["t"][self.PLAIN]["zz"] == "kept"

    def test_the_rule_runs_in_the_other_direction_too(self):
        """``takeoff`` is a QR unknown key and a full-format spec field.

        The full format writes ``takeoff`` only when the task has one, so on a
        task without one the slot is free and a carried ``takeoff`` would be
        emitted as the takeoff object — a string where the spec says object.
        """
        from pyxctsk.qrcode.task import QRCodeTask

        source = json.loads(Task.from_json(task_json()).to_qr_code_task().to_json())
        source["takeoff"] = "rogue"

        task = QRCodeTask.from_dict(source).to_task()

        assert task.unknown == {}
        assert "takeoff" not in json.loads(task.to_json())


class TestNestedShapesCarryUnknownKeys:
    """Passthrough belongs to every serializable shape, not just the outer two.

    ``Task`` and ``Turnpoint`` each had a ``KNOWN_KEYS`` allow-list and an
    ``unknown`` field. The objects nested inside them did not, so a non-spec key
    in a ``waypoint``, ``sss``, ``goal`` or ``takeoff`` was read past and
    dropped — the same round-trip loss the passthrough exists to prevent, one
    level down.
    """

    def _source(self) -> dict:
        data: dict = json.loads(task_json())
        data["turnpoints"][0]["waypoint"]["zz"] = "waypoint-extra"
        data["sss"]["zz"] = "sss-extra"
        data["goal"]["zz"] = "goal-extra"
        data["takeoff"] = {"timeOpen": "08:00:00Z", "zz": "takeoff-extra"}
        return data

    def _task(self) -> Task:
        return Task.from_json(json.dumps(self._source()))

    def test_each_nested_shape_reads_its_own_extras(self):
        """The key lands on the object it was nested in, not on the task."""
        task = self._task()

        assert task.turnpoints[0].waypoint.unknown == {"zz": "waypoint-extra"}
        assert task.sss is not None and task.goal is not None
        assert task.takeoff is not None
        assert task.sss.unknown == {"zz": "sss-extra"}
        assert task.goal.unknown == {"zz": "goal-extra"}
        assert task.takeoff.unknown == {"zz": "takeoff-extra"}
        assert task.unknown == {}

    def test_they_come_back_out_again(self):
        """Reading without writing is the loss; both halves are needed."""
        emitted = json.loads(self._task().to_json())

        assert emitted["turnpoints"][0]["waypoint"]["zz"] == "waypoint-extra"
        assert emitted["sss"]["zz"] == "sss-extra"
        assert emitted["goal"]["zz"] == "goal-extra"
        assert emitted["takeoff"]["zz"] == "takeoff-extra"

    def test_the_roundtrip_is_lossless(self):
        """Nothing in the source may be dropped."""
        source = self._source()

        assert json.loads(Task.from_json(json.dumps(source)).to_json()) == source

    def test_an_unknown_key_cannot_shadow_a_nested_spec_field(self):
        """The never-shadow rule applies at every level it is used."""
        goal = Goal(type=GoalType.CYLINDER, unknown={"type": "NONSENSE"})

        assert goal.to_dict()["type"] == "CYLINDER"

    def test_the_qr_nested_shapes_carry_them_too(self):
        """``s`` and ``g`` are objects in the QR format as well."""
        from pyxctsk.qrcode.task import QRCodeTask

        source = json.loads(Task.from_json(task_json()).to_qr_code_task().to_json())
        source["s"]["zz"] = "sss-extra"
        source["g"]["zz"] = "goal-extra"

        qr = QRCodeTask.from_dict(source)

        assert qr.sss is not None and qr.goal is not None
        assert qr.sss.unknown == {"zz": "sss-extra"}
        assert qr.goal.unknown == {"zz": "goal-extra"}
        assert json.loads(qr.to_json()) == source

    def test_the_shapes_with_a_counterpart_carry_them_across_formats(self):
        """``sss`` and ``goal`` are objects in both formats, so extras travel."""
        emitted = json.loads(self._task().to_qr_code_task().to_json())

        assert emitted["s"]["zz"] == "sss-extra"
        assert emitted["g"]["zz"] == "goal-extra"

    def test_the_shapes_without_one_keep_them_in_the_full_format(self):
        """A waypoint and a takeoff have no QR object to carry them into.

        The QR format flattens the waypoint into its turnpoint and the takeoff
        into root ``to``/``tc``, so there is no dict on the other side that
        these keys belong to — and merging them upwards would leave nothing to
        split them apart by on the way back.
        """
        emitted = json.loads(self._task().to_qr_code_task().to_json())

        assert "zz" not in emitted["t"][0]
        assert "zz" not in emitted

    def test_line_length_stays_dropped(self):
        """The one key read and deliberately discarded rather than carried.

        ``lineLength`` is always twice the last turnpoint's radius, which is
        what the spec says that radius means. Carrying it would preserve a
        derived duplicate that a task can contradict, so it is on the goal's
        allow-list rather than in its ``unknown``.
        """
        data = json.loads(task_json())
        data["goal"]["lineLength"] = 5000

        task = Task.from_json(json.dumps(data))

        assert task.goal is not None
        assert task.goal.unknown == {}
        assert "lineLength" not in json.loads(task.to_json())["goal"]


class TestWaypointsFormatPreservesExtras:
    """The XC/Waypoints path must preserve what the competition path does.

    The simplified branches were initially left behind when extensions and
    unknown-field passthrough were added, so a waypoints payload could be read
    with its extras and re-encoded without them. Reading and writing have to
    stay symmetric or the round-trip loses data silently.
    """

    SOURCE = {
        "T": "W",
        "V": 2,
        "t": [
            {
                "n": "WPT1",
                "z": "|dz~FligrB?",
                "x": [{"k": "v"}],
                "zz": "turnpoint-extra",
            },
            {"n": "WPT2", "z": "vqz_G~{ztB?"},
        ],
        "x": [{"id": "ACME", "a": "1"}],
        "o": {"v": 2, "fa": 1220},
    }

    def _parsed(self):
        from pyxctsk.qrcode.task import QRCodeTask

        return QRCodeTask.from_dict(json.loads(json.dumps(self.SOURCE)))

    def test_root_extensions_are_read(self):
        """A simplified payload's root "x" must reach .extensions."""
        assert self._parsed().extensions == [{"id": "ACME", "a": "1"}]

    def test_root_extensions_are_written(self):
        """...and come back out again."""
        emitted = json.loads(self._parsed().to_waypoints_json())

        assert emitted["x"] == [{"id": "ACME", "a": "1"}]

    def test_turnpoint_extensions_and_unknown_are_written(self):
        """Per-turnpoint "x" and unknown keys were read but never re-emitted."""
        emitted = json.loads(self._parsed().to_waypoints_json())

        assert emitted["t"][0]["x"] == [{"k": "v"}]
        assert emitted["t"][0]["zz"] == "turnpoint-extra"

    def test_simplified_roundtrip_is_lossless(self):
        """Nothing in the source may be dropped."""
        emitted = json.loads(self._parsed().to_waypoints_json())

        assert emitted == self.SOURCE

    def test_a_plain_waypoints_task_gains_nothing(self):
        """Absent extras must stay absent — no empty "x" appearing."""
        from pyxctsk.qrcode.task import QRCodeTask

        plain = {"T": "W", "V": 2, "t": [{"n": "WPT1", "z": "|dz~FligrB?"}]}
        emitted = json.loads(QRCodeTask.from_dict(plain).to_waypoints_json())

        assert emitted == plain
