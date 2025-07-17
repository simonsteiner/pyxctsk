"""XCTrack Task Data Structures and Domain Models.

This module defines immutable dataclasses, enums, and validation logic for representing,
parsing, and serializing XCTrack competition tasks. It covers the core domain models:
  - Task, Turnpoint, Waypoint, Takeoff, SSS, Goal, TimeOfDay
  - Enums for constrained values (e.g., TaskType, TurnpointType, GoalType)
  - Serialization/deserialization to/from JSON and internal dicts
  - Validation and logic for task structure and goal/ESS handling

Intended for use in parsing, generating, and manipulating XCTrack task formats, including
support for QR code encoding/decoding and distance calculations (see related modules).
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .exceptions import InvalidTimeOfDayError

if TYPE_CHECKING:
    from .qrcode_task import QRCodeTask


class Direction(str, Enum):
    """Enumeration of direction types for turnpoints.

    Attributes:
        ENTER (str): Enter direction.
        EXIT (str): Exit direction.
    """

    ENTER = "ENTER"
    EXIT = "EXIT"


class EarthModel(str, Enum):
    """Enumeration of supported earth models.

    Attributes:
        WGS84 (str): WGS84 ellipsoid.
        FAI_SPHERE (str): FAI sphere model.
    """

    WGS84 = "WGS84"
    FAI_SPHERE = "FAI_SPHERE"


class GoalType(str, Enum):
    """Enumeration of goal types.

    Attributes:
        CYLINDER (str): Cylinder goal.
        LINE (str): Line goal.
    """

    CYLINDER = "CYLINDER"
    LINE = "LINE"


class SSSType(str, Enum):
    """Enumeration of start of speed section (SSS) types.

    Attributes:
        RACE (str): Race start.
        ELAPSED_TIME (str): Elapsed time start.
    """

    RACE = "RACE"
    ELAPSED_TIME = "ELAPSED-TIME"


class TaskType(str, Enum):
    """Enumeration of task types.

    Attributes:
        CLASSIC (str): Classic task.
        WAYPOINTS (str): Waypoints task.
    """

    CLASSIC = "CLASSIC"
    WAYPOINTS = "W"


class TurnpointType(str, Enum):
    """Enumeration of turnpoint types.

    Attributes:
        NONE (str): No type.
        TAKEOFF (str): Takeoff point.
        SSS (str): Start of speed section.
        ESS (str): End of speed section.
    """

    NONE = ""
    TAKEOFF = "TAKEOFF"
    SSS = "SSS"
    ESS = "ESS"


@dataclass
class TimeOfDay:
    """Represents a time of day (HH:MM:SS).

    Attributes:
        hour (int): Hour (0-23).
        minute (int): Minute (0-59).
        second (int): Second (0-59).
    """

    hour: int
    minute: int
    second: int

    def __post_init__(self) -> None:
        """Validate time values."""
        if not (0 <= self.hour <= 23):
            raise ValueError("Hour must be between 0 and 23")
        if not (0 <= self.minute <= 59):
            raise ValueError("Minute must be between 0 and 59")
        if not (0 <= self.second <= 59):
            raise ValueError("Second must be between 0 and 59")

    def to_json_string(self) -> str:
        """Convert to JSON string format.

        Returns:
            str: JSON string representation of the time.
        """
        return f'"{self.hour:02d}:{self.minute:02d}:{self.second:02d}Z"'

    @classmethod
    def from_json_string(cls, time_str: str) -> "TimeOfDay":
        """Parse from JSON string format.

        Args:
            time_str (str): JSON string to parse.

        Returns:
            TimeOfDay: Parsed TimeOfDay object.

        Raises:
            InvalidTimeOfDayError: If the string is not a valid time.
        """
        # Handle both quoted and unquoted formats
        if time_str.startswith('"') and time_str.endswith('"'):
            time_str = time_str[1:-1]  # Remove quotes

        pattern = r"^(\d{2}):(\d{2}):(\d{2})Z$"
        match = re.match(pattern, time_str)
        if not match:
            raise InvalidTimeOfDayError(time_str)

        hour = int(match.group(1))
        minute = int(match.group(2))
        second = int(match.group(3))

        return cls(hour=hour, minute=minute, second=second)

    def __str__(self) -> str:
        """Return string representation in HH:MM:SSZ format."""
        return f"{self.hour:02d}:{self.minute:02d}:{self.second:02d}Z"


@dataclass
class Waypoint:
    """Represents a waypoint with coordinates and optional description.

    Attributes:
        name (str): Name of the waypoint.
        lat (float): Latitude in decimal degrees.
        lon (float): Longitude in decimal degrees.
        alt_smoothed (int): Smoothed altitude in meters.
        description (Optional[str]): Optional description.
    """

    name: str
    lat: float
    lon: float
    alt_smoothed: int
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result = {
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "altSmoothed": self.alt_smoothed,
        }
        if self.description:
            result["description"] = self.description
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Waypoint":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Waypoint: Parsed Waypoint object.
        """
        return cls(
            name=data["name"],
            lat=data["lat"],
            lon=data["lon"],
            alt_smoothed=data["altSmoothed"],
            description=data.get("description"),
        )


