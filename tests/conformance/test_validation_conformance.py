"""Structural and strict-validation conformance regressions.

Derived from docs/arch-review/2026-08-16-competition-interfaces-audit.md.
Each test keeps the finding and specification provenance that it pins.
"""

import json

import pytest

from pyxctsk import (
    Task,
    TaskType,
    TaskValidationError,
    TurnpointType,
    parse_task,
)
from pyxctsk.model.validation import ValidationRule
from tests.conformance._support import task_json
from tests.corpus import reference_task, reference_tasks


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
