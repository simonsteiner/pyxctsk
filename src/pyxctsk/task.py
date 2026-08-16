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
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from .passthrough import EXTENSIONS_KEY, read_passthrough, write_passthrough
from .qrcode_task import QRCodeTask
from .rounding import round_half_up
from .shared_enums import TimeOfDay


class Direction(str, Enum):
    """Enumeration of direction types for turnpoints.

    Attributes:
        ENTER (str): Enter direction.
        EXIT (str): Exit direction.
    """

    ENTER = "ENTER"
    EXIT = "EXIT"


# ``sss.direction`` is obsolete: the spec requires readers to ignore it and
# writers to still emit *some* value so older devices keep working. This is the
# value used when a task omits the field. EXIT is what all 22 reference tasks
# carry, so a task read without it re-exports the way XCTrack writes it.
OBSOLETE_DIRECTION_DEFAULT = Direction.EXIT


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
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "Waypoint":
        """Create from dictionary.

        The spec types ``altSmoothed`` as a number rather than an integer, but
        it is metres AMSL and the QR encoding can only carry whole metres, so a
        fractional value is rounded to honor this class's ``int`` annotation.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Waypoint: Parsed Waypoint object.
        """
        return cls(
            name=data["name"],
            lat=data["lat"],
            lon=data["lon"],
            alt_smoothed=round_half_up(data["altSmoothed"]),
            description=data.get("description"),
        )


@dataclass
class Turnpoint:
    """Represents a turnpoint in a task.

    Attributes:
        radius (int): Turnpoint radius in meters.
        waypoint (Waypoint): Associated waypoint.
        type (Optional[TurnpointType]): Type of turnpoint.
        extensions (list): Opaque manufacturer extensions, preserved verbatim.
            The spec requires them to be in the same order as the root
            ``extensions`` list, with the ``id`` key not repeated here.
        unknown (dict): Keys the spec does not define, preserved verbatim.
            See :attr:`Task.unknown`.
    """

    radius: int
    waypoint: Waypoint
    type: TurnpointType | None = None
    extensions: list[dict[str, Any]] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands; everything else lands in ``unknown``.
    KNOWN_KEYS = frozenset({"radius", "waypoint", "type", "extensions"})

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result: dict[str, Any] = {
            "radius": self.radius,
            "waypoint": self.waypoint.to_dict(),
        }
        if self.type and self.type != TurnpointType.NONE:
            result["type"] = self.type.value
        write_passthrough(result, self.extensions, self.unknown, EXTENSIONS_KEY)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Turnpoint":
        """Create from dictionary.

        The spec types ``radius`` as a number rather than an integer; it is
        metres and the QR encoding can only carry whole metres, so a fractional
        value is rounded to honor this class's ``int`` annotation.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Turnpoint: Parsed Turnpoint object.
        """
        turnpoint_type = None
        if "type" in data and data["type"]:
            turnpoint_type = TurnpointType(data["type"])

        extensions, unknown = read_passthrough(data, cls.KNOWN_KEYS, EXTENSIONS_KEY)
        return cls(
            radius=round_half_up(data["radius"]),
            waypoint=Waypoint.from_dict(data["waypoint"]),
            type=turnpoint_type,
            extensions=extensions,
            unknown=unknown,
        )


@dataclass
class Takeoff:
    """Represents takeoff window with open/close times.

    Attributes:
        time_open (Optional[TimeOfDay]): Opening time.
        time_close (Optional[TimeOfDay]): Closing time.
    """

    time_open: TimeOfDay | None = None
    time_close: TimeOfDay | None = None

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "Takeoff":
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
        direction (Direction): SSS direction. Obsolete — ignored on read, still
            written so older devices keep working.
        time_gates (List[TimeOfDay]): List of time gates.
        time_close (Optional[TimeOfDay]): Optional closing time.
    """

    type: SSSType
    direction: Direction = OBSOLETE_DIRECTION_DEFAULT
    time_gates: list[TimeOfDay] = field(default_factory=list)
    time_close: TimeOfDay | None = None

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "SSS":
        """Create from dictionary.

        ``direction`` is obsolete. The spec requires readers to ignore it, so a
        task that omits it parses fine and falls back to
        :data:`OBSOLETE_DIRECTION_DEFAULT`.

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

        direction = OBSOLETE_DIRECTION_DEFAULT
        if data.get("direction"):
            direction = Direction(data["direction"])

        return cls(
            type=SSSType(data["type"]),
            direction=direction,
            time_gates=time_gates,
            time_close=time_close,
        )


