"""A task bound to the optimized route flown for it.

The value exists to make one mistake unrepresentable: pairing a task with
another task's route. These pin what it derives, and that every module needing
both now takes the pair rather than two arguments.
"""

import inspect

import pytest

from pyxctsk import Goal, GoalType, Task, TaskType, TurnpointType
from pyxctsk.distance import MeasuredTask, task_distances_from, task_to_turnpoints
from pyxctsk.distance.goal_line import GoalLine
from pyxctsk.distance.speed_section import SpeedSection
from tests.builders import task, turnpoint
from tests.corpus import reference_task


def _race_task():
    """A task with a speed section and a cylinder goal."""
    return task(
        turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
        turnpoint("S", 46.3, 8.2, radius=5000, type=TurnpointType.SSS),
        turnpoint("C", 46.6, 8.6, radius=8000),
        turnpoint("G", 46.9, 8.3, radius=2000, type=TurnpointType.ESS),
        goal=GoalType.CYLINDER,
    )


class TestWhatItHolds:
    """The three things a measured task carries, and what it derives."""

    def test_it_holds_the_task_it_was_built_from(self):
        """The task is carried by identity, not copied."""
        built = _race_task()

        assert MeasuredTask.from_task(built).task is built

    def test_it_derives_one_cylinder_per_turnpoint(self):
        """The cylinders are the task's turnpoints, in order."""
        built = _race_task()

        measured = MeasuredTask.from_task(built)

        assert len(measured.turnpoints) == len(built.turnpoints)
        assert [tp.radius for tp in measured.turnpoints] == [400, 5000, 8000, 2000]

    def test_the_cylinders_are_task_to_turnpoints(self):
        """The LINE-goal rule is applied in exactly one place."""
        built = _race_task()

        assert [tp.center for tp in MeasuredTask.from_task(built).turnpoints] == [
            tp.center for tp in task_to_turnpoints(built)
        ]

    def test_a_line_goal_becomes_a_zero_radius_point(self):
        """The goal cylinder is sized by the goal's type, not its radius."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
            turnpoint("G", 46.5, 8.5, radius=2000),
            goal=GoalType.LINE,
        )

        assert MeasuredTask.from_task(built).turnpoints[-1].radius == 0

    def test_the_route_has_a_point_per_turnpoint(self):
        """One route point per cylinder, so the two zip without a length guard."""
        measured = MeasuredTask.from_task(_race_task())

        assert len(measured.route.points) == len(measured.turnpoints)


class TestTheNumbersItProjects:
    """`total_m` and `cumulative_m` are projections of the one route."""

    def test_total_is_the_routes_total(self):
        """The task distance is read off the route, not measured again."""
        measured = MeasuredTask.from_task(_race_task())

        assert measured.total_m == measured.route.total_m

    def test_cumulative_starts_at_zero_and_ends_at_the_total(self):
        """A prefix of the route by construction, launch through goal."""
        measured = MeasuredTask.from_task(reference_task("task_bevo").task)

        cumulative = measured.cumulative_m()

        assert cumulative[0] == 0.0
        assert cumulative[-1] == pytest.approx(measured.total_m)

    def test_cumulative_never_decreases(self):
        """Distance along a route only grows."""
        cumulative = MeasuredTask.from_task(
            reference_task("task_gibe").task
        ).cumulative_m()

        assert cumulative == sorted(cumulative)

    def test_cumulative_has_one_entry_per_turnpoint(self):
        """So a report can index it without asking whether the entry exists.

        The report used to guard this with ``if i < len(cumulative) else 0.0``,
        which was unreachable for a correctly-paired call and a wrong-number
        generator for a mismatched one.
        """
        measured = MeasuredTask.from_task(reference_task("task_gibe").task)

        assert len(measured.cumulative_m()) == len(measured.task.turnpoints)

    def test_a_task_with_no_turnpoints_projects_to_nothing(self):
        """The degenerate case is empty, not an error."""
        measured = MeasuredTask.from_task(
            Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])
        )

        assert measured.turnpoints == ()
        assert measured.cumulative_m() == []
        assert task_distances_from(measured).turnpoints == ()

    @pytest.mark.parametrize(
        "goal", [None, Goal(type=GoalType.LINE)], ids=["no goal", "a goal"]
    )
    def test_no_turnpoints_is_no_cylinders_whatever_the_goal_says(self, goal):
        """The empty case does not depend on reading the goal's type.

        ``task_to_turnpoints`` computes the goal type before the comprehension,
        from ``effective_goal`` — which for a task with no turnpoints is
        whatever the file carried, including None. The guard is a conditional
        expression, so it is evaluated before the attribute access; a review of
        that line read the precedence the other way and predicted a crash here.
        """
        task = Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[], goal=goal)

        assert task_to_turnpoints(task) == []


class TestTheMismatchIsGone:
    """The defect the value was introduced to kill.

    ``task_distances_from_route(task, route)`` and
    ``GoalLine.from_task(task, route=route)`` each took a task and a route as
    two arguments, with the pairing stated only in prose. Handing them a
    mismatched pair returned a fully formed report 12.8 km out — no error, and
    nothing a type checker could see.
    """

    @pytest.mark.parametrize(
        "func",
        [
            task_distances_from,
            GoalLine.from_measured_task,
            SpeedSection.from_measured_task,
        ],
        ids=["task_distances_from", "GoalLine.from_measured_task", "SpeedSection"],
    )
    def test_no_interface_takes_a_task_and_a_route_separately(self, func):
        """Each takes the pair as one value, so the two cannot disagree."""
        params = inspect.signature(func).parameters

        assert "route" not in params, f"{func.__name__} still takes a loose route"
        assert "measured" in params

    def test_the_report_reads_the_route_the_task_was_measured_with(self):
        """Two different tasks cannot contribute to one report."""
        bevo = MeasuredTask.from_task(reference_task("task_bevo").task)
        duna = MeasuredTask.from_task(reference_task("task_duna").task)

        assert task_distances_from(bevo) != task_distances_from(duna)
        assert task_distances_from(bevo).optimized_distance_km == round(
            bevo.total_m / 1000, 1
        )
