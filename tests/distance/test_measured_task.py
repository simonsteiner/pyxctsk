"""A task bound to the optimized route flown for it.

The value exists to make one mistake unrepresentable: pairing a task with
another task's route. These pin what it derives, and that every module needing
both now takes the pair rather than two arguments.
"""

import inspect

import pytest

from pyxctsk import (
    EarthModel,
    Goal,
    GoalType,
    MismatchedRouteError,
    Task,
    TaskType,
    TaskValidationError,
    TurnpointType,
    UnmeasurableRouteError,
)
from pyxctsk.distance import (
    MeasuredTask,
    OptimizedRoute,
    TooFewTurnpointsError,
    task_distances_from,
    task_to_turnpoints,
)
from pyxctsk.distance.earth import geodesic_distance
from pyxctsk.distance.goal_line import GoalLine
from pyxctsk.distance.speed_section import SpeedSection
from pyxctsk.model.validation import ValidationRule
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

    def test_a_task_with_no_turnpoints_measures_to_nothing(self):
        """The measurement is empty; asking it for a *distance* is the error.

        `MeasuredTask` stays total — it is the pair, not the verdict — while
        the two published distance shapes both refuse, which they did not
        always: `task_distances_from` used to answer zeros for the task
        `DistanceReport` raised on.
        """
        measured = MeasuredTask.from_task(
            Task(task_type=TaskType.CLASSIC, version=1, turnpoints=[])
        )

        assert measured.turnpoints == ()
        assert measured.cumulative_m() == []
        with pytest.raises(TooFewTurnpointsError):
            task_distances_from(measured)

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


class TestTheConstructorChecksThePair:
    """The constructor is public, so it is where the pairing is enforced.

    Only ``from_task`` used to pair a task with its own route. Calling the
    dataclass directly checked nothing, and ``MeasuredTask(bevo, fobe's
    route)`` reported 47.8 km for a 94.0 km task.
    """

    def test_another_tasks_route_is_refused(self):
        """The reproduction: bevo's task, fobe's route."""
        bevo = reference_task("task_bevo").task
        fobe = MeasuredTask.from_task(reference_task("task_fobe_line").task)

        with pytest.raises(MismatchedRouteError):
            MeasuredTask(task=bevo, route=fobe.route)

    def test_a_route_of_the_wrong_length_is_refused(self):
        """One route point per turnpoint, or it is not this task's route."""
        measured = MeasuredTask.from_task(_race_task())
        short = OptimizedRoute(
            points=measured.route.points[:-1],
            legs=measured.route.legs[:-1],
            earth_model=measured.route.earth_model,
        )

        with pytest.raises(MismatchedRouteError, match="3 points for 4"):
            MeasuredTask(task=measured.task, route=short)

    def test_a_route_on_another_earth_is_refused(self):
        """The points may fit, but the legs were measured somewhere else."""
        measured = MeasuredTask.from_task(_race_task())
        sphere = OptimizedRoute(
            points=measured.route.points,
            legs=measured.route.legs,
            earth_model=EarthModel.FAI_SPHERE,
        )

        with pytest.raises(MismatchedRouteError, match="FAI_SPHERE"):
            MeasuredTask(task=measured.task, route=sphere)

    def test_a_point_outside_its_cylinder_is_refused(self):
        """Every point touches its own cylinder; a moved one does not."""
        measured = MeasuredTask.from_task(_race_task())
        points = list(measured.route.points)
        points[2] = (points[2][0] + 0.5, points[2][1])
        moved = OptimizedRoute(
            points=tuple(points),
            legs=measured.route.legs,
            earth_model=measured.route.earth_model,
        )

        with pytest.raises(MismatchedRouteError, match="route point 2"):
            MeasuredTask(task=measured.task, route=moved)

    def test_its_own_route_is_accepted(self):
        """Rebuilding from the parts ``from_task`` produced is the same value."""
        measured = MeasuredTask.from_task(_race_task())

        assert MeasuredTask(task=measured.task, route=measured.route) == measured

    def test_the_cylinders_are_not_an_argument(self):
        """Derived from the task, so they cannot come from somewhere else."""
        assert "turnpoints" not in inspect.signature(MeasuredTask).parameters


