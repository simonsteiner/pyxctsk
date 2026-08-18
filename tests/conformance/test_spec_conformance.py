"""Regression tests for the two conformance audits.

These tests encode the findings from the spec-conformance audits
(docs/arch-review/2026-08-16-competition-interfaces-audit.md for the XCTrack
format, 2026-08-18-s7f-2026-conformance-audit.md for FAI S7F). Each test
names the finding it pins, so a failure points straight at the spec clause it
violates.

The reference corpus in ``tests/data/reference_tasks/`` only covers the fields
tools.xcontest.org exports, which is why these gaps survived a green suite. The
tests here deliberately exercise the optional half of the spec instead.
"""

import json

import pytest

from pyxctsk import (
    Direction,
    Goal,
    GoalType,
    InvalidFormatError,
    SSSType,
    Task,
    TaskType,
    TaskValidationError,
    TurnpointType,
    parse_task,
    parser,
)
from pyxctsk.distance import optimized_distance
from pyxctsk.distance.goal_line import (
    GoalLine,
    GoalLineOrientation,
    goal_line_length_from_turnpoints,
)
from pyxctsk.distance.measured_task import MeasuredTask, task_to_turnpoints
from pyxctsk.distance.route_optimization import calculate_iteratively_refined_route
from pyxctsk.distance.turnpoint import (
    LocalPlane,
    geod_for_earth_model,
    geodesic_distance,
    local_tm_transformers,
    task_area_center,
)
from pyxctsk.model.validation import ValidationRule
from tests.corpus import reference_task, reference_tasks
from tests.paths import ELEVATED_GOAL_DIR

# Polyline-encoded "z" literals below are opaque tokens, not words.
# cspell:ignore Fligr

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


