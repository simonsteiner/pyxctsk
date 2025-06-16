"""QR code task format implementation."""

import json
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import polyline

if TYPE_CHECKING:
    from .task import Task, TimeOfDay

# Constants
QR_CODE_SCHEME = "XCTSK:"
QR_CODE_TASK_VERSION = 2


class QRCodeDirection(IntEnum):
    """QR code direction enumeration."""

    ENTER = 1
    EXIT = 2


class QRCodeEarthModel(IntEnum):
    """QR code earth model enumeration."""

    WGS84 = 0
    FAI_SPHERE = 1


class QRCodeGoalType(IntEnum):
    """QR code goal type enumeration."""

    LINE = 1
    CYLINDER = 2


class QRCodeSSSType(IntEnum):
    """QR code SSS type enumeration."""

    RACE = 1
    ELAPSED_TIME = 2


class QRCodeTaskType(IntEnum):
    """QR code task type enumeration."""

    CLASSIC = 1
    WAYPOINTS = 2


class QRCodeTurnpointType(IntEnum):
    """QR code turnpoint type enumeration."""

    NONE = 0
    TAKEOFF = 1
    SSS = 2
    ESS = 3


@dataclass
class QRCodeGoal:
    """QR code goal representation."""

    deadline: Optional["TimeOfDay"] = None
    type: Optional[QRCodeGoalType] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}
        if self.deadline:
            result["d"] = self.deadline.to_json_string()
        if self.type is not None:
            result["t"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeGoal":
        """Create from dictionary."""
        from .task import TimeOfDay

        deadline = None
        if "d" in data:
            deadline = TimeOfDay.from_json_string(data["d"])

        goal_type = None
        if "t" in data:
            goal_type = QRCodeGoalType(data["t"])

        return cls(deadline=deadline, type=goal_type)


@dataclass
class QRCodeSSS:
    """QR code SSS representation."""

    direction: QRCodeDirection
    type: QRCodeSSSType
    time_gates: List["TimeOfDay"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "d": self.direction.value,
            "t": self.type.value,
        }
        if self.time_gates:
            result["g"] = [gate.to_json_string() for gate in self.time_gates]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeSSS":
        """Create from dictionary."""
        from .task import TimeOfDay

        time_gates = []
        if "g" in data:
            time_gates = [TimeOfDay.from_json_string(gate) for gate in data["g"]]

        return cls(
            direction=QRCodeDirection(data["d"]),
            type=QRCodeSSSType(data["t"]),
            time_gates=time_gates,
        )


@dataclass
class QRCodeTakeoff:
    """QR code takeoff representation."""

    time_open: Optional["TimeOfDay"] = None
    time_close: Optional["TimeOfDay"] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}
        if self.time_open:
            result["o"] = self.time_open.to_json_string()
        if self.time_close:
            result["c"] = self.time_close.to_json_string()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeTakeoff":
        """Create from dictionary."""
        from .task import TimeOfDay

        time_open = None
        time_close = None

        if "o" in data:
            time_open = TimeOfDay.from_json_string(data["o"])
        if "c" in data:
            time_close = TimeOfDay.from_json_string(data["c"])

        return cls(time_open=time_open, time_close=time_close)


