"""pyxctsk - Python implementation of XCTrack's task format.

This package implements XCTrack's task format for reading and writing .xctsk files,
generating and parsing XCTSK: URLs, and encoding/decoding XCTSK: URLs as QR codes.

See http://xctrack.org/ and http://xctrack.org/Competition_Interfaces.html
"""

from importlib.metadata import version

from .distance import (
    DistanceReport,
    MeasuredTask,
    OptimizedRoute,
    SpeedSection,
    TaskTurnpoint,
    calculate_task_distances,
    distance_through_centers,
    optimized_distance,
    task_distances_from,
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
