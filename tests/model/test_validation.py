"""The spec's structural rules, tested through the value they read.

A 352-line module with no test file of its own: its rules were covered only
through the two format adapters, in `tests/conformance/` and `tests/qrcode/`.
That left `TaskStructure` and `validate_structure` never named directly, so a
third format had no worked example of what presenting one means — and the one
field carrying a default had nothing checking that both adapters set it.

These test the rules where they live. The adapters keep their own tests: this
file is about what a structure has to say, not about how a format says it.
"""

import pytest

from pyxctsk import GoalType, TaskType, TurnpointType
from pyxctsk.model.validation import (
    FULL_FORMAT_VERSION,
    MAX_FINISH_ALTITUDE_M,
    TaskStructure,
    ValidationRule,
    validate_structure,
    validate_task,
)
from tests.builders import task, turnpoint


def structure(
    *roles: TurnpointType | None,
    radii: list[float] | None = None,
    turnpoint_extensions: list[list[object]] | None = None,
    root_extensions: list[object] | None = None,
    version: int = FULL_FORMAT_VERSION,
    expected_version: int = FULL_FORMAT_VERSION,
    is_waypoints_task: bool = False,
    finish_altitude: float | None = None,
) -> TaskStructure:
    """A structure of these turnpoint roles, everything else defaulted valid.

    Building one directly is the point: the rules read a structure and nothing
    else, so a test of a rule need not invent a task in either format.
    """
    count = len(roles)
    return TaskStructure(
        roles=list(roles),
        radii=radii if radii is not None else [400.0] * count,
        turnpoint_extensions=(
            turnpoint_extensions if turnpoint_extensions is not None else [[]] * count
        ),
        root_extensions=root_extensions if root_extensions is not None else [],
        version=version,
        expected_version=expected_version,
        is_waypoints_task=is_waypoints_task,
        finish_altitude=finish_altitude,
    )


def rules_of(built: TaskStructure) -> list[ValidationRule]:
    """The rules a structure breaks, in the order reported."""
    return [issue.rule for issue in validate_structure(built)]


class TestTheStructureIsTheWholeInput:
    """The rules read a `TaskStructure` and nothing else."""

    def test_a_well_formed_race_passes(self):
        """The baseline every other case is a mutation of."""
        built = structure(
            TurnpointType.TAKEOFF, TurnpointType.SSS, None, TurnpointType.ESS
        )

        assert validate_structure(built) == []

    def test_no_turnpoints_is_reported(self):
        """An empty task is not a task."""
        assert rules_of(structure()) == [ValidationRule.NO_TURNPOINTS]

    def test_a_structure_needs_no_task_in_either_format(self):
        """Which is what lets a QR payload be checked as it arrived."""
        built = structure(
            None, TurnpointType.TAKEOFF, TurnpointType.SSS, TurnpointType.ESS
        )

        assert rules_of(built) == [ValidationRule.TAKEOFF_NOT_FIRST]


