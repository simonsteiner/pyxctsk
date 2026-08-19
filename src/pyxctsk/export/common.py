"""What the KML and GeoJSON writers both need to draw a task.

:class:`TaskDrawing` is that answer, derived once per task: which turnpoints to
draw, which of them is the goal, whether there is a goal line, and the optimized
route. Both writers render the same value rather than each asking the same
questions again — which is not only cheaper (the optimizer ran once per format)
but the reason the answers cannot disagree. They did: the goal line's presence
and the decision to drop the last turnpoint were computed separately, and a LINE
goal with no usable approach direction lost its goal from both outputs. There is
no free function beside the drawing that answers any of those a second way.

Also here: the palette, as :class:`Color` values that each writer renders with a
total function of its own format, and the polygon that approximates a cylinder.
That circle is planar — a fixed metres-per-degree constant, not a
geodesic — because it draws a decorative outline, not a measured shape. Anything
a distance depends on is computed properly in
:mod:`pyxctsk.distance.plane` and :mod:`pyxctsk.distance.goal_line`, and
this module must not grow a second opinion about task geometry.
"""

import math
from dataclasses import dataclass

from ..distance.goal_line import GoalLine
from ..distance.measured_task import MeasuredTask
from ..distance.route_optimization import OptimizedRoute
from ..model.task import Task, Turnpoint, TurnpointType

# Constants for visualization
CIRCLE_POINTS = 64  # Number of points to approximate circle
METERS_PER_DEGREE = 111320.0  # 1 degree ≈ 111.32 km at equator


