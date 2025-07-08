"""QR code task format data models.

This module contains the data classes used in the XCTrack QR code task format.
These classes represent the various components of a QR code task: Goal, SSS,
Takeoff, and Turnpoint.
"""

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import polyline

from .qrcode_encoding import decode_nums, encode_competition_turnpoint
from .qrcode_enums import (
    QRCodeDirection,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTurnpointType,
)

if TYPE_CHECKING:
    from .task import TimeOfDay


@dataclass
class QRCodeGoal:
    """QR code goal representation.

    Represents goal timing and type information for QR code format.

    Fields correspond to JSON format:
    - deadline: Goal deadline time (optional, defaults to 23:00 local time)
    - type: Goal type - LINE (1) or CYLINDER (2, default)
    """

    deadline: Optional["TimeOfDay"] = None
    type: Optional[QRCodeGoalType] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {}
        if self.deadline:
            result["d"] = self.deadline.to_json_string().strip('"')
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
    """QR code SSS (Start Speed Section) representation.

    Represents start timing and type information for QR code format.

    Fields correspond to JSON format:
    - direction: OBSOLETE field kept for backwards compatibility (ignored when reading)
    - type: Start type - RACE (1) or ELAPSED_TIME (2)
    - time_gates: Array of time gates for start timing
    """

    direction: QRCodeDirection
    type: QRCodeSSSType
    time_gates: List["TimeOfDay"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        # Create an ordered dict to ensure field order
        result = OrderedDict()
        # Add direction first - OBSOLETE but kept for backwards compatibility
        result["d"] = self.direction.value
        # Add time_gates in the middle if they exist
        if self.time_gates:
            result["g"] = [gate.to_json_string().strip('"') for gate in self.time_gates]
        # Add type last
        result["t"] = self.type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeSSS":
        """Create from dictionary."""
        from .task import TimeOfDay

        time_gates = []
        if "g" in data:
            time_gates = [TimeOfDay.from_json_string(gate) for gate in data["g"]]

        # Direction field is OBSOLETE and should be ignored when reading
        # Use ENTER as default when not present or when ignoring obsolete field
        direction = QRCodeDirection.ENTER
        if "d" in data:
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
    description: Optional[str] = None

    def to_dict(self, simplified: bool = False) -> Dict[str, Any]:
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
        # Use the XCTrack custom encoding
        encoded = encode_competition_turnpoint(
            self.lon, self.lat, self.alt_smoothed, self.radius
        )

        if simplified:
            # XC/Waypoints simplified format - only name and encoded coordinates
            return OrderedDict([("n", self.name), ("z", encoded)])

        # Full format - Create result dictionary with exact order to match expected output
        result = OrderedDict()

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
    def from_dict(cls, data: Dict[str, Any]) -> "QRCodeTurnpoint":
        """Create from dictionary.

        Decodes turnpoint data from QR code JSON format. Handles both individual
        coordinate fields (x, y, a, r) and polyline-encoded data (z field).

        Args:
            data: Dictionary with turnpoint data

        Returns:
            QRCodeTurnpoint instance
        """
        # Use individual fields for better reliability
        lon = data.get("x", 0.0)
        lat = data.get("y", 0.0)
        alt_smoothed = data.get("a", 0)
        radius = data.get("r", 1000)

        # Fallback: try polyline decoding if individual fields not available
        if "z" in data and ("x" not in data or "y" not in data):
            try:
                # Try using our custom decoder for XCTrack format first
                nums = decode_nums(data["z"])
                if len(nums) >= 4:
                    lon = nums[0] / 1e5
                    lat = nums[1] / 1e5
                    alt_smoothed = nums[2]
                    radius = nums[3]
                elif len(nums) >= 2:
                    lon = nums[0] / 1e5
                    lat = nums[1] / 1e5
            except Exception:
                # Fallback to standard polyline library
                try:
                    coords = polyline.decode(data["z"], precision=5)
                    if coords:
                        coord = coords[0]  # Take first coordinate
                        lon, lat = (
                            coord[1],
                            coord[0],
                        )  # Note: polyline lib uses lat,lon order
                except Exception:
                    # If all else fails, use defaults
                    pass

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
