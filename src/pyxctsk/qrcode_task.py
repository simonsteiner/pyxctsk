"""XCTrack QR Code Task Format (Version 2).

Implements the XCTrack QR code task format for compact, efficient encoding of paragliding/hang gliding competition tasks.
This format is designed for QR code transfer, minimizing data size for reliable scanning in challenging conditions (e.g., direct sunlight).

Features:
- Polyline-encoded turnpoint coordinates (Google's polyline algorithm, ~0.8m lossy compression)
- Turnpoint metadata: altitude, radius, name, type, description
- Compressed time representations for takeoff, start, and goal
- Optional and backward-compatible fields to reduce QR payload
- Supports CLASSIC and WAYPOINTS task types
- Optional earth model (WGS84 or FAI sphere)
- Time gates for start/goal

Format details:
- Full and simplified (waypoints-only) JSON structures
- Field order and presence optimized for XCTrack compatibility
- See: https://xctrack.org/Competition_Interfaces.html
- Reference polyline implementation: https://gitlab.com/xcontest-public/xctrack-public/-/snippets/1927372

This module provides:
- `QRCodeTask` dataclass for QR code task representation
- Conversion to/from regular Task objects
- Serialization to JSON and XCTSK: URL strings
- Parsing from QR code strings and JSON.
"""

import base64
import binascii
import json
import zlib
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .passthrough import QR_EXTENSIONS_KEY, read_passthrough, write_passthrough
from .qrcode_enums import (
    QRCodeEarthModel,
    QRCodeTaskType,
)
from .qrcode_models import QRCodeGoal, QRCodeSSS, QRCodeTakeoff, QRCodeTurnpoint

if TYPE_CHECKING:
    from .task import Task

# Constants
QR_CODE_SCHEME = "XCTSK:"
# The spec's zlib+base64 variant: "It is recommended that the software accepts
# both XCTSK and XCTSKZ [...] In the future we prefer to use the XCTSKZ
# encoding." Reading both is mandatory; which one we write is the caller's
# choice, and XCTSK: stays the default so existing output is unchanged.
QR_CODE_SCHEME_COMPRESSED = "XCTSKZ:"
QR_CODE_TASK_VERSION = 2


def compress_payload(json_str: str) -> str:
    """Compress a QR payload to the ``XCTSKZ:`` body: zlib, then base64.

    Args:
        json_str: The task JSON to compress.

    Returns:
        str: The base64-encoded zlib stream, as ASCII.
    """
    return base64.b64encode(zlib.compress(json_str.encode("utf-8"))).decode("ascii")


def decompress_payload(payload: str) -> str:
    """Decompress an ``XCTSKZ:`` body back to task JSON.

    Args:
        payload: The base64-encoded zlib stream that followed ``XCTSKZ:``.

    Returns:
        str: The decompressed task JSON.

    Raises:
        ValueError: If the payload is not valid base64 or not a zlib stream.
    """
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"XCTSKZ payload is not valid base64: {exc}") from exc

    try:
        return zlib.decompress(raw).decode("utf-8")
    except (zlib.error, UnicodeDecodeError) as exc:
        raise ValueError(f"XCTSKZ payload is not a zlib stream: {exc}") from exc


