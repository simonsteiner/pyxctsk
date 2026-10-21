"""The earth model: WGS84 (the default) against the FAI sphere (R = 6371 km).

`TestEarthModel` pins the distances each model gives; `TestTheEarthModelSelector`
pins how a selector (`None`, a string, the enum) reaches `distance/earth.py`.
"""

import math

import pytest
from pyproj import Geod

from pyxctsk import EarthModel
from pyxctsk.distance import (
    MeasuredTask,
    TaskTurnpoint,
    distance_through_centers,
    geodesic_distance,
    optimized_distance,
)
from tests.builders import task, turnpoint
from tests.corpus import reference_task

WGS84 = Geod(ellps="WGS84")


class TestEarthModel:
    """earthModel field: WGS84 (default) vs FAI sphere (R = 6371 km)."""

    def test_fai_sphere_great_circle_distance(self):
        """Zero-radius points 1° apart along a meridian: exactly R·π/180."""
        turnpoints = [TaskTurnpoint(0.0, 8.0, 0), TaskTurnpoint(1.0, 8.0, 0)]
        sphere = EarthModel.FAI_SPHERE
        sphere_deg = 6_371_000.0 * math.pi / 180.0  # 111194.93 m
        assert optimized_distance(turnpoints, earth_model=sphere) == pytest.approx(
            sphere_deg, abs=1.0
        )
        assert distance_through_centers(turnpoints, sphere) == pytest.approx(
            sphere_deg, abs=1.0
        )

    def test_wgs84_differs_from_sphere(self):
        """The same task measures differently on the two earth models."""
        turnpoints = [TaskTurnpoint(0.0, 8.0, 0), TaskTurnpoint(1.0, 8.0, 0)]
        wgs = optimized_distance(turnpoints)
        sph = optimized_distance(turnpoints, earth_model="FAI_SPHERE")
        # A meridian degree at the equator is ~110.57 km on WGS84.
        assert wgs == pytest.approx(110_574.4, abs=10.0)
        assert abs(wgs - sph) > 500.0

    def test_task_earth_model_propagates(self):
        """The measured task hands the task's earthModel to the optimizer."""
        task = reference_task("task_bevo").task
        task.earth_model = EarthModel.FAI_SPHERE
        sphere = MeasuredTask.from_task(task)
        task.earth_model = None
        wgs = MeasuredTask.from_task(task)

        assert sphere.route.earth_model is EarthModel.FAI_SPHERE
        assert abs(sphere.total_m - wgs.total_m) > 50.0


class TestTheEarthModelSelector:
    """The three values ADR 0003 admits, and the ones it does not.

    The selector was typed `object` in 16 signatures, so anything unrecognised
    fell through to WGS84 and neither mypy nor the runtime said a word: a
    misspelled "FAI-SPHERE" cost 97.6 m on a 135 km leg, silently.
    """

    A = (46.0, 8.0)
    B = (47.0, 9.0)

    @pytest.mark.parametrize("selector", [None, "WGS84", EarthModel.WGS84, "wgs84"])
    def test_the_ellipsoid_is_named_three_ways_and_defaulted(self, selector):
        """None means WGS84, and the enum and its string value agree."""
        assert geodesic_distance(self.A, self.B, selector) == pytest.approx(
            geodesic_distance(self.A, self.B)
        )

    @pytest.mark.parametrize("selector", ["FAI_SPHERE", EarthModel.FAI_SPHERE])
    def test_the_sphere_is_named_two_ways(self, selector):
        """And it really is a different answer, not a synonym."""
        sphere = geodesic_distance(self.A, self.B, selector)

        assert sphere == pytest.approx(134989.615, abs=0.01)
        assert sphere != pytest.approx(geodesic_distance(self.A, self.B), abs=1.0)

    @pytest.mark.parametrize(
        "selector", ["WSG84", "FAI-SPHERE", "SPHERE", "", 42, object()]
    )
    def test_anything_else_is_refused_rather_than_treated_as_wgs84(self, selector):
        """The failure mode this replaces: a typo that measured 97.6 m short."""
        with pytest.raises(ValueError, match="not an earth model"):
            geodesic_distance(self.A, self.B, selector)

    def test_the_message_names_what_is_allowed(self):
        """So a caller can fix it without reading the source."""
        with pytest.raises(ValueError, match="WGS84.*FAI_SPHERE"):
            geodesic_distance(self.A, self.B, "WSG84")

    def test_a_task_declaring_a_bad_model_fails_when_measured(self):
        """The model is a format field, so this is reachable from a real file."""
        built = task(
            turnpoint("A", 46.0, 8.0, radius=400),
            turnpoint("B", 46.5, 8.5, radius=400),
        )
        built.earth_model = "NOT_AN_EARTH"  # type: ignore[assignment]

        with pytest.raises(ValueError, match="not an earth model"):
            MeasuredTask.from_task(built)