class TestStructuralValidation:
    """The spec's structural rules for special turnpoint types.

    Spec: "TAKEOFF type can be used only for the first turnpoint"; "SSS and ESS
    turnpoints must appear exactly once and SSS turnpoint must appear before
    ESS".
    """

    def _mutated(self, mutate):
        """Return validate() for BASE_TASK after applying a mutation."""
        data = json.loads(task_json())
        mutate(data)
        return Task.from_dict(data).validate()

    def _assert_one(self, issues, rule, message):
        """Assert a single issue, checking both its rule and its message."""
        assert [(i.rule, str(i)) for i in issues] == [(rule, message)]

    def test_valid_task_reports_nothing(self):
        """The base fixture is spec-valid."""
        assert Task.from_json(task_json()).validate() == []

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_every_reference_task_is_valid(self, reference):
        """Real XCTrack tasks must not trip the validator.

        Read from the QR string rather than the `.xctsk`, so this covers the
        representation the other consumers of the corpus do not.
        """
        assert parse_task(reference.qr_string).validate() == []

    def test_takeoff_must_be_first(self):
        """Only the first turnpoint may be TAKEOFF."""
        issues = self._mutated(
            lambda d: d["turnpoints"][2].update(type="TAKEOFF"),
        )
        self._assert_one(
            issues,
            ValidationRule.TAKEOFF_NOT_FIRST,
            "TAKEOFF is only allowed on the first turnpoint, found at index 2",
        )

    def test_sss_must_appear_exactly_once(self):
        """A second SSS is a violation."""
        self._assert_one(
            self._mutated(lambda d: d["turnpoints"][2].update(type="SSS")),
            ValidationRule.SPECIAL_NOT_ONCE,
            "SSS must appear exactly once, found 2",
        )

    def test_ess_must_appear_exactly_once(self):
        """A missing ESS is a violation."""
        self._assert_one(
            self._mutated(lambda d: d["turnpoints"][1].pop("type")),
            ValidationRule.SPECIAL_NOT_ONCE,
            "ESS must appear exactly once, found 0",
        )

    def test_sss_must_precede_ess(self):
        """Order between the two is constrained."""

        def swap(data):
            data["turnpoints"][0]["type"] = "ESS"
            data["turnpoints"][1]["type"] = "SSS"

        self._assert_one(
            self._mutated(swap),
            ValidationRule.SSS_AFTER_ESS,
            "SSS must appear before ESS, found SSS at 1 and ESS at 0",
        )

    def test_empty_task_is_reported_once(self):
        """No turnpoints short-circuits rather than cascading messages."""
        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])

        self._assert_one(
            task.validate(), ValidationRule.NO_TURNPOINTS, "task has no turnpoints"
        )

    def test_waypoints_tasks_are_exempt_from_speed_section_rules(self):
        """A route "without cylinders" has no speed section to constrain."""
        task = parse_task(reference_task("task_noha_route").qr_string)

        assert task.task_type == TaskType.WAYPOINTS
        assert task.validate() == []

    def test_parsing_stays_lenient_by_default(self):
        """A malformed task must remain readable so it can be inspected."""
        data = json.loads(task_json())
        data["turnpoints"][2]["type"] = "TAKEOFF"

        task = parse_task(json.dumps(data))

        assert task.turnpoints[2].type == TurnpointType.TAKEOFF
        assert task.validate() != []

    def test_a_caller_can_branch_on_the_rule_without_reading_prose(self):
        """The point of the typed issue: react to *which* rule broke.

        A message is free to be reworded; the rule is the contract.
        """

        def swap(data):
            data["turnpoints"][0]["type"] = "ESS"
            data["turnpoints"][1]["type"] = "SSS"

        rules = {issue.rule for issue in self._mutated(swap)}

        assert ValidationRule.SSS_AFTER_ESS in rules
        assert ValidationRule.NO_TURNPOINTS not in rules

    def test_every_rule_is_reachable(self):
        """A rule nothing can emit is a rule that does not exist."""
        emitted = set()
        for mutate in (
            lambda d: d["turnpoints"][2].update(type="TAKEOFF"),
            lambda d: d["turnpoints"][2].update(type="SSS"),
            lambda d: (
                d["turnpoints"][0].update(type="ESS"),
                d["turnpoints"][1].update(type="SSS"),
            ),
            lambda d: d["turnpoints"][2].update(radius=-1),
            lambda d: d.update(version=99),
            lambda d: d["turnpoints"][2].update(extensions=[{"a": "1"}]),
            lambda d: (
                d.update(extensions=[{"id": "ACME"}]),
                d["turnpoints"][2].update(extensions=[{"id": "ACME", "a": "1"}]),
            ),
            lambda d: d["goal"].update(finishAltitude=5000),
            lambda d: d["goal"].update(finishAltitude=300),
        ):
            emitted |= {issue.rule for issue in self._mutated(mutate)}
        emitted |= {
            issue.rule
            for issue in Task(
                task_type=TaskType.CLASSIC, version=1, turnpoints=[]
            ).validate()
        }

        assert emitted == set(ValidationRule)

    def test_a_negative_radius_is_rejected(self):
        """A cylinder cannot be smaller than a point."""
        issues = self._mutated(lambda d: d["turnpoints"][2].update(radius=-1))

        self._assert_one(
            issues,
            ValidationRule.NEGATIVE_RADIUS,
            "turnpoint 2 has a negative radius (-1)",
        )

    def test_a_zero_radius_is_not(self):
        """Zero is legitimate: every XC/Waypoints turnpoint has it.

        The 2026-08-17 review's candidate H proposed rejecting ``radius <= 0``.
        That would fail every waypoints task, and the optimizer reads radius 0
        as the point itself.
        """
        issues = self._mutated(lambda d: d["turnpoints"][2].update(radius=0))

        assert issues == []

    def test_a_version_this_format_does_not_define_is_rejected(self):
        """The full format is version 1; the QR one says 2."""
        issues = self._mutated(lambda d: d.update(version=2))

        self._assert_one(
            issues,
            ValidationRule.UNKNOWN_VERSION,
            "this format defines version 1, the task declares 2",
        )

    def test_a_turnpoint_extension_with_no_root_entry_is_rejected(self):
        """Spec: turnpoint extensions are "in the same order as the root ones".

        Position is the only thing linking one to a root entry, so a turnpoint
        carrying more of them than the root list has entries has some that
        correspond to nothing.
        """
        issues = self._mutated(
            lambda d: d["turnpoints"][2].update(extensions=[{"a": "1"}])
        )

        self._assert_one(
            issues,
            ValidationRule.EXTENSION_WITHOUT_ROOT,
            "turnpoint 2 has 1 extensions but the root list has 0, so some "
            "correspond to nothing",
        )

    def test_a_turnpoint_extension_repeating_the_id_is_rejected(self):
        """Spec: the ``id`` is "not repeated" on the turnpoint entries."""
        issues = self._mutated(
            lambda d: (
                d.update(extensions=[{"id": "ACME"}]),
                d["turnpoints"][2].update(extensions=[{"id": "ACME", "a": "1"}]),
            )
        )

        self._assert_one(
            issues,
            ValidationRule.EXTENSION_REPEATS_ID,
            "turnpoint 2 repeats the extension id 'ACME', which belongs to the "
            "root entry",
        )

    def test_well_formed_extensions_pass(self):
        """One root entry, one matching turnpoint entry without the id."""
        issues = self._mutated(
            lambda d: (
                d.update(extensions=[{"id": "ACME"}]),
                d["turnpoints"][2].update(extensions=[{"a": "1"}]),
            )
        )

        assert issues == []

    def test_strict_rejects_an_invalid_task(self):
        """The opt-in flag turns the report into a failure."""
        data = json.loads(task_json())
        data["turnpoints"][2]["type"] = "TAKEOFF"

        with pytest.raises(TaskValidationError) as excinfo:
            parse_task(json.dumps(data), strict=True)

        self._assert_one(
            excinfo.value.issues,
            ValidationRule.TAKEOFF_NOT_FIRST,
            "TAKEOFF is only allowed on the first turnpoint, found at index 2",
        )
        # The exception message is still the joined prose.
        assert "found at index 2" in str(excinfo.value)

    def test_strict_accepts_a_valid_task(self):
        """Strict must not reject what the spec allows."""
        assert parse_task(task_json(), strict=True).turnpoints

    def test_a_caller_can_react_to_a_specific_rule(self):
        """The whole point of naming a rule, and it did not typecheck.

        ``TaskValidationError.issues`` was ``Sequence[object]``, so the
        documented way to use it — matching on ``issue.rule`` rather than on
        the English message — failed mypy with *"object" has no attribute
        "rule"* for any downstream caller.
        """
        data = json.loads(task_json())
        data["turnpoints"][2]["type"] = "TAKEOFF"

        with pytest.raises(TaskValidationError) as excinfo:
            parse_task(json.dumps(data), strict=True)

        rules = [issue.rule for issue in excinfo.value.issues]
        assert rules == [ValidationRule.TAKEOFF_NOT_FIRST]
        assert excinfo.value.issues[0].message