@dataclass(frozen=True)
class TaskDrawing:
    """Everything both writers need to draw one task, derived once.

    Built by :meth:`from_task`, which runs the optimizer once. Rendering the
    same task in both formats therefore costs one route, not two, and — more
    importantly — the two formats cannot disagree about what the task looks
    like, because they are reading one value rather than each deriving their
    own.

    A drawing is a snapshot: it holds the turnpoints and route as they were
    when it was built, so build it after the task is final.

    Attributes:
        task: The task being drawn, for names, counts and descriptions.
        turnpoints: The turnpoints to draw, in order — the task's own, less the
            last one when a goal line replaces it.
        goal_line: The task's goal line, or None if it has none.
        measured: The task beside the optimized route through its cylinders.
            Read :attr:`route` for the route alone; hand the whole value to
            ``task_distances_from`` for the table beside the map, which is
            that same measurement rendered rather than a second one.
    """

    task: Task
    turnpoints: tuple[Turnpoint, ...]
    goal_line: GoalLine | None
    measured: MeasuredTask

    @property
    def route(self) -> OptimizedRoute:
        """The optimized route through the task's cylinders."""
        return self.measured.route

    @classmethod
    def from_task(cls, task: Task) -> "TaskDrawing":
        """Derive the drawing for a task, optimizing its route once.

        Args:
            task: The task to draw.

        Returns:
            The drawing both writers render.
        """
        # Measuring comes first: under S7F 2025+ the goal line is oriented
        # against the optimized route point on the last control zone before
        # goal, so deriving the line from the task alone would optimize the
        # same task a second time.
        measured = MeasuredTask.from_task(task)
        goal_line = GoalLine.from_measured_task(measured)
        # A goal line replaces the last turnpoint, so it is dropped exactly when
        # there is a line to draw in its place — one decision, made here.
        turnpoints = task.turnpoints[:-1] if goal_line else task.turnpoints
        return cls(
            task=task,
            turnpoints=tuple(turnpoints),
            goal_line=goal_line,
            measured=measured,
        )

    def is_goal(self, turnpoint: Turnpoint) -> bool:
        """Whether this turnpoint is the task's goal.

        Compares identity, not value: a task may legitimately end by flying the
        same turnpoint twice, and ``Turnpoint`` is a plain dataclass, so
        searching by value would find the earlier occurrence and draw the goal
        as an ordinary turnpoint.

        Args:
            turnpoint: One of the task's turnpoints.

        Returns:
            True if this is the goal turnpoint and the task has a goal defined.
        """
        if self.task.effective_goal is None:
            return False
        return bool(self.task.turnpoints) and turnpoint is self.task.turnpoints[-1]

    def color_of(self, turnpoint: Turnpoint) -> "Color":
        """The colour this turnpoint is drawn in, in either format.

        Both writers used to compose this themselves out of :meth:`is_goal` and
        the turnpoint's type, and they spelled the type differently: KML
        normalized a missing one to ``TurnpointType.NONE`` while GeoJSON passed
        ``None`` into a parameter annotated ``TurnpointType``. They agreed only
        by falling through to the same default, which is the shape this module
        exists to remove — a question both writers must answer identically is a
        method on the drawing, not something each of them assembles.

        Args:
            turnpoint: One of the turnpoints being drawn.

        Returns:
            The colour for that turnpoint, the goal's red included.
        """
        return turnpoint_color(
            turnpoint.type or TurnpointType.NONE, self.is_goal(turnpoint)
        )

    def label_of(self, turnpoint: Turnpoint, index: int) -> str:
        """The name this turnpoint is drawn under, in either format.

        Falls back to a positional name for an unnamed turnpoint. The spec
        requires the key but the writers tolerate an empty value, and both
        composed the same ``TP{i+1}`` fallback themselves — three times
        between them.

        Args:
            turnpoint: One of the turnpoints being drawn.
            index: Its position in the drawing, zero-based.

        Returns:
            The turnpoint's name, or ``TP1``, ``TP2``, … if it has none.
        """
        return turnpoint.waypoint.name or f"TP{index + 1}"

    def description_of(self, turnpoint: Turnpoint) -> str:
        """The description this turnpoint is drawn with, in either format.

        Both writers assembled their own and disagreed. KML interpolated the
        enum member itself — ``Type: TurnpointType.TAKEOFF`` — putting a Python
        repr into user-visible map text, and printed ``Type: None`` for an
        ordinary turnpoint; GeoJSON left the role out of the description
        entirely and reached for it with ``getattr(turnpoint, "type", None)``,
        a defensive lookup on a dataclass field that always exists, skipping
        the ``or TurnpointType.NONE`` normalisation :meth:`color_of` performs.
        That asymmetry is exactly what this module exists to remove.

        Args:
            turnpoint: One of the turnpoints being drawn.

        Returns:
            The role and radius, with the role omitted when it has none.
        """
        role = turnpoint.type or TurnpointType.NONE
        radius = f"Radius: {turnpoint.radius}m"
        if role is TurnpointType.NONE:
            return radius
        return f"Type: {role.value}, {radius}"

    def role_of(self, turnpoint: Turnpoint) -> TurnpointType:
        """The turnpoint's role, normalized the way :meth:`color_of` reads it.

        Args:
            turnpoint: One of the turnpoints being drawn.

        Returns:
            The role, or :attr:`TurnpointType.NONE` if it carries none.
        """
        return turnpoint.type or TurnpointType.NONE

    def route_label(self) -> str:
        """The name the optimized route is drawn under, in either format.

        The two writers disagreed: KML wrote "Course Line" and GeoJSON wrote
        "Optimized Route" for the same line, each pinned as expected by a test
        in its own file, so the suite enforced the divergence. This is the
        glossary's term (``CONTEXT.md``: *optimized route*), which is what
        makes it the one to keep.

        Returns:
            The route's name.
        """
        return "Optimized Route"

    def goal_line_label(self) -> str:
        """The name the goal line is drawn under, in either format."""
        return "Goal Line"

    def goal_line_description(self) -> str:
        """The description the goal line is drawn with, in either format.

        Both writers composed this themselves, character for character. A
        question both must answer identically is a method here — the rule this
        module states, applied to the goal line as it already was to the
        turnpoints.

        Returns:
            The line's length, rounded to the metre.

        Raises:
            ValueError: If the task has no goal line to describe.
        """
        if self.goal_line is None:
            raise ValueError("this task has no goal line")
        return f"Goal line length: {self.goal_line.length:.0f}m"

    def control_zone_label(self) -> str:
        """The name the control zone is drawn under, in either format."""
        return "Goal Control Zone"

    def control_zone_description(self) -> str:
        """The description the control zone is drawn with, in either format.

        The radius is asked of the goal line, which owns S7F §6.2.3.1's rule
        that it is half the line. Both writers used to spell ``length / 2``
        here instead, so the rule lived in three modules.

        Returns:
            The zone's radius, rounded to the metre.

        Raises:
            ValueError: If the task has no goal line, so no control zone.
        """
        if self.goal_line is None:
            raise ValueError("this task has no goal line")
        return f"Goal control zone radius: {self.goal_line.control_zone_radius:.0f}m"

    def route_coordinates(self) -> list[tuple[float, float]] | None:
        """The optimized route as (lat, lon) points, or None if there is no line.

        A route needs two points to be a line, so a task with fewer than two
        turnpoints has nothing to draw here.

        Returns:
            The route's (lat, lon) points, or None if there are fewer than two.
        """
        if len(self.route.points) < 2:
            return None
        return list(self.route.points)

    def route_coordinates_lon_lat(self) -> list[tuple[float, float]] | None:
        """The optimized route in the axis order both output formats want.

        KML coordinates and GeoJSON positions are both (lon, lat), and both
        writers flipped :meth:`route_coordinates` themselves — one by unpacking,
        one by positional index — in a codebase that records axis-order
        confusion as a defect class it has already paid for.

        Returns:
            The route's (lon, lat) points, or None if there is no line to draw.
        """
        points = self.route_coordinates()
        if points is None:
            return None
        return [(lon, lat) for lat, lon in points]


