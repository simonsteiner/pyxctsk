"""XCTrack's task, ``Task``, and its serialization to and from the full JSON format.

``Task`` is a plain dataclass built from the parts defined in ``task_parts`` —
``Turnpoint``, ``Waypoint``, ``Takeoff``, ``SSS`` and ``Goal`` — which are
re-exported here for callers. It is not frozen, it does not validate on
construction, and **nothing derived is stored on it** — including the goal's
default, which is :attr:`Task.effective_goal` rather than something
``__post_init__`` writes back onto :attr:`Task.goal`. A task therefore
serializes to what it was read from, with no key invented along the way.

Neighbouring modules hold what this one deliberately does not:
  - ``task_parts`` — the dataclasses and field tables of a task's parts
  - ``enums`` — the constrained values (``TaskType``, ``TurnpointType``, …),
    re-exported here for callers
  - ``validation`` — the spec's structural rules, reached via ``Task.validate()``
  - ``qrcode.conversion`` — the mapping to and from the compact QR format
  - ``time_of_day`` — ``TimeOfDay``, shared with the QR models
"""

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, ClassVar

from .codec import INTEGER, enum_codec, list_codec

# The enums are re-exported: they are part of task.py's public surface and
# callers import them from here. They live in their own module so validation.py
# can use them without importing the model it checks.
from .enums import (  # noqa: F401
    OBSOLETE_DIRECTION_DEFAULT,
    Direction,
    EarthModel,
    GoalType,
    SSSType,
    TaskType,
    TurnpointType,
)
from .json_io import dump_json, load_json
from .passthrough import EXTENSIONS_KEY
from .shape import REQUIRED, Shape, Value, shape_codec

# The parts are re-exported: callers import them from here, as they did when
# they were defined in this module. The ``*_SHAPE`` tables are here for
# ``TASK_SHAPE`` and are not part of that surface.
from .task_parts import (  # noqa: F401
    GOAL_SHAPE,
    SSS,
    SSS_SHAPE,
    TAKEOFF_SHAPE,
    TURNPOINT_SHAPE,
    Goal,
    Takeoff,
    Turnpoint,
    Waypoint,
)
from .validation import ValidationIssue, validate_task

if TYPE_CHECKING:
    from ..qrcode.task import QRCodeTask


