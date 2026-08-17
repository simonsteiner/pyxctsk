"""QR code task format enumerations.

This module contains all the enumeration classes used in the XCTrack QR code
task format (version 2). These enums define the various types and options
available in the compressed QR code format.
"""

from enum import IntEnum


class QRCodeDirection(IntEnum):
    """QR code direction enumeration (OBSOLETE).

    Kept for backwards compatibility with older QR code tasks. The spec has
    readers "ignore this field", which this library takes to mean *do not act
    on it* rather than *discard it*: the value is read, carried across the
    format seam and written back out, and nothing anywhere behaves differently
    for ENTER or EXIT. ``tests/conformance`` pins both halves — that an
    explicit direction survives a round-trip, and that an absent or empty one
    falls back rather than raising.
    """

    ENTER = 1
    EXIT = 2


#: The value used when a QR task omits the obsolete ``s.d`` field. Kept beside
#: the enum it belongs to, and asserted equal to the full-JSON format's
#: :data:`~pyxctsk.model.task.OBSOLETE_DIRECTION_DEFAULT` by the conversion tests, so
#: the two readers cannot drift apart.
QR_OBSOLETE_DIRECTION_DEFAULT = QRCodeDirection.EXIT


class QRCodeEarthModel(IntEnum):
    """QR code earth model enumeration.

    Specifies the earth model used for distance calculations:
    - WGS84 (0): World Geodetic System 1984 (default)
    - FAI_SPHERE (1): FAI sphere model (used in some competitions)
    """

    WGS84 = 0
    FAI_SPHERE = 1


class QRCodeGoalType(IntEnum):
    """QR code goal type enumeration.

    Specifies the type of goal crossing:
    - LINE (1): Goal line crossing
    - CYLINDER (2): Cylindrical goal zone (default)
    """

    LINE = 1
    CYLINDER = 2


class QRCodeSSSType(IntEnum):
    """QR code SSS (Start Speed Section) type enumeration.

    Specifies the start timing method for the task:
    - RACE (1): Race start with time gates
    - ELAPSED_TIME (2): Elapsed time start (individual)
    """

    RACE = 1
    ELAPSED_TIME = 2


class QRCodeTaskType(IntEnum):
    """QR code task type enumeration.

    Specifies the overall task format:
    - CLASSIC (1): Traditional task with turnpoints (e.g., Race to Goal, Elapsed Time)
    - WAYPOINTS (2): Waypoint-based task (free flight, open distance, etc.)
    """

    CLASSIC = 1
    WAYPOINTS = 2


class QRCodeTurnpointType(IntEnum):
    """QR code turnpoint type enumeration.

    Specifies special turnpoint types for QR code encoding:
    - NONE (0): Regular turnpoint
    - TAKEOFF (1): Takeoff point (not included in QR "t" field)
    - SSS (2): Start Speed Section
    - ESS (3): End Speed Section
    """

    NONE = 0
    TAKEOFF = 1
    SSS = 2
    ESS = 3