class TestStrictValidatesWhatArrived:
    """`--strict` checks the payload, not what converting it invented.

    Three of the four format adapters are the compact one, and they used to
    call `to_task()` inside the adapter — so by the strict gate the payload was
    gone and `Task.validate()` reported on a conversion that had invented a
    version, a task type and a goal the payload never carried. That is the
    failure `model/validation.py` says the `TaskStructure` split exists to
    prevent, and it meant `UNKNOWN_VERSION` could not be reported for any QR
    input at all.
    """

    def _payloads(self, qr):
        """The same payload in each of the three text QR formats."""
        return {
            "XCTSK:": qr.to_string(),
            "XCTSKZ:": qr.to_string(compressed=True),
            "qrcode-json": qr.to_json(),
        }

    def _bad_version_qr(self):
        """A QR payload declaring a version its format does not define."""
        qr = reference_task("task_bevo").task.to_qr_code_task()
        qr.version = 99
        return qr

    @pytest.mark.parametrize(
        "fmt", ["XCTSK:", "XCTSKZ:", "qrcode-json"], ids=lambda f: f.strip(":-")
    )
    def test_a_qr_payloads_own_version_rule_reaches_strict(self, fmt):
        """The QR format defines version 2; 99 is a violation of *that* rule."""
        payload = self._payloads(self._bad_version_qr())[fmt]

        with pytest.raises(TaskValidationError) as excinfo:
            parse_task(payload, strict=True)

        assert any(
            issue.rule is ValidationRule.UNKNOWN_VERSION
            for issue in excinfo.value.issues
        )

    @pytest.mark.parametrize(
        "fmt", ["XCTSK:", "XCTSKZ:", "qrcode-json"], ids=lambda f: f.strip(":-")
    )
    def test_the_report_matches_the_payloads_own_verdict(self, fmt):
        """parse_task(strict) says exactly what QRCodeTask.validate() says."""
        qr = self._bad_version_qr()
        payload = self._payloads(qr)[fmt]

        with pytest.raises(TaskValidationError) as excinfo:
            parse_task(payload, strict=True)

        assert [str(i) for i in excinfo.value.issues] == [str(i) for i in qr.validate()]

    def test_lenient_parsing_still_reads_it(self):
        """Validation is a report, not a gate — reading stays lenient."""
        payload = self._bad_version_qr().to_string()

        # The converted Task declares the full format's version, not the 99
        # the payload carried; that is exactly why validating it was wrong.
        assert parse_task(payload).version == 1

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_strict_accepts_every_corpus_task_in_every_format(self, reference):
        """Strict must not reject what the spec allows, in any format."""
        qr = reference.task.to_qr_code_task()

        assert parse_task(reference.task.to_json(), strict=True).turnpoints
        for payload in self._payloads(qr).values():
            assert parse_task(payload, strict=True).turnpoints


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

    @pytest.mark.parametrize("stem", ["task_bevo", "task_noha_route"])
    def test_compressed_round_trips_to_the_same_task(self, stem):
        """Compression must be transparent: same task in, same task out."""
        reference = reference_task(stem)
        original = parse_task(reference.qr_string)
        waypoints = reference.is_waypoints_format

        qr = original.to_qr_code_task()
        compressed = (
            qr.to_waypoints_string(compressed=True)
            if waypoints
            else qr.to_string(compressed=True)
        )

        assert parse_task(compressed).to_json() == original.to_json()

    def test_compression_actually_shrinks_a_real_task(self):
        """The point of the format is fitting more task in a scannable code."""
        qr = parse_task(reference_task("task_bevo").qr_string).to_qr_code_task()

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
        from pyxctsk.qrcode.task import QRCodeTask

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


