"""Constrained values in the XCTrack task format.

The vocabulary the domain model is written in: every field the spec restricts
to a fixed set of strings is one of these, so an unknown value fails at parse
time rather than moving through the library as an unchecked string.

Kept apart from ``task.py`` so the spec's structural rules can live in
``validation.py`` without importing the model they check — see that module.
The QR format spells the same concepts with its own integer enums in
``qrcode_enums.py``; ``qrcode_conversion.py`` translates between the two.
"""

from enum import Enum


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
