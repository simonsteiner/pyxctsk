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

import json
import re
from pathlib import Path

import pytest

from pyxctsk import Goal, GoalType, Task, TaskType, Turnpoint, TurnpointType, Waypoint
from pyxctsk.distance import GoalLine, GoalLineOrientation
from pyxctsk.export import common
from pyxctsk.export.common import (
    CONTROL_ZONE_EDGE_COLOR,
    CONTROL_ZONE_FILL_COLOR,
    GOAL_COLOR,
    GOAL_LINE_COLOR,
    ROUTE_COLOR,
    Color,
    TaskDrawing,
    turnpoint_color,
)
from pyxctsk.export.geojson import drawing_to_geojson, generate_task_geojson
from pyxctsk.export.kml import FILL_ALPHA, ROUTE_ALPHA, drawing_to_kml


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

        A LINE goal needs an approach direction. With every point of the
        optimized route sitting on the goal there is none, so there is no line
        — and the goal turnpoint must stay drawn.
        """
        task = _task(GoalType.LINE)
        for turnpoint in task.turnpoints:
            turnpoint.waypoint.lat = 47.0
            turnpoint.waypoint.lon = 8.0
            # Zero radius: with a cylinder the route would still reach a
            # boundary point away from the goal, which *is* a direction.
            turnpoint.radius = 0

        drawing = TaskDrawing.from_task(task)

        assert drawing.goal_line is None
        assert len(drawing.turnpoints) == 3
        assert drawing.is_goal(drawing.turnpoints[-1])

    def test_coincident_centres_still_yield_a_line(self):
        """Concentric cylinders have an approach direction even so.

        Under S7F 2025+ the line is oriented against the optimized route
        point, and the route touches the previous cylinder's *boundary*. The
        pilot really does arrive from there, so there is a direction to face —
        where the 2024 rule, comparing centres, saw none.
        """
        drawing = TaskDrawing.from_task(_task(GoalType.LINE, prev_lat=47.0))

        assert drawing.goal_line is not None
        assert drawing.goal_line.approach_from != (47.0, 8.0)
        assert len(drawing.turnpoints) == 2

    def test_the_line_faces_the_route_not_the_turnpoint_centre(self):
        """S7F 2025+ §6.2.3.1, and the 2024 rule is still reachable."""
        task = _task(GoalType.LINE, prev_lat=47.0)
        drawing = TaskDrawing.from_task(task)

        assert drawing.goal_line is not None
        assert drawing.goal_line.approach_from == drawing.route.points[-2]

        legacy = GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)
        assert legacy is not None
        assert legacy.approach_from == (45.5, 8.0)

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
        coordinates = drawing.route_coordinates()
        assert coordinates is not None
        assert len(coordinates) == 3


class TestOneDrawingTwoFormats:
    """The reason the value exists: both writers render the same one."""

    def test_rendering_both_formats_optimizes_the_route_once(self, monkeypatch):
        """Two formats, one drawing, one measured task.

        Each writer used to derive its own route, so producing both formats for
        one task optimized it twice. Counting optimizer calls is no longer the
        way to say so: the drawing holds a ``MeasuredTask``, so the claim is
        that both renderings read that one value — an assertion about identity,
        which a call count could only approximate.
        """
        calls = []
        real = common.MeasuredTask.from_task

        def counting(task, *args, **kwargs):
            calls.append(task)
            return real(task, *args, **kwargs)

        monkeypatch.setattr(common.MeasuredTask, "from_task", counting)

        drawing = TaskDrawing.from_task(_task(GoalType.LINE))
        kml = drawing_to_kml(drawing)
        geojson = drawing_to_geojson(drawing)

        assert len(calls) == 1, (
            "the drawing is the shared measurement, not a per-format one"
        )
        assert "Goal Line" in kml
        assert any(f["properties"]["type"] == "goal_line" for f in geojson["features"])

    def test_the_drawings_route_is_its_measured_tasks_route(self):
        """``drawing.route`` reads through to the measured task, not a copy."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE))

        assert drawing.route is drawing.measured.route
        assert drawing.measured.task is drawing.task

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

    #: Every role a turnpoint can be drawn in, as (turnpoint type, is_goal).
    #: Derived from the enum, not hand-listed: a new ``TurnpointType`` has to
    #: arrive here, and therefore in the palette, rather than being defaulted
    #: into the ordinary-turnpoint colour by a test that never noticed it.
    ROLES = [(t, False) for t in TurnpointType] + [(TurnpointType.NONE, True)]

    @staticmethod
    def _placemark_style(kml: str, name: str) -> str:
        """The named placemark's style block, followed through its styleUrl.

        simplekml hoists styles into the document and references them by id, so
        reading a placemark's colour means resolving that reference rather than
        counting occurrences.

        Args:
            kml: The rendered document.
            name: The placemark's ``<name>``.

        Returns:
            The `<Style>` element the placemark points at.
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
        return style.group(0)

    @classmethod
    def _placemark_color(cls, kml: str, name: str, element: str = "LineStyle") -> str:
        """One colour out of the named placemark's style.

        Args:
            kml: The rendered document.
            name: The placemark's ``<name>``.
            element: The style element to read, ``LineStyle`` or ``PolyStyle``.

        Returns:
            That element's colour as KML's ``aabbggrr``.
        """
        style = cls._placemark_style(kml, name)
        color = re.search(
            rf"<{element}[^>]*>\s*<color>([0-9a-f]{{8}})</color>", style, re.S
        )
        assert color, f"{name!r} has no {element} colour:\n{style}"
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

    @pytest.mark.parametrize("turnpoint_type", list(TurnpointType))
    def test_every_turnpoint_type_has_a_colour(self, turnpoint_type):
        """The palette is total over the enum, so nothing degrades silently.

        Card D's complaint about the deleted KML dict was its `.get(hex, blue)`
        default: an entry it did not know about rendered as blue rather than
        failing. A lookup with a default one level up would have kept exactly
        that failure mode for a newly added `TurnpointType`, so the table is
        spelled out per member and this test is what makes adding one a CI
        failure rather than a colour nobody chose.

        It asserts the membership directly rather than letting
        `turnpoint_color`'s `KeyError` be the failure: the property under test is
        that the table covers the enum, and reading the private table is the only
        way to say that without the assertion restating the implementation.
        """
        assert turnpoint_type in common._TURNPOINT_COLORS, (
            f"{turnpoint_type} has no palette entry, so it would render as "
            "whatever the lookup fell back to"
        )

    @pytest.mark.parametrize(("turnpoint_type", "is_goal"), ROLES)
    def test_every_role_has_a_colour_of_its_own(self, turnpoint_type, is_goal):
        """One colour per role, no two roles sharing and no default standing in."""
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

    def test_a_turnpoint_with_no_type_is_an_ordinary_one(self):
        """`type=None` is legal on the model, and the drawing normalizes it.

        The two writers used to normalize it differently — KML to
        `TurnpointType.NONE`, GeoJSON not at all — and agreed only because both
        lookups fell through to the same default. `color_of` is the one answer.
        """
        task = _task(GoalType.CYLINDER)
        task.turnpoints[0].type = None
        drawing = TaskDrawing.from_task(task)

        assert drawing.color_of(drawing.turnpoints[0]) == turnpoint_color(
            TurnpointType.NONE
        )

    def test_both_writers_draw_the_turnpoints_in_the_palette_colours(self):
        """The regression: KML's colours are the shared ones, not a remapping."""
        drawing = TaskDrawing.from_task(self._task_of_every_role())
        expected = [drawing.color_of(tp) for tp in drawing.turnpoints]

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

    def test_both_writers_name_the_same_turnpoint_the_same_way(self):
        """The label was assembled twice, so it could differ; now it is asked for.

        The ``TP{i+1}`` fallback for an unnamed turnpoint was written three
        times across the two writers.
        """
        drawing = TaskDrawing.from_task(self._task_of_every_role())
        expected = [drawing.label_of(tp, i) for i, tp in enumerate(drawing.turnpoints)]

        geojson = drawing_to_geojson(drawing)
        from_geojson = [
            f["properties"]["name"]
            for f in geojson["features"]
            if f["properties"]["type"] == "cylinder"
        ]

        assert from_geojson == expected
        kml = drawing_to_kml(drawing)
        for label in expected:
            assert f"<name>{label}</name>" in kml

    def test_both_writers_describe_the_same_turnpoint_the_same_way(self):
        """KML wrote `Type: TurnpointType.TAKEOFF`; GeoJSON wrote no role at all."""
        drawing = TaskDrawing.from_task(self._task_of_every_role())
        expected = [drawing.description_of(tp) for tp in drawing.turnpoints]

        geojson = drawing_to_geojson(drawing)
        from_geojson = [
            f["properties"]["description"]
            for f in geojson["features"]
            if f["properties"]["type"] == "cylinder"
        ]

        assert from_geojson == expected
        kml = drawing_to_kml(drawing)
        for description in expected:
            assert f"<description>{description}</description>" in kml

    def test_no_writer_puts_a_python_repr_in_user_visible_text(self):
        """`Type: TurnpointType.TAKEOFF` and `Type: None` reached the map."""
        drawing = TaskDrawing.from_task(self._task_of_every_role())

        kml = drawing_to_kml(drawing)
        geojson = json.dumps(drawing_to_geojson(drawing), default=str)

        for rendered in (kml, geojson):
            assert "TurnpointType." not in rendered
            assert "Type: None" not in rendered

    @pytest.mark.parametrize("role", [None, TurnpointType.NONE])
    def test_an_ordinary_turnpoint_is_described_without_a_role(self, role):
        """It has none, and printing `Type: None` said otherwise.

        Both spellings of "no role" describe the same — the asymmetry
        ``color_of`` normalizes away, applied here too.
        """
        drawing = TaskDrawing.from_task(self._task_of_every_role())
        ordinary = Turnpoint(
            radius=1500,
            waypoint=Waypoint(name="X", lat=46.0, lon=8.0, alt_smoothed=0),
            type=role,
        )

        assert drawing.description_of(ordinary) == "Radius: 1500m"

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

    def test_both_writers_draw_the_goal_line_in_one_colour(self):
        """It was red in KML and green in GeoJSON — the same shape, two colours."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE))
        assert drawing.goal_line is not None, "this task has a goal line to draw"

        geojson = drawing_to_geojson(drawing)
        (goal_line,) = [
            f for f in geojson["features"] if f["properties"]["type"] == "goal_line"
        ]
        assert goal_line["properties"]["stroke"] == GOAL_LINE_COLOR.hex

        kml = drawing_to_kml(drawing)
        assert self._placemark_color(kml, "Goal Line") == GOAL_LINE_COLOR.kml()

    def test_both_writers_draw_the_control_zone_in_one_pair_of_colours(self):
        """Edge and fill differ from each other, but not between formats."""
        drawing = TaskDrawing.from_task(_task(GoalType.LINE))

        geojson = drawing_to_geojson(drawing)
        (zone,) = [
            f
            for f in geojson["features"]
            if f["properties"]["type"] == "goal_control_zone"
        ]
        assert zone["properties"]["stroke"] == CONTROL_ZONE_EDGE_COLOR.hex
        assert zone["properties"]["fill"] == CONTROL_ZONE_FILL_COLOR.hex

        kml = drawing_to_kml(drawing)
        name = "Goal Control Zone"
        assert self._placemark_color(kml, name) == CONTROL_ZONE_EDGE_COLOR.kml(), (
            "the zone's edge"
        )
        assert self._placemark_color(
            kml, name, "PolyStyle"
        ) == CONTROL_ZONE_FILL_COLOR.kml(FILL_ALPHA), "the zone's fill"

    def test_neither_writer_declares_a_colour_of_its_own(self):
        """The structural half: a colour literal in a writer is the drift itself.

        Every defect this class covers was a colour spelled out in a writer —
        a `simplekml.Color` constant, a `#rrggbb` string, or an `aabbggrr` one
        typed by hand. The palette is the only place those may appear, so a new
        one appearing in a writer fails here rather than in a map three months
        from now.

        The `aabbggrr` rule is by shape, so any quoted 8-hex-digit literal in a
        writer trips it, colour or not. That is deliberate: nothing else in these
        two modules has wanted one, and the failure is a prompt to move a colour
        into the palette or to narrow this check on purpose — the same kind of
        review gate as `EXPECTED_DEFERRED_IMPORTS` in test_layering.py.
        """
        moved_to = "move it into common.py's palette, or narrow this check"
        package = Path(common.__file__).parent
        for writer in ("kml.py", "geojson.py"):
            source = (package / writer).read_text()
            assert not re.search(r"#[0-9a-fA-F]{6}\b", source), (
                f"{writer} spells out a #rrggbb colour: {moved_to}"
            )
            assert "simplekml.Color" not in source, (
                f"{writer} uses a simplekml.Color constant: {moved_to}"
            )
            assert not re.search(r"""["'][0-9a-fA-F]{8}["']""", source), (
                f"{writer} has a quoted 8-hex-digit literal, which is how a KML "
                f"colour gets hand-written: {moved_to}"
            )
