"""The "distance through centres" convention — the number S7F does not define.

These pin the reading pyxctsk proposes, and that the alternatives it keeps for
diagnosis really are different answers. See `docs/s7f-distance-reference.md`.
"""

import pytest

from pyxctsk import EarthModel, GoalType, TurnpointType
from pyxctsk.distance import (
    PROPOSED_READING,
    CenterDistanceReading,
    center_distance,
    center_distance_readings,
    distance_through_centers,
    task_to_turnpoints,
)
from tests.builders import task, turnpoint
from tests.corpus import reference_task, reference_tasks, tasks_with_reference_distance


def _race_task():
    """A task with a pre-start leg and a goal cylinder, so all readings differ."""
    return task(
        turnpoint("A", 46.0, 8.0, radius=400, type=TurnpointType.TAKEOFF),
        turnpoint("S", 46.3, 8.2, radius=5000, type=TurnpointType.SSS),
        turnpoint("C", 46.6, 8.6, radius=8000),
        turnpoint("G", 46.9, 8.3, radius=2000, type=TurnpointType.ESS),
        goal=GoalType.CYLINDER,
    )


class TestTheProposedReading:
    """What pyxctsk publishes: every centre, launch to goal."""

    def test_the_default_is_the_proposed_reading(self):
        """Callers who do not choose get the one we are proposing."""
        built = _race_task()

        assert center_distance(built) == center_distance(built, PROPOSED_READING)
        assert PROPOSED_READING is CenterDistanceReading.LAUNCH_TO_GOAL

    def test_it_is_the_polyline_through_every_centre(self):
        """No turnpoint is skipped and nothing is subtracted."""
        built = _race_task()

        assert center_distance(built) == pytest.approx(
            distance_through_centers(task_to_turnpoints(built))
        )

    def test_it_honours_the_declared_earth_model(self):
        """ADR 0003 — and on the FAI sphere this is not an S7F number at all."""
        built = _race_task()
        wgs84 = center_distance(built)
        built.earth_model = EarthModel.FAI_SPHERE

        assert center_distance(built) != pytest.approx(wgs84, abs=1.0)

    def test_consecutive_duplicates_contribute_a_zero_leg(self):
        """Stated in the module docstring, so it is stated here too."""
        with_duplicate = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("B", 46.5, 8.0, radius=1000),
            turnpoint("B again", 46.5, 8.0, radius=1000),
            turnpoint("G", 47.0, 8.0, radius=400),
        )
        without = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("B", 46.5, 8.0, radius=1000),
            turnpoint("G", 47.0, 8.0, radius=400),
        )

        assert center_distance(with_duplicate) == pytest.approx(
            center_distance(without)
        )


class TestTheAlternativeReadings:
    """Kept so a vendor can tell a convention apart from a bug."""

    def test_the_goal_boundary_reading_is_shorter_by_the_goal_radius(self):
        """It ends where the *optimized* distance ends."""
        built = _race_task()

        assert center_distance(
            built, CenterDistanceReading.LAUNCH_TO_GOAL_BOUNDARY
        ) == pytest.approx(center_distance(built) - built.turnpoints[-1].radius)

    def test_the_start_reading_drops_the_pre_start_leg(self):
        """From the SSS, the way §7.2's speed section excludes it."""
        built = _race_task()

        from_start = center_distance(built, CenterDistanceReading.START_TO_GOAL)

        assert from_start is not None
        assert from_start < center_distance(built)

    def test_the_start_reading_does_not_apply_without_an_sss(self):
        """Undefined rather than silently equal to the launch reading."""
        no_sss = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("G", 47.0, 8.0, radius=400),
        )

        assert center_distance(no_sss, CenterDistanceReading.START_TO_GOAL) is None

    def test_every_reading_is_reported_together(self):
        """The diagnostic: one call, every answer, keyed by name."""
        readings = center_distance_readings(_race_task())

        assert set(readings) == {r.value for r in CenterDistanceReading}
        assert all(v is not None for v in readings.values())

    def test_the_readings_really_do_disagree(self):
        """If they all agreed there would be nothing to pin down."""
        readings = center_distance_readings(reference_task("task_pepi").task)
        values = [v for v in readings.values() if v is not None]

        # 39.9 km apart on a task whose optimized distance is 92 km.
        assert max(values) - min(values) > 39_000

    def test_an_unknown_reading_is_an_error(self):
        """Not silently the default."""
        with pytest.raises(ValueError, match="not a center-distance reading"):
            center_distance(_race_task(), "LAUNCH_TO_SOMEWHERE")  # type: ignore[arg-type]


class TestDegenerateTasks:
    """A single point is not a distance."""

    @pytest.mark.parametrize(
        "reading", list(CenterDistanceReading), ids=lambda r: r.value
    )
    def test_one_turnpoint_has_no_centre_distance(self, reading):
        """Under every reading."""
        one = task(turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF))

        assert center_distance(one, reading) is None

    def test_an_sss_as_the_last_turnpoint_has_no_start_reading(self):
        """There is no leg left after it."""
        odd = task(
            turnpoint("A", 46.0, 8.0, type=TurnpointType.TAKEOFF),
            turnpoint("S", 47.0, 8.0, radius=400, type=TurnpointType.SSS),
        )

        assert center_distance(odd, CenterDistanceReading.START_TO_GOAL) is None
        assert center_distance(odd) is not None


class TestAgainstThePublishedValues:
    """Why this reading is the one proposed: it is what the boards already show."""

    @pytest.mark.parametrize("reference", tasks_with_reference_distance(), ids=str)
    def test_the_proposed_reading_matches_within_the_display_rounding(self, reference):
        """Agreement by convention, not by specification — but agreement."""
        published = reference.metadata.get("distance_through_centers_km")
        if published is None:
            pytest.skip("no published centre distance for this task")

        ours = center_distance(reference.task)

        assert ours is not None
        assert abs(ours - published * 1000) <= 50.0, (
            f"{reference.stem}: {ours:.1f} m vs {published * 1000:.0f} m published"
        )

    def test_every_corpus_task_reports_a_centre_distance(self):
        """Including the route tasks, which have no speed section."""
        for reference in reference_tasks():
            assert center_distance(reference.task) is not None, reference.stem
