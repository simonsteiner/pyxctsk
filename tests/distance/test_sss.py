"""The optimizer's behaviour on a task with a speed section.

What is under test is route optimization, not a start-of-speed-section
module: there is no longer one. `distance/sss.py` held four functions —
`calculate_sss_info` with zero callers anywhere and a test body of
`assert True`, its two private helpers, and `calculate_optimal_sss_entry_point`,
a one-line pass-through to `TaskTurnpoint.optimal_point` that only tests
called. An SSS entry point is a query on the computed route, which is what
these tests ask it for.
"""

import pytest
from geopy.distance import geodesic

from pyxctsk.distance import calculate_iteratively_refined_route
from pyxctsk.distance.task_distances import task_to_turnpoints


class TestSpeedSectionRouting:
    """A task whose second turnpoint starts the speed section."""

    def test_the_fixture_has_the_shape_these_tests_assume(self, sss_task):
        """Takeoff, then SSS, then an ordinary turnpoint."""
        turnpoints = sss_task.turnpoints

        assert len(turnpoints) >= 3
        assert turnpoints[0].type.value == "TAKEOFF"
        assert turnpoints[1].type.value == "SSS"
        assert turnpoints[2].type is None or turnpoints[2].type.value == ""

    def test_the_first_leg_reaches_the_boundary_not_the_centre(self, sss_task):
        """The route enters the SSS cylinder rather than flying to its middle.

        Regression: the optimized route used to navigate turnpoint *centers*,
        so the first leg was the takeoff-to-SSS-center distance rather than
        the shorter one to the perimeter point the route actually crosses.
        """
        turnpoints = task_to_turnpoints(sss_task)
        centres = [(tp.center[0], tp.center[1]) for tp in turnpoints]
        optimized = calculate_iteratively_refined_route(turnpoints).points

        assert len(optimized) == len(centres)

        to_centre = geodesic(centres[0], centres[1]).meters
        to_boundary = geodesic(optimized[0], optimized[1]).meters

        assert to_boundary < to_centre
        # And the point it reaches is on the cylinder, within snapping error.
        radius = turnpoints[1].radius
        assert geodesic(optimized[1], centres[1]).meters == pytest.approx(
            radius, abs=1.0
        )
