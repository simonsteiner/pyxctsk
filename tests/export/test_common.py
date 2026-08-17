"""What both writers share: the `TaskDrawing` value and the palette.

Covers what the drawing answers once — which turnpoints to draw, whether there
is a goal line, where the optimized route runs — and the property that made it
worth introducing: rendering one task in both formats optimizes the route once
and cannot produce two different pictures of the same task.

The palette is the same idea for colour. `Color` is shared and each writer
renders it in its own format, so the tests read the colours back out of both
outputs and compare them: that is the only way the drift the KML writer used to
introduce could have been caught.
"""

import re

import pytest

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.export import common
from pyxctsk.export.common import (
    GOAL_COLOR,
    ROUTE_COLOR,
    Color,
    TaskDrawing,
    turnpoint_color,
)
from pyxctsk.export.geojson import drawing_to_geojson, generate_task_geojson
from pyxctsk.export.kml import ROUTE_ALPHA, drawing_to_kml


def _task(goal_type: GoalType | None = None, prev_lat: float = 46.0) -> Task:
    """A three-turnpoint task, optionally with a goal of the given type."""
    return Task(
        task_type=TaskType.CLASSIC,
        version=1,
        turnpoints=[
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(name="A", lat=45.5, lon=8.0, alt_smoothed=0),
                type=TurnpointType.TAKEOFF,
            ),
            Turnpoint(
                radius=1000,
                waypoint=Waypoint(name="B", lat=prev_lat, lon=8.0, alt_smoothed=0),
                type=TurnpointType.NONE,
            ),
            Turnpoint(
                radius=400,
                waypoint=Waypoint(name="Goal", lat=47.0, lon=8.0, alt_smoothed=0),
                type=TurnpointType.NONE,
            ),
        ],
        goal=None if goal_type is None else Goal(type=goal_type),
    )


class TestTaskDrawing:
    """What the drawing derives, and that it derives it once."""

    def test_cylinder_goal_draws_every_turnpoint(self):
        """With no goal line, every turnpoint is drawn and the goal is the last."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])
        assert not drawing.is_goal(drawing.turnpoints[0])

    def test_goal_line_replaces_the_last_turnpoint(self):
        """A goal line is drawn instead of the goal cylinder, never as well as."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE))

        assert drawing.goal_line is not None
        assert len(drawing.turnpoints) == 2
        assert drawing.turnpoints == tuple(drawing.task.turnpoints[:-1])

    def test_the_render_list_and_the_goal_line_cannot_disagree(self):
        """Dropping the last turnpoint and having a line are one decision.

        A LINE goal needs some earlier turnpoint at different coordinates to
        give it an approach direction. With every earlier turnpoint sitting on
        the goal there is no line — and the goal turnpoint must stay drawn.
        (One coincident turnpoint is not enough: the search walks back past it.)
        """
        task = _task(GoalType.LINE)
        for turnpoint in task.turnpoints:
            turnpoint.waypoint.lat = 47.0
            turnpoint.waypoint.lon = 8.0

        drawing = TaskDrawing.from_task(task)

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])

    def test_one_coincident_turnpoint_still_yields_a_line(self):
        """The approach direction comes from the last turnpoint that differs."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE, prev_lat=47.0))

        assert drawing.goal_line is not None
        assert drawing.goal_line.approach_from == (45.5, 8.0)
        assert len(drawing.turnpoints) == 2

    def test_route_below_two_points_is_not_a_line(self):
        """One turnpoint is a point, not a line, so there is nothing to draw."""
        task = _task(GoalType.CYLINDER)
        task.turnpoints = task.turnpoints[:1]
        drawing = TaskDrawing.from_task(task)

        assert len(drawing.route.points) == 1
        assert drawing.route_coordinates() is None

    def test_route_coordinates_follow_the_route(self):
        """The drawn line is the optimized route, in order."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))

        assert drawing.route_coordinates() == list(drawing.route.points)
        assert len(drawing.route_coordinates()) == 3