@dataclass
class QRCodeTurnpoint:
    """QR code turnpoint representation."""

    lat: float
    lon: float
    radius: int
    name: str
    alt_smoothed: int
    type: QRCodeTurnpointType = QRCodeTurnpointType.NONE
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Store coordinates and metadata separately for better compatibility
        result = {
            "n": self.name,
            "x": self.lon,
            "y": self.lat,
            "a": self.alt_smoothed,
            "r": self.radius,
        }
        if self.description:
            result["d"] = self.description
        if self.type != QRCodeTurnpointType.NONE:
            result["t"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeTurnpoint":
        """Create from dictionary."""
        # Use individual fields for better reliability
        lon = data.get("x", 0.0)
        lat = data.get("y", 0.0)
        alt_smoothed = data.get("a", 0)
        radius = data.get("r", 1000)

        # Fallback: try polyline decoding if individual fields not available
        if "z" in data and ("x" not in data or "y" not in data):
            coords = polyline.decode(data["z"], precision=5)
            if coords:
                coord = coords[0]  # Take first coordinate
                lon, lat = coord[0], coord[1]
                alt_smoothed = int(coord[2]) if len(coord) > 2 else 0
                radius = int(coord[3]) if len(coord) > 3 else 1000

        turnpoint_type = QRCodeTurnpointType.NONE
        if "t" in data:
            turnpoint_type = QRCodeTurnpointType(data["t"])

        description = data.get("d")

        return cls(
            lat=lat,
            lon=lon,
            radius=radius,
            name=data["n"],
            alt_smoothed=alt_smoothed,
            type=turnpoint_type,
            description=description,
        )


@dataclass
class QRCodeTask:
    """QR code task representation."""

    version: int = QR_CODE_TASK_VERSION
    task_type: Optional[QRCodeTaskType] = None
    earth_model: Optional[QRCodeEarthModel] = None
    turnpoints_polyline: Optional[str] = None
    turnpoints: List[QRCodeTurnpoint] = field(default_factory=list)
    takeoff: Optional[QRCodeTakeoff] = None
    sss: Optional[QRCodeSSS] = None
    goal: Optional[QRCodeGoal] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"version": self.version}

        if self.task_type is not None:
            result["taskType"] = (
                "CLASSIC" if self.task_type == QRCodeTaskType.CLASSIC else "WAYPOINTS"
            )
        if self.earth_model is not None:
            result["e"] = self.earth_model.value
        if self.turnpoints:
            result["t"] = [tp.to_dict() for tp in self.turnpoints]
        if self.takeoff:
            takeoff_dict = self.takeoff.to_dict()
            if "o" in takeoff_dict:
                result["to"] = takeoff_dict["o"]
            if "c" in takeoff_dict:
                result["tc"] = takeoff_dict["c"]
        if self.sss:
            result["s"] = self.sss.to_dict()
        if self.goal:
            result["g"] = self.goal.to_dict()

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeTask":
        """Create from dictionary."""
        version = data.get("version", QR_CODE_TASK_VERSION)

        task_type = None
        if "taskType" in data:
            if data["taskType"] == "CLASSIC":
                task_type = QRCodeTaskType.CLASSIC
            elif data["taskType"] == "W":
                task_type = QRCodeTaskType.WAYPOINTS

        earth_model = None
        if "e" in data:
            earth_model = QRCodeEarthModel(data["e"])

        turnpoints_polyline = data.get("p")

        turnpoints = []
        if "t" in data:
            turnpoints = [QRCodeTurnpoint.from_dict(tp) for tp in data["t"]]

        takeoff = None
        if "to" in data or "tc" in data:
            takeoff_data = {}
            if "to" in data:
                takeoff_data["o"] = data["to"]
            if "tc" in data:
                takeoff_data["c"] = data["tc"]
            takeoff = QRCodeTakeoff.from_dict(takeoff_data)

        sss = None
        if "s" in data:
            sss = QRCodeSSS.from_dict(data["s"])

        goal = None
        if "g" in data:
            goal = QRCodeGoal.from_dict(data["g"])

        return cls(
            version=version,
            task_type=task_type,
            earth_model=earth_model,
            turnpoints_polyline=turnpoints_polyline,
            turnpoints=turnpoints,
            takeoff=takeoff,
            sss=sss,
            goal=goal,
        )

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_json(cls, json_str: str) -> "QRCodeTask":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def to_string(self) -> str:
        """Convert to XCTSK: URL string."""
        return QR_CODE_SCHEME + self.to_json()

    @classmethod
    def from_string(cls, url_str: str) -> "QRCodeTask":
        """Create from XCTSK: URL string."""
        if not url_str.startswith(QR_CODE_SCHEME):
            raise ValueError(f"Invalid QR code scheme, expected {QR_CODE_SCHEME}")

        json_str = url_str[len(QR_CODE_SCHEME) :]
        return cls.from_json(json_str)

    @classmethod
    def from_task(cls, task: "Task") -> "QRCodeTask":
        """Convert from regular Task format."""
        from .task import (
            Direction,
            EarthModel,
            GoalType,
            SSSType,
            TaskType,
            TurnpointType,
        )

        # Convert task type
        qr_task_type = None
        if task.task_type == TaskType.CLASSIC:
            qr_task_type = QRCodeTaskType.CLASSIC
        elif task.task_type == TaskType.WAYPOINTS:
            qr_task_type = QRCodeTaskType.WAYPOINTS

        # Convert earth model
        qr_earth_model = None
        if task.earth_model == EarthModel.WGS84:
            qr_earth_model = QRCodeEarthModel.WGS84
        elif task.earth_model == EarthModel.FAI_SPHERE:
            qr_earth_model = QRCodeEarthModel.FAI_SPHERE

        # Convert turnpoints
        qr_turnpoints = []
        coordinates = []

        for tp in task.turnpoints:
            qr_type = QRCodeTurnpointType.NONE
            if tp.type == TurnpointType.TAKEOFF:
                qr_type = QRCodeTurnpointType.TAKEOFF
            elif tp.type == TurnpointType.SSS:
                qr_type = QRCodeTurnpointType.SSS
            elif tp.type == TurnpointType.ESS:
                qr_type = QRCodeTurnpointType.ESS

            qr_turnpoint = QRCodeTurnpoint(
                lat=tp.waypoint.lat,
                lon=tp.waypoint.lon,
                radius=tp.radius,
                name=tp.waypoint.name,
                alt_smoothed=tp.waypoint.alt_smoothed,
                type=qr_type,
                description=tp.waypoint.description,
            )
            qr_turnpoints.append(qr_turnpoint)
            coordinates.append((tp.waypoint.lat, tp.waypoint.lon))

        # Generate polyline from coordinates
        turnpoints_polyline = polyline.encode(coordinates, precision=5)

        # Convert takeoff
        qr_takeoff = None
        if task.takeoff:
            qr_takeoff = QRCodeTakeoff(
                time_open=task.takeoff.time_open,
                time_close=task.takeoff.time_close,
            )

        # Convert SSS
        qr_sss = None
        if task.sss:
            qr_direction = (
                QRCodeDirection.ENTER
                if task.sss.direction == Direction.ENTER
                else QRCodeDirection.EXIT
            )
            qr_sss_type = (
                QRCodeSSSType.RACE
                if task.sss.type == SSSType.RACE
                else QRCodeSSSType.ELAPSED_TIME
            )

            qr_sss = QRCodeSSS(
                direction=qr_direction,
                type=qr_sss_type,
                time_gates=task.sss.time_gates,
            )

        # Convert goal
        qr_goal = None
        if task.goal:
            qr_goal_type = None
            if task.goal.type == GoalType.LINE:
                qr_goal_type = QRCodeGoalType.LINE
            elif task.goal.type == GoalType.CYLINDER:
                qr_goal_type = QRCodeGoalType.CYLINDER

            qr_goal = QRCodeGoal(
                deadline=task.goal.deadline,
                type=qr_goal_type,
            )

        return cls(
            version=QR_CODE_TASK_VERSION,
            task_type=qr_task_type,
            earth_model=qr_earth_model,
            turnpoints_polyline=turnpoints_polyline,
            turnpoints=qr_turnpoints,
            takeoff=qr_takeoff,
            sss=qr_sss,
            goal=qr_goal,
        )

    def to_task(self) -> "Task":
        """Convert to regular Task format."""
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
            Turnpoint,
            TurnpointType,
            Waypoint,
        )

        # Convert task type
        task_type = TaskType.CLASSIC
        if self.task_type == QRCodeTaskType.WAYPOINTS:
            task_type = TaskType.WAYPOINTS

        # Convert earth model
        earth_model = None
        if self.earth_model == QRCodeEarthModel.WGS84:
            earth_model = EarthModel.WGS84
        elif self.earth_model == QRCodeEarthModel.FAI_SPHERE:
            earth_model = EarthModel.FAI_SPHERE

        # Convert turnpoints
        turnpoints = []
        for qr_tp in self.turnpoints:
            tp_type = None
            if qr_tp.type == QRCodeTurnpointType.TAKEOFF:
                tp_type = TurnpointType.TAKEOFF
            elif qr_tp.type == QRCodeTurnpointType.SSS:
                tp_type = TurnpointType.SSS
            elif qr_tp.type == QRCodeTurnpointType.ESS:
                tp_type = TurnpointType.ESS

            waypoint = Waypoint(
                name=qr_tp.name,
                lat=qr_tp.lat,
                lon=qr_tp.lon,
                alt_smoothed=qr_tp.alt_smoothed,
                description=qr_tp.description,
            )

            turnpoint = Turnpoint(
                radius=qr_tp.radius,
                waypoint=waypoint,
                type=tp_type,
            )
            turnpoints.append(turnpoint)

        # Convert takeoff
        takeoff = None
        if self.takeoff:
            takeoff = Takeoff(
                time_open=self.takeoff.time_open,
                time_close=self.takeoff.time_close,
            )

        # Convert SSS
        sss = None
        if self.sss:
            direction = (
                Direction.ENTER
                if self.sss.direction == QRCodeDirection.ENTER
                else Direction.EXIT
            )
            sss_type = (
                SSSType.RACE
                if self.sss.type == QRCodeSSSType.RACE
                else SSSType.ELAPSED_TIME
            )

            sss = SSS(
                type=sss_type,
                direction=direction,
                time_gates=self.sss.time_gates,
                time_close=None,  # QR code format doesn't include time_close
            )

        # Convert goal
        goal = None
        if self.goal:
            goal_type = None
            if self.goal.type == QRCodeGoalType.LINE:
                goal_type = GoalType.LINE
            elif self.goal.type == QRCodeGoalType.CYLINDER:
                goal_type = GoalType.CYLINDER

            goal = Goal(
                type=goal_type,
                deadline=self.goal.deadline,
            )

        return Task(
            task_type=task_type,
            version=1,  # Regular task version
            turnpoints=turnpoints,
            earth_model=earth_model,
            takeoff=takeoff,
            sss=sss,
            goal=goal,
        )