@dataclass
class QRCodeTask:
    """QR code task representation.

    Represents a complete XCTrack task in QR code format (version 2).

    This format is optimized for QR codes with efficient data representation:
    - Polyline-encoded turnpoint coordinates (lossy ~0.8m precision)
    - Compressed time representations
    - Optional fields to minimize data size
    - Backward compatibility with obsolete fields

    JSON structure:
    {
        "taskType": "CLASSIC" | "WAYPOINTS",
        "version": 2,
        "t": [turnpoints array],
        "s": {start section, optional},
        "g": {goal section, optional},
        "e": earth_model (optional, 0=WGS84 default, 1=FAI sphere),
        "to": takeoff_open_time (optional),
        "tc": takeoff_close_time (optional)
    }
    """

    version: int = QR_CODE_TASK_VERSION
    task_type: QRCodeTaskType | None = None
    earth_model: QRCodeEarthModel | None = None
    turnpoints: list[QRCodeTurnpoint] = field(default_factory=list)
    takeoff: QRCodeTakeoff | None = None
    sss: QRCodeSSS | None = None
    goal: QRCodeGoal | None = None
    extensions: list[dict[str, Any]] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands; everything else lands in ``unknown``.
    KNOWN_KEYS = frozenset(
        {"taskType", "version", "T", "V", "t", "s", "g", "e", "to", "tc", "x"}
    )

    def to_dict(self, simplified: bool = False) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Builds the QR code task dictionary in the precise field order required
        by the XCTrack format specification.

        A WAYPOINTS task always uses the simplified form regardless of the
        argument: the spec's competition format only defines
        ``"taskType": "CLASSIC"``, and an XC/Waypoints task is identified by
        ``"T": "W"`` instead.

        Args:
            simplified: If True, use simplified XC/Waypoints format with only T, V, and t fields

        Returns:
            Dictionary with QR code task format fields
        """
        if simplified or self.task_type == QRCodeTaskType.WAYPOINTS:
            # XC/Waypoints simplified format
            simplified_result: OrderedDict[str, Any] = OrderedDict()
            simplified_result["T"] = "W"  # taskType: Waypoints
            simplified_result["V"] = self.version  # version: 2

            # Turnpoints - only include if they exist
            if self.turnpoints:
                simplified_result["t"] = [
                    tp.to_dict(simplified=True) for tp in self.turnpoints
                ]
            # Extensions and unknown keys are preserved here for the same
            # reason as in the full format: from_dict reads them, so dropping
            # them on the way out would lose data on a round-trip.
            write_passthrough(
                simplified_result, self.extensions, self.unknown, QR_EXTENSIONS_KEY
            )

            return simplified_result

        # Full format - Create an empty dict to start with
        result: dict[str, Any] = {}

        # To match the expected output exactly, we need to build the dictionary
        # in the precise order seen in the expected output

        # 1. Goal (if exists)
        if self.goal:
            result["g"] = self.goal.to_dict()

        # 2. SSS (if exists)
        if self.sss:
            result["s"] = self.sss.to_dict()

        # 3. Turnpoints (if exist)
        if self.turnpoints:
            result["t"] = [tp.to_dict() for tp in self.turnpoints]

        # 4. Task type - CLASSIC is the only value this format defines;
        #    WAYPOINTS took the simplified branch above.
        if self.task_type is not None:
            result["taskType"] = "CLASSIC"

        # 5. Takeoff fields - always include them as null if not set
        # This is important to match the expected test output exactly
        if self.takeoff:
            takeoff_dict = self.takeoff.to_dict()
            result["tc"] = takeoff_dict.get("c", None)
            result["to"] = takeoff_dict.get("o", None)
        else:
            result["tc"] = None
            result["to"] = None

        # 6. Earth model - only include if not default (WGS84 = 0)
        if self.earth_model is not None and self.earth_model != QRCodeEarthModel.WGS84:
            result["e"] = self.earth_model.value

        # 7. Version
        result["version"] = self.version

        # 8. Extensions and unknown keys last
        write_passthrough(result, self.extensions, self.unknown, QR_EXTENSIONS_KEY)

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeTask":
        """Create from dictionary.

        Handles both full format and simplified XC/Waypoints format.
        """
        # Check if this is the simplified XC/Waypoints format
        is_simplified = "T" in data and "V" in data
        extensions, unknown = read_passthrough(data, cls.KNOWN_KEYS, QR_EXTENSIONS_KEY)

        if is_simplified:
            # Simplified XC/Waypoints format
            version = data.get("V", QR_CODE_TASK_VERSION)

            # Task type is always WAYPOINTS in simplified format
            simplified_task_type = QRCodeTaskType.WAYPOINTS

            turnpoints = []
            if "t" in data:
                turnpoints = [QRCodeTurnpoint.from_dict(tp) for tp in data["t"]]

            return cls(
                version=version,
                task_type=simplified_task_type,
                earth_model=None,  # Default to WGS84
                turnpoints=turnpoints,
                takeoff=None,
                sss=None,
                goal=None,
                extensions=extensions,
                unknown=unknown,
            )

        # Full format
        version_raw = data.get("version", QR_CODE_TASK_VERSION)
        version = version_raw if isinstance(version_raw, int) else int(str(version_raw))

        task_type: QRCodeTaskType | None = None
        if "taskType" in data:
            if data["taskType"] == "CLASSIC":
                task_type = QRCodeTaskType.CLASSIC
            elif data["taskType"] == "WAYPOINTS" or data["taskType"] == "W":
                task_type = QRCodeTaskType.WAYPOINTS

        earth_model: QRCodeEarthModel | None = None
        if "e" in data:
            e_val = data["e"]
            e_int = e_val if isinstance(e_val, int) else int(str(e_val))
            earth_model = QRCodeEarthModel(e_int)

        turnpoints = []
        if "t" in data and isinstance(data["t"], list):
            turnpoints = [QRCodeTurnpoint.from_dict(tp) for tp in data["t"]]

        takeoff = None
        if ("to" in data and data["to"] is not None) or (
            "tc" in data and data["tc"] is not None
        ):
            takeoff_data = {}
            if "to" in data:
                takeoff_data["o"] = data["to"]
            if "tc" in data:
                takeoff_data["c"] = data["tc"]
            takeoff = QRCodeTakeoff.from_dict(takeoff_data)

        sss = None
        if "s" in data and isinstance(data["s"], dict):
            sss = QRCodeSSS.from_dict(data["s"])

        goal = None
        if "g" in data and isinstance(data["g"], dict):
            goal = QRCodeGoal.from_dict(data["g"])

        return cls(
            version=version,
            task_type=task_type,
            earth_model=earth_model,
            turnpoints=turnpoints,
            takeoff=takeoff,
            sss=sss,
            goal=goal,
            extensions=extensions,
            unknown=unknown,
        )

    def to_json(self, simplified: bool = False) -> str:
        """Convert to JSON string.

        Returns:
            Compact JSON string suitable for QR code embedding
        """
        return json.dumps(
            self.to_dict(simplified=simplified),
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def to_waypoints_json(self) -> str:
        """Convert to XC/Waypoints simplified JSON format.

        Returns:
            Compact JSON string in XC/Waypoints format
        """
        return self.to_json(simplified=True)

    def _to_scheme_string(self, json_str: str, compressed: bool) -> str:
        """Prefix a payload with the scheme it belongs to, compressing if asked."""
        if compressed:
            return QR_CODE_SCHEME_COMPRESSED + compress_payload(json_str)
        return QR_CODE_SCHEME + json_str

    def to_string(self, compressed: bool = False) -> str:
        """Convert to a QR code URL string.

        Args:
            compressed: If True, emit the ``XCTSKZ:`` form — the same JSON
                zlib-compressed and base64-encoded, which the spec prefers going
                forward because it fits far more task into a scannable code.

        Returns:
            Complete QR code string with the XCTSK: or XCTSKZ: scheme prefix
        """
        return self._to_scheme_string(self.to_json(), compressed)

    def to_compressed_string(self) -> str:
        """Convert to an ``XCTSKZ:`` URL string.

        Convenience for :meth:`to_string` with ``compressed=True``.

        Returns:
            Complete QR code string with the XCTSKZ: scheme prefix
        """
        return self.to_string(compressed=True)

    def to_waypoints_string(self, compressed: bool = False) -> str:
        """Convert to an XC/Waypoints QR code URL string.

        Args:
            compressed: If True, emit the ``XCTSKZ:`` form.

        Returns:
            Complete QR code string in simplified format
        """
        return self._to_scheme_string(self.to_waypoints_json(), compressed)

    @classmethod
    def from_json(cls, json_str: str) -> "QRCodeTask":
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_string(cls, url_str: str) -> "QRCodeTask":
        """Create from a QR code URL string in either scheme.

        Both ``XCTSK:`` and ``XCTSKZ:`` are accepted, as the spec requires.

        Args:
            url_str: Complete QR code string with a scheme prefix

        Returns:
            QRCodeTask instance

        Raises:
            ValueError: If the string carries neither scheme, or if an
                ``XCTSKZ:`` payload cannot be decompressed.
        """
        if url_str.startswith(QR_CODE_SCHEME_COMPRESSED):
            payload = url_str[len(QR_CODE_SCHEME_COMPRESSED) :]
            return cls.from_json(decompress_payload(payload))

        if url_str.startswith(QR_CODE_SCHEME):
            return cls.from_json(url_str[len(QR_CODE_SCHEME) :])

        raise ValueError(
            f"Invalid QR code scheme, expected {QR_CODE_SCHEME} "
            f"or {QR_CODE_SCHEME_COMPRESSED}"
        )

    @classmethod
    def from_task(cls, task: "Task") -> "QRCodeTask":
        """Convert from regular Task format.

        Args:
            task: Task object to convert

        Returns:
            QRCodeTask instance optimized for QR code embedding
        """
        from .qrcode_conversion import task_to_qr_code_task

        return task_to_qr_code_task(task)

    @classmethod
    def from_task_waypoints(cls, task: "Task") -> "QRCodeTask":
        """Convert from regular Task format to XC/Waypoints simplified format.

        Args:
            task: Task object to convert

        Returns:
            QRCodeTask instance optimized for XC/Waypoints format
        """
        from .qrcode_conversion import task_to_qr_code_waypoints

        return task_to_qr_code_waypoints(task)

    def to_task(self) -> "Task":
        """Convert to regular Task format.

        Returns:
            Task object with full format specification
        """
        from .qrcode_conversion import qr_code_task_to_task

        return qr_code_task_to_task(self)
