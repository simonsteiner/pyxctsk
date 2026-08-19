"""pyxctsk - Python implementation of XCTrack's task format.

This package implements XCTrack's task format for reading and writing .xctsk files,
generating and parsing XCTSK: URLs, and encoding/decoding XCTSK: URLs as QR codes.

This is the whole library's front door: every **answer** a caller needs is
named here — parse a task, convert it, measure it, draw it — while the four
packages behind it hold the primitives those answers are built from. Reach into
``pyxctsk.model``, ``pyxctsk.qrcode``, ``pyxctsk.distance`` and
``pyxctsk.export`` for those: ``LocalPlane``, ``plane_circle`` and the
optimizer's tuning constants are deliberately not re-exported here.

Start with :func:`parse_task` for reading, :class:`Task` for the model,
:class:`DistanceReport` for every number S7F defines about a task, and
:func:`task_to_kml` / :func:`generate_task_geojson` for a map.

See http://xctrack.org/ and http://xctrack.org/Competition_Interfaces.html
"""

# The answer/primitive split above is the rule this file once broke, and the
# reason it is stated: ``distance_through_centers`` was exported while
# ``center_distance`` — which that function's own docstring tells you to call
# instead — was not, and ``OptimizedRoute`` was exported alongside a function
# taking one but nothing that could construct one, which is why
# ``docs/s7f-distance-reference.md`` had to reach past this module for four
# names. ``tests/test_layering.py`` now asserts every documented name is
# reachable from here.

from importlib.metadata import version

from .distance import (
    PROPOSED_READING,
    CenterDistanceReading,
    DistanceReport,
    GoalLine,
    GoalLineOrientation,
    MeasuredTask,
    OptimizedRoute,
    SpeedSection,
    TaskTurnpoint,
    TooFewTurnpointsError,
    calculate_iteratively_refined_route,
    calculate_task_distances,
    center_distance,
    center_distance_readings,
    distance_through_centers,
    geodesic_distance,
    optimized_distance,
    task_distances_from,
    task_to_turnpoints,
)
from .exceptions import (
    EmptyInputError,
    InvalidFormatError,
    InvalidTimeOfDayError,
    MissingQRCodeSupportError,
    TaskValidationError,
)
from .export.common import TaskDrawing
from .export.geojson import drawing_to_geojson, generate_task_geojson
from .export.kml import drawing_to_kml, task_to_kml
from .model.task import (
    SSS,
    Direction,
    EarthModel,
    Goal,
    GoalType,
    SSSType,
    Takeoff,
    Task,
    TaskType,
    TimeOfDay,
    Turnpoint,
    TurnpointType,
    Waypoint,
)
from .model.validation import FULL_FORMAT_VERSION, ValidationIssue, ValidationRule
from .parser import parse_task
from .qrcode.image import generate_qrcode_image
from .qrcode.task import QRCodeTask

# Constants
EXTENSION = ".xctsk"
MIME_TYPE = "application/xctsk"

#: The version the full JSON task format declares — an alias, not a fourth
#: spelling. This was one of three independent literal ``1``s, beside
#: ``model.validation.FULL_FORMAT_VERSION`` (what ``Task.validate()`` checks
#: against) and ``qrcode.conversion.TASK_VERSION`` (what every converted task
#: was stamped with), so the library could be made to write a version its own
#: validator rejects by editing one of three files.
#:
#: Note this is the *format's* version and has nothing to do with
#: :data:`__version__`, which is the library's. The QR format's counterpart is
#: ``pyxctsk.qrcode.QR_CODE_TASK_VERSION``, which has always been declared once.
VERSION = FULL_FORMAT_VERSION

# Single source of truth: the version declared in pyproject.toml, read from the
# installed package metadata.
__version__ = version("pyxctsk")
# Sorted, case-insensitively. It was in no discernible order, which is what
# makes an accidental omission invisible; tests/test_layering.py checks the
# contents, this checks that a reader can find a name in them.
__all__ = [
    "calculate_iteratively_refined_route",
    "calculate_task_distances",
    "center_distance",
    "center_distance_readings",
    "CenterDistanceReading",
    "Direction",
    "distance_through_centers",
    "DistanceReport",
    "drawing_to_geojson",
    "drawing_to_kml",
    "EarthModel",
    "EmptyInputError",
    "EXTENSION",
    "FULL_FORMAT_VERSION",
    "generate_qrcode_image",
    "generate_task_geojson",
    "geodesic_distance",
    "Goal",
    "GoalLine",
    "GoalLineOrientation",
    "GoalType",
    "InvalidFormatError",
    "InvalidTimeOfDayError",
    "MeasuredTask",
    "MIME_TYPE",
    "MissingQRCodeSupportError",
    "optimized_distance",
    "OptimizedRoute",
    "parse_task",
    "PROPOSED_READING",
    "QRCodeTask",
    "SpeedSection",
    "SSS",
    "SSSType",
    "Takeoff",
    "Task",
    "task_distances_from",
    "task_to_kml",
    "task_to_turnpoints",
    "TaskDrawing",
    "TaskTurnpoint",
    "TaskType",
    "TaskValidationError",
    "TimeOfDay",
    "TooFewTurnpointsError",
    "Turnpoint",
    "TurnpointType",
    "ValidationIssue",
    "ValidationRule",
    "VERSION",
    "Waypoint",
]
