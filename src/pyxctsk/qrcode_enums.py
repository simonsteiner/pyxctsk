"""QR code task format enumerations.

This module contains all the enumeration classes used in the XCTrack QR code
task format (version 2). These enums define the various types and options
available in the compressed QR code format.
"""

from enum import IntEnum


class QRCodeDirection(IntEnum):
    """QR code direction enumeration.

    OBSOLETE: This field is kept for backwards compatibility but ignored when reading tasks.
    """

    ENTER = 1
    EXIT = 2


class QRCodeEarthModel(IntEnum):
    """QR code earth model enumeration.

    Specifies the earth model for distance calculations:
    - WGS84 (0): World Geodetic System 1984 (default)
    - FAI_SPHERE (1): FAI sphere model
    """

    WGS84 = 0
    FAI_SPHERE = 1


class QRCodeGoalType(IntEnum):
    """QR code goal type enumeration.

    Specifies the goal crossing type:
    - LINE (1): Goal line crossing
    - CYLINDER (2): Cylindrical goal zone (default)
    """

    LINE = 1
    CYLINDER = 2


class QRCodeSSSType(IntEnum):
    """QR code SSS (Start Speed Section) type enumeration.

    Specifies the start timing method:
    - RACE (1): Race start with time gates
    - ELAPSED_TIME (2): Elapsed time start
    """

    RACE = 1
    ELAPSED_TIME = 2


class QRCodeTaskType(IntEnum):
    """QR code task type enumeration.

    Specifies the task format:
    - CLASSIC (1): Traditional task with turnpoints
    - WAYPOINTS (2): Waypoint-based task
    """

    CLASSIC = 1
    WAYPOINTS = 2


class QRCodeTurnpointType(IntEnum):
    """QR code turnpoint type enumeration.

    Specifies special turnpoint types:
    - NONE (0): Regular turnpoint
    - TAKEOFF (1): Takeoff point (not included in QR "t" field)
    - SSS (2): Start Speed Section
    - ESS (3): End Speed Section
    """

    NONE = 0
    TAKEOFF = 1
    SSS = 2
    ESS = 3
