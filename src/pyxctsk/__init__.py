"""
pyxctsk - Python implementation of XCTrack's task format.

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

# Constants
EXTENSION = ".xctsk"
MIME_TYPE = "application/xctsk"
VERSION = 1

__version__ = "1.0.0"
__all__ = [
    "Task",
    "Takeoff",
    "SSS",
    "Goal",
    "Turnpoint",
    "Waypoint",
    "TimeOfDay",
    "Direction",
    "EarthModel",
    "GoalType",
    "SSSType",
    "TaskType",
    "TurnpointType",
    "generate_task_geojson",
    "QRCodeTask",
    "parse_task",
    "calculate_task_distances",
    "optimized_distance",
    "distance_through_centers",
    "TaskTurnpoint",
    "EmptyInputError",
    "InvalidFormatError",
    "InvalidTimeOfDayError",
    "EXTENSION",
    "MIME_TYPE",
    "VERSION",
]
