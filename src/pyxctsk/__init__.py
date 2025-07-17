"""pyxctsk - Python implementation of XCTrack's task format.

This package implements XCTrack's task format for reading and writing .xctsk files,
generating and parsing XCTSK: URLs, and encoding/decoding XCTSK: URLs as QR codes.

See http://xctrack.org/ and http://xctrack.org/Competition_Interfaces.html
"""

from .distance import (
    TaskTurnpoint,
    calculate_task_distances,
    distance_through_centers,
    optimized_distance,
)
from .exceptions import (
    EmptyInputError,
    InvalidFormatError,
    InvalidTimeOfDayError,
)
from .geojson import generate_task_geojson
from .parser import parse_task
from .qrcode_task import QRCodeTask
from .task import (
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

# Utility functions
from .utils import generate_qr_code, task_to_kml

# Constants
EXTENSION = ".xctsk"
MIME_TYPE = "application/xctsk"
VERSION = 1

__version__ = "1.0.0"
__all__ = [
    "calculate_task_distances",
    "Direction",
    "distance_through_centers",
    "EarthModel",
    "EmptyInputError",
    "EXTENSION",
    "generate_qr_code",
    "generate_task_geojson",
    "Goal",
    "GoalType",
    "InvalidFormatError",
    "InvalidTimeOfDayError",
    "MIME_TYPE",
    "optimized_distance",
    "parse_task",
    "QRCodeTask",
    "SSS",
    "SSSType",
    "Takeoff",
    "task_to_kml",
    "Task",
    "TaskTurnpoint",
    "TaskType",
    "TimeOfDay",
    "Turnpoint",
    "TurnpointType",
    "VERSION",
    "Waypoint",
]
