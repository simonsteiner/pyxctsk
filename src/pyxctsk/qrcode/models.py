"""Data models for the XCTrack QR code task format.

This module defines immutable dataclasses representing the main components of an XCTrack QR code task:
- QRCodeGoal: Goal timing and type
- QRCodeSSS: Start Speed Section (SSS) timing and type
- QRCodeTakeoff: Takeoff open/close times
- QRCodeTurnpoint: Turnpoint with compressed coordinate encoding

Each class declares its wire mapping as a field table — see
:mod:`pyxctsk.model.shape` — and its ``to_dict`` / ``from_dict`` are the two
traversals of it. The turnpoint has two tables rather than one, because the
competition format and the simplified XC/Waypoints one are two shapes of the
same class and each reads exactly what it writes.
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping, MutableMapping

from ..model.passthrough import QR_EXTENSIONS_KEY
from ..model.shape import (
    DEFAULTED,
    OPTIONAL_EMPTY,
    REQUIRED,
    TIME_OF_DAY,
    Field,
    Optionality,
    Shape,
    Value,
    enum_codec,
    list_codec,
)
from ..model.time_of_day import TimeOfDay
from .encoding import (
    decode_nums,
    encode_competition_turnpoint,
    encode_waypoint_turnpoint,
)
from .enums import (
    QR_OBSOLETE_DIRECTION_DEFAULT,
    QRCodeDirection,
    QRCodeGoalType,
    QRCodeSSSType,
    QRCodeTurnpointType,
)


@dataclass
class QRCodeGoal:
    """QR code goal representation.

    Represents goal timing and type information for QR code format.

    Fields correspond to JSON format:
    - deadline: Goal deadline time (optional, defaults to 23:00 local time)
    - type: Goal type - LINE (1) or CYLINDER (2, default)
    - finish_altitude: Elevated goal altitude in meters AGL (optional, "fa")
    - unknown: Keys this format does not define, preserved verbatim
    """

    deadline: TimeOfDay | None = None
    type: QRCodeGoalType | None = None
    finish_altitude: float | None = None
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands, derived from :data:`QR_GOAL_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Keys are emitted in the order tools.xcontest.org uses — ``d``, ``fa``,
        ``t`` — so output stays byte-identical to the reference producer. That
        order is the table's row order.
        """
        return QR_GOAL_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeGoal":
        """Create from dictionary."""
        return QR_GOAL_SHAPE.read(data)


QR_GOAL_SHAPE = Shape(
    QRCodeGoal,
    (
        Value("deadline", "d", TIME_OF_DAY),
        Value("finish_altitude", "fa"),
        Value("type", "t", enum_codec(QRCodeGoalType)),
    ),
)
QRCodeGoal.KNOWN_KEYS = QR_GOAL_SHAPE.keys