@dataclass
class Turnpoint:
    """Represents a turnpoint in a task.

    Attributes:
        radius (int): Turnpoint radius in meters.
        waypoint (Waypoint): Associated waypoint.
        type (Optional[TurnpointType]): Type of turnpoint.
    """

    radius: int
    waypoint: Waypoint
    type: Optional[TurnpointType] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result = {
            "radius": self.radius,
            "waypoint": self.waypoint.to_dict(),
        }
        if self.type and self.type != TurnpointType.NONE:
            result["type"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Turnpoint":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Turnpoint: Parsed Turnpoint object.
        """
        turnpoint_type = None
        if "type" in data and data["type"]:
            turnpoint_type = TurnpointType(data["type"])

        return cls(
            radius=data["radius"],
            waypoint=Waypoint.from_dict(data["waypoint"]),
            type=turnpoint_type,
        )


@dataclass
class Takeoff:
    """Represents takeoff window with open/close times.

    Attributes:
        time_open (Optional[TimeOfDay]): Opening time.
        time_close (Optional[TimeOfDay]): Closing time.
    """

    time_open: Optional[TimeOfDay] = None
    time_close: Optional[TimeOfDay] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result = {}
        if self.time_open:
            result["timeOpen"] = self.time_open.to_json_string()
        if self.time_close:
            result["timeClose"] = self.time_close.to_json_string()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Takeoff":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Takeoff: Parsed Takeoff object.
        """
        time_open = None
        time_close = None

        if "timeOpen" in data:
            time_open = TimeOfDay.from_json_string(data["timeOpen"])
        if "timeClose" in data:
            time_close = TimeOfDay.from_json_string(data["timeClose"])

        return cls(time_open=time_open, time_close=time_close)


@dataclass
class SSS:
    """Represents a start of speed section (SSS).

    Attributes:
        type (SSSType): SSS type.
        direction (Direction): SSS direction.
        time_gates (List[TimeOfDay]): List of time gates.
        time_close (Optional[TimeOfDay]): Optional closing time.
    """

    type: SSSType
    direction: Direction
    time_gates: List[TimeOfDay] = field(default_factory=list)
    time_close: Optional[TimeOfDay] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result = {
            "type": self.type.value,
            "direction": self.direction.value,
            "timeGates": [gate.to_json_string() for gate in self.time_gates],
        }
        if self.time_close:
            result["timeClose"] = self.time_close.to_json_string()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SSS":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            SSS: Parsed SSS object.
        """
        time_gates = []
        if "timeGates" in data:
            time_gates = [
                TimeOfDay.from_json_string(gate) for gate in data["timeGates"]
            ]

        time_close = None
        if "timeClose" in data:
            time_close = TimeOfDay.from_json_string(data["timeClose"])

        return cls(
            type=SSSType(data["type"]),
            direction=Direction(data["direction"]),
            time_gates=time_gates,
            time_close=time_close,
        )


@dataclass
class Goal:
    """Represents a goal for a task.

    For goal type LINE, the line_length represents the total length of the goal line. The radius of the last turnpoint represents half of this length. The goal line orientation is perpendicular to the azimuth to the last turnpoint center.

    Attributes:
        type (Optional[GoalType]): Goal type.
        deadline (Optional[TimeOfDay]): Goal deadline.
        line_length (Optional[float]): Length of the goal line (for LINE type).
    """

    type: Optional[GoalType] = None
    deadline: Optional[TimeOfDay] = None
    line_length: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result = {}
        if self.type:
            result["type"] = self.type.value
        if self.deadline:
            result["deadline"] = self.deadline.to_json_string()
        if self.type == GoalType.LINE and self.line_length is not None:
            # For goal LINE type, lineLength represents the total length of the goal line
            result["lineLength"] = str(
                self.line_length
            )  # Convert to string for consistency
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Goal":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Goal: Parsed Goal object.
        """
        goal_type = None
        deadline = None
        line_length = None  # No default line length

        if "type" in data:
            goal_type = GoalType(data["type"])
        if "deadline" in data:
            deadline = TimeOfDay.from_json_string(data["deadline"])
        if "lineLength" in data and data["lineLength"] is not None:
            line_length = float(data["lineLength"])

        return cls(type=goal_type, deadline=deadline, line_length=line_length)


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
    """

    task_type: TaskType
    version: int
    turnpoints: List[Turnpoint]
    earth_model: Optional[EarthModel] = None
    takeoff: Optional[Takeoff] = None
    sss: Optional[SSS] = None
    goal: Optional[Goal] = None

    def __post_init__(self) -> None:
        """Post-initialization validation and processing."""
        if not self.turnpoints or len(self.turnpoints) == 0:
            return

        # Find ESS turnpoint (if any)
        ess_tp = None
        for tp in self.turnpoints:
            if tp.type == TurnpointType.ESS:
                ess_tp = tp
                break

        # The last turnpoint is always the goal
        last_tp = self.turnpoints[-1]

        # Create goal object if it doesn't exist yet
        if not self.goal and len(self.turnpoints) > 0:
            self.goal = Goal()

        # Only process goal settings if a goal object exists
        if self.goal:
            # If goal type is not specified, default to CYLINDER
            if not self.goal.type:
                self.goal.type = GoalType.CYLINDER

            # If goal type is LINE, set goal line length from last turnpoint radius
            if self.goal.type == GoalType.LINE:
                # The last turnpoint's radius represents half of the goal line length
                self.goal.line_length = float(last_tp.radius * 2)

        # If the last turnpoint is marked as ESS, it shares goal settings
        # Otherwise, ESS is always a cylinder (if present)
        if ess_tp and ess_tp != self.turnpoints[-1]:
            # ESS is not the last turnpoint, so it's always a cylinder
            pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        # Apply goal line length logic before serializing
        if (
            self.goal
            and self.goal.type == GoalType.LINE
            and self.turnpoints
            and len(self.turnpoints) > 0
        ):
            # For goal LINE type, make sure the line length is set to twice the last turnpoint radius
            # as the radius represents half of the total goal line length
            self.goal.line_length = float(self.turnpoints[-1].radius) * 2.0

        result: Dict[str, Any] = {
            "taskType": self.task_type.value,
            "version": self.version,
            "turnpoints": [tp.to_dict() for tp in self.turnpoints],
        }

        if self.earth_model:
            result["earthModel"] = self.earth_model.value
        if self.takeoff:
            result["takeoff"] = self.takeoff.to_dict()
        if self.sss:
            result["sss"] = self.sss.to_dict()
        if self.goal:
            result["goal"] = self.goal.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Task: Parsed Task object.
        """
        turnpoints = [Turnpoint.from_dict(tp) for tp in data["turnpoints"]]

        earth_model = None
        if "earthModel" in data:
            earth_model = EarthModel(data["earthModel"])

        takeoff = None
        if "takeoff" in data:
            takeoff = Takeoff.from_dict(data["takeoff"])

        sss = None
        if "sss" in data:
            sss = SSS.from_dict(data["sss"])

        goal = None
        if "goal" in data:
            goal = Goal.from_dict(data["goal"])
        elif turnpoints:  # Create goal object even if not explicitly in data
            goal = Goal()

        # Process goal settings if it exists
        if goal and turnpoints:
            # If goal type is not specified, default to CYLINDER
            if not goal.type:
                goal.type = GoalType.CYLINDER

            # If goal type is LINE, make sure line length is correctly set
            if goal.type == GoalType.LINE:
                if goal.line_length is None and turnpoints:
                    # For goal LINE type, the line length is twice the last turnpoint radius
                    # as the radius represents half of the total goal line length
                    goal.line_length = float(turnpoints[-1].radius * 2)

        return cls(
            task_type=TaskType(data["taskType"]),
            version=data["version"],
            turnpoints=turnpoints,
            earth_model=earth_model,
            takeoff=takeoff,
            sss=sss,
            goal=goal,
        )

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            str: JSON string representation of the task.
        """
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "Task":
        """Create from JSON string.

        Args:
            json_str (str): JSON string to parse.

        Returns:
            Task: Parsed Task object.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_qr_code_task(self) -> "QRCodeTask":
        """Convert to QR code task format.

        Returns:
            QRCodeTask: QRCodeTask object created from this task.
        """
        from .qrcode_task import QRCodeTask

        return QRCodeTask.from_task(self)

    def find_ess_turnpoint(self) -> Optional[Turnpoint]:
        """Find and return the ESS turnpoint, if any.

        Returns:
            Optional[Turnpoint]: The turnpoint marked as ESS or None if no ESS turnpoint exists.
        """
        for tp in self.turnpoints:
            if tp.type == TurnpointType.ESS:
                return tp
        return None

    def is_ess_goal(self) -> bool:
        """Check if the ESS turnpoint is the same as the goal (last turnpoint).

        Returns:
            bool: True if ESS is the same as goal, False otherwise.
        """
        if not self.turnpoints:
            return False

        ess_tp = self.find_ess_turnpoint()
        if not ess_tp:
            return False

        return ess_tp == self.turnpoints[-1]
