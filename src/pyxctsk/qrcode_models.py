"""Data models for the XCTrack QR code task format.

This module defines immutable dataclasses representing the main components of an XCTrack QR code task:
- QRCodeGoal: Goal timing and type
- QRCodeSSS: Start Speed Section (SSS) timing and type
- QRCodeTakeoff: Takeoff open/close times
- QRCodeTurnpoint: Turnpoint with compressed coordinate encoding

Each class provides methods for serialization to and from the compact JSON format used in QR codes,
including custom polyline encoding for turnpoint coordinates. These models are used for parsing,
generating, and manipulating XCTrack-compatible QR code tasks.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from .qrcode_encoding import (
    decode_nums,
    encode_competition_turnpoint,
    encode_waypoint_turnpoint,
)
from .qrcode_enums import (
    QRCodeDirection,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTurnpointType,
)
from .shared_enums import TimeOfDay


@dataclass
class QRCodeGoal:
    """QR code goal representation.

    Represents goal timing and type information for QR code format.

    Fields correspond to JSON format:
    - deadline: Goal deadline time (optional, defaults to 23:00 local time)
    - type: Goal type - LINE (1) or CYLINDER (2, default)
    """

    deadline: TimeOfDay | None = None
    type: QRCodeGoalType | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {}
        if self.deadline:
            result["d"] = self.deadline.to_json_string()
        if self.type is not None:
            result["t"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeGoal":
        """Create from dictionary."""
        # TimeOfDay imported from shared_enums

        deadline = None
        if "d" in data:
            deadline = TimeOfDay.from_json_string(data["d"])

        goal_type = None
        if "t" in data:
            goal_type = QRCodeGoalType(data["t"])

        return cls(deadline=deadline, type=goal_type)


@dataclass
class QRCodeSSS:
    """QR code SSS (Start Speed Section) representation.

    Represents start timing and type information for QR code format.

    Fields correspond to JSON format:
    - direction: OBSOLETE field kept for backwards compatibility (ignored when reading)
    - type: Start type - RACE (1) or ELAPSED_TIME (2)
    - time_gates: Array of time gates for start timing
    """

    direction: QRCodeDirection
    type: QRCodeSSSType
    time_gates: list["TimeOfDay"] = field(default_factory=list)

    def to_dict(self) -> OrderedDict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Create an ordered dict to ensure field order
        result: OrderedDict[str, Any] = OrderedDict()
        # Add direction first - OBSOLETE but kept for backwards compatibility
        result["d"] = self.direction.value
        # Add time_gates in the middle if they exist
        if self.time_gates:
            result["g"] = [gate.to_json_string() for gate in self.time_gates]
        # Add type last
        result["t"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeSSS":
        """Create from dictionary."""
        # TimeOfDay imported from shared_enums

        time_gates = []
        if "g" in data:
            time_gates = [TimeOfDay.from_json_string(gate) for gate in data["g"]]

        # Direction field is OBSOLETE and should be ignored when reading.
        # Falls back to the same value as the full-JSON path (see
        # task.OBSOLETE_DIRECTION_DEFAULT) so both readers agree.
        direction = QRCodeDirection.EXIT
        if data.get("d"):
            # For backwards compatibility, still read it if present
            direction = QRCodeDirection(data["d"])

        return cls(
            direction=direction,
            type=QRCodeSSSType(data["t"]),
            time_gates=time_gates,
        )


@dataclass
class QRCodeTakeoff:
    """QR code takeoff representation.

    Represents takeoff timing information for QR code format.

    Fields correspond to JSON format:
    - time_open: Takeoff open time (optional)
    - time_close: Takeoff close time (optional)
    """

    time_open: TimeOfDay | None = None
    time_close: TimeOfDay | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {}
        if self.time_open:
            result["o"] = self.time_open.to_json_string()
        if self.time_close:
            result["c"] = self.time_close.to_json_string()
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeTakeoff":
        """Create from dictionary."""
        # TimeOfDay imported from shared_enums

        time_open = None
        time_close = None

        if "o" in data and data["o"] is not None:
            time_open = TimeOfDay.from_json_string(data["o"])
        if "c" in data and data["c"] is not None:
            time_close = TimeOfDay.from_json_string(data["c"])

        return cls(time_open=time_open, time_close=time_close)


@dataclass
class QRCodeTurnpoint:
    """QR code turnpoint representation.

    Represents a single turnpoint in the QR code format with compressed coordinates.

    Fields correspond to JSON format:
    - lat, lon: Geographic coordinates
    - radius: Turnpoint radius in meters
    - name: Turnpoint name (required in JSON as "n")
    - alt_smoothed: Altitude in meters
    - type: Turnpoint type - SSS (2), ESS (3), or NONE (0) for regular turnpoints
    - description: Optional turnpoint description (JSON field "d")

    The coordinates are encoded using a custom polyline algorithm that compresses
    longitude, latitude, altitude, and radius into a single string field "z".
    This encoding is lossy with ~0.8m precision, well within FAI 5m tolerance.
    """

    lat: float
    lon: float
    radius: int
    name: str
    alt_smoothed: int
    type: QRCodeTurnpointType = QRCodeTurnpointType.NONE
    description: str | None = None

    def to_dict(self, simplified: bool = False) -> OrderedDict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Uses custom polyline encoding for turnpoint coordinates (lon, lat, alt, radius)
        following XCTrack's implementation. The encoding is lossy with ~0.8m precision
        but well within FAI 5m tolerance.

        Args:
            simplified: If True, use simplified XC/Waypoints format with only "z" and "n"

        Returns:
            Dictionary with fields: d (description), n (name), t (type), z (encoded coords)
            For simplified format: only n (name) and z (encoded coords)
        """
        if simplified:
            # XC/Waypoints simplified format - only name and encoded coordinates.
            # Its "z" carries three numbers; the radius belongs to the
            # competition format only.
            return OrderedDict(
                [
                    ("n", self.name),
                    (
                        "z",
                        encode_waypoint_turnpoint(
                            self.lon, self.lat, self.alt_smoothed
                        ),
                    ),
                ]
            )

        # Use the XCTrack custom encoding
        encoded = encode_competition_turnpoint(
            self.lon, self.lat, self.alt_smoothed, self.radius
        )

        # Full format - Create result dictionary with exact order to match expected output
        result: OrderedDict[str, Any] = OrderedDict()

        # Only include description if it has a non-empty value
        if self.description:
            result["d"] = self.description

        result["n"] = self.name

        # Add type field before z - only for SSS (2) and ESS (3)
        # TAKEOFF (1) should not have the "t" field in QR code format
        if self.type == QRCodeTurnpointType.SSS or self.type == QRCodeTurnpointType.ESS:
            result["t"] = self.type.value

        # Add z last
        result["z"] = encoded

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeTurnpoint":
        """Create from dictionary.

        The ``z`` field is the only source of coordinates, and its length says
        which format it is: four numbers for a competition turnpoint
        (lon, lat, altitude, radius), three for an XC/Waypoints one
        (lon, lat, altitude — a route "without cylinders", hence radius 0).

        Args:
            data: Dictionary with turnpoint data

        Returns:
            QRCodeTurnpoint instance
        """
        lon = 0.0
        lat = 0.0
        alt_smoothed = 0
        radius = 0

        nums = decode_nums(data["z"]) if "z" in data else []
        if len(nums) >= 4:
            lon, lat, alt_smoothed, radius = (
                nums[0] / 1e5,
                nums[1] / 1e5,
                nums[2],
                nums[3],
            )
        elif len(nums) == 3:
            lon, lat, alt_smoothed = nums[0] / 1e5, nums[1] / 1e5, nums[2]
        elif len(nums) == 2:
            lon, lat = nums[0] / 1e5, nums[1] / 1e5

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
