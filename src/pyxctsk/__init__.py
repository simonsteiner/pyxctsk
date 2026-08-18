"""pyxctsk - Python implementation of XCTrack's task format.

This package implements XCTrack's task format for reading and writing .xctsk files,
generating and parsing XCTSK: URLs, and encoding/decoding XCTSK: URLs as QR codes.

This is the whole library's front door: every answer a caller needs is named
here, and the four packages behind it hold the primitives those answers are
built from. That distinction is the one this file got wrong — it exported
``distance_through_centers``, whose own docstring says *"the primitive, not the
published number… a caller producing a figure for a task board wants
``center_distance(task)``"*, while ``center_distance`` itself was absent. It
also exported ``OptimizedRoute`` and a function taking one without exporting
anything that could construct one, which is why the S7F reference document had
to reach past this module for four names.

Reach into ``pyxctsk.distance`` and friends for the pieces below the answers —
``LocalPlane``, ``plane_circle``, the optimizer's tuning constants — which are
deliberately not re-exported here.

See http://xctrack.org/ and http://xctrack.org/Competition_Interfaces.html
"""

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
from .model.validation import ValidationIssue, ValidationRule
from .parser import parse_task
from .qrcode.image import generate_qrcode_image
from .qrcode.task import QRCodeTask

# Constants
EXTENSION = ".xctsk"
MIME_TYPE = "application/xctsk"
VERSION = 1

# Single source of truth: the version declared in pyproject.toml, read from the
# installed package metadata.
__version__ = version("pyxctsk")
__all__ = [
    "task_to_turnpoints",
    "geodesic_distance",
    "center_distance_readings",
    "center_distance",
    "calculate_iteratively_refined_route",
    "TooFewTurnpointsError",
    "PROPOSED_READING",
    "GoalLineOrientation",
    "GoalLine",
    "CenterDistanceReading",
    "SpeedSection",
    "calculate_task_distances",
    "Direction",
    "distance_through_centers",
    "drawing_to_geojson",
    "drawing_to_kml",
    "EarthModel",
    "EmptyInputError",
    "EXTENSION",
    "generate_qrcode_image",
    "generate_task_geojson",
    "Goal",
    "GoalType",
    "InvalidFormatError",
    "InvalidTimeOfDayError",
    "MeasuredTask",
    "DistanceReport",
    "MIME_TYPE",
    "optimized_distance",
    "OptimizedRoute",
    "parse_task",
    "QRCodeTask",
    "SSS",
    "SSSType",
    "Takeoff",
    "task_distances_from",
    "task_to_kml",
    "Task",
    "TaskDrawing",
    "TaskTurnpoint",
    "TaskType",
    "TaskValidationError",
    "TimeOfDay",
    "Turnpoint",
    "TurnpointType",
    "ValidationIssue",
    "ValidationRule",
    "VERSION",
    "Waypoint",
]
