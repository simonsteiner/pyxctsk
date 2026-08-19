"""The spec's structural rules for a task, and the issues they report.

The XCTrack Competition Interfaces spec constrains how the special turnpoint
types may be arranged. Those rules live here rather than on ``Task`` so that
adding one means editing a rule, not a method on the domain model — and so the
model does not have to carry the vocabulary of its own diagnostics.

This module imports only :mod:`~pyxctsk.model.enums`, never ``task`` itself, so there is
no cycle: it is reached through :meth:`pyxctsk.Task.validate`.

Validation is a report, not a gate. Parsing accepts structurally invalid tasks
so a malformed file can still be read, inspected and converted; pass
``strict=True`` to :func:`pyxctsk.parse_task` to turn violations into a
:class:`~pyxctsk.exceptions.TaskValidationError`.

The rules read a :class:`TaskStructure` and nothing else — the turnpoint roles
and radii, the extensions at both levels, the declared version and the version
the format defines, whether this is a waypoints task, and the elevated goal's
height. That is what lets a QR payload be checked *as it arrived*: converting
it to a ``Task`` first invents a version, a task type and a goal the payload
never carried, and validating inventions reports on the converter rather than
on the input. :func:`validate_structure` applies the rules;
:func:`validate_task` is the adapter for the full format and
:meth:`pyxctsk.QRCodeTask.validate` for the compact one, and
:func:`pyxctsk.parse_task` asks the arrived payload rather than its conversion.

Widening that input from "the turnpoint roles" to a whole structure is what
let four later rules reach both formats without either adapter being touched.
"""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, Sequence

from .enums import TaskType, TurnpointType

if TYPE_CHECKING:
    from .task import Task

#: The version the full JSON task format declares. The QR format says 2.
FULL_FORMAT_VERSION = 1

#: How far above the goal waypoint an elevated goal may sit, in metres.
#: FAI S7F 2026 §6.2.3.2: "The elevation above goal is by default 300 m but can
#: be increased up to 1000 m for each task." Zero is the floor because the
#: field is a height *above* the goal; a ground-level goal omits it entirely.
MAX_FINISH_ALTITUDE_M = 1000.0


class ValidationRule(str, Enum):
    """The structural rules a task can break.

    Naming each rule lets a caller react to a specific violation without
    matching on the English message, which is free to change.

    Attributes:
        NO_TURNPOINTS (str): The task has no turnpoints at all.
        TAKEOFF_NOT_FIRST (str): "TAKEOFF type can be used only for the first
            turnpoint."
        SPECIAL_NOT_ONCE (str): "SSS and ESS turnpoints must appear exactly
            once."
        SSS_AFTER_ESS (str): "SSS turnpoint must appear before ESS."
        NEGATIVE_RADIUS (str): A cylinder cannot have a negative radius. Zero
            is legitimate — every XC/Waypoints turnpoint has it, and it means
            the point itself.
        UNKNOWN_VERSION (str): The task declares a version this format does not
            define.
        EXTENSION_WITHOUT_ROOT (str): "Turnpoint extensions must be in the same
            order as the root ones" — so a turnpoint carrying more of them than
            the root list has entries has some that correspond to nothing.
        EXTENSION_REPEATS_ID (str): A turnpoint extension repeats the ``id``
            key, which the spec says belongs to the root entry alone.
        FINISH_ALTITUDE_OUT_OF_RANGE (str): An elevated goal sits further above
            the goal waypoint than FAI S7F 2026 §6.2.3.2 allows.
        ELEVATED_GOAL_IS_NOT_ESS (str): The task declares an elevated goal *and*
            an ESS somewhere other than the goal, which §6.2.3.2 says cannot
            both be true.
    """

    NO_TURNPOINTS = "NO_TURNPOINTS"
    TAKEOFF_NOT_FIRST = "TAKEOFF_NOT_FIRST"
    SPECIAL_NOT_ONCE = "SPECIAL_NOT_ONCE"
    SSS_AFTER_ESS = "SSS_AFTER_ESS"
    NEGATIVE_RADIUS = "NEGATIVE_RADIUS"
    UNKNOWN_VERSION = "UNKNOWN_VERSION"
    EXTENSION_WITHOUT_ROOT = "EXTENSION_WITHOUT_ROOT"
    EXTENSION_REPEATS_ID = "EXTENSION_REPEATS_ID"
    FINISH_ALTITUDE_OUT_OF_RANGE = "FINISH_ALTITUDE_OUT_OF_RANGE"
    ELEVATED_GOAL_IS_NOT_ESS = "ELEVATED_GOAL_IS_NOT_ESS"


