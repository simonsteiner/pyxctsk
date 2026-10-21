"""The palette: `Color`, and that every turnpoint role has a colour of its own.

`Color` is shared and each writer renders it in its own format. The tests here
cover the palette itself; `test_writers_agree.py` reads the colours back out of
both outputs and compares them.
"""

import pytest

from pyxctsk import GoalType, TurnpointType
from pyxctsk.export import common
from pyxctsk.export.common import GOAL_COLOR, Color, TaskDrawing, turnpoint_color
from tests.builders import three_turnpoint_task


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
    """One palette: every turnpoint role has a colour, and no two share one.

    The KML writer used to map the shared ``#rrggbb`` string back through a
    hand-written dict of ``simplekml.Color`` constants, which re-declared the
    palette and lost four of its five turnpoint values: a TAKEOFF turnpoint was
    ``#204d74`` in GeoJSON and ``#00008b`` in KML. These tests cover the palette
    itself; ``test_writers_agree.py`` reads the colour out of both outputs and
    compares them.
    """

    #: Every role a turnpoint can be drawn in, as (turnpoint type, is_goal).
    #: Derived from the enum, not hand-listed: a new ``TurnpointType`` has to
    #: arrive here, and therefore in the palette, rather than being defaulted
    #: into the ordinary-turnpoint colour by a test that never noticed it.
    ROLES = [(t, False) for t in TurnpointType] + [(TurnpointType.NONE, True)]

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
        task = three_turnpoint_task(GoalType.CYLINDER)
        task.turnpoints[0].type = None
        drawing = TaskDrawing.from_task(task)

        assert drawing.color_of(drawing.turnpoints[0]) == turnpoint_color(
            TurnpointType.NONE
        )
