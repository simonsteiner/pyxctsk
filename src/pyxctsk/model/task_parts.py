"""The parts of a task: ``Waypoint``, ``Turnpoint``, ``Takeoff``, ``SSS`` and ``Goal``.

Each is a plain dataclass with its field table beside it, and ``Task`` in
``task`` is built from them. They are re-exported from ``task``, where callers
import them.

They do not validate on construction, and nothing derived is stored on them.
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .codec import (
    LATITUDE,
    LONGITUDE,
    NUMBER,
    TEXT,
    TIME_OF_DAY,
    WHOLE_METRES,
    enum_codec,
    list_codec,
)
from .enums import (
    OBSOLETE_DIRECTION_DEFAULT,
    Direction,
    GoalType,
    SSSType,
    TurnpointType,
)
from .passthrough import EXTENSIONS_KEY
from .shape import (
    DEFAULTED,
    OPTIONAL_EMPTY,
    REQUIRED,
    Optionality,
    Shape,
    Value,
    shape_codec,
)
from .time_of_day import TimeOfDay


@dataclass
class Waypoint:
    """Represents a waypoint with coordinates and optional description.

    Attributes:
        name (str): Name of the waypoint.
        lat (float): Latitude in decimal degrees.
        lon (float): Longitude in decimal degrees.
        alt_smoothed (int): Smoothed altitude in meters.
        description (Optional[str]): Optional description.
        unknown (dict): Keys the spec does not define, preserved verbatim.
            See :attr:`Task.unknown`.
    """

    name: str
    lat: float
    lon: float
    alt_smoothed: int
    description: str | None = None
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands, derived from :data:`WAYPOINT_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        return WAYPOINT_SHAPE.write(self)

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
        return WAYPOINT_SHAPE.read(data)


WAYPOINT_SHAPE = Shape(
    Waypoint,
    (
        Value("name", "name", TEXT, REQUIRED),
        Value("lat", "lat", LATITUDE, REQUIRED),
        Value("lon", "lon", LONGITUDE, REQUIRED),
        Value("alt_smoothed", "altSmoothed", WHOLE_METRES, REQUIRED),
        Value("description", "description", TEXT, OPTIONAL_EMPTY),
    ),
)
Waypoint.KNOWN_KEYS = WAYPOINT_SHAPE.keys


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

    #: Keys this class understands, derived from :data:`TURNPOINT_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        return TURNPOINT_SHAPE.write(self)

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
        return TURNPOINT_SHAPE.read(data)


TURNPOINT_SHAPE = Shape(
    Turnpoint,
    (
        Value("radius", "radius", WHOLE_METRES, REQUIRED),
        Value("waypoint", "waypoint", shape_codec(WAYPOINT_SHAPE), REQUIRED),
        # ``TurnpointType.NONE`` is the empty string, so "no type" and "the
        # type that means none" are the same absence to OPTIONAL_EMPTY.
        Value("type", "type", enum_codec(TurnpointType), OPTIONAL_EMPTY),
    ),
    ext_key=EXTENSIONS_KEY,
)
Turnpoint.KNOWN_KEYS = TURNPOINT_SHAPE.keys


@dataclass
class Takeoff:
    """Represents takeoff window with open/close times.

    Attributes:
        time_open (Optional[TimeOfDay]): Opening time.
        time_close (Optional[TimeOfDay]): Closing time.
        unknown (dict): Keys the spec does not define, preserved verbatim.
            See :attr:`Task.unknown`.
    """

    time_open: TimeOfDay | None = None
    time_close: TimeOfDay | None = None
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands, derived from :data:`TAKEOFF_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        return TAKEOFF_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Takeoff":
        """Create from dictionary.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Takeoff: Parsed Takeoff object.
        """
        return TAKEOFF_SHAPE.read(data)


TAKEOFF_SHAPE = Shape(
    Takeoff,
    (
        Value("time_open", "timeOpen", TIME_OF_DAY),
        Value("time_close", "timeClose", TIME_OF_DAY),
    ),
)
Takeoff.KNOWN_KEYS = TAKEOFF_SHAPE.keys


@dataclass
class SSS:
    """Represents a start of speed section (SSS).

    Attributes:
        type (SSSType): SSS type.
        direction (Direction): SSS direction. Obsolete: read and carried so a
            round-trip does not lose it, never interpreted, and always written
            so older devices keep working.
        time_gates (List[TimeOfDay]): List of time gates.
        time_close (Optional[TimeOfDay]): Optional closing time.
        unknown (dict): Keys the spec does not define, preserved verbatim.
            See :attr:`Task.unknown`.
    """

    type: SSSType
    direction: Direction = OBSOLETE_DIRECTION_DEFAULT
    time_gates: list[TimeOfDay] = field(default_factory=list)
    time_close: TimeOfDay | None = None
    unknown: dict[str, Any] = field(default_factory=dict)

    #: Keys this class understands, derived from :data:`SSS_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict[str, Any]: Dictionary representation for JSON.
        """
        return SSS_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SSS":
        """Create from dictionary.

        ``direction`` is obsolete. The spec has readers ignore it, which here
        means nothing acts on the value — not that it is discarded: a task
        carrying one keeps it through a round-trip, and one that omits it, or
        leaves it null or empty, falls back to
        :data:`OBSOLETE_DIRECTION_DEFAULT`.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            SSS: Parsed SSS object.
        """
        return SSS_SHAPE.read(data)