@dataclass(frozen=True)
class ValidationIssue:
    """One violated structural rule.

    ``str()`` gives the message, so an issue drops into a f-string or a
    ``"; ".join(...)`` wherever a plain string used to be.

    Attributes:
        rule (ValidationRule): Which rule was broken.
        message (str): Human-readable detail, including the turnpoint indices
            involved.
    """

    rule: ValidationRule
    message: str

    def __str__(self) -> str:
        """Return the human-readable message."""
        return self.message


@dataclass(frozen=True)
class TaskStructure:
    """What the spec's structural rules read, in either format.

    The rules do not need a task — they need the handful of facts below, and
    both formats can present them without being turned into the other. That is
    what makes a QR payload checkable *as it arrived*: converting it first
    invents a version, a task type and a goal it never carried, so a report on
    the conversion is partly a report on the converter.

    Attributes:
        roles: The turnpoints' types, in task order. None for an ordinary one.
        radii: The turnpoints' cylinder radii, in the same order.
        turnpoint_extensions: Each turnpoint's opaque extensions list, in the
            same order again.
        root_extensions: The task's own extensions list, whose order the
            turnpoint ones must follow.
        version: The version the payload declares.
        expected_version: The version this format defines — 1 for the full
            JSON format, 2 for the QR one. Carried rather than assumed, so the
            rule is stated once for both.
        is_waypoints_task: Whether this is an XC/Waypoints task, which has no
            speed section to constrain.
        finish_altitude: The elevated goal's height above the goal waypoint in
            metres, or None for a ground-level goal. Both formats carry it —
            ``goal.finishAltitude`` in the full one, ``g.fa`` in the QR one.
    """

    roles: Sequence[TurnpointType | None]
    radii: Sequence[float]
    turnpoint_extensions: Sequence[Sequence[Any]]
    root_extensions: Sequence[Any]
    version: int
    expected_version: int
    is_waypoints_task: bool
    finish_altitude: float | None = None


def validate_structure(structure: TaskStructure) -> list[ValidationIssue]:
    """Check a task's structure against the spec's rules.

    The rules, quoting the spec:

    - ``TAKEOFF`` "can be used only for the first turnpoint";
    - ``SSS`` and ``ESS`` "must appear exactly once";
    - ``SSS`` "must appear before ESS";
    - turnpoint extensions are "in the same order as the root extensions" with
      the ``id`` "not repeated";
    - an elevated goal sits at most 1000 m above the goal waypoint, and
      "implicitly also serves as the End of Speed Section" (FAI S7F 2026
      §6.2.3.2 — the only rule here that comes from the scoring code rather
      than the interface spec, because it is the only one the interface spec
      leaves unconstrained).

    The speed-section rules apply to CLASSIC tasks only; an XC/Waypoints task
    is a plain route without one.

    Args:
        structure: What the rules read, presented by either format.

    Returns:
        list[ValidationIssue]: One issue per violated rule, empty if valid.
    """
    if not structure.roles:
        return [ValidationIssue(ValidationRule.NO_TURNPOINTS, "task has no turnpoints")]

    issues = _turnpoint_role_issues(structure)
    issues += _radius_issues(structure)
    issues += _version_issues(structure)
    issues += _extension_issues(structure)
    issues += _elevated_goal_issues(structure)
    return issues


def _turnpoint_role_issues(structure: TaskStructure) -> list[ValidationIssue]:
    """Return issues about where the special turnpoint types sit."""
    issues = [
        ValidationIssue(
            ValidationRule.TAKEOFF_NOT_FIRST,
            f"TAKEOFF is only allowed on the first turnpoint, found at index {i}",
        )
        for i, role in enumerate(structure.roles)
        if role == TurnpointType.TAKEOFF and i != 0
    ]

    if structure.is_waypoints_task:
        return issues

    indices = {
        special: [i for i, role in enumerate(structure.roles) if role == special]
        for special in (TurnpointType.SSS, TurnpointType.ESS)
    }
    for special, found in indices.items():
        if len(found) != 1:
            issues.append(
                ValidationIssue(
                    ValidationRule.SPECIAL_NOT_ONCE,
                    f"{special.value} must appear exactly once, found {len(found)}",
                )
            )

    sss, ess = indices[TurnpointType.SSS], indices[TurnpointType.ESS]
    if len(sss) == 1 and len(ess) == 1 and sss[0] > ess[0]:
        issues.append(
            ValidationIssue(
                ValidationRule.SSS_AFTER_ESS,
                f"SSS must appear before ESS, found SSS at {sss[0]} "
                f"and ESS at {ess[0]}",
            )
        )

    return issues


