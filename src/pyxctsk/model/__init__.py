"""The XCTrack task domain model.

This package holds the task itself and the rules that belong to it: the
dataclasses of the spec's object graph (:mod:`~pyxctsk.model.task`), the
enumerations that constrain their fields (:mod:`~pyxctsk.model.enums`), the
``HH:MM:SSZ`` value type (:mod:`~pyxctsk.model.time_of_day`), the
unknown-field passthrough rules (:mod:`~pyxctsk.model.passthrough`), the
spec's structural checks (:mod:`~pyxctsk.model.validation`) and the Java
``Math.round`` semantics both the model and the QR codec need
(:mod:`~pyxctsk.model.rounding`).

Nothing here depends on distance calculation or on export formats.

Modules *inside* the package import each other directly (``from .enums import
TaskType``) rather than through this file, so that partially-initialized
imports can never bite; the re-exports below are for callers outside it.
"""

from .enums import (
    Direction,
    EarthModel,
    GoalType,
    SSSType,
    TaskType,
    TurnpointType,
)
from .passthrough import EXTENSIONS_KEY, QR_EXTENSIONS_KEY
from .rounding import round_half_up
from .task import SSS, Goal, Takeoff, Task, Turnpoint, Waypoint
from .time_of_day import TimeOfDay
from .validation import ValidationIssue, ValidationRule, validate_task

__all__ = [
    "Direction",
    "EarthModel",
    "EXTENSIONS_KEY",
    "Goal",
    "GoalType",
    "QR_EXTENSIONS_KEY",
    "round_half_up",
    "SSS",
    "SSSType",
    "Takeoff",
    "Task",
    "TaskType",
    "TimeOfDay",
    "Turnpoint",
    "TurnpointType",
    "validate_task",
    "ValidationIssue",
    "ValidationRule",
    "Waypoint",
]
