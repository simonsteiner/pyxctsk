"""FAI Sporting Code S7F 2026 conformance regressions.

Derived from docs/arch-review/2026-08-18-s7f-2026-conformance-audit.md.
Each test keeps the finding and specification provenance that it pins.
"""

import json

import pytest

from pyxctsk import (
    GoalType,
    Task,
    parse_task,
)
from pyxctsk.distance import optimized_distance
from pyxctsk.distance.earth import geod_for_earth_model, geodesic_distance
from pyxctsk.distance.goal_line import (
    GoalLine,
    GoalLineOrientation,
)
from pyxctsk.distance.measured_task import MeasuredTask, task_to_turnpoints
from pyxctsk.distance.plane import (
    LocalPlane,
    local_tm_transformers,
    task_area_center,
)
from pyxctsk.distance.route_optimization import calculate_iteratively_refined_route
from pyxctsk.model.validation import ValidationRule
from tests.conformance._support import BASE_TASK, task_json
from tests.corpus import reference_task, reference_tasks
from tests.paths import ELEVATED_GOAL_DIR


class TestGoalLineFollowsTheOptimizedRoute:
    """S7F-01: goal-line orientation, S7F 2025+ §6.2.3.1.

    *"The previous point p is defined as the optimized route point on the last
    control zone before goal."* The 2024 edition said the centre of "the last
    turn point that is different from the goal line centre" instead, which is
    what this used to implement.
    """

    def _azimuth(self, task, line):
        """Approach azimuth the line is built perpendicular to."""
        geod = geod_for_earth_model(task.earth_model)
        return geod.inv(
            line.approach_from[1],
            line.approach_from[0],
            line.center[1],
            line.center[0],
        )[0]

    @pytest.mark.parametrize(
        "name",
        [
            "task_fobe_line",
            "task_motu_line",
            "task_piga_line",
            "task_qoga_line",
            "task_quno_line",
        ],
    )
    def test_approach_is_the_optimized_route_point(self, name):
        """Every LINE-goal reference task orients against the route, not a centre."""
        task = reference_task(name).task
        measured = MeasuredTask.from_task(task)

        line = GoalLine.from_measured_task(measured)

        assert line is not None
        assert line.approach_from == measured.route.points[-2]

    def test_a_goal_inside_the_previous_cylinder_faces_the_right_way(self):
        """The case that showed the rule mattered.

        task_qoga_line's goal sits 2 259 m from the centre of a 3 000 m ESS
        cylinder — inside it. The route therefore touches that cylinder on the
        far side and arrives from the opposite direction to the one the centre
        suggests, so the 2024 rule drew the line nearly *parallel* to the real
        approach and put the control-zone semicircle behind the pilot.
        """
        task = reference_task("task_qoga_line").task

        current = GoalLine.from_task(task)
        legacy = GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)

        assert current is not None and legacy is not None
        moved = abs(
            (self._azimuth(task, current) - self._azimuth(task, legacy) + 180) % 360
            - 180
        )
        assert moved > 150.0, (
            f"expected the two editions to differ sharply, got {moved}"
        )

    def test_the_2024_rule_is_still_reachable(self):
        """Kept deliberately: it is what a task drawn before 2025 shows."""
        task = reference_task("task_qoga_line").task

        legacy = GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)

        assert legacy is not None
        previous = task.turnpoints[-2].waypoint
        assert legacy.approach_from == (previous.lat, previous.lon)

    def test_measuring_first_matches_deriving_one(self):
        """Passing a measured task is an optimization, not a different answer."""
        task = reference_task("task_fobe_line").task

        assert GoalLine.from_measured_task(MeasuredTask.from_task(task)) == (
            GoalLine.from_task(task)
        )

    def test_the_orientation_does_not_move_the_distance(self):
        """A LINE goal is a zero-radius circle either way (§7.2).

        Only the drawn shape changes; the optimized distance must not.
        """
        task = reference_task("task_qoga_line").task
        before = MeasuredTask.from_task(task).route.total_m

        GoalLine.from_task(task, GoalLineOrientation.TURNPOINT_CENTERS)
        after = MeasuredTask.from_task(task).route.total_m

        assert before == after


