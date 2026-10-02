"""pyxctsk - Python implementation of XCTrack's task format.

This package implements XCTrack's task format for reading and writing .xctsk files,
generating and parsing XCTSK: URLs, and encoding/decoding XCTSK: URLs as QR codes.

This is the whole library's front door: every **answer** a caller needs is
named here — parse a task, convert it, measure it, draw it — while the four
packages behind it hold the primitives those answers are built from. Reach into
``pyxctsk.model``, ``pyxctsk.qrcode``, ``pyxctsk.distance`` and
``pyxctsk.export`` for those: ``LocalPlane``, ``plane_circle`` and the
optimizer's tuning constants are deliberately not re-exported here.

Start with :func:`parse_task` for reading a payload (:func:`load_task` for a
file), :class:`Task` for the model, :class:`DistanceReport` for every number
S7F defines about a task, and
:func:`task_to_kml` / :func:`generate_task_geojson` for a map.

See http://xctrack.org/ and http://xctrack.org/Competition_Interfaces.html
"""

# `pyXCTSKError` is exported for the same reason: it is the one name a caller
# writes in `except`, and the front door carried five of its subclasses and not
# it, so the suite itself reached past this module (`from pyxctsk.exceptions
# import pyXCTSKError`) to catch anything the library raises.

# The answer/primitive split above is the rule this file once broke, and the
# reason it is stated: ``distance_through_centers`` was exported while
# ``center_distance`` — which that function's own docstring tells you to call
# instead — was not, and ``OptimizedRoute`` was exported alongside a function
# taking one but nothing that could construct one, which is why
# ``docs/s7f-distance-reference.md`` had to reach past this module for four
# names. ``tests/test_layering.py`` now asserts every documented name is
# reachable from here.

from .distance import (
    PROPOSED_READING,
    CenterDistanceReading,
    DistanceReport,
    GoalLine,
    GoalLineOrientation,
    MeasuredTask,
    OptimizedRoute,
    SpeedSection,
    TaskDistanceTable,
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
    MalformedPayloadError,
    MismatchedRouteError,
    MissingQRCodeSupportError,
    TaskValidationError,
    UnmeasurableRouteError,
    pyXCTSKError,
)
from .export.common import TaskDrawing
from .export.geojson import drawing_to_geojson, generate_task_geojson
from .export.kml import drawing_to_kml, task_to_kml
from .metadata import pyxctsk_version
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
from .parser import load_task, parse_task
from .qrcode.image import generate_qrcode_image
from .qrcode.task import QRCodeTask
from .renderer import OUTPUT_FORMATS, OutputFormat, render_task

# Single source of truth: the version declared in pyproject.toml, read from the
# installed package metadata. Through `metadata.pyxctsk_version`, which is also
# what `pyxctsk --version` and the distance report print — this line used to
# call `importlib.metadata.version` itself and raise on a source checkout,
# where the other spelling returned "unknown".
__version__ = pyxctsk_version()
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
    "MalformedPayloadError",
    "MeasuredTask",
    "MismatchedRouteError",
    "MissingQRCodeSupportError",
    "optimized_distance",
    "OUTPUT_FORMATS",
    "OutputFormat",
    "OptimizedRoute",
    "load_task",
    "parse_task",
    "PROPOSED_READING",
    "pyXCTSKError",
    "QRCodeTask",
    "render_task",
    "SpeedSection",
    "SSS",
    "SSSType",
    "Takeoff",
    "Task",
    "task_distances_from",
    "task_to_kml",
    "task_to_turnpoints",
    "TaskDistanceTable",
    "TaskDrawing",
    "TaskTurnpoint",
    "TaskType",
    "TaskValidationError",
    "TimeOfDay",
    "TooFewTurnpointsError",
    "Turnpoint",
    "TurnpointType",
    "UnmeasurableRouteError",
    "ValidationIssue",
    "ValidationRule",
    "Waypoint",
]
