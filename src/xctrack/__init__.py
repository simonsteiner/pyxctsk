"""
Python implementation of XCTrack's task format.

This package implements XCTrack's task format for reading and writing .xctsk files,
generating and parsing XCTSK: URLs, and encoding/decoding XCTSK: URLs as QR codes.

See http://xctrack.org/ and http://xctrack.org/Competition_Interfaces.html
"""

from .task import (
    Task,
    Takeoff,
    SSS,
    Goal,
    Turnpoint,
    Waypoint,
    TimeOfDay,
    Direction,
    EarthModel,
    GoalType,
    SSSType,
    TaskType,
    TurnpointType,
)
from .qrcode_task import QRCodeTask
from .parser import parse_task
from .exceptions import (
    EmptyInputError,
    InvalidFormatError,
    InvalidTimeOfDayError,
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
    "QRCodeTask",
    "parse_task",
    "EmptyInputError",
    "InvalidFormatError",
    "InvalidTimeOfDayError",
    "EXTENSION",
    "MIME_TYPE",
    "VERSION",
]