class TestEachQRShapeIsMeasuredAgainstItsOwnKeys:
    """A key one QR shape defines is unknown to the other, not understood.

    ``QRCodeTask`` used to carry a single allow-list spanning both shapes, so a
    competition key in a waypoints payload passed for a key this class reads.
    It was neither read into an attribute nor captured as unknown: ``from_dict``
    dropped it and ``to_dict`` had nothing to write back.
    """

    SOURCE = {
        "T": "W",
        "V": 2,
        "t": [{"n": "WPT1", "z": "|dz~FligrB?"}],
        "e": 1,
        "to": "09:00:00Z",
        "g": {"t": 2},
    }

    def _parsed(self):
        from pyxctsk.qrcode.task import QRCodeTask

        return QRCodeTask.from_dict(json.loads(json.dumps(self.SOURCE)))

    def test_competition_keys_are_unknown_to_the_waypoints_shape(self):
        """This shape reads none of them, so all three are carried."""
        assert self._parsed().unknown == {"e": 1, "to": "09:00:00Z", "g": {"t": 2}}

    def test_they_are_not_read_into_attributes(self):
        """Being unknown is the point — nothing may interpret them either."""
        parsed = self._parsed()

        assert (parsed.earth_model, parsed.takeoff, parsed.goal) == (None, None, None)

    def test_the_waypoints_roundtrip_keeps_them(self):
        """The whole payload comes back, which it did not before."""
        emitted = json.loads(self._parsed().to_waypoints_json())

        assert emitted == self.SOURCE

    def test_the_waypoints_keys_stay_unknown_to_the_competition_shape(self):
        """The rule runs the other way too: ``V`` is not the competition key."""
        from pyxctsk.qrcode.task import QRCodeTask

        source = {"taskType": "CLASSIC", "version": 2, "t": [], "V": 9}
        parsed = QRCodeTask.from_dict(source)

        assert parsed.version == 2
        assert parsed.unknown == {"V": 9}