@dataclass(frozen=True)
class Color:
    """One colour, as the bytes it is, for either writer to render.

    The palette used to be shared as ``#rrggbb`` strings, which meant the KML
    writer needed a hand-written dict mapping each of those strings back to a
    ``simplekml.Color`` constant. That dict re-declared the whole palette and
    lost four of its five turnpoint values — a TAKEOFF turnpoint was ``#204d74``
    in GeoJSON and ``#00008b`` in KML, and only the goal's red survived — and its
    ``.get(hex, blue)`` default meant a sixth entry would have degraded to blue
    rather than failing. A colour value with one total renderer per format has
    nothing to look up and nothing to default to.

    Attributes:
        red: Red channel, 0-255.
        green: Green channel, 0-255.
        blue: Blue channel, 0-255.
    """

    red: int
    green: int
    blue: int

    @property
    def hex(self) -> str:
        """This colour as ``#rrggbb``, which GeoJSON and CSS want."""
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"

    def kml(self, alpha: int = 255) -> str:
        """This colour as KML's ``aabbggrr``.

        KML orders the channels backwards from CSS and puts alpha first, which
        is why hand-writing these strings goes wrong: the course line was
        ``E64136ff``, the digits of ``#ff4136`` after the alpha in CSS order,
        which KML reads as ``#ff3641``.

        Args:
            alpha: Opacity, 0 (transparent) to 255 (opaque).

        Returns:
            The 8-character ``aabbggrr`` string a KML colour field takes.
        """
        return f"{alpha:02x}{self.blue:02x}{self.green:02x}{self.red:02x}"


#: The one palette. Both writers render these values; neither declares a colour.
GOAL_COLOR = Color(0xFF, 0x00, 0x00)
TAKEOFF_COLOR = Color(0x20, 0x4D, 0x74)
SSS_COLOR = Color(0xAC, 0x29, 0x25)
ESS_COLOR = Color(0xFF, 0x8C, 0x00)
TURNPOINT_COLOR = Color(0x26, 0x9A, 0xBC)
ROUTE_COLOR = Color(0xFF, 0x41, 0x36)
GOAL_LINE_COLOR = Color(0x00, 0xFF, 0x00)
CONTROL_ZONE_EDGE_COLOR = Color(0x00, 0xBC, 0xD4)
CONTROL_ZONE_FILL_COLOR = Color(0x4E, 0xCD, 0xC4)

#: Every :class:`TurnpointType`, spelled out rather than defaulted. A lookup with
#: a default is what the old KML writer had, and it meant a palette entry it did
#: not know about rendered as an ordinary turnpoint with nothing failing. This
#: table is total over the enum, `test_every_turnpoint_type_has_a_colour` says so,
#: and a new member therefore fails the suite instead of quietly turning blue.
_TURNPOINT_COLORS = {
    TurnpointType.NONE: TURNPOINT_COLOR,
    TurnpointType.TAKEOFF: TAKEOFF_COLOR,
    TurnpointType.SSS: SSS_COLOR,
    TurnpointType.ESS: ESS_COLOR,
}


def turnpoint_color(turnpoint_type: TurnpointType, is_goal: bool = False) -> Color:
    """The colour a turnpoint is drawn in, in either format.

    Args:
        turnpoint_type: The type of turnpoint.
        is_goal: Whether this is the goal (last) turnpoint. The goal wins over
            the type: a goal that is also the ESS is drawn as the goal.

    Returns:
        The turnpoint's colour.

    Raises:
        KeyError: If the type has no palette entry, which the test over the enum
            makes a CI failure rather than something a map can hit.
    """
    if is_goal:
        return GOAL_COLOR
    return _TURNPOINT_COLORS[turnpoint_type]


def generate_circle_coordinates_2d(
    center_lat: float, center_lon: float, radius_meters: float
) -> list[tuple[float, float]]:
    """Generate 2D coordinates for a circular turnpoint zone.

    Args:
        center_lat: Latitude of the circle center.
        center_lon: Longitude of the circle center.
        radius_meters: Radius of the circle in meters.

    Returns:
        List of (longitude, latitude) tuples forming a circle.
    """
    coords = []
    radius_deg = radius_meters / METERS_PER_DEGREE

    for i in range(CIRCLE_POINTS + 1):  # +1 to close the circle
        angle = 2 * math.pi * i / CIRCLE_POINTS
        lat = center_lat + radius_deg * math.sin(angle)
        lon = center_lon + radius_deg * math.cos(angle) / math.cos(
            math.radians(center_lat)
        )
        coords.append((lon, lat))

    return coords


def generate_circle_coordinates_3d(
    center_lat: float, center_lon: float, radius_meters: float, altitude: int
) -> list[tuple[float, float, int]]:
    """Generate 3D coordinates for a circular turnpoint zone.

    Args:
        center_lat: Latitude of the circle center.
        center_lon: Longitude of the circle center.
        radius_meters: Radius of the circle in meters.
        altitude: Altitude for all points in meters.

    Returns:
        List of (longitude, latitude, altitude) tuples forming a circle.
    """
    coords_2d = generate_circle_coordinates_2d(center_lat, center_lon, radius_meters)
    return [(lon, lat, altitude) for lon, lat in coords_2d]
