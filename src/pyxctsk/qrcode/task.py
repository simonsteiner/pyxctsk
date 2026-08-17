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
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, ClassVar, Mapping, MutableMapping

from ..model.passthrough import QR_EXTENSIONS_KEY
from ..model.shape import (
    DEFAULTED,
    LENIENT_INT,
    Codec,
    Discriminator,
    Field,
    Nested,
    NestedList,
    Optionality,
    Shape,
    Value,
)
from .enums import (
    QRCodeEarthModel,
    QRCodeTaskType,
    QRCodeTurnpointType,
)
from .models import (
    QR_GOAL_SHAPE,
    QR_SSS_SHAPE,
    QR_TAKEOFF_SHAPE,
    QR_TURNPOINT_SHAPE,
    QR_WAYPOINT_TURNPOINT_SHAPE,
    QRCodeGoal,
    QRCodeSSS,
    QRCodeTakeoff,
    QRCodeTurnpoint,
)

if TYPE_CHECKING:
    from ..model.task import Task

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

    #: Keys the competition shape reads, derived from
    #: :data:`QR_TASK_SHAPE`; everything else lands in ``unknown``.
    COMPETITION_KEYS: ClassVar[frozenset[str]]

    #: Keys the simplified XC/Waypoints shape reads, derived from
    #: :data:`QR_WAYPOINTS_TASK_SHAPE`. Deliberately *not* the union with
    #: :attr:`COMPETITION_KEYS`: a single allow-list spanning both shapes told
    #: the passthrough that a competition key in a waypoints payload was
    #: understood, when this shape neither reads nor writes it, so ``e``,
    #: ``to`` and ``g`` were swallowed instead of carried through. With two
    #: tables there is no one place that union could be written down.
    SIMPLIFIED_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Builds the QR code task dictionary in the precise field order required
        by the XCTrack format specification.

        The shape follows from :attr:`task_type` alone. A WAYPOINTS task is the
        simplified XC/Waypoints form, identified by ``"T": "W"``; anything else
        is the competition form, whose only defined ``taskType`` is
        ``"CLASSIC"``. To render a task in the other shape, change its type —
        see :meth:`to_waypoints_json`.

        Returns:
            Dictionary with QR code task format fields
        """
        return self._shape_for(self.task_type == QRCodeTaskType.WAYPOINTS).write(self)

    @staticmethod
    def _shape_for(simplified: bool) -> "Shape[QRCodeTask]":
        """Return the table for one of this format's two shapes."""
        return QR_WAYPOINTS_TASK_SHAPE if simplified else QR_TASK_SHAPE

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeTask":
        """Create from dictionary.

        Handles both full format and simplified XC/Waypoints format.

        Each format is identified by its own task-type key, and only that:
        ``T`` for the simplified one, ``taskType`` for the competition one.
        The competition format has no ``T``, so there is no ambiguity. Version
        is not part of the discriminator — a payload missing ``V`` is still
        plainly a waypoints task, and treating it as a competition one left the
        task type unset and swallowed ``T`` as an unknown key.

        The same discriminator picks the passthrough allow-list, so each shape
        is measured against the keys it actually reads: a competition key in a
        waypoints payload is unknown here, and is carried through rather than
        silently dropped.
        """
        return cls._shape_for("T" in data).read(data)

    def to_json(self) -> str:
        """Convert to JSON string.

        Returns:
            Compact JSON string suitable for QR code embedding
        """
        return json.dumps(self.to_dict(), separators=(",", ":"), ensure_ascii=False)

    def as_waypoints(self) -> "QRCodeTask":
        """Return this task as an XC/Waypoints one.

        Rendering the simplified shape is a change of task type, not a mode
        flag: ``to_dict`` follows :attr:`task_type` and nothing else.

        The copy is reduced to what the format can represent — "a simple route
        from waypoints without cylinders". Radii, turnpoint types, descriptions,
        the timing sections and the earth model are dropped, because the
        simplified payload has nowhere to put them. Serialized output is
        unchanged either way, since ``to_dict`` never wrote those fields; what
        this fixes is the in-memory object, which used to keep values that
        reading the same payload back would not produce. Extensions and unknown
        keys stay: the simplified payload does carry those.

        Returns:
            QRCodeTask: A copy typed WAYPOINTS, carrying only representable
            values.
        """
        return replace(
            self,
            task_type=QRCodeTaskType.WAYPOINTS,
            turnpoints=[
                replace(
                    tp,
                    radius=0,
                    type=QRCodeTurnpointType.NONE,
                    description=None,
                )
                for tp in self.turnpoints
            ],
            earth_model=None,
            takeoff=None,
            sss=None,
            goal=None,
        )

    def to_waypoints_json(self) -> str:
        """Convert to XC/Waypoints simplified JSON format.

        Returns:
            Compact JSON string in XC/Waypoints format
        """
        return self.as_waypoints().to_json()

    def to_string(self, compressed: bool = False) -> str:
        """Convert to a QR code URL string.

        Args:
            compressed: If True, emit the ``XCTSKZ:`` form — the same JSON
                zlib-compressed and base64-encoded, which the spec prefers going
                forward because it fits far more task into a scannable code.

        Returns:
            Complete QR code string with the XCTSK: or XCTSKZ: scheme prefix
        """
        if compressed:
            return QR_CODE_SCHEME_COMPRESSED + compress_payload(self.to_json())
        return QR_CODE_SCHEME + self.to_json()

    def to_waypoints_string(self, compressed: bool = False) -> str:
        """Convert to an XC/Waypoints QR code URL string.

        Args:
            compressed: If True, emit the ``XCTSKZ:`` form.

        Returns:
            Complete QR code string in simplified format
        """
        return self.as_waypoints().to_string(compressed=compressed)

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
        from .conversion import task_to_qr_code_task

        return task_to_qr_code_task(task)

    @classmethod
    def from_task_waypoints(cls, task: "Task") -> "QRCodeTask":
        """Convert from regular Task format to XC/Waypoints simplified format.

        Args:
            task: Task object to convert

        Returns:
            QRCodeTask instance optimized for XC/Waypoints format
        """
        from .conversion import task_to_qr_code_waypoints

        return task_to_qr_code_waypoints(task)

    def to_task(self) -> "Task":
        """Convert to regular Task format.

        Returns:
            Task object with full format specification
        """
        from .conversion import qr_code_task_to_task

        return qr_code_task_to_task(self)


