"""What the KML and GeoJSON writers both draw: the task's features.

:class:`TaskDrawing` is derived once per task and yields :attr:`~TaskDrawing.features`,
the things a map shows, in the order both writers emit them: a
:class:`CylinderFeature` per drawn turnpoint, the :class:`RouteFeature`, and
the :class:`GoalLineFeature` and :class:`ControlZoneFeature` when the task has
a goal line. Each carries its name, description, colour and geometry, so a
writer only serializes, and the two formats cannot disagree about what the
task looks like. Whether there is a goal line, and the decision to drop the
last turnpoint for it, is made once, in :meth:`TaskDrawing.from_task`.

Also here: the palette, as :class:`Color` values that each writer renders with a
total function of its own format. Geometry is not computed here: cylinder
outlines and the control zone come from
:func:`~pyxctsk.distance.earth.geodesic_arc` and :mod:`pyxctsk.distance.goal_line`
on the task's earth model, the same primitives the distance calculation uses.
This module must not grow a second opinion about task geometry.
"""

from dataclasses import dataclass

from ..distance.earth import EarthModelLike, geodesic_arc
from ..distance.goal_line import GoalLine
from ..distance.measured_task import MeasuredTask
from ..distance.route_optimization import OptimizedRoute
from ..model.task import Task, Turnpoint, TurnpointType

#: Segments in a drawn cylinder outline.
CIRCLE_POINTS = 64


@dataclass(frozen=True)
class CylinderFeature:
    """One turnpoint cylinder, as a map draws it.

    Geometry is computed by :meth:`outline`, not when the drawing is built: a
    cylinder no earth can hold still has a drawing, and only a writer that
    draws its ring fails.

    Attributes:
        index: Position among the drawn turnpoints, zero-based.
        name: The turnpoint's name, or ``TP1``, ``TP2``, ... if it has none.
        description: The role and radius, the role omitted when it has none.
        role: The turnpoint's role; :attr:`TurnpointType.NONE` if it has none.
        color: The cylinder's colour, the goal's red included.
        centre: The centre as (lon, lat).
        radius: The radius in metres, as the task declares it.
        earth_model: The task's earth, which :meth:`outline` measures on.
    """

    index: int
    name: str
    description: str
    role: TurnpointType
    color: "Color"
    centre: tuple[float, float]
    radius: int
    earth_model: EarthModelLike

    def outline(self) -> list[tuple[float, float]]:
        """The cylinder's boundary as a closed ring of (lon, lat) points.

        Measured on the task's earth model, so every point is exactly the
        radius from the centre: the boundary the optimized route touches
        (S7F 7.1.7), not an approximation of it.

        Returns:
            ``CIRCLE_POINTS + 1`` points, the last equal to the first.
        """
        lon, lat = self.centre
        ring = geodesic_arc(
            (lat, lon), self.radius, 0.0, 360.0, CIRCLE_POINTS, self.earth_model
        )
        ring[-1] = ring[0]  # closed exactly, not to within float noise
        return ring