#: ``sss.direction`` is obsolete: the spec has readers ignore it and writers
#: still emit *some* value. A present-but-empty one is therefore as absent as a
#: missing key, and the field is written either way.
_OBSOLETE = Optionality(absent=lambda raw: not raw, omit=lambda value: False)

SSS_SHAPE = Shape(
    SSS,
    (
        Value("type", "type", enum_codec(SSSType), REQUIRED),
        Value("direction", "direction", enum_codec(Direction), _OBSOLETE),
        # Written even when empty: the spec's sss object always has the key.
        Value("time_gates", "timeGates", list_codec(TIME_OF_DAY), DEFAULTED),
        Value("time_close", "timeClose", TIME_OF_DAY),
    ),
)
SSS.KNOWN_KEYS = SSS_SHAPE.keys


@dataclass
class Goal:
    """Represents a goal for a task.

    For goal type LINE, the radius of the last turnpoint represents half of the
    goal line's total length. The line itself is not stored here — it is derived
    from that radius by
    :func:`~pyxctsk.distance.goal_line.goal_line_length_from_turnpoints`, which
    is the single source of that rule. Which way it faces is
    :class:`~pyxctsk.distance.goal_line.GoalLine`'s question: under S7F 2025
    and later it is perpendicular to the approach from the *optimized route
    point* on the last control zone before goal, not from that turnpoint's
    centre as in 2024.

    Attributes:
        type (Optional[GoalType]): Goal type.
        deadline (Optional[TimeOfDay]): Goal deadline.
        finish_altitude (Optional[float]): Elevated goal altitude in meters AGL,
            measured from the altitude of the last turnpoint.
        unknown (dict): Keys the spec does not define, preserved verbatim.
            See :attr:`Task.unknown`.
    """

    type: GoalType | None = None
    deadline: TimeOfDay | None = None
    finish_altitude: float | None = None
    unknown: dict[str, Any] = field(default_factory=dict)

    #: The non-spec key older versions wrote, read and deliberately discarded
    #: rather than carried. It is always twice the last turnpoint's radius —
    #: which is what the spec already says that radius means — so a task whose
    #: two disagree has one wrong number, and echoing it back would preserve
    #: it. Everything else this class does not define is carried verbatim;
    #: naming this one here is what makes the drop a decision rather than an
    #: omission.
    IGNORED_KEYS = frozenset({"lineLength"})

    #: Keys this class understands, derived from :data:`GOAL_SHAPE`;
    #: everything else lands in ``unknown``.
    KNOWN_KEYS: ClassVar[frozenset[str]]

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
        return GOAL_SHAPE.write(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Goal":
        """Create from dictionary.

        The non-spec ``lineLength`` older versions wrote is ignored: it is
        always twice the last turnpoint's radius, so it carries nothing the
        turnpoints do not already say. It is on :attr:`KNOWN_KEYS` via
        :attr:`IGNORED_KEYS` for that reason — otherwise the unknown-key
        passthrough would carry it back out.

        Args:
            data (Dict[str, Any]): Dictionary to parse.

        Returns:
            Goal: Parsed Goal object.
        """
        return GOAL_SHAPE.read(data)


GOAL_SHAPE = Shape(
    Goal,
    (
        Value("type", "type", enum_codec(GoalType)),
        Value("deadline", "deadline", TIME_OF_DAY),
        Value("finish_altitude", "finishAltitude", NUMBER),
    ),
    ignored_keys=Goal.IGNORED_KEYS,
)
Goal.KNOWN_KEYS = GOAL_SHAPE.keys