class TestTurnpointRoles:
    """TAKEOFF first, SSS and ESS once each, SSS before ESS."""

    def test_takeoff_must_be_first(self):
        """The spec: TAKEOFF is allowed only on the first turnpoint."""
        built = structure(
            None, TurnpointType.TAKEOFF, TurnpointType.SSS, TurnpointType.ESS
        )

        assert ValidationRule.TAKEOFF_NOT_FIRST in rules_of(built)

    def test_takeoff_first_is_fine(self):
        """The position the spec allows."""
        built = structure(TurnpointType.TAKEOFF, TurnpointType.SSS, TurnpointType.ESS)

        assert rules_of(built) == []

    @pytest.mark.parametrize("role", [TurnpointType.SSS, TurnpointType.ESS])
    def test_a_special_role_twice_is_reported(self, role):
        """The spec: SSS and ESS must appear exactly once."""
        other = TurnpointType.ESS if role is TurnpointType.SSS else TurnpointType.SSS
        built = structure(TurnpointType.TAKEOFF, role, role, other)

        assert ValidationRule.SPECIAL_NOT_ONCE in rules_of(built)

    def test_a_missing_role_is_reported(self):
        """Exactly once means once, not at most once — so absent counts too."""
        built = structure(TurnpointType.TAKEOFF, TurnpointType.SSS, None)

        assert ValidationRule.SPECIAL_NOT_ONCE in rules_of(built)

    def test_the_sss_must_come_before_the_ess(self):
        """A speed section cannot end before it starts."""
        built = structure(TurnpointType.TAKEOFF, TurnpointType.ESS, TurnpointType.SSS)

        assert ValidationRule.SSS_AFTER_ESS in rules_of(built)

    def test_a_waypoints_task_is_exempt_from_the_speed_section_rules(self):
        """It is "a simple route from waypoints", with no speed section at all.

        This is the exemption `distance/speed_section.py` reads as its own
        rule, and the one `center_distance` was missing.
        """
        built = structure(TurnpointType.ESS, TurnpointType.SSS, is_waypoints_task=True)

        assert ValidationRule.SSS_AFTER_ESS not in rules_of(built)
        assert ValidationRule.SPECIAL_NOT_ONCE not in rules_of(built)


class TestRadii:
    """Negative is impossible; zero is legitimate."""

    def test_a_negative_radius_is_reported(self):
        """A cylinder cannot have a negative radius."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            radii=[400.0, 400.0, -1.0],
        )

        assert ValidationRule.NEGATIVE_RADIUS in rules_of(built)

    def test_zero_is_valid(self):
        """Every XC/Waypoints turnpoint has one, and it means the point itself."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            radii=[0.0, 0.0, 0.0],
        )

        assert ValidationRule.NEGATIVE_RADIUS not in rules_of(built)


class TestTheVersionIsCarried:
    """Each format declares its own, so the rule is stated once for both."""

    def test_the_declared_version_must_match_the_formats(self):
        """1 for the full JSON format, 2 for the QR one."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            version=99,
            expected_version=1,
        )

        assert ValidationRule.UNKNOWN_VERSION in rules_of(built)

    def test_the_qr_formats_version_is_valid_when_that_is_what_is_expected(self):
        """The same number is right or wrong depending on the format."""
        assert ValidationRule.UNKNOWN_VERSION not in rules_of(
            structure(
                TurnpointType.TAKEOFF,
                TurnpointType.SSS,
                TurnpointType.ESS,
                version=2,
                expected_version=2,
            )
        )
        assert ValidationRule.UNKNOWN_VERSION in rules_of(
            structure(
                TurnpointType.TAKEOFF,
                TurnpointType.SSS,
                TurnpointType.ESS,
                version=2,
                expected_version=1,
            )
        )


class TestExtensionOrdering:
    """Only the checkable half: position is what links one to a root entry."""

    def test_more_turnpoint_extensions_than_root_entries_is_reported(self):
        """There is nothing for the extra one to correspond to."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            turnpoint_extensions=[[{"a": "1"}, {"b": "2"}], [], []],
            root_extensions=[{"id": "ACME"}],
        )

        assert ValidationRule.EXTENSION_WITHOUT_ROOT in rules_of(built)

    def test_a_turnpoint_extension_repeating_the_root_id_is_reported(self):
        """The spec says the id is "not repeated"."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            turnpoint_extensions=[[{"id": "ACME"}], [], []],
            root_extensions=[{"id": "ACME"}],
        )

        assert ValidationRule.EXTENSION_REPEATS_ID in rules_of(built)

    def test_a_matching_pair_without_the_id_is_fine(self):
        """One root entry, one turnpoint entry, position doing the linking."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            turnpoint_extensions=[[{"a": "1"}], [], []],
            root_extensions=[{"id": "ACME"}],
        )

        assert rules_of(built) == []