class TestElevatedGoal:
    """S7F-06 and S7F-07: the bounds FAI S7F 2026 §6.2.3.2 puts on an elevated goal.

    The XCTrack interface spec defines ``goal.finishAltitude`` but constrains
    nothing about it, so these two rules are the only ones in
    ``model/validation.py`` sourced from the scoring code.
    """

    def _validate(self, goal, **overrides):
        """Validate BASE_TASK with a replaced goal."""
        return Task.from_json(task_json(goal=goal, **overrides)).validate()

    @pytest.mark.parametrize("altitude", [0, 300, 1000])
    def test_an_altitude_in_range_is_accepted(self, altitude):
        """Zero to 1000 m above the goal waypoint, inclusive.

        BASE_TASK marks ESS at turnpoint 1, so the goal is moved onto the ESS
        here — otherwise the *other* rule fires and this one proves nothing.
        """
        issues = self._validate(
            {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": altitude},
            turnpoints=_turnpoints_with_ess_last(),
        )

        assert issues == []

    @pytest.mark.parametrize("altitude", [-1, 1001, 5000])
    def test_an_altitude_out_of_range_is_reported(self, altitude):
        """Spec: "by default 300 m but can be increased up to 1000 m"."""
        issues = self._validate(
            {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": altitude},
            turnpoints=_turnpoints_with_ess_last(),
        )

        assert [i.rule for i in issues] == [ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE]

    def test_a_ground_level_goal_is_not_checked(self):
        """No elevated goal, no elevated-goal rules — BASE_TASK has ESS early."""
        assert Task.from_json(task_json()).validate() == []

    def test_an_elevated_goal_elsewhere_than_the_ess_is_reported(self):
        """Spec: an elevated goal "implicitly also serves as the ESS"."""
        issues = self._validate(
            {"type": "CYLINDER", "deadline": "18:00:00Z", "finishAltitude": 300}
        )

        assert [i.rule for i in issues] == [ValidationRule.ELEVATED_GOAL_IS_NOT_ESS]
        # Both numbers are 0-based indices, and the message says so: "1 of 2"
        # read as a count, which on a three-turnpoint task is simply wrong.
        assert "turnpoint index 1, not at the goal (index 2)" in str(issues[0])

    def test_the_reference_elevated_goal_task_stays_valid(self):
        """The real task this rule was written against must not now fail."""
        task = parse_task(
            ELEVATED_GOAL_DIR.joinpath("xcontest-conformant.xctsk").read_text()
        )

        assert task.goal is not None
        assert task.goal.finish_altitude == 300
        assert task.validate() == []

    def test_the_qr_format_is_checked_too(self):
        """``g.fa`` reaches the same rule as ``goal.finishAltitude``."""
        task = Task.from_json(
            task_json(
                goal={
                    "type": "CYLINDER",
                    "deadline": "18:00:00Z",
                    "finishAltitude": 5000,
                }
            )
        )

        qr = task.to_qr_code_task()
        assert qr.goal is not None and qr.goal.finish_altitude == 5000
        assert ValidationRule.FINISH_ALTITUDE_OUT_OF_RANGE in {
            issue.rule for issue in qr.validate()
        }


def _turnpoints_with_ess_last():
    """BASE_TASK's turnpoints with ESS moved onto the goal."""
    turnpoints = json.loads(json.dumps(BASE_TASK["turnpoints"]))
    del turnpoints[1]["type"]
    turnpoints[-1]["type"] = "ESS"
    return turnpoints


class TestRouteOptimizerConformance:
    """S7F-03 and S7F-04: §7.1.6's two passes, and §7's "shortest path"."""

    def _shifted_plane(self, lat_offset, lon_offset):
        """A plane deliberately centred away from the task area."""

        def around(centers, earth_model=None):
            lat, lon = task_area_center(centers)
            return LocalPlane(
                *local_tm_transformers(lat + lat_offset, lon + lon_offset, earth_model)
            )

        return staticmethod(around)

    @pytest.mark.parametrize("name", ["task_bevo", "task_duna", "task_nohe"])
    def test_the_answer_does_not_depend_on_the_projection(self, name, monkeypatch):
        """§7 asks for *the* shortest path, so the plane must not pick which one.

        The alternating method converges to a local optimum, and before
        multi-start these three tasks each had a shorter valid route reachable
        by nothing more than moving the projection centre — `task_bevo` by
        98.6 m. Every route compared here touches every cylinder in order, so
        a shorter one is strictly better.
        """
        turnpoints = task_to_turnpoints(reference_task(name).task)
        shipped = calculate_iteratively_refined_route(turnpoints).total_m

        for lat_offset in (-0.45, 0.0, 0.45):
            for lon_offset in (-0.45, 0.0, 0.45):
                monkeypatch.setattr(
                    LocalPlane, "around", self._shifted_plane(lat_offset, lon_offset)
                )
                shifted = calculate_iteratively_refined_route(turnpoints).total_m
                monkeypatch.undo()

                assert shipped <= shifted + 0.05, (
                    f"a plane shifted by ({lat_offset}, {lon_offset}) finds a route "
                    f"{shipped - shifted:.3f} m shorter"
                )

    def test_every_route_point_touches_its_cylinder(self):
        """Whatever basin the sweep lands in, the route must still be a route.

        A shorter number is only better if it is a legal path: §7 requires each
        control zone to be touched, in order.
        """
        for reference in reference_tasks():
            turnpoints = task_to_turnpoints(reference.task)
            route = calculate_iteratively_refined_route(turnpoints)

            for i, (point, turnpoint) in enumerate(zip(route.points, turnpoints)):
                want = 0.0 if i == 0 else turnpoint.radius
                assert geodesic_distance(turnpoint.center, point) == pytest.approx(
                    want, abs=0.01
                ), f"{reference.stem} turnpoint {i}"

    def test_the_plane_is_rebuilt_from_the_corrected_path(self, monkeypatch):
        """§7.1.6 runs PathFinder twice, the second time on the found path.

        "boundingBox_final = FindBoundingBox(correctedPath)" — so the centre
        the spec says to keep comes from the route, not from the turnpoints
        that produced it.
        """
        seen = []
        real = LocalPlane.around.__func__  # type: ignore[attr-defined]

        def spy(centers, earth_model=None):
            seen.append(list(centers))
            return real(LocalPlane, centers, earth_model)

        monkeypatch.setattr(LocalPlane, "around", staticmethod(spy))
        turnpoints = task_to_turnpoints(reference_task("task_bevo").task)
        route = calculate_iteratively_refined_route(turnpoints)

        assert len(seen) == 2, "the optimizer must build two planes, not one"
        assert seen[0] == [tp.center for tp in turnpoints]
        # The second plane is centred on the first pass's corrected path: its
        # points sit on cylinder boundaries, so they are not the centres.
        assert seen[1] != seen[0]
        assert len(seen[1]) == len(route.points)

    def test_a_second_pass_plane_differs_from_a_turnpoint_plane(self):
        """The two bounding boxes are genuinely different, so the pass is not a no-op."""
        turnpoints = task_to_turnpoints(reference_task("task_bevo").task)
        route = calculate_iteratively_refined_route(turnpoints)

        from_turnpoints = task_area_center([tp.center for tp in turnpoints])
        from_path = task_area_center(list(route.points))

        assert from_turnpoints != from_path


class TestS7FShapesTheFormatCannotCarry:
    """S7F-09: two 2026 features the XCTrack format has no keys for.

    §6.2.1 gives every turnpoint cylinder an optional upper and lower altitude
    limit in metres AMSL, and §6.2.2 defines a line control zone anywhere in a
    task. XCTrack's format defines neither, so pyxctsk cannot promote them to
    model fields without inventing keys for a format that is not ours — and a
    reader would then be free to write them back out as though they were spec.

    What *is* in our hands is that a producer sending such keys does not lose
    them. These pin that: the passthrough carries them verbatim through both
    formats, and never interprets them.
    """

    def _with_turnpoint_keys(self, **extra):
        """BASE_TASK with extra non-spec keys on its first turnpoint."""
        data = json.loads(task_json())
        data["turnpoints"][0].update(extra)
        return Task.from_dict(data)

    def test_altitude_limits_survive_the_json_round_trip(self):
        """§6.2.1's limits are carried, not dropped."""
        task = self._with_turnpoint_keys(altitudeMin=500, altitudeMax=3000)

        assert task.turnpoints[0].unknown == {
            "altitudeMin": 500,
            "altitudeMax": 3000,
        }
        exported = json.loads(task.to_json())["turnpoints"][0]
        assert exported["altitudeMin"] == 500
        assert exported["altitudeMax"] == 3000

    def test_altitude_limits_survive_the_qr_round_trip(self):
        """Including across the format seam, where unknown keys are re-homed."""
        task = self._with_turnpoint_keys(altitudeMin=500, altitudeMax=3000)

        back = task.to_qr_code_task().to_task()

        assert back.turnpoints[0].unknown == {
            "altitudeMin": 500,
            "altitudeMax": 3000,
        }

    def test_the_limits_are_never_interpreted(self):
        """Carried is not understood: nothing reads them as a real constraint.

        A cylinder with altitude limits is the same cylinder to the optimizer
        — S7F applies the limits when validating a *tracklog* crossing
        (§9.2.1), which is not something this library does.
        """
        plain = Task.from_json(task_json())
        limited = self._with_turnpoint_keys(altitudeMin=500, altitudeMax=3000)

        assert optimized_distance(task_to_turnpoints(limited)) == pytest.approx(
            optimized_distance(task_to_turnpoints(plain))
        )
        assert limited.validate() == []

    def test_a_line_control_zone_is_carried_the_same_way(self):
        """§6.2.2's parameters have no home either, and are not invented one."""
        task = self._with_turnpoint_keys(
            lineDistance=5.0, lineOrientation="NE", lineLength=1.0
        )

        exported = json.loads(task.to_json())["turnpoints"][0]

        assert exported["lineOrientation"] == "NE"
        # And nothing has quietly become a goal line.
        assert task.goal is not None and task.goal.type is GoalType.CYLINDER
