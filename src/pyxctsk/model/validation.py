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

The rules read exactly two things — the order of the turnpoint roles, and
whether this is a waypoints task — so :func:`validate_turnpoint_roles` takes
those and nothing else. That is what lets a QR payload be checked *as it
arrived*: converting it to a ``Task`` first invents a version, a task type and
a goal the payload never carried, and validating inventions reports on the
converter rather than on the input. :func:`validate_task` is the adapter for
the full format and :meth:`pyxctsk.QRCodeTask.validate` for the compact one.
"""

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Sequence

from .enums import TaskType, TurnpointType

if TYPE_CHECKING:
    from .task import Task


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
    """

    NO_TURNPOINTS = "NO_TURNPOINTS"
    TAKEOFF_NOT_FIRST = "TAKEOFF_NOT_FIRST"
    SPECIAL_NOT_ONCE = "SPECIAL_NOT_ONCE"
    SSS_AFTER_ESS = "SSS_AFTER_ESS"


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


def validate_turnpoint_roles(
    roles: Sequence[TurnpointType | None], is_waypoints_task: bool
) -> list[ValidationIssue]:
    """Check the arrangement of special turnpoints against the spec.

    The rules, quoting the spec:

    - ``TAKEOFF`` "can be used only for the first turnpoint";
    - ``SSS`` and ``ESS`` "must appear exactly once";
    - ``SSS`` "must appear before ESS".

    These apply to CLASSIC tasks. An XC/Waypoints task is a plain route with no
    speed section, so the SSS/ESS rules are not checked for it.

    Both task formats can answer what this reads, which is why it takes roles
    rather than a task: neither format has to be turned into the other, and no
    default has to be invented, before its structure can be checked.

    Args:
        roles: The turnpoints' types, in task order. None for an ordinary one.
        is_waypoints_task: Whether this is an XC/Waypoints task.

    Returns:
        list[ValidationIssue]: One issue per violated rule, empty if valid.
    """
    if not roles:
        return [ValidationIssue(ValidationRule.NO_TURNPOINTS, "task has no turnpoints")]

    issues = [
        ValidationIssue(
            ValidationRule.TAKEOFF_NOT_FIRST,
            f"TAKEOFF is only allowed on the first turnpoint, found at index {i}",
        )
        for i, role in enumerate(roles)
        if role == TurnpointType.TAKEOFF and i != 0
    ]

    if is_waypoints_task:
        return issues

    indices = {
        special: [i for i, role in enumerate(roles) if role == special]
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


def validate_task(task: "Task") -> list[ValidationIssue]:
    """Check a task against the spec's structural rules.

    The full format's adapter onto :func:`validate_turnpoint_roles`.

    Args:
        task: The task to check.

    Returns:
        list[ValidationIssue]: One issue per violated rule, empty if valid.
    """
    return validate_turnpoint_roles(
        [tp.type for tp in task.turnpoints],
        is_waypoints_task=task.task_type == TaskType.WAYPOINTS,
    )