@dataclass
class Task:
    """Represents an XCTrack task, including turnpoints and settings.

    Attributes:
        task_type (TaskType): Type of the task.
        version (int): Task format version.
        turnpoints (List[Turnpoint]): List of turnpoints.
        earth_model (Optional[EarthModel]): Earth model used.
        takeoff (Optional[Takeoff]): Takeoff window.
        sss (Optional[SSS]): Start of speed section.
        goal (Optional[Goal]): Task goal.
        extensions (list): Opaque manufacturer extensions, preserved verbatim.
            Each carries an obligatory ``id`` identifying manufacturer and
            version; their order defines the order of turnpoint extensions.
        unknown (dict): Keys the spec does not define, preserved verbatim so a
            round-trip does not silently discard them. Producers do put data
            outside the spec's ``extensions`` mechanism — one writes the
            elevated goal altitude as a root ``{"o": {"v": 2, "fa": 1220}}``.
            Nothing here is interpreted: the value is carried, not understood,
            and in particular is never mapped onto a spec field, since a
            look-alike key may not share the spec's units (that ``fa`` is
            absolute AMSL where the spec's ``goal.finishAltitude`` is AGL
            above the last turnpoint).
    """

    task_type: TaskType
    version: int
    turnpoints: list[Turnpoint]
    earth_model: EarthModel | None = None
    takeoff: Takeoff | None = None
    sss: SSS | None = None
    goal: Goal | None = None
    extensions: list[dict[str, Any]] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands, derived from :data:`TASK_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    @property
    def effective_goal(self) -> "Goal | None":
        """The goal this task is flown to, with the format's default applied.

        A task with at least one turnpoint always has a goal, and that goal
        always has a type: an absent goal is a ``CYLINDER`` one, and a goal
        with an unspecified type is a ``CYLINDER`` goal. With no turnpoints
        there is nothing to be a goal, and this is ``self.goal`` — typically
        None.

        **Derived, not stored.** ``__post_init__`` used to write this back onto
        :attr:`goal`, which made it part of the object and therefore part of
        the output: a task file with no ``goal`` key round-tripped into one
        carrying ``{"goal": {"type": "CYLINDER"}}``. That is the only place the
        library invented a field, in the module whose own docstring says
        nothing derived is stored on these dataclasses and in a codebase whose
        passthrough design exists so that what arrives is what leaves. It went
        unnoticed because every reference task carries a goal.

        Ask for this wherever the *flown* goal is meant — the cylinders and the
        goal line. Read :attr:`goal` where what the file said is meant, which
        is :mod:`~pyxctsk.model.validation`'s whole job and the QR conversion's
        too: it writes no ``g`` object for a task that never spelled one out.

        Returns:
            The goal with defaults applied, or None for a task with no
            turnpoints and no goal. Never the caller's own object once a
            default has been applied — a copy is returned instead.
        """
        if not self.turnpoints:
            return self.goal
        if self.goal is None:
            return Goal(type=GoalType.CYLINDER)
        if not self.goal.type:
            return replace(self.goal, type=GoalType.CYLINDER)
        return self.goal

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        return TASK_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Task: Parsed Task object.

        Raises:
            MalformedPayloadError: If the dictionary is not a task.
        """
        return TASK_SHAPE.read(data)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            str: JSON string representation of the task.
        """
        return dump_json(self.to_dict(), layout="compact")

    @classmethod
    def from_json(cls, json_str: str) -> "Task":
        """Create from JSON string.

        Args:
            json_str (str): JSON string to parse.

        Returns:
            Task: Parsed Task object.

        Raises:
            MalformedPayloadError: If the string is not JSON, or not a task.
        """
        return cls.from_dict(load_json(json_str))

    def to_qr_code_task(self) -> "QRCodeTask":
        """Convert to QR code task format.

        The import is function-local by necessity, not by oversight. The
        mapping lives in :mod:`pyxctsk.qrcode.conversion`, which imports this
        module to build a ``Task`` in the other direction; importing it at
        module level here would make the two packages a circular import. This
        method is the only place the model reaches into the QR format at all,
        which is what lets everything else in :mod:`pyxctsk.model` stay
        independent of it — a property ``tests/test_layering.py`` enforces.

        Returns:
            QRCodeTask: QRCodeTask object created from this task.
        """
        from ..qrcode.conversion import task_to_qr_code_task

        return task_to_qr_code_task(self)

    def validate(self) -> list[ValidationIssue]:
        """Check the task against the spec's structural rules.

        The rules themselves live in :mod:`pyxctsk.model.validation`; this is the
        entry point onto them. Validation is a report, not a gate — parsing
        accepts structurally invalid tasks so they can still be inspected and
        converted. Pass ``strict=True`` to :func:`pyxctsk.parse_task` to turn
        violations into a
        :class:`~pyxctsk.exceptions.TaskValidationError`.

        Returns:
            list[ValidationIssue]: One issue per violated rule; empty if the
            task is valid. Each issue names its
            :class:`~pyxctsk.model.validation.ValidationRule` and stringifies to a
            human-readable message.
        """
        return validate_task(self)

    def is_ess_goal(self) -> bool:
        """Whether the task's last turnpoint is also its ESS.

        Reports what the file says, which is the model's job: an elevated goal
        "implicitly also serves as the End of Speed Section" (FAI S7F 2026
        §6.2.3.2), but resolving that contradiction is
        :mod:`~pyxctsk.model.validation`'s — it reports
        ``ELEVATED_GOAL_IS_NOT_ESS`` and leaves this answering the annotation.

        This used to search for the *first* turnpoint marked ESS and compare it
        to the last one by value. ``Turnpoint`` is a plain dataclass, so a task
        that legitimately flies the same turnpoint twice could match the wrong
        occurrence — the hazard :meth:`~pyxctsk.export.TaskDrawing.is_goal`
        documents and avoids by comparing identity. Asking the last turnpoint
        what it is needs neither a search nor a comparison. It also drops
        ``find_ess_turnpoint``, which had no other caller, no test and no
        mention in the docs.

        Note this is *not* "does the task have a speed section" — that is
        :func:`~pyxctsk.distance.speed_section.speed_section_indices`, which
        also weighs the task type, and which lives in ``distance/`` because
        ``model/`` may not depend on it.

        Returns:
            bool: True if the last turnpoint carries the ESS role.
        """
        return bool(self.turnpoints) and self.turnpoints[-1].type is TurnpointType.ESS


TASK_SHAPE = Shape(
    Task,
    (
        Value("task_type", "taskType", enum_codec(TaskType), REQUIRED),
        Value("version", "version", INTEGER, REQUIRED),
        Value(
            "turnpoints",
            "turnpoints",
            list_codec(shape_codec(TURNPOINT_SHAPE)),
            REQUIRED,
        ),
        Value("earth_model", "earthModel", enum_codec(EarthModel)),
        Value("takeoff", "takeoff", shape_codec(TAKEOFF_SHAPE)),
        Value("sss", "sss", shape_codec(SSS_SHAPE)),
        Value("goal", "goal", shape_codec(GOAL_SHAPE)),
    ),
    ext_key=EXTENSIONS_KEY,
)
Task.KNOWN_KEYS = TASK_SHAPE.keys