@dataclass(frozen=True)
class _CompetitionTaskType(Field):
    """``taskType``, which this shape reads more spellings than it writes.

    ``CLASSIC`` is the only value the competition shape defines — a WAYPOINTS
    task is the *other* shape, named by ``T``. So the key is read leniently,
    because older payloads did spell the waypoints type here (as ``WAYPOINTS``
    or ``W``), and written as the one constant this shape means.
    """

    @property
    def keys(self) -> tuple[str, ...]:
        """The competition shape's task-type key."""
        return ("taskType",)

    def read(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Accept either spelling of either type, or neither."""
        raw = data.get("taskType")
        if raw == "CLASSIC":
            return {"task_type": QRCodeTaskType.CLASSIC}
        if raw in ("WAYPOINTS", "W"):
            return {"task_type": QRCodeTaskType.WAYPOINTS}
        return {}

    def write(self, obj: Any, result: MutableMapping[str, Any]) -> None:
        """Write the only value this shape defines."""
        if obj.task_type is not None:
            result["taskType"] = "CLASSIC"


@dataclass(frozen=True)
class _TakeoffTimes(Field):
    """The takeoff window, which this format keeps at the root.

    Two keys and one attribute: ``to`` and ``tc`` are root keys rather than an
    object, and both are written even when there is no takeoff — as explicit
    nulls, which is what the reference producer emits and what the golden
    strings carry. A row owning two keys is what keeps that a row rather than a
    special case bolted onto the task's writer.
    """

    @property
    def keys(self) -> tuple[str, ...]:
        """Both root keys, in the order this format writes them."""
        return ("tc", "to")

    def read(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Rebuild the takeoff object from the two root keys."""
        times = {
            key: value
            for key, value in (("o", data.get("to")), ("c", data.get("tc")))
            if value is not None
        }
        if not times:
            return {}
        return {"takeoff": QR_TAKEOFF_SHAPE.read(times)}

    def write(self, obj: Any, result: MutableMapping[str, Any]) -> None:
        """Flatten the takeoff object back onto the root, nulls included."""
        rendered = QR_TAKEOFF_SHAPE.write(obj.takeoff) if obj.takeoff else {}
        result["tc"] = rendered.get("c")
        result["to"] = rendered.get("o")


#: WGS84 is the default, so the format omits it rather than spelling it out.
_NON_DEFAULT_EARTH_MODEL = Optionality(
    absent=lambda raw: raw is None,
    omit=lambda value: value is None or value == QRCodeEarthModel.WGS84,
)

#: The nested sections are objects or they are not there. A value of the wrong
#: shape is not read rather than raising: it lands in ``unknown`` and travels
#: back out untouched, which is what this library does with anything it cannot
#: interpret.
_A_DICT_OR_NOTHING = Optionality(
    absent=lambda raw: not isinstance(raw, dict),
    omit=lambda value: value is None,
)
_A_LIST_OR_NOTHING = Optionality(
    absent=lambda raw: not isinstance(raw, list),
    omit=lambda value: not value,
)

#: ``e`` is an integer a producer may have written as a string.
_EARTH_MODEL = Codec(
    lambda model: model.value,
    lambda raw: QRCodeEarthModel(LENIENT_INT.from_wire(raw)),
)

#: The competition shape, in the key order tools.xcontest.org emits.
QR_TASK_SHAPE = Shape(
    QRCodeTask,
    (
        Nested("goal", "g", QR_GOAL_SHAPE, _A_DICT_OR_NOTHING),
        Nested("sss", "s", QR_SSS_SHAPE, _A_DICT_OR_NOTHING),
        NestedList("turnpoints", "t", QR_TURNPOINT_SHAPE, _A_LIST_OR_NOTHING),
        _CompetitionTaskType(),
        _TakeoffTimes(),
        Value("earth_model", "e", _EARTH_MODEL, _NON_DEFAULT_EARTH_MODEL),
        Value("version", "version", LENIENT_INT, DEFAULTED),
    ),
    ext_key=QR_EXTENSIONS_KEY,
)
QRCodeTask.COMPETITION_KEYS = QR_TASK_SHAPE.keys

#: The simplified XC/Waypoints shape: a task type, a version, and a route.
QR_WAYPOINTS_TASK_SHAPE = Shape(
    QRCodeTask,
    (
        Discriminator("T", "W", "task_type", QRCodeTaskType.WAYPOINTS),
        Value("version", "V", LENIENT_INT, DEFAULTED),
        NestedList("turnpoints", "t", QR_WAYPOINT_TURNPOINT_SHAPE, _A_LIST_OR_NOTHING),
    ),
    ext_key=QR_EXTENSIONS_KEY,
)
QRCodeTask.SIMPLIFIED_KEYS = QR_WAYPOINTS_TASK_SHAPE.keys
