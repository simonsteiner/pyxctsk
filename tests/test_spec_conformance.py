"""Regression tests for the XCTrack Competition Interfaces conformance audit.

These tests encode the findings from the spec-conformance audit
(docs/arch-review/2026-08-16-competition-interfaces-audit.md). Each test
names the finding it pins, so a failure points straight at the spec clause it
violates.

The reference corpus in ``tests/data/reference_tasks/`` only covers the fields
tools.xcontest.org exports, which is why these gaps survived a green suite. The
tests here deliberately exercise the optional half of the spec instead.
"""

import json
from pathlib import Path

import pytest

from pyxctsk import (
    Direction,
    SSSType,
    Task,
    TaskType,
    TaskValidationError,
    TurnpointType,
    parse_task,
)
from pyxctsk.goal_line import GoalLine, goal_line_length_from_turnpoints

# Polyline-encoded "z" literals below are opaque tokens, not words.
# cspell:ignore Fligr

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


class TestStructuralValidation:
    """The spec's structural rules for special turnpoint types.

    Spec: "TAKEOFF type can be used only for the first turnpoint"; "SSS and ESS
    turnpoints must appear exactly once and SSS turnpoint must appear before
    ESS".
    """

    def _mutated(self, mutate) -> list[str]:
        """Return validate() for BASE_TASK after applying a mutation."""
        data = json.loads(task_json())
        mutate(data)
        return Task.from_dict(data).validate()

    def test_valid_task_reports_nothing(self):
        """The base fixture is spec-valid."""
        assert Task.from_json(task_json()).validate() == []

    @pytest.mark.parametrize("name", sorted(p.name for p in REFERENCE_QR.glob("*.txt")))
    def test_every_reference_task_is_valid(self, name):
        """Real XCTrack tasks must not trip the validator."""
        assert parse_task(str(REFERENCE_QR / name)).validate() == []

    def test_takeoff_must_be_first(self):
        """Only the first turnpoint may be TAKEOFF."""
        issues = self._mutated(
            lambda d: d["turnpoints"][2].update(type="TAKEOFF"),
        )
        assert issues == [
            "TAKEOFF is only allowed on the first turnpoint, found at index 2"
        ]

    def test_sss_must_appear_exactly_once(self):
        """A second SSS is a violation."""
        assert self._mutated(lambda d: d["turnpoints"][2].update(type="SSS")) == [
            "SSS must appear exactly once, found 2"
        ]

    def test_ess_must_appear_exactly_once(self):
        """A missing ESS is a violation."""
        assert self._mutated(lambda d: d["turnpoints"][1].pop("type")) == [
            "ESS must appear exactly once, found 0"
        ]

    def test_sss_must_precede_ess(self):
        """Order between the two is constrained."""

        def swap(data):
            data["turnpoints"][0]["type"] = "ESS"
            data["turnpoints"][1]["type"] = "SSS"

        assert self._mutated(swap) == [
            "SSS must appear before ESS, found SSS at 1 and ESS at 0"
        ]

    def test_empty_task_is_reported_once(self):
        """No turnpoints short-circuits rather than cascading messages."""
        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])

        assert task.validate() == ["task has no turnpoints"]

    def test_waypoints_tasks_are_exempt_from_speed_section_rules(self):
        """A route "without cylinders" has no speed section to constrain."""
        task = parse_task(str(REFERENCE_QR / "task_noha_route.txt"))

        assert task.task_type == TaskType.WAYPOINTS
        assert task.validate() == []

    def test_parsing_stays_lenient_by_default(self):
        """A malformed task must remain readable so it can be inspected."""
        data = json.loads(task_json())
        data["turnpoints"][2]["type"] = "TAKEOFF"

        task = parse_task(json.dumps(data))

        assert task.turnpoints[2].type == TurnpointType.TAKEOFF
        assert task.validate() != []

    def test_strict_rejects_an_invalid_task(self):
        """The opt-in flag turns the report into a failure."""
        data = json.loads(task_json())
        data["turnpoints"][2]["type"] = "TAKEOFF"

        with pytest.raises(TaskValidationError) as excinfo:
            parse_task(json.dumps(data), strict=True)

        assert excinfo.value.issues == [
            "TAKEOFF is only allowed on the first turnpoint, found at index 2"
        ]

    def test_strict_accepts_a_valid_task(self):
        """Strict must not reject what the spec allows."""
        assert parse_task(task_json(), strict=True).turnpoints