@dataclass(frozen=True)
class RouteFeature:
    """The optimized route, drawn as a line.

    Attributes:
        name: The route's name, the glossary's *optimized route*.
        description: How many turnpoints the task has.
        color: The line's colour.
        points: The route as (lon, lat) points, at least two.
    """

    name: str
    description: str
    color: "Color"
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class GoalLineFeature:
    """The goal line of a LINE goal.

    Attributes:
        name: The line's name.
        description: The line's length, rounded to the metre.
        color: The line's colour.
        length: The line's length in metres.
        goal_line: The line itself, which :meth:`ends` asks on call.
    """

    name: str
    description: str
    color: "Color"
    length: float
    goal_line: GoalLine

    def ends(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """The line's two ends as (lon, lat), computed on call."""
        first, second, _ = self.goal_line.endpoints()
        return first, second


@dataclass(frozen=True)
class ControlZoneFeature:
    """The control zone around a goal line.

    Attributes:
        name: The zone's name.
        description: The zone's radius, rounded to the metre.
        edge_color: The outline's colour.
        fill_color: The fill's colour.
        radius: The zone's radius in metres, which S7F 6.2.3.1 makes half the
            goal line.
        goal_line: The line the zone surrounds, which :meth:`outline` asks on
            call.
    """

    name: str
    description: str
    edge_color: "Color"
    fill_color: "Color"
    radius: float
    goal_line: GoalLine

    def outline(self) -> list[tuple[float, float]]:
        """The zone's boundary as (lon, lat) points, computed on call."""
        return self.goal_line.control_zone()


#: What a map shows, so a writer's ``match`` ends in ``assert_never`` and a new
#: kind fails the type check in every writer.
Feature = CylinderFeature | RouteFeature | GoalLineFeature | ControlZoneFeature


@dataclass(frozen=True)
class TaskDrawing:
    """Everything both writers need to draw one task, derived once.

    Built by :meth:`from_task`, which runs the optimizer once, so both formats
    cost one route and read one value. A drawing is a snapshot: build it after
    the task is final.

    Attributes:
        turnpoints: The turnpoints to draw, in order: the task's own, less the
            last one when a goal line replaces it.
        goal_line: The task's goal line, or None if it has none.
        measured: The task beside the optimized route through its cylinders.
            Read :attr:`route` for the route alone; hand the whole value to
            ``DistanceReport.from_measured_task`` for the distances beside the
            map.
    """

    turnpoints: tuple[Turnpoint, ...]
    goal_line: GoalLine | None
    measured: MeasuredTask

    @property
    def task(self) -> Task:
        """The task being drawn."""
        return self.measured.task

    @property
    def route(self) -> OptimizedRoute:
        """The optimized route through the task's cylinders."""
        return self.measured.route

    @property
    def features(self) -> tuple[Feature, ...]:
        """What to draw, in order: cylinders, route, goal line, control zone.

        The route is present only at two points or more, the goal line and
        control zone only when the task has a goal line. Built on each read;
        no geometry is computed until a feature's method asks for it.
        """
        task = self.task
        # The goal is found by identity, not value (``turnpoint is last``
        # below): a task may end by flying the same turnpoint twice, and a
        # value search would draw the goal as an ordinary one.
        last = task.turnpoints[-1] if task.turnpoints else None
        features: list[Feature] = []
        for index, turnpoint in enumerate(self.turnpoints):
            role = turnpoint.type or TurnpointType.NONE
            radius = f"Radius: {turnpoint.radius}m"
            waypoint = turnpoint.waypoint
            features.append(
                CylinderFeature(
                    index=index,
                    name=waypoint.name or f"TP{index + 1}",
                    description=(
                        radius
                        if role is TurnpointType.NONE
                        else f"Type: {role.value}, {radius}"
                    ),
                    role=role,
                    color=turnpoint_color(role, turnpoint is last),
                    centre=(waypoint.lon, waypoint.lat),
                    radius=turnpoint.radius,
                    earth_model=task.earth_model,
                )
            )
        if len(self.route.points) >= 2:
            features.append(
                RouteFeature(
                    name="Optimized Route",
                    description=f"XCTrack task course with {len(task.turnpoints)} turnpoints",
                    color=ROUTE_COLOR,
                    points=tuple((lon, lat) for lat, lon in self.route.points),
                )
            )
        if self.goal_line is not None:
            line = self.goal_line
            features.append(
                GoalLineFeature(
                    name="Goal Line",
                    description=f"Goal line length: {line.length:.0f}m",
                    color=GOAL_LINE_COLOR,
                    length=line.length,
                    goal_line=line,
                )
            )
            features.append(
                ControlZoneFeature(
                    name="Goal Control Zone",
                    description=(
                        f"Goal control zone radius: {line.control_zone_radius:.0f}m"
                    ),
                    edge_color=CONTROL_ZONE_EDGE_COLOR,
                    fill_color=CONTROL_ZONE_FILL_COLOR,
                    radius=line.control_zone_radius,
                    goal_line=line,
                )
            )
        return tuple(features)

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
        # there is a line to draw in its place.
        turnpoints = task.turnpoints[:-1] if goal_line else task.turnpoints
        return cls(
            turnpoints=tuple(turnpoints),
            goal_line=goal_line,
            measured=measured,
        )


@dataclass(frozen=True)
class Color:
    """One colour, as the bytes it is, for either writer to render.

    The palette is shared as colour values, not ``#rrggbb`` strings, so the KML
    writer needs no dict mapping strings back to ``simplekml.Color`` constants
    that would re-declare the palette and default an unknown entry. A colour
    value with one total renderer per format has nothing to look up and nothing
    to default to.

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