class TestARouteThePlaneCannotHoldIsRefused:
    """A task the local Transverse Mercator plane cannot represent is an error.

    Every case here is a task ``Task.validate()`` accepts. The route is solved
    in one plane centred on the task area (S7F §7.1.2, §7.1.6), and a
    Transverse Mercator plane cannot hold a point a quarter of the globe from
    its central meridian, nor map a planar point thousands of kilometres out
    back onto the earth. These used to leave as a bare ``AssertionError`` from
    the solver ("_INITIAL_PLACEMENTS is never empty"), as pyproj's
    ``CRSError`` for a projection centred on ``lon_0=nan``, or — worst — as a
    report of ``NaN`` metres with exit 0.
    """

    @pytest.mark.parametrize(
        ("course", "cause"),
        [
            pytest.param(
                [(0.0, 0.0, 0), (0.0, 180.0, 0)],
                "projected",
                id="half-the-globe-apart",
            ),
            pytest.param(
                [(0.0, 0.0, 0), (0.0, 179.9, 400)],
                "projected",
                id="nearly-half-the-globe-apart",
            ),
            pytest.param(
                [(46.0, 8.0, 0), (46.1, 8.1, 10**300)],
                "mapped back",
                id="huge-radius-was-a-crs-error",
            ),
            pytest.param(
                [(46.0, 8.0, 0), (46.1, 8.1, 20_000_000), (46.2, 8.0, 0)],
                "mapped back",
                id="radius-past-half-the-earth-was-nan-metres",
            ),
            pytest.param(
                [(46.0, 8.0, 0), (46.1, 8.1, 10**308), (46.2, 8.0, 0)],
                "mapped back",
                id="radius-overflowing-the-planar-length",
            ),
        ],
    )
    def test_it_is_refused_naming_the_plane(self, course, cause):
        """One library error, saying which way the projection failed."""
        unmeasurable = task(
            *(
                turnpoint(
                    f"P{i}",
                    lat,
                    lon,
                    radius=radius,
                    type=(
                        TurnpointType.SSS
                        if i == 0
                        else TurnpointType.ESS
                        if i == len(course) - 1
                        else None
                    ),
                )
                for i, (lat, lon, radius) in enumerate(course)
            )
        )
        assert unmeasurable.validate() == []

        with pytest.raises(UnmeasurableRouteError, match=cause) as raised:
            MeasuredTask.from_task(unmeasurable)

        assert "Transverse Mercator" in str(raised.value)