@dataclass
class QRCodeSSS:
    """QR code SSS (Start Speed Section) representation.

    Represents start timing and type information for QR code format.

    Fields correspond to JSON format:
    - type: Start type - RACE (1) or ELAPSED_TIME (2)
    - direction: OBSOLETE field kept for backwards compatibility (ignored when
      reading, so it carries the same default as the full format's ``SSS``)
    - time_gates: Array of time gates for start timing
    - unknown: Keys this format does not define, preserved verbatim
    """

    type: QRCodeSSSType
    direction: QRCodeDirection = QR_OBSOLETE_DIRECTION_DEFAULT
    time_gates: list["TimeOfDay"] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands, derived from :data:`QR_SSS_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return QR_SSS_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeSSS":
        """Create from dictionary."""
        return QR_SSS_SHAPE.read(data)


QR_SSS_SHAPE = Shape(
    QRCodeSSS,
    (
        # ``d`` is OBSOLETE: ignored on read, still written so older devices
        # keep working. It comes first, and the type last, to match the order
        # the reference producer emits.
        Value("direction", "d", enum_codec(QRCodeDirection), DEFAULTED),
        Value("time_gates", "g", list_codec(TIME_OF_DAY), OPTIONAL_EMPTY),
        Value("type", "t", enum_codec(QRCodeSSSType), REQUIRED),
    ),
)
QRCodeSSS.KNOWN_KEYS = QR_SSS_SHAPE.keys


@dataclass
class QRCodeTakeoff:
    """QR code takeoff representation.

    Represents takeoff timing information for QR code format.

    Fields correspond to JSON format:
    - time_open: Takeoff open time (optional)
    - time_close: Takeoff close time (optional)

    The one serializable shape here with no ``unknown``, because it is the one
    that is not an object on the wire: ``QRCodeTask`` flattens it to the root
    keys ``to`` and ``tc`` and rebuilds this ``{"o": …, "c": …}`` to read it
    back. No payload is ever handed to :meth:`from_dict` unfiltered, so an
    ``unknown`` here could never hold anything — those keys are the task's, and
    are on its allow-list.
    """

    time_open: TimeOfDay | None = None
    time_close: TimeOfDay | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return QR_TAKEOFF_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QRCodeTakeoff":
        """Create from dictionary."""
        return QR_TAKEOFF_SHAPE.read(data)


QR_TAKEOFF_SHAPE = Shape(
    QRCodeTakeoff,
    (
        Value("time_open", "o", TIME_OF_DAY),
        Value("time_close", "c", TIME_OF_DAY),
    ),
    carries_unknown=False,
)


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
    extensions: list[dict[str, Any]] = field(default_factory=list)
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys the competition shape understands, derived from
    #: :data:`QR_TURNPOINT_SHAPE`; everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    #: Keys the simplified XC/Waypoints shape understands, derived from
    #: :data:`QR_WAYPOINT_TURNPOINT_SHAPE`. A description or a type in such a
    #: payload is a key that shape does not define, so it is carried verbatim
    #: rather than read into an attribute the shape would never write back.
    SIMPLIFIED_KEYS: ClassVar[frozenset[str]]

    def to_dict(self, simplified: bool = False) -> dict[str, Any]:
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
        shape = QR_WAYPOINT_TURNPOINT_SHAPE if simplified else QR_TURNPOINT_SHAPE
        return shape.write(self)

    @classmethod
    def from_dict(
        cls, data: dict[str, Any], simplified: bool = False
    ) -> "QRCodeTurnpoint":
        """Create from dictionary.

        The ``z`` field is the only source of coordinates, and its length says
        which format it is: four numbers for a competition turnpoint
        (lon, lat, altitude, radius), three for an XC/Waypoints one
        (lon, lat, altitude — a route "without cylinders", hence radius 0).
        That dispatch is on the value, so it is the same in both shapes.

        Both formats require ``z``, so a payload without one is malformed
        rather than a turnpoint at 0°N 0°E — inventing coordinates would put
        the task in the Gulf of Guinea and report it as read successfully.

        Args:
            data: Dictionary with turnpoint data
            simplified: If True, read the simplified XC/Waypoints shape, which
                defines only ``n`` and ``z``. Mirrors :meth:`to_dict`, so what
                each shape reads is exactly what it writes.

        Returns:
            QRCodeTurnpoint instance

        Raises:
            KeyError: If ``z`` or ``n`` is missing.
            ValueError: If ``z`` does not decode to three or four numbers.
        """
        shape = QR_WAYPOINT_TURNPOINT_SHAPE if simplified else QR_TURNPOINT_SHAPE
        return shape.read(data)


@dataclass(frozen=True)
class _PolylineCoordinates(Field):
    """The one key that carries four numbers, or three.

    ``z`` is the turnpoint's whole geometry — longitude, latitude, altitude and
    (in the competition format) radius — polyline-encoded into a single string.
    One row over four attributes, which is why a field owns keys rather than a
    key owning a field.

    Reading does not depend on which shape asked: the number count says which
    encoding it is, so a three-number ``z`` in a competition payload is a
    waypoint turnpoint with radius 0 rather than an error.

    Attributes:
        with_radius: Whether this shape's ``z`` carries the fourth number.
    """

    with_radius: bool

    @property
    def keys(self) -> tuple[str, ...]:
        """The coordinate key."""
        return ("z",)

    def read(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Decode ``z`` into the four coordinate attributes."""
        nums = decode_nums(data["z"])
        if len(nums) == 4:
            lon, lat, alt_smoothed, radius = (
                nums[0] / 1e5,
                nums[1] / 1e5,
                nums[2],
                nums[3],
            )
        elif len(nums) == 3:
            lon, lat, alt_smoothed = nums[0] / 1e5, nums[1] / 1e5, nums[2]
            radius = 0
        else:
            raise ValueError(
                f'turnpoint "z" must hold 3 or 4 numbers, got {len(nums)}: {data["z"]!r}'
            )
        return {
            "lon": lon,
            "lat": lat,
            "alt_smoothed": alt_smoothed,
            "radius": radius,
        }

    def write(self, obj: Any, result: MutableMapping[str, Any]) -> None:
        """Encode the four coordinate attributes into ``z``."""
        if self.with_radius:
            result["z"] = encode_competition_turnpoint(
                obj.lon, obj.lat, obj.alt_smoothed, obj.radius
            )
        else:
            result["z"] = encode_waypoint_turnpoint(obj.lon, obj.lat, obj.alt_smoothed)


#: TAKEOFF is a type this format knows but does not spell: only SSS and ESS
#: carry a ``t``, and a turnpoint without one is an ordinary turnpoint.
_SPEED_SECTION_ONLY = Optionality(
    absent=lambda raw: raw is None,
    omit=lambda value: value not in (QRCodeTurnpointType.SSS, QRCodeTurnpointType.ESS),
)

QR_TURNPOINT_SHAPE = Shape(
    QRCodeTurnpoint,
    (
        Value("description", "d", optionality=OPTIONAL_EMPTY),
        Value("name", "n", optionality=REQUIRED),
        Value("type", "t", enum_codec(QRCodeTurnpointType), _SPEED_SECTION_ONLY),
        _PolylineCoordinates(with_radius=True),
    ),
    ext_key=QR_EXTENSIONS_KEY,
)
QRCodeTurnpoint.KNOWN_KEYS = QR_TURNPOINT_SHAPE.keys

#: "A simple route from waypoints without cylinders": a name and a position.
QR_WAYPOINT_TURNPOINT_SHAPE = Shape(
    QRCodeTurnpoint,
    (
        Value("name", "n", optionality=REQUIRED),
        _PolylineCoordinates(with_radius=False),
    ),
    ext_key=QR_EXTENSIONS_KEY,
)
QRCodeTurnpoint.SIMPLIFIED_KEYS = QR_WAYPOINT_TURNPOINT_SHAPE.keys