class TestCompressedQRScheme:
    """Finding 3 — the ``XCTSKZ:`` zlib+base64 encoding.

    Spec: "The QR code can be also compressed using zlib format and converted
    using base64 encoding to ascii. This must be prefixed with a string
    'XCTSKZ:'. It is recommended that the software accepts both XCTSK and
    XCTSKZ and is able to produce QR code in both formats."
    """

    def test_compressed_output_carries_the_right_prefix(self):
        """Each scheme must announce itself correctly."""
        task = Task.from_json(task_json())

        assert task.to_qr_code_task().to_string(compressed=True).startswith("XCTSKZ:")
        assert task.to_qr_code_task().to_string().startswith("XCTSK:")

    def test_plain_remains_the_default(self):
        """Existing callers must see no change."""
        qr = Task.from_json(task_json()).to_qr_code_task()

        assert qr.to_string() == qr.to_string(compressed=False)
        assert not qr.to_string().startswith("XCTSKZ:")

    @pytest.mark.parametrize("name", ["task_bevo.txt", "task_noha_route.txt"])
    def test_compressed_round_trips_to_the_same_task(self, name):
        """Compression must be transparent: same task in, same task out."""
        original = parse_task(str(REFERENCE_QR / name))
        waypoints = (REFERENCE_QR / name).read_text().startswith('XCTSK:{"T"')

        qr = original.to_qr_code_task()
        compressed = (
            qr.to_waypoints_string(compressed=True)
            if waypoints
            else qr.to_string(compressed=True)
        )

        assert parse_task(compressed).to_json() == original.to_json()

    def test_compression_actually_shrinks_a_real_task(self):
        """The point of the format is fitting more task in a scannable code."""
        qr = parse_task(str(REFERENCE_QR / "task_bevo.txt")).to_qr_code_task()

        assert len(qr.to_string(compressed=True)) < len(qr.to_string())

    def test_parser_accepts_both_schemes(self):
        """The spec makes reading both mandatory."""
        qr = Task.from_json(task_json()).to_qr_code_task()

        assert (
            parse_task(qr.to_string()).to_json()
            == parse_task(qr.to_string(compressed=True)).to_json()
        )

    def test_compressed_url_is_not_mistaken_for_a_file_path(self):
        """Base64 contains "/", which the path heuristic used to trip over."""
        from pyxctsk.parser import _looks_like_file_path

        payloads = [
            Task.from_json(
                task_json(sss={"type": "RACE", "timeGates": [f"1{n}:00:00Z"]})
            )
            .to_qr_code_task()
            .to_string(compressed=True)
            for n in range(10)
        ]
        assert any("/" in p for p in payloads), "no sample exercised the '/' case"
        assert not any(_looks_like_file_path(p) for p in payloads)

    @pytest.mark.parametrize(
        "payload", ["XCTSKZ:not valid base64!!", "XCTSKZ:aGVsbG8=", "XCTSKZ:"]
    )
    def test_malformed_compressed_payload_is_reported(self, payload):
        """A recognized prefix with a bad body must not fall through silently."""
        from pyxctsk import InvalidFormatError

        with pytest.raises(InvalidFormatError):
            parse_task(payload)

    def test_unknown_scheme_is_rejected(self):
        """A lookalike prefix is not silently treated as plain JSON."""
        from pyxctsk.qrcode_task import QRCodeTask

        with pytest.raises(ValueError, match="Invalid QR code scheme"):
            QRCodeTask.from_string("NOT-A-SCHEME:{}")


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
        from pyxctsk.rounding import round_half_up

        assert round_half_up(value) == expected


