"""The speed section's distance — FAI Sporting Code S7F 2026 §7.2.

§7.2 defines two task distances. `test_task_distances.py` covers the first;
this covers the second, including the property that made it a module of its
own: the ESS route is a *separate* optimization, not a prefix of the task's.
"""

import pytest

from pyxctsk import GoalType, TurnpointType
from pyxctsk.distance import (
    SpeedSection,
    calculate_iteratively_refined_route,
    task_to_turnpoints,
)
from tests.builders import task, turnpoint
from tests.corpus import reference_tasks


def _race_task(goal_type: GoalType = GoalType.CYLINDER):
    """A five-turnpoint task with a speed section in the middle."""
    return task(
        turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
        turnpoint("B", 46.2, 8.1, radius=5000, type=TurnpointType.SSS),
        turnpoint("C", 46.5, 8.6, radius=8000),
        turnpoint("D", 46.8, 8.2, radius=3000, type=TurnpointType.ESS),
        turnpoint("G", 46.9, 8.3, radius=400),
        goal=goal_type,
    )


class TestWhenThereIsNoSpeedSection:
    """A task without one has no number to report, and must say so."""

    def test_a_task_without_an_sss(self):
        """No start, no speed section."""
        built = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("E", 46.5, 8.5, type=TurnpointType.ESS),
            turnpoint("G", 46.9, 8.3, radius=400),
        )

        assert SpeedSection.from_task(built) is None

    def test_a_task_without_an_ess(self):
        """No end, no speed section."""
        built = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.5, 8.5, type=TurnpointType.SSS),
            turnpoint("G", 46.9, 8.3, radius=400),
        )

        assert SpeedSection.from_task(built) is None

    def test_an_ess_before_its_sss(self):
        """A task `validate()` already rejects; there is no honest number."""
        built = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("E", 46.3, 8.2, type=TurnpointType.ESS),
            turnpoint("S", 46.5, 8.5, type=TurnpointType.SSS),
            turnpoint("G", 46.9, 8.3, radius=400),
        )

        assert SpeedSection.from_task(built) is None

    def test_a_route_task_with_no_roles_at_all(self):
        """An XC/Waypoints route has no speed section by definition."""
        assert SpeedSection.from_task(task()) is None


class TestTheThreeNumbers:
    """§7.2: speed section = launch-to-ESS, minus the pre-start portion."""

    def test_the_speed_section_is_the_difference(self):
        """The definition, checked against the two it is built from."""
        section = SpeedSection.from_task(_race_task())

        assert section is not None
        assert section.distance_m == pytest.approx(
            section.to_ess_m - section.pre_start_m
        )

    def test_the_pre_start_portion_reaches_the_sss(self):
        """It is how far along its own route the start sits."""
        section = SpeedSection.from_task(_race_task())

        assert section is not None
        assert section.start_index == 1
        assert section.pre_start_m == pytest.approx(
            section.route.cumulative_m()[section.start_index]
        )

    def test_all_three_are_positive_and_ordered(self):
        """Sanity on a task where every leg is real."""
        section = SpeedSection.from_task(_race_task())

        assert section is not None
        assert 0 < section.pre_start_m < section.to_ess_m
        assert 0 < section.distance_m < section.to_ess_m

    def test_the_route_stops_at_the_ess(self):
        """`taskToESS` ends there — the goal is not on it."""
        built = _race_task()
        section = SpeedSection.from_task(built)

        assert section is not None
        assert len(section.route.points) == 4  # A, B, C, D — not G


class TestNotAPrefixOfTheTaskRoute:
    """Why this is a separate optimization, and a module of its own.

    The optimizer treats the last circle it is handed as the finish, so a
    route ending at the ESS bends toward it rather than passing through on the
    way to goal. Reading the ESS distance off the task route instead is the
    same mistake that once put cumulative distances 5.09 km out.
    """

    def test_the_ess_distance_differs_from_the_task_routes_prefix(self):
        """The two disagree, which is the whole point of optimizing twice."""
        built = _race_task()
        section = SpeedSection.from_task(built)
        task_route = calculate_iteratively_refined_route(task_to_turnpoints(built))

        assert section is not None
        prefix = task_route.cumulative_m()[3]  # distance to the ESS along the task
        assert section.to_ess_m != pytest.approx(prefix, abs=1.0)

    def test_the_ess_route_is_never_longer_than_the_task_route(self):
        """It is a shorter course, optimized in its own right."""
        for reference in reference_tasks():
            section = SpeedSection.from_task(reference.task)
            if section is None:
                continue
            total = calculate_iteratively_refined_route(
                task_to_turnpoints(reference.task)
            ).total_m

            assert section.to_ess_m <= total + 1e-6, reference.stem


class TestGoalShapes:
    """The ESS can be the goal, and the goal can be a line."""

    def test_an_ess_that_is_the_goal_cylinder(self):
        """The whole task is the speed section, less the pre-start."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.2, 8.1, radius=5000, type=TurnpointType.SSS),
            turnpoint("G", 46.9, 8.3, radius=400, type=TurnpointType.ESS),
            goal=GoalType.CYLINDER,
        )
        section = SpeedSection.from_task(built)
        total = calculate_iteratively_refined_route(task_to_turnpoints(built)).total_m

        assert section is not None
        assert section.to_ess_m == pytest.approx(total)

    def test_an_ess_that_is_a_line_goal_keeps_the_line_semantics(self):
        """A LINE goal is a zero-radius point, not a cylinder of half its length.

        Slicing the task's own turnpoints is what preserves this: the goal
        handling lives in ``task_to_turnpoints``, and the ESS here *is* the
        last turnpoint.
        """
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
            turnpoint("S", 46.2, 8.1, radius=5000, type=TurnpointType.SSS),
            turnpoint("G", 46.9, 8.3, radius=400, type=TurnpointType.ESS),
            goal=GoalType.LINE,
        )
        section = SpeedSection.from_task(built)

        assert section is not None
        # The route ends on the goal centre, not 400 m short of it.
        assert section.route.points[-1] == (46.9, 8.3)


class TestAcrossTheCorpus:
    """Every real task that has a speed section reports a coherent one."""

    @pytest.mark.parametrize("reference", reference_tasks(), ids=str)
    def test_the_numbers_hold_together(self, reference):
        """Or the task genuinely has no speed section."""
        section = SpeedSection.from_task(reference.task)
        if section is None:
            roles = {tp.type for tp in reference.task.turnpoints}
            assert not {TurnpointType.SSS, TurnpointType.ESS} <= roles
            return

        assert section.distance_m == pytest.approx(
            section.to_ess_m - section.pre_start_m
        )
        assert 0.0 <= section.pre_start_m <= section.to_ess_m
        assert section.distance_m > 0.0