class TestWaypointsTaskEncoding:
    """Findings 7 and 8 — the XC/Waypoints ``z`` carries three numbers.

    Spec: the XC/Waypoints task is a "simple route from waypoints without
    cylinders", and its ``z`` is "polyline encoded coordinates with altitude"
    — longitude, latitude, altitude. No radius.
    """

    def test_altitudes_survive_reading(self):
        """A three-number z must yield its altitude, not zero."""
        task = parse_task(reference_task("task_noha_route").qr_string)

        altitudes = [tp.waypoint.alt_smoothed for tp in task.turnpoints[:4]]
        assert altitudes == [1149, 175, 606, 1450]

    def test_no_cylinder_is_invented(self):
        """A route "without cylinders" must not acquire a radius on read."""
        task = parse_task(reference_task("task_noha_route").qr_string)

        assert all(tp.radius == 0 for tp in task.turnpoints)

    @pytest.mark.parametrize("stem", ["task_noha_route", "task_dami_route"])
    def test_roundtrip_is_byte_identical_to_xctrack(self, stem):
        """Re-encoding an XCTrack waypoints QR must reproduce it exactly.

        These fixtures were decoded from QR codes generated by
        tools.xcontest.org, so they are ground truth rather than our own output.
        """
        reference = reference_task(stem)
        task = parse_task(reference.qr_string)

        assert task.to_qr_code_task().to_waypoints_string() == reference.qr_string

    def test_competition_z_keeps_its_radius(self):
        """The four-number competition encoding must be left alone."""
        reference = reference_task("task_bevo")
        task = parse_task(reference.qr_string)

        assert task.to_qr_code_task().to_string() == reference.qr_string
        assert task.turnpoints[0].radius == 400

    def test_z_length_selects_the_format(self):
        """Three numbers means waypoints, four means competition."""
        from pyxctsk.qrcode.encoding import (
            encode_competition_turnpoint,
            encode_waypoint_turnpoint,
        )
        from pyxctsk.qrcode.models import QRCodeTurnpoint

        waypoint_z = encode_waypoint_turnpoint(8.1, 46.5, 1234)
        competition_z = encode_competition_turnpoint(8.1, 46.5, 1234, 400)

        waypoint = QRCodeTurnpoint.from_dict({"n": "X", "z": waypoint_z})
        competition = QRCodeTurnpoint.from_dict({"n": "X", "z": competition_z})

        assert (waypoint.alt_smoothed, waypoint.radius) == (1234, 0)
        assert (competition.alt_smoothed, competition.radius) == (1234, 400)
        assert competition_z.startswith(waypoint_z)


class TestGoalLineFollowsTheOptimizedRoute:
    """S7F-01: goal-line orientation, S7F 2025+ §6.2.3.1.

    *"The previous point p is defined as the optimized route point on the last
    control zone before goal."* The 2024 edition said the centre of "the last
    turn point that is different from the goal line centre" instead, which is
    what this used to implement.
    """

    def _azimuth(self, task, line):
        """Approach azimuth the line is built perpendicular to."""
        geod = geod_for_earth_model(task.earth_model)
        return geod.inv(
            line.approach_from[1],
            line.approach_from[0],
            line.center[1],
            line.center[0],
        )[0]

    @pytest.mark.parametrize(
        "name",
        [
            "task_fobe_line",
            "task_motu_line",
            "task_piga_line",
            "task_qoga_line",
            "task_quno_line",
        ],
    )
    def test_approach_is_the_optimized_route_point(self, name):
        """Every LINE-goal reference task orients against the route, not a centre."""
        task = reference_task(name).task
        measured = MeasuredTask.from_task(task)

        line = GoalLine.from_measured_task(measured)

        assert line is not None
        assert line.approach_from == measured.route.points[-2]

    def test_a_goal_inside_the_previous_cylinder_faces_the_right_way(self):
        """The case that showed the rule mattered.

        task_qoga_line's goal sits 2 259 m from the centre of a 3 000 m ESS
        cylinder — inside it. The route therefore touches that cylinder on the
        far side and arrives from the opposite direction to the one the centre
        suggests, so the 2024 rule drew the line nearly *parallel* to the real
        approach and put the control-zone semicircle behind the pilot.
        """
        task = reference_task("task_qoga_line").task

        current = GoalLine.from_task(task)
        legacy = GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)

        assert current is not None and legacy is not None
        moved = abs(
            (self._azimuth(task, current) - self._azimuth(task, legacy) + 180) % 360
            - 180
        )
        assert moved > 150.0, (
            f"expected the two editions to differ sharply, got {moved}"
        )

    def test_the_2024_rule_is_still_reachable(self):
        """Kept deliberately: it is what a task drawn before 2025 shows."""
        task = reference_task("task_qoga_line").task

        legacy = GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)

        assert legacy is not None
        previous = task.turnpoints[-2].waypoint
        assert legacy.approach_from == (previous.lat, previous.lon)

    def test_measuring_first_matches_deriving_one(self):
        """Passing a measured task is an optimization, not a different answer."""
        task = reference_task("task_fobe_line").task

        assert GoalLine.from_measured_task(MeasuredTask.from_task(task)) == (
            GoalLine.from_task(task)
        )

    def test_the_orientation_does_not_move_the_distance(self):
        """A LINE goal is a zero-radius circle either way (§7.2).

        Only the drawn shape changes; the optimized distance must not.
        """
        task = reference_task("task_qoga_line").task
        before = MeasuredTask.from_task(task).route.total_m

        GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)
        after = MeasuredTask.from_task(task).route.total_m

        assert before == after