def _radius_issues(structure: TaskStructure) -> list[ValidationIssue]:
    """Return issues about impossible cylinder sizes.

    Zero is not one of them: an XC/Waypoints turnpoint has radius 0, and the
    optimizer reads that as the point itself.
    """
    return [
        ValidationIssue(
            ValidationRule.NEGATIVE_RADIUS,
            f"turnpoint {i} has a negative radius ({radius})",
        )
        for i, radius in enumerate(structure.radii)
        if radius < 0
    ]


def _version_issues(structure: TaskStructure) -> list[ValidationIssue]:
    """Return an issue if the payload declares a version this format lacks."""
    if structure.version == structure.expected_version:
        return []
    return [
        ValidationIssue(
            ValidationRule.UNKNOWN_VERSION,
            f"this format defines version {structure.expected_version}, "
            f"the task declares {structure.version}",
        )
    ]


def _extension_issues(structure: TaskStructure) -> list[ValidationIssue]:
    """Return issues about how manufacturer extensions are arranged.

    Only the checkable half of the ordering rule. Turnpoint extensions carry
    no ``id``, so nothing identifies which root entry one belongs to except
    its position — which is exactly why the spec fixes the order, and why a
    turnpoint with more of them than the root list has entries is broken.
    """
    issues = []
    for i, extensions in enumerate(structure.turnpoint_extensions):
        if len(extensions) > len(structure.root_extensions):
            issues.append(
                ValidationIssue(
                    ValidationRule.EXTENSION_WITHOUT_ROOT,
                    f"turnpoint {i} has {len(extensions)} extensions but the "
                    f"root list has {len(structure.root_extensions)}, so some "
                    f"correspond to nothing",
                )
            )
        for extension in extensions:
            if isinstance(extension, dict) and "id" in extension:
                issues.append(
                    ValidationIssue(
                        ValidationRule.EXTENSION_REPEATS_ID,
                        f"turnpoint {i} repeats the extension id "
                        f"{extension['id']!r}, which belongs to the root entry",
                    )
                )
    return issues


def _elevated_goal_issues(structure: TaskStructure) -> list[ValidationIssue]:
    """Return issues about an elevated goal (FAI S7F 2026 §6.2.3.2).

    Two rules, both about a field the XCTrack interface spec defines but puts
    no bounds on — the bounds are the scoring code's:

    - the elevation is a height above the goal waypoint between 0 and
      :data:`MAX_FINISH_ALTITUDE_M`;
    - an elevated goal "implicitly also serves as the End of Speed Section",
      so a task that also marks an *earlier* turnpoint as ESS says two
      different things about where race time is taken.

    The second is reported rather than resolved. Deciding that the elevated
    goal wins would make :meth:`Task.is_ess_goal` disagree with the ``ESS``
    the file actually carries, and this module's job is to report what
    arrived, not to pick a reading of it.
    """
    if structure.finish_altitude is None:
        return []

    issues = []
    if not 0.0 <= structure.finish_altitude <= MAX_FINISH_ALTITUDE_M:
        issues.append(
            ValidationIssue(
                ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE,
                f"an elevated goal may sit 0 to {MAX_FINISH_ALTITUDE_M:.0f} m "
                f"above the goal waypoint, the task declares "
                f"{structure.finish_altitude}",
            )
        )

    if structure.is_waypoints_task:
        return issues

    last = len(structure.roles) - 1
    ess = [i for i, role in enumerate(structure.roles) if role == TurnpointType.ESS]
    if ess and ess != [last]:
        issues.append(
            ValidationIssue(
                ValidationRule.ELEVATED_GOAL_IS_NOT_ESS,
                f"an elevated goal is itself the ESS, but the task marks ESS "
                f"at turnpoint index {ess[0]}, not at the goal "
                f"(index {last})",
            )
        )

    return issues


def validate_task(task: "Task") -> list[ValidationIssue]:
    """Check a task against the spec's structural rules.

    The full format's adapter onto :func:`validate_structure`.

    Args:
        task: The task to check.

    Returns:
        list[ValidationIssue]: One issue per violated rule, empty if valid.
    """
    return validate_structure(
        TaskStructure(
            roles=[tp.type for tp in task.turnpoints],
            radii=[tp.radius for tp in task.turnpoints],
            turnpoint_extensions=[tp.extensions for tp in task.turnpoints],
            root_extensions=task.extensions,
            version=task.version,
            expected_version=FULL_FORMAT_VERSION,
            is_waypoints_task=task.task_type == TaskType.WAYPOINTS,
            finish_altitude=task.goal.finish_altitude if task.goal else None,
        )
    )