@dataclass
class Goal:
    """Represents a goal for a task.

    For goal type LINE, the radius of the last turnpoint represents half of the
    goal line's total length. The line itself is not stored here — it is derived
    from that radius by :func:`~pyxctsk.goal_line.goal_line_length_from_turnpoints`,
    which is the single source of that rule. The goal line orientation is
    perpendicular to the azimuth to the last turnpoint center.

    Attributes:
        type (Optional[GoalType]): Goal type.
        deadline (Optional[TimeOfDay]): Goal deadline.
        finish_altitude (Optional[float]): Elevated goal altitude in meters AGL,
            measured from the altitude of the last turnpoint.
    """

    type: GoalType | None = None
    deadline: TimeOfDay | None = None
    finish_altitude: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        The spec's goal object has exactly three keys — ``type``, ``deadline``
        and ``finishAltitude``. The non-spec ``lineLength`` older versions wrote
        is deliberately not emitted: it is always twice the last turnpoint's
        radius, which is what the spec already says that radius means, so
        writing it would invent a field.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result: dict[str, Any] = {}
        if self.type:
            result["type"] = self.type.value
        if self.deadline:
            result["deadline"] = self.deadline.to_json_string()
        if self.finish_altitude is not None:
            result["finishAltitude"] = self.finish_altitude
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        """Create from dictionary.

        The non-spec ``lineLength`` older versions wrote is ignored: it is
        always twice the last turnpoint's radius, so it carries nothing the
        turnpoints do not already say.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Goal: Parsed Goal object.
        """
        goal_type = None
        deadline = None
        finish_altitude = None

        if "type" in data:
            goal_type = GoalType(data["type"])
        if "deadline" in data:
            deadline = TimeOfDay.from_json_string(data["deadline"])
        if data.get("finishAltitude") is not None:
            finish_altitude = data["finishAltitude"]

        return cls(
            type=goal_type,
            deadline=deadline,
            finish_altitude=finish_altitude,
        )


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
        extensions (list): Opaque manufacturer extensions, preserved verbatim.
            Each carries an obligatory ``id`` identifying manufacturer and
            version; their order defines the order of turnpoint extensions.
        unknown (dict): Keys the spec does not define, preserved verbatim so a
            round-trip does not silently discard them. Producers do put data
            outside the spec's ``extensions`` mechanism — one writes the
            elevated goal altitude as a root ``{"o": {"v": 2, "fa": 1220}}``.
            Nothing here is interpreted: the value is carried, not understood,
            and in particular is never mapped onto a spec field, since a
            look-alike key may not share the spec's units (that ``fa`` is
            absolute AMSL where the spec's ``goal.finishAltitude`` is AGL
            above the last turnpoint).
    """

    task_type: TaskType
    version: int
    turnpoints: list[Turnpoint]
    earth_model: EarthModel | None = None
    takeoff: Takeoff | None = None
    sss: SSS | None = None
    goal: Goal | None = None
    extensions: list[dict[str, Any]] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands; everything else lands in ``unknown``.
    KNOWN_KEYS = frozenset(
        {
            "taskType",
            "version",
            "earthModel",
            "turnpoints",
            "takeoff",
            "sss",
            "goal",
            "extensions",
        }
    )

    def __post_init__(self) -> None:
        """Post-initialization processing.

        Enriches the task's goal so the constructed object always satisfies
        the documented contract below. This is the single place that derives
        goal defaults; ``from_dict`` and ``to_dict`` rely on it rather than
        re-deriving the same rules.
        """
        self.goal = self._derive_goal(self.turnpoints, self.goal)

    @staticmethod
    def _derive_goal(
        turnpoints: "list[Turnpoint]", goal: "Goal | None"
    ) -> "Goal | None":
        """Return the effective goal for a task, applying defaults explicitly.

        Contract — a task with at least one turnpoint always has a goal:
          - if no goal was supplied, an empty one is created;
          - an unspecified goal type defaults to ``CYLINDER``.

        With no turnpoints the goal is returned unchanged (typically ``None``).
        A goal that already satisfies the contract is returned as-is; otherwise
        a copy is returned, so constructing a Task never mutates the caller's
        object.

        Args:
            turnpoints: The task's turnpoints.
            goal: The goal supplied at construction, if any.

        Returns:
            The enriched goal, or the original value when there are no turnpoints.
        """
        if not turnpoints:
            return goal

        if goal is None:
            return Goal(type=GoalType.CYLINDER)

        if not goal.type:
            return replace(goal, type=GoalType.CYLINDER)

        return goal

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        result: dict[str, Any] = {
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
        write_passthrough(result, self.extensions, self.unknown, EXTENSIONS_KEY)

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
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

        extensions, unknown = read_passthrough(data, cls.KNOWN_KEYS, EXTENSIONS_KEY)
        # Goal defaults are derived once in Task.__post_init__; no need to
        # repeat the rules here.
        return cls(
            task_type=TaskType(data["taskType"]),
            version=data["version"],
            turnpoints=turnpoints,
            earth_model=earth_model,
            takeoff=takeoff,
            sss=sss,
            goal=goal,
            extensions=extensions,
            unknown=unknown,
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

    def to_qr_code_task(self) -> QRCodeTask:
        """Convert to QR code task format.

        Returns:
            QRCodeTask: QRCodeTask object created from this task.
        """
        return QRCodeTask.from_task(self)

    def validate(self) -> list[str]:
        """Check the task against the spec's structural rules.

        The spec constrains how the special turnpoint types may be arranged:

        - ``TAKEOFF`` "can be used only for the first turnpoint";
        - ``SSS`` and ``ESS`` "must appear exactly once";
        - ``SSS`` "must appear before ESS".

        These apply to CLASSIC tasks. An XC/Waypoints task is a plain route
        with no speed section, so the SSS/ESS rules are not checked for it.

        This is a report, not a gate — parsing accepts structurally invalid
        tasks so they can still be inspected and converted. Pass
        ``strict=True`` to :func:`pyxctsk.parse_task` to turn violations into a
        :class:`~pyxctsk.exceptions.TaskValidationError`.

        Returns:
            list[str]: One message per violated rule; empty if the task is valid.
        """
        issues: list[str] = []

        if not self.turnpoints:
            issues.append("task has no turnpoints")
            return issues

        misplaced = [
            i
            for i, tp in enumerate(self.turnpoints)
            if tp.type == TurnpointType.TAKEOFF and i != 0
        ]
        for i in misplaced:
            issues.append(
                f"TAKEOFF is only allowed on the first turnpoint, found at index {i}"
            )

        if self.task_type == TaskType.WAYPOINTS:
            return issues

        indices = {
            special: [i for i, tp in enumerate(self.turnpoints) if tp.type == special]
            for special in (TurnpointType.SSS, TurnpointType.ESS)
        }
        for special, found in indices.items():
            if len(found) != 1:
                issues.append(
                    f"{special.value} must appear exactly once, found {len(found)}"
                )

        sss, ess = indices[TurnpointType.SSS], indices[TurnpointType.ESS]
        if len(sss) == 1 and len(ess) == 1 and sss[0] > ess[0]:
            issues.append(
                f"SSS must appear before ESS, found SSS at {sss[0]} and ESS at {ess[0]}"
            )

        return issues

    def find_ess_turnpoint(self) -> Turnpoint | None:
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