class TestElevatedGoal:
    """S7F-06 and S7F-07: the bounds FAI S7F 2026 §6.2.3.2 puts on an elevated goal.

    The XCTrack interface spec defines ``goal.finishAltitude`` but constrains
    nothing about it, so these two rules are the only ones in
    ``model/validation.py`` sourced from the scoring code.
    """

    def _validate(self, goal, **overrides):
        """Validate BASE_TASK with a replaced goal."""
        return Task.from_json(task_json(goal=goal, **overrides)).validate()

    @pytest.mark.parametrize("altitude", [0, 300, 1000])
    def test_an_altitude_in_range_is_accepted(self, altitude):
        """Zero to 1000 m above the goal waypoint, inclusive.

        BASE_TASK marks ESS at turnpoint 1, so the goal is moved onto the ESS
        here — otherwise the *other* rule fires and this one proves nothing.
        """
        issues = self._validate(
            {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": altitude},
            turnpoints=_turnpoints_with_ess_last(),
        )

        assert issues == []

    @pytest.mark.parametrize("altitude", [-1, 1001, 5000])
    def test_an_altitude_out_of_range_is_reported(self, altitude):
        """Spec: "by default 300 m but can be increased up to 1000 m"."""
        issues = self._validate(
            {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": altitude},
            turnpoints=_turnpoints_with_ess_last(),
        )

        assert [i.rule for i in issues] == [ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE]

    def test_a_ground_level_goal_is_not_checked(self):
        """No elevated goal, no elevated-goal rules — BASE_TASK has ESS early."""
        assert Task.from_json(task_json()).validate() == []

    def test_an_elevated_goal_elsewhere_than_the_ess_is_reported(self):
        """Spec: an elevated goal "implicitly also serves as the ESS"."""
        issues = self._validate(
            {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": 300}
        )

        assert [i.rule for i in issues] == [ValidationRule.ELEVATED_GOAL_IS_NOT_ESS]
        # Both numbers are 0-based indices, and the message says so: "1 of 2"
        # read as a count, which on a three-turnpoint task is simply wrong.
        assert "turnpoint index 1, not at the goal (index 2)" in str(issues[0])

    def test_the_reference_elevated_goal_task_stays_valid(self):
        """The real task this rule was written against must not now fail."""
        task = parse_task(
            ELEVATED_GOAL_DIR.joinpath("xcontest-conformant.xctsk").read_text()
        )

        assert task.goal is not None
        assert task.goal.finish_altitude == 300
        assert task.validate() == []

    def test_the_qr_format_is_checked_too(self):
        """``g.fa`` reaches the same rule as ``goal.finishAltitude``."""
        task = Task.from_json(
            task_json(
                goal={
                    "type": "CYLINDER",
                    "deadline": "18:00:00Z",
                    "finishAltitude": 5000,
                }
            )
        )

        qr = task.to_qr_code_task()
        assert qr.goal is not None and qr.goal.finish_altitude == 5000
        assert ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE in {
            issue.rule for issue in qr.validate()
        }


def _turnpoints_with_ess_last():
    """BASE_TASK's turnpoints with ESS moved onto the goal."""
    turnpoints = json.loads(json.dumps(BASE_TASK["turnpoints"]))
    del turnpoints[1]["type"]
    turnpoints[-1]["type"] = "ESS"
    return turnpoints


class TestRouteOptimizerConformance:
    """S7F-03 and S7F-04: §7.1.6's two passes, and §7's "shortest path"."""

    def _shifted_plane(self, lat_offset, lon_offset):
        """A plane deliberately centred away from the task area."""

        def around(centers, earth_model=None):
            lat, lon = task_area_center(centers)
            return LocalPlane(
                *local_tm_transformers(lat + lat_offset, lon + lon_offset, earth_model)
            )

        return staticmethod(around)

    @pytest.mark.parametrize("name", ["task_bevo", "task_duna", "task_nohe"])
    def test_the_answer_does_not_depend_on_the_projection(self, name, monkeypatch):
        """§7 asks for *the* shortest path, so the plane must not pick which one.

        The alternating method converges to a local optimum, and before
        multi-start these three tasks each had a shorter valid route reachable
        by nothing more than moving the projection centre — `task_bevo` by
        98.6 m. Every route compared here touches every cylinder in order, so
        a shorter one is strictly better.
        """
        turnpoints = task_to_turnpoints(reference_task(name).task)
        shipped = calculate_iteratively_refined_route(turnpoints).total_m

        for lat_offset in (-0.45, 0.0, 0.45):
            for lon_offset in (-0.45, 0.0, 0.45):
                monkeypatch.setattr(
                    LocalPlane, "around", self._shifted_plane(lat_offset, lon_offset)
                )
                shifted = calculate_iteratively_refined_route(turnpoints).total_m
                monkeypatch.undo()

                assert shipped <= shifted + 0.05, (
                    f"a plane shifted by ({lat_offset}, {lon_offset}) finds a route "
                    f"{shipped - shifted:.3f} m shorter"
                )

    def test_every_route_point_touches_its_cylinder(self):
        """Whatever basin the sweep lands in, the route must still be a route.

        A shorter number is only better if it is a legal path: §7 requires each
        control zone to be touched, in order.
        """
        for reference in reference_tasks():
            turnpoints = task_to_turnpoints(reference.task)
            route = calculate_iteratively_refined_route(turnpoints)

            for i, (point, turnpoint) in enumerate(zip(route.points, turnpoints)):
                want = 0.0 if i == 0 else turnpoint.radius
                assert geodesic_distance(turnpoint.center, point) == pytest.approx(
                    want, abs=0.01
                ), f"{reference.stem} turnpoint {i}"

    def test_the_plane_is_rebuilt_from_the_corrected_path(self, monkeypatch):
        """§7.1.6 runs PathFinder twice, the second time on the found path.

        "boundingBox_final = FindBoundingBox(correctedPath)" — so the centre
        the spec says to keep comes from the route, not from the turnpoints
        that produced it.
        """
        seen = []
        real = LocalPlane.around.__func__  # type: ignore[attr-defined]

        def spy(centers, earth_model=None):
            seen.append(list(centers))
            return real(LocalPlane, centers, earth_model)

        monkeypatch.setattr(LocalPlane, "around", staticmethod(spy))
        turnpoints = task_to_turnpoints(reference_task("task_bevo").task)
        route = calculate_iteratively_refined_route(turnpoints)

        assert len(seen) == 2, "the optimizer must build two planes, not one"
        assert seen[0] == [tp.center for tp in turnpoints]
        # The second plane is centred on the first pass's corrected path: its
        # points sit on cylinder boundaries, so they are not the centres.
        assert seen[1] != seen[0]
        assert len(seen[1]) == len(route.points)

    def test_a_second_pass_plane_differs_from_a_turnpoint_plane(self):
        """The two bounding boxes are genuinely different, so the pass is not a no-op."""
        turnpoints = task_to_turnpoints(reference_task("task_bevo").task)
        route = calculate_iteratively_refined_route(turnpoints)

        from_turnpoints = task_area_center([tp.center for tp in turnpoints])
        from_path = task_area_center(list(route.points))

        assert from_turnpoints != from_path


class TestS7FShapesTheFormatCannotCarry:
    """S7F-09: two 2026 features the XCTrack format has no keys for.

    §6.2.1 gives every turnpoint cylinder an optional upper and lower altitude
    limit in metres AMSL, and §6.2.2 defines a line control zone anywhere in a
    task. XCTrack's format defines neither, so pyxctsk cannot promote them to
    model fields without inventing keys for a format that is not ours — and a
    reader would then be free to write them back out as though they were spec.

    What *is* in our hands is that a producer sending such keys does not lose
    them. These pin that: the passthrough carries them verbatim through both
    formats, and never interprets them.
    """

    def _with_turnpoint_keys(self, **extra):
        """BASE_TASK with extra non-spec keys on its first turnpoint."""
        data = json.loads(task_json())
        data["turnpoints"][0].update(extra)
        return Task.from_dict(data)

    def test_altitude_limits_survive_the_json_round_trip(self):
        """§6.2.1's limits are carried, not dropped."""
        task = self._with_turnpoint_keys(altitudeMin=500, altitudeMax=3000)

        assert task.turnpoints[0].unknown == {
            "altitudeMin": 500,
            "altitudeMax": 3000,
        }
        exported = json.loads(task.to_json())["turnpoints"][0]
        assert exported["altitudeMin"] == 500
        assert exported["altitudeMax"] == 3000

    def test_altitude_limits_survive_the_qr_round_trip(self):
        """Including across the format seam, where unknown keys are re-homed."""
        task = self._with_turnpoint_keys(altitudeMin=500, altitudeMax=3000)

        back = task.to_qr_code_task().to_task()

        assert back.turnpoints[0].unknown == {
            "altitudeMin": 500,
            "altitudeMax": 3000,
        }

    def test_the_limits_are_never_interpreted(self):
        """Carried is not understood: nothing reads them as a real constraint.

        A cylinder with altitude limits is the same cylinder to the optimizer
        — S7F applies the limits when validating a *tracklog* crossing
        (§9.2.1), which is not something this library does.
        """
        plain = Task.from_json(task_json())
        limited = self._with_turnpoint_keys(altitudeMin=500, altitudeMax=3000)

        assert optimized_distance(task_to_turnpoints(limited)) == pytest.approx(
            optimized_distance(task_to_turnpoints(plain))
        )
        assert limited.validate() == []

    def test_a_line_control_zone_is_carried_the_same_way(self):
        """§6.2.2's parameters have no home either, and are not invented one."""
        task = self._with_turnpoint_keys(
            lineDistance=5.0, lineOrientation="NE", lineLength=1.0
        )

        exported = json.loads(task.to_json())["turnpoints"][0]

        assert exported["lineOrientation"] == "NE"
        # And nothing has quietly become a goal line.
        assert task.goal is not None and task.goal.type is GoalType.CYLINDER


class TestUnrecognizedInputSaysWhy:
    """One message for every failure hid a missing install as a corrupt file.

    `InvalidFormatError("invalid format")` was raised for a nonexistent path, a
    directory, truncated JSON, a PNG carrying no QR code — and for a perfectly
    good QR image on a machine without Pillow and zxing-cpp, because the
    adapter returns None when the optional dependencies are absent.
    """

    def test_a_missing_file_says_so(self):
        """The path case was lost when _read_file swallowed the OSError."""
        with pytest.raises(InvalidFormatError, match="No such file or directory"):
            parse_task("/no/such/task.xctsk")

    def test_a_directory_says_so(self, tmp_path):
        """A different OS error, reported as itself."""
        with pytest.raises(InvalidFormatError, match="Is a directory"):
            parse_task(f"{tmp_path}/")

    def test_truncated_json_is_named_as_json(self):
        """It parsed as far as being JSON-shaped; that is worth saying."""
        with pytest.raises(InvalidFormatError, match="looks like JSON"):
            parse_task('{"taskType": "CLASSIC", "vers')

    def test_an_image_with_no_qr_code_says_so(self, tmp_path):
        """Not "invalid format": the file was read, it just carries no task."""
        png = tmp_path / "blank.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

        with pytest.raises(InvalidFormatError, match="no XCTSK: QR code"):
            parse_task(str(png))

    def test_a_missing_dependency_is_not_reported_as_a_bad_file(
        self, tmp_path, monkeypatch
    ):
        """The failure that most needed telling apart, and could not be."""
        png = tmp_path / "task.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        monkeypatch.setattr(parser, "QR_CODE_SUPPORT", False)

        with pytest.raises(
            InvalidFormatError, match="QR code support is not installed"
        ):
            parse_task(str(png))

    def test_inline_json_containing_a_slash_still_parses(self):
        """The path heuristic matches it, so the fallthrough must survive.

        `_looks_like_file_path` is `"/" in data`, so a waypoint name with a
        slash trips it. Reading has to stay non-fatal.
        """
        task = parse_task(
            json.dumps(
                {
                    "taskType": "CLASSIC",
                    "version": 1,
                    "turnpoints": [
                        {
                            "radius": 400,
                            "waypoint": {
                                "name": "A/B",
                                "lat": 46.5,
                                "lon": 8.0,
                                "altSmoothed": 100,
                            },
                        }
                    ],
                }
            )
        )

        assert task.turnpoints[0].waypoint.name == "A/B"

    def test_unrecognized_bytes_still_fall_back_to_the_plain_message(self):
        """Nothing to say beyond "not a format I know"."""
        with pytest.raises(InvalidFormatError, match="invalid format"):
            parse_task(b"\x00\x01\x02\x03")