class TestACylinderPastTheFarSideOfTheEarthIsRefused:
    """A cylinder reaching past the far side of the earth has no boundary.

    The plane refuses what it cannot represent, but a route point placed far
    out *along its central meridian* is representable: a meridian is a closed
    curve, so the inverse projection wraps round it and returns a finite point.
    The snap onto the boundary (§7.1.7) then walked the radius round the earth
    too. Every shape here used to report a finite distance with exit 0.
    """

    @pytest.mark.parametrize("model", [None, EarthModel.FAI_SPHERE])
    @pytest.mark.parametrize(
        "course",
        [
            pytest.param([(46.0, 8.0, 400), (46.1, 8.0, 10**300)], id="goal-1e300"),
            pytest.param(
                [(46.0, 8.0, 400), (46.1, 8.0, 25_000_000)], id="goal-25000km"
            ),
            pytest.param(
                [(46.0, 8.0, 400), (46.1, 8.0, 400), (46.2, 8.0, 30_000_000)],
                id="third-of-three-30000km",
            ),
        ],
    )
    def test_it_is_refused(self, course, model):
        """Not 2 941 637 m, nor any other number."""
        unmeasurable = task(
            *(
                turnpoint(
                    f"P{i}",
                    lat,
                    lon,
                    radius=radius,
                    type=(
                        TurnpointType.SSS
                        if i == 0
                        else TurnpointType.ESS
                        if i == len(course) - 1
                        else None
                    ),
                )
                for i, (lat, lon, radius) in enumerate(course)
            )
        )
        unmeasurable.earth_model = model
        assert unmeasurable.validate() == []

        with pytest.raises(UnmeasurableRouteError, match="far side of the earth"):
            MeasuredTask.from_task(unmeasurable)

    @pytest.mark.parametrize("radius", [45_000_000, 10**300], ids=["45000km", "1e300"])
    def test_a_middle_cylinder_is_refused_on_the_sphere(self, radius):
        """Measured 9 939 253 m and 9 699 152 m before."""
        unmeasurable = task(
            turnpoint("A", 46.0, 8.0, radius=400),
            turnpoint("B", 46.1, 8.0, radius=radius),
            turnpoint("C", 46.2, 8.0, radius=400),
        )
        unmeasurable.earth_model = EarthModel.FAI_SPHERE

        with pytest.raises(UnmeasurableRouteError, match="far side of the earth"):
            MeasuredTask.from_task(unmeasurable)

    @pytest.mark.parametrize(
        ("model", "radius"),
        [
            (None, 10_000_000),
            (EarthModel.FAI_SPHERE, 10_000_000),
            (EarthModel.FAI_SPHERE, 20_000_000),
        ],
    )
    def test_a_cylinder_short_of_the_far_side_still_measures(self, model, radius):
        """From inside a goal cylinder the route runs straight out to its edge.

        The takeoff lies on the goal's meridian, so the edge is the radius less
        the distance between the centres — exactly, on either earth.
        """
        inside = task(
            turnpoint("A", 46.0, 8.0, radius=400),
            turnpoint("B", 46.1, 8.0, radius=radius),
        )
        inside.earth_model = model

        measured = MeasuredTask.from_task(inside)

        apart = geodesic_distance((46.0, 8.0), (46.1, 8.0), model)
        assert measured.route.total_m == pytest.approx(radius - apart, abs=0.01)

    def test_the_takeoff_radius_is_not_touched_so_it_is_not_refused(self):
        """ADR 0002: the route starts at the takeoff's centre whatever its size."""
        huge = task(
            turnpoint("A", 46.0, 8.0, radius=10**300),
            turnpoint("B", 46.1, 8.0, radius=400),
        )
        small = task(
            turnpoint("A", 46.0, 8.0, radius=0),
            turnpoint("B", 46.1, 8.0, radius=400),
        )

        assert (
            MeasuredTask.from_task(huge).route.total_m
            == MeasuredTask.from_task(small).route.total_m
        )


class TestANegativeRadiusIsNamed:
    """S9: ``"radius": -11`` was reported as a route that does not fit.

    ``MismatchedRouteError`` said route point 0 was 11.0 m outside turnpoint
    0's cylinder — blaming the optimizer for the task. A cylinder cannot have a
    negative radius, which is the rule ``Task.validate()`` already states, so
    measuring refuses with that rule's issue rather than a second wording.
    """

    @pytest.mark.parametrize("index", [0, 1, 3])
    def test_every_role_is_refused_with_the_validation_rule(self, index):
        """The takeoff and the goal too: no role makes a negative size mean one."""
        measured = _race_task()
        measured.turnpoints[index].radius = -11

        with pytest.raises(TaskValidationError) as caught:
            MeasuredTask.from_task(measured)

        (issue,) = caught.value.issues
        assert issue.rule is ValidationRule.NEGATIVE_RADIUS
        assert str(issue) == f"turnpoint {index} has a negative radius (-11)"

    def test_a_negative_line_goal_is_refused_too(self):
        """Its cylinder is a point, but the radius it declares is still a size."""
        line = _race_task()
        line.goal = Goal(type=GoalType.LINE)
        line.turnpoints[-1].radius = -400

        with pytest.raises(TaskValidationError, match="negative radius"):
            task_to_turnpoints(line)