class TestOneDrawingTwoFormats:
    """The reason the value exists: both writers render the same one."""

    def test_rendering_both_formats_optimizes_the_route_once(self, monkeypatch):
        """Two formats, one drawing, one optimizer run.

        Each writer used to derive its own route, so producing both formats for
        one task optimized it twice. Note the patch target: the name is looked
        up in ``export.common`` at call time, which is exactly what the four
        inert ``@patch`` decorators in test_geojson.py got wrong — they patched
        a name ``geojson.py`` had already bound into its own module.
        """
        calls = []
        real = common.calculate_iteratively_refined_route

        def counting(*args, **kwargs):
            calls.append(args)
            return real(*args, **kwargs)

        monkeypatch.setattr(common, "calculate_iteratively_refined_route", counting)

        drawing = TaskDrawing.from_task(_task(GoalType.LINE))
        kml = drawing_to_kml(drawing)
        geojson = drawing_to_geojson(drawing)

        assert len(calls) == 1, "the drawing is the shared route, not a per-format one"
        assert "Goal Line" in kml
        assert any(f["properties"]["type"] == "goal_line" for f in geojson["features"])

    def test_the_task_entry_point_agrees_with_the_drawing_one(self):
        """``generate_task_geojson(task)`` is ``drawing_to_geojson(from_task(task))``."""
        task = _task(GoalType.LINE)

        assert generate_task_geojson(task) == drawing_to_geojson(
            TaskDrawing.from_task(task)
        )

    def test_both_formats_draw_the_same_route(self):
        """The KML course line and the GeoJSON route come from one value."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))
        route = drawing.route_coordinates()
        assert route is not None

        geojson = drawing_to_geojson(drawing)
        (feature,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]
        assert feature["geometry"]["coordinates"] == [[lon, lat] for lat, lon in route]

        kml = drawing_to_kml(drawing)
        for lat, lon in route:
            assert f"{lon},{lat}" in kml


class TestColorValue:
    """`Color` renders itself per format, so neither writer converts anything."""

    def test_hex_is_css_order(self):
        """``#rrggbb``, which GeoJSON and CSS want."""
        assert Color(0x20, 0x4D, 0x74).hex == "#204d74"
        assert Color(0, 0, 0).hex == "#000000"
        assert Color(0xFF, 0xFF, 0xFF).hex == "#ffffff"

    def test_kml_is_alpha_then_reversed_channels(self):
        """``aabbggrr``: KML puts alpha first and the channels backwards.

        Hand-writing this is what went wrong in the writer — the course line
        read ``E64136ff``, the digits of ``#ff4136`` in CSS order after the
        alpha, which KML renders as ``#ff3641``.
        """
        assert Color(0xFF, 0x41, 0x36).kml(0xE6) == "e63641ff"
        assert Color(0x20, 0x4D, 0x74).kml() == "ff744d20"

    def test_kml_defaults_to_opaque(self):
        """A colour with no alpha given is fully opaque."""
        assert Color(0x26, 0x9A, 0xBC).kml().startswith("ff")