class TestTaskTypeValue:
    """Finding 10 — ``taskType`` in the competition format is only "CLASSIC".

    Spec: the v2 competition format defines ``"taskType": "CLASSIC"``. An
    XC/Waypoints task is signalled by ``"T": "W"`` in the simplified format,
    so "WAYPOINTS" is not a value either format defines.
    """

    @pytest.mark.parametrize("name", ["task_noha_route.txt", "task_dami_route.txt"])
    def test_waypoints_task_serializes_as_the_simplified_format(self, name):
        """to_string() on a waypoints task must produce XCTrack's own form."""
        expected = (REFERENCE_QR / name).read_text().strip()
        task = parse_task(str(REFERENCE_QR / name))

        assert task.to_qr_code_task().to_string() == expected

    def test_waypoints_value_is_never_emitted(self):
        """The non-spec "WAYPOINTS" value must not appear anywhere."""
        task = parse_task(str(REFERENCE_QR / "task_noha_route.txt"))
        emitted = json.loads(task.to_qr_code_task().to_json())

        assert "taskType" not in emitted
        assert emitted["T"] == "W"

    def test_classic_still_says_classic(self):
        """The competition format is untouched."""
        task = parse_task(str(REFERENCE_QR / "task_bevo.txt"))

        assert json.loads(task.to_qr_code_task().to_json())["taskType"] == "CLASSIC"

    def test_serialized_shape_follows_task_type_alone(self):
        """There is one source of truth for the shape, not a flag beside it."""
        qr = parse_task(str(REFERENCE_QR / "task_bevo.txt")).to_qr_code_task()

        assert json.loads(qr.to_json())["taskType"] == "CLASSIC"
        assert json.loads(qr.as_waypoints().to_json())["T"] == "W"

    def test_as_waypoints_does_not_mutate_the_original(self):
        """Downgrading to waypoints returns a copy, so the source is reusable."""
        qr = parse_task(str(REFERENCE_QR / "task_bevo.txt")).to_qr_code_task()

        before = qr.to_json()
        qr.to_waypoints_json()

        assert qr.to_json() == before


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
        from pyxctsk.qrcode_task import QRCodeTask

        source = json.loads(Task.from_json(task_json()).to_qr_code_task().to_json())
        source["p"] = "_p~iF~ps|U"

        qr = QRCodeTask.from_dict(source)

        assert qr.unknown["p"] == "_p~iF~ps|U"
        assert json.loads(qr.to_json())["p"] == "_p~iF~ps|U"

    def test_turnpoint_x_is_not_read_as_a_coordinate(self):
        """The ``x`` key means extensions, not longitude as it once did."""
        from pyxctsk.qrcode_encoding import encode_competition_turnpoint
        from pyxctsk.qrcode_models import QRCodeTurnpoint

        z = encode_competition_turnpoint(8.1, 46.5, 1234, 400)
        turnpoint = QRCodeTurnpoint.from_dict({"n": "X", "z": z, "x": [{"k": "v"}]})

        assert turnpoint.lon == pytest.approx(8.1)
        assert turnpoint.lat == pytest.approx(46.5)
        assert turnpoint.extensions == [{"k": "v"}]


class TestTurnpointCoordinatesAreNeverInvented:
    """A malformed ``z`` is an error, not a turnpoint at 0°N 0°E.

    Both QR formats require ``z``. Defaulting the coordinates to zero produced
    a valid-looking turnpoint in the Gulf of Guinea and reported the task as
    read successfully — a silent fallback papering over malformed input.
    """

    def _from_dict(self, data):
        from pyxctsk.qrcode_models import QRCodeTurnpoint

        return QRCodeTurnpoint.from_dict(data)

    def test_missing_z_raises(self):
        """No coordinates at all is malformed input."""
        with pytest.raises(KeyError):
            self._from_dict({"n": "TP"})

    @pytest.mark.parametrize("count", [0, 1, 2, 5])
    def test_wrong_number_count_raises(self, count):
        """Only the 3- and 4-number forms are defined."""
        from pyxctsk.qrcode_encoding import encode_num

        z = "".join(encode_num(n) for n in range(count))
        with pytest.raises(ValueError, match="3 or 4 numbers"):
            self._from_dict({"n": "TP", "z": z})

    def test_the_error_reaches_the_parser_as_a_format_error(self):
        """Raising here must surface as a descriptive parse failure."""
        from pyxctsk.exceptions import InvalidFormatError

        with pytest.raises(InvalidFormatError, match="could not be parsed"):
            parse_task('XCTSK:{"taskType":"CLASSIC","version":2,"t":[{"n":"TP"}]}')


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
        from pyxctsk.qrcode_task import QRCodeTask

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
        from pyxctsk.qrcode_task import QRCodeTask

        plain = {"T": "W", "V": 2, "t": [{"n": "WPT1", "z": "|dz~FligrB?"}]}
        emitted = json.loads(QRCodeTask.from_dict(plain).to_waypoints_json())

        assert emitted == plain


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