class TestTheElevatedGoal:
    """§6.2.3.2's two constraints, both checked from the structure."""

    def test_above_the_ceiling_is_reported(self):
        """The spec: "can be increased up to 1000 m for each task"."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            finish_altitude=MAX_FINISH_ALTITUDE_M + 1,
        )

        assert ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE in rules_of(built)

    def test_the_ceiling_itself_is_allowed(self):
        """The spec says "up to", which includes it."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            finish_altitude=MAX_FINISH_ALTITUDE_M,
        )

        assert ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE not in rules_of(built)

    def test_a_negative_height_is_reported(self):
        """The field is a height *above* the goal; a ground-level goal omits it."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            finish_altitude=-1.0,
        )

        assert ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE in rules_of(built)

    def test_an_elevated_goal_that_is_not_the_ess_is_reported(self):
        """The spec makes an elevated goal implicitly the ESS."""
        built = structure(
            TurnpointType.TAKEOFF,
            TurnpointType.SSS,
            TurnpointType.ESS,
            None,
            finish_altitude=300.0,
        )

        assert ValidationRule.ELEVATED_GOAL_IS_NOT_ESS in rules_of(built)

    def test_no_elevated_goal_reports_neither_rule(self):
        """None is a ground-level goal, not a zero-height one."""
        built = structure(TurnpointType.TAKEOFF, TurnpointType.SSS, TurnpointType.ESS)

        assert rules_of(built) == []


class TestTheFullFormatAdapter:
    """`validate_task` presents a `TaskStructure`; this checks it presents all of it.

    `finish_altitude` is the only field with a default and was the most
    recently added, so a future defaulted field could silently be dropped by
    one adapter. These pin that each field reaches the rules from a real task.
    """

    def test_it_carries_the_roles(self):
        """The oldest field, and the one every other rule sits beside."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400),
            turnpoint("B", 46.5, 8.5, radius=400, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.2, 8.2, radius=400, type=TurnpointType.SSS),
            turnpoint("G", 46.7, 8.7, radius=400, type=TurnpointType.ESS),
        )

        assert [i.rule for i in validate_task(built)] == [
            ValidationRule.TAKEOFF_NOT_FIRST
        ]

    def test_it_carries_the_radii(self):
        """A negative radius on a real task reaches the rule."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=-5, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.2, 8.2, radius=400, type=TurnpointType.SSS),
            turnpoint("G", 46.5, 8.5, radius=400, type=TurnpointType.ESS),
        )

        assert ValidationRule.NEGATIVE_RADIUS in [i.rule for i in validate_task(built)]

    def test_it_carries_the_version(self):
        """The full format declares 1."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.2, 8.2, radius=400, type=TurnpointType.SSS),
            turnpoint("G", 46.5, 8.5, radius=400, type=TurnpointType.ESS),
        )
        built.version = 7

        assert ValidationRule.UNKNOWN_VERSION in [i.rule for i in validate_task(built)]

    def test_it_carries_the_waypoints_exemption(self):
        """Otherwise a waypoints task would be reported for its missing SSS."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=0),
            turnpoint("B", 46.5, 8.5, radius=0),
        )
        built.task_type = TaskType.WAYPOINTS

        assert validate_task(built) == []

    def test_it_carries_the_finish_altitude(self):
        """The field with a default — the one a new adapter is likeliest to drop."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.2, 8.2, radius=400, type=TurnpointType.SSS),
            turnpoint("G", 46.5, 8.5, radius=400, type=TurnpointType.ESS),
            goal=GoalType.CYLINDER,
        )
        assert built.goal is not None
        built.goal.finish_altitude = MAX_FINISH_ALTITUDE_M + 500

        assert ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE in [
            i.rule for i in validate_task(built)
        ]

    def test_every_field_of_the_structure_is_set_by_the_adapter(self):
        """A field the adapter forgets defaults to something harmless and hides.

        Read structurally rather than by outcome, so a *new* field is caught
        even before a rule reads it.
        """
        import ast
        import inspect

        source = inspect.getsource(validate_task)
        call = next(
            node
            for node in ast.walk(ast.parse(source.strip()))
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", None) == "TaskStructure"
        )
        passed = {kw.arg for kw in call.keywords}

        assert passed == set(TaskStructure.__dataclass_fields__)