class TestOnePalette:
    """One palette, rendered twice — not two palettes that have to agree.

    The KML writer used to map the shared ``#rrggbb`` string back through a
    hand-written dict of ``simplekml.Color`` constants, which re-declared the
    palette and lost four of its five turnpoint values: a TAKEOFF turnpoint was
    ``#204d74`` in GeoJSON and ``#00008b`` in KML. Only the goal's red survived
    the round trip. These tests read the colour out of both outputs and compare
    them, so a drift cannot pass again.
    """

    #: The whole palette a task can show, as (turnpoint type, is_goal).
    ROLES = [
        (TurnpointType.TAKEOFF, False),
        (TurnpointType.SSS, False),
        (TurnpointType.ESS, False),
        (TurnpointType.NONE, False),
        (TurnpointType.NONE, True),
    ]

    @staticmethod
    def _placemark_color(kml: str, name: str) -> str:
        """The line colour of the named placemark, followed through its styleUrl.

        simplekml hoists styles into the document and references them by id, so
        reading a placemark's colour means resolving that reference rather than
        counting occurrences.

        Args:
            kml: The rendered document.
            name: The placemark's ``<name>``.

        Returns:
            The placemark's LineStyle colour as KML's ``aabbggrr``.
        """
        placemark = re.search(
            rf"<Placemark[^>]*>\s*<name>{re.escape(name)}</name>.*?</Placemark>",
            kml,
            re.S,
        )
        assert placemark, f"no placemark named {name!r}"
        reference = re.search(r"<styleUrl>#(\d+)</styleUrl>", placemark.group(0))
        assert reference, f"placemark {name!r} has no styleUrl"
        style = re.search(rf'<Style id="{reference.group(1)}">.*?</Style>', kml, re.S)
        assert style, f"style #{reference.group(1)} is not in the document"
        color = re.search(
            r"<LineStyle[^>]*>\s*<color>([0-9a-f]{8})</color>", style.group(0)
        )
        assert color, f"style #{reference.group(1)} has no line colour"
        return color.group(1)

    @staticmethod
    def _task_of_every_role() -> Task:
        """A task showing every palette entry once, goal last."""
        types = [t for t, is_goal in TestOnePalette.ROLES if not is_goal]
        return Task(
            task_type=TaskType.CLASSIC,
            version=1,
            goal=Goal(type=GoalType.CYLINDER),
            turnpoints=[
                Turnpoint(
                    radius=1000,
                    waypoint=Waypoint(
                        name=f"TP{i}", lat=46.0 + i / 10, lon=8.0, alt_smoothed=0
                    ),
                    type=turnpoint_type,
                )
                for i, turnpoint_type in enumerate([*types, TurnpointType.NONE])
            ],
        )

    @pytest.mark.parametrize(("turnpoint_type", "is_goal"), ROLES)
    def test_every_role_has_a_colour_of_its_own(self, turnpoint_type, is_goal):
        """Five roles, five distinct colours, no default standing in for one."""
        color = turnpoint_color(turnpoint_type, is_goal)

        others = [
            turnpoint_color(t, g)
            for t, g in self.ROLES
            if (t, g) != (turnpoint_type, is_goal)
        ]
        assert color not in others, f"{turnpoint_type} shares a colour"

    def test_the_goal_wins_over_the_turnpoint_type(self):
        """A goal that is also the ESS is drawn as the goal."""
        assert turnpoint_color(TurnpointType.ESS, is_goal=True) == GOAL_COLOR

    def test_both_writers_draw_the_turnpoints_in_the_palette_colours(self):
        """The regression: KML's colours are the shared ones, not a remapping."""
        drawing = TaskDrawing.from_task(self._task_of_every_role())
        expected = [
            turnpoint_color(tp.type, drawing.is_goal(tp)) for tp in drawing.turnpoints
        ]

        geojson = drawing_to_geojson(drawing)
        from_geojson = [
            f["properties"]["color"]
            for f in geojson["features"]
            if f["properties"]["type"] == "cylinder"
        ]
        assert from_geojson == [color.hex for color in expected]

        kml = drawing_to_kml(drawing)
        from_kml = [
            self._placemark_color(kml, tp.waypoint.name) for tp in drawing.turnpoints
        ]
        assert from_kml == [color.kml() for color in expected]

    def test_both_writers_draw_the_route_in_one_colour(self):
        """KML's course line was ``#ff3641`` where GeoJSON's route was ``#ff4136``."""
        drawing = TaskDrawing.from_task(_task(GoalType.CYLINDER))

        geojson = drawing_to_geojson(drawing)
        (route,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "optimized_route"
        ]
        assert route["properties"]["color"] == ROUTE_COLOR.hex
        assert route["properties"]["arrow_color"] == ROUTE_COLOR.hex

        kml = drawing_to_kml(drawing)
        assert self._placemark_color(kml, "Course Line") == ROUTE_COLOR.kml(ROUTE_ALPHA)
