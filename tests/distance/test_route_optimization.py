"""Unit tests for the Ding–Xie–Jiang alternating route optimizer.

These tests exercise the planar solver through its two entry points and the
TurnpointGeometry seam that lets route orchestration use lightweight fakes.
"""

import math
from dataclasses import dataclass
from pathlib import Path

import pytest
from pyproj import CRS, Transformer

from pyxctsk import UnmeasurableRouteError
from pyxctsk.distance import OptimizedRoute
from pyxctsk.distance.earth import (
    FAI_SPHERE_RADIUS_M,
    geodesic_distance,
)
from pyxctsk.distance.plane import LocalPlane, ltm_scale_factor, task_area_center
from pyxctsk.distance.route_optimization import (
    boundary_point,
    calculate_iteratively_refined_route,
)
from pyxctsk.distance.turnpoint import TaskTurnpoint, TurnpointGeometry


@dataclass
class FakeTurnpoint:
    """A minimal TurnpointGeometry stand-in for seam tests.

    It declares no ``earth_model`` and no ``goal_type`` because the protocol
    declares neither: the earth is an argument of the optimizer, and a LINE
    goal is a zero-radius circle by the time it gets here, which
    ``task_to_turnpoints`` arranges and this fake can express with
    ``radius=0``.
    """

    center: tuple[float, float]
    radius: float = 0.0


def test_fake_turnpoint_satisfies_protocol():
    """FakeTurnpoint and TaskTurnpoint should satisfy the TurnpointGeometry seam."""
    assert isinstance(FakeTurnpoint((0.0, 0.0)), TurnpointGeometry)
    assert isinstance(TaskTurnpoint(0.0, 0.0), TurnpointGeometry)


def test_the_protocol_declares_exactly_what_the_optimizer_reads():
    """Neither more nor less: both directions have been wrong here.

    Too many, twice. ``earth_model`` was declared because the optimizer picked
    the route's earth off the *first* turnpoint — so a misspelling on any
    other was ignored, and a list mixing the two earths measured differently
    depending on which came first. It is an argument of the optimizer now.
    ``goal_type`` was declared because ``plane_circle`` read it to
    collapse a LINE goal to a zero-radius circle. That rule belongs to
    ``task_to_turnpoints``, which builds the cylinders, and stating it in both
    places left three modules disagreeing about which one owned it. A LINE goal
    now arrives already carrying ``radius=0``, nothing in the optimizer reads
    the goal type, and an interface declaring a value nothing reads misleads a
    caller as much as one omitting a value it needs.
    """
    assert set(TurnpointGeometry.__annotations__) == {"center", "radius"}


def test_a_turnpoint_without_a_goal_type_is_enough_to_optimize():
    """The seam's whole claim: geometry in, route out, no goal vocabulary.

    ``FakeTurnpoint`` has no ``goal_type`` at all, so this fails to even
    construct if the optimizer starts reading one again.
    """
    route = calculate_iteratively_refined_route(
        [
            FakeTurnpoint((46.5, 8.0)),
            FakeTurnpoint((46.7, 8.1), radius=1_000.0),
            FakeTurnpoint((47.0, 8.0), radius=0.0),
        ]
    )

    assert len(route.points) == 3
    assert route.total_m > 0


def test_route_through_fake_turnpoints():
    """The public entry point should run against the TurnpointGeometry seam."""
    turnpoints = [
        FakeTurnpoint((47.0, 8.0)),
        FakeTurnpoint((47.0, 8.1), radius=1_000.0),
        FakeTurnpoint((47.0, 8.2)),
    ]
    optimized = calculate_iteratively_refined_route(turnpoints)
    assert optimized.total_m > 0
    assert len(optimized.points) == 3
    assert optimized.points[0] == (47.0, 8.0)
    assert optimized.points[-1] == (47.0, 8.2)
    # The legs are kept, and they are what the total is made of.
    assert len(optimized.legs) == 2
    assert optimized.cumulative_m()[-1] == optimized.total_m


class TestTheTakeoffIsAPoint:
    """ADR 0002's takeoff rule, stated once: at projection, not in the solver."""

    def test_the_route_starts_at_the_takeoff_centre_whatever_its_radius(self):
        """A 5 km takeoff cylinder is not touched; the route leaves its centre."""
        route = calculate_iteratively_refined_route(
            [
                FakeTurnpoint((46.5, 8.0), radius=5_000.0),
                FakeTurnpoint((46.8, 8.0), radius=1_000.0),
            ]
        )

        assert route.points[0] == (46.5, 8.0)

    def test_a_concentric_first_turnpoint_is_flown_out_to(self):
        """Its boundary is a real leg, not merged into the takeoff."""
        route = calculate_iteratively_refined_route(
            [
                FakeTurnpoint((46.5, 8.0), radius=3_000.0),
                FakeTurnpoint((46.5, 8.0), radius=3_000.0),
                FakeTurnpoint((46.8, 8.0), radius=0.0),
            ]
        )

        assert route.legs[0] == pytest.approx(3_000.0, abs=0.01)


def test_short_input_handling():
    """Fewer than two turnpoints yields a zero distance and pass-through path."""
    empty = calculate_iteratively_refined_route([])
    assert empty.total_m == 0.0
    assert empty.points == ()
    assert empty.legs == ()
    # One entry per point means none at all here: accumulate's initial=0.0 seed
    # would otherwise report a distance to a point that does not exist.
    assert empty.cumulative_m() == []
    single = calculate_iteratively_refined_route([FakeTurnpoint((1.0, 2.0))])
    assert single.total_m == 0.0
    assert single.points == ((1.0, 2.0),)
    assert single.cumulative_m() == [0.0]


def test_cumulative_m_has_one_entry_per_point():
    """The documented invariant, across every route length."""
    for points, legs in (
        ((), ()),
        (((1.0, 2.0),), ()),
        (((1.0, 2.0), (1.1, 2.1)), (100.0,)),
        (((1.0, 2.0), (1.1, 2.1), (1.2, 2.2)), (100.0, 200.0)),
    ):
        route = OptimizedRoute(points=points, legs=legs)
        cumulative = route.cumulative_m()

        assert len(cumulative) == len(route.points), f"{len(points)} points"
        if cumulative:
            assert cumulative[0] == 0.0
            assert cumulative[-1] == route.total_m


class TestLtmScaleFactor:
    """The LTM scale factor k₀ the plane is built with (S7F §7.1.2)."""

    def test_below_the_break_is_the_flat_value(self):
        """Up to 55° the spec fixes a single constant."""
        for lat in (0.0, 46.5, 55.0):
            assert ltm_scale_factor(lat) == pytest.approx(0.99994)

    def test_above_the_break_grows_linearly(self):
        """Beyond 55° it grows by 1.3e-4 per 60° of latitude."""
        assert ltm_scale_factor(115.0) == pytest.approx(0.99994 + 1.3e-4)
        assert ltm_scale_factor(85.0) == pytest.approx(0.99994 + 0.5 * 1.3e-4)

    def test_southern_hemisphere_scales_like_the_northern(self):
        """Annex A takes ``abs(refLat)`` before applying the formula."""
        for lat in (46.5, 60.0, 78.0):
            assert ltm_scale_factor(-lat) == ltm_scale_factor(lat)

    def test_the_plane_is_actually_built_with_it(self):
        """A coordinate in the plane carries k₀, not 1.

        Guards the wiring rather than the formula: the projection used to be
        built with ``+k=1``, and asserting the constant alone would not have
        caught that.
        """
        unscaled = Transformer.from_crs(
            CRS.from_epsg(4326),
            CRS.from_proj4(
                "+proj=tmerc +lat_0=46.0 +lon_0=8.0 +k_0=1 +x_0=0 +y_0=0 "
                "+ellps=WGS84 +units=m +no_defs"
            ),
            always_xy=True,
        )
        x, _ = LocalPlane.around([(46.0, 8.0)]).xy((46.0, 8.1))
        x_unscaled, _ = unscaled.transform(8.1, 46.0)

        assert x == pytest.approx(x_unscaled * ltm_scale_factor(46.0), rel=1e-12)
        assert x != pytest.approx(x_unscaled, rel=1e-9)


class TestThePlaneRefusesWhatItCannotRepresent:
    """``LocalPlane`` is the only way into and out of the plane, so it refuses.

    A Transverse Mercator projection has no finite image for a point 90° of
    longitude from its central meridian on the equator, and no finite inverse
    for a planar point far beyond the earth.
    """

    def test_a_point_off_the_plane_is_refused_going_in(self):
        """A point on the equator 90° from the central meridian has no image."""
        plane = LocalPlane.around([(0.0, 0.0)])

        with pytest.raises(UnmeasurableRouteError, match="cannot be projected"):
            plane.xy((0.0, 90.0))

    def test_a_point_off_the_earth_is_refused_coming_back(self):
        """A planar point 10^300 m out has no geographic inverse."""
        plane = LocalPlane.around([(46.0, 8.0)])

        with pytest.raises(UnmeasurableRouteError, match="cannot be mapped back"):
            plane.lon_lat((1e300, 0.0))

    def test_a_non_finite_planar_point_is_refused_coming_back(self):
        """What the solver returns when its lengths overflowed."""
        plane = LocalPlane.around([(46.0, 8.0)])

        with pytest.raises(UnmeasurableRouteError, match="cannot be mapped back"):
            plane.lon_lat((math.inf, math.nan))


class TestTaskAreaCenter:
    """The projection centre S7F §7.1.6 asks for."""

    def test_is_the_box_centre_not_the_mean(self):
        """Six clustered points and one outlier centre between the extremes."""
        points = [(46.0, 8.0)] * 6 + [(47.0, 9.0)]

        assert task_area_center(points) == (46.5, 8.5)

    def test_single_point_is_its_own_centre(self):
        """A one-turnpoint area has a degenerate box."""
        assert task_area_center([(46.25, 8.75)]) == (46.25, 8.75)

    def test_empty_has_no_area(self):
        """There is no area of interest to centre on."""
        with pytest.raises(ValueError, match="at least one point"):
            task_area_center([])

    def test_antimeridian_box_wraps_through_the_widest_gap(self):
        """A task at ±180° centres near ±180°, not near 0°.

        Averaging longitudes directly puts this centre at -60°, half a world
        from the task — which is what the mean-of-longitudes rule did.
        """
        lat, lon = task_area_center([(-17.0, 179.5), (-17.0, -179.5), (-17.2, -179.0)])

        assert lat == pytest.approx(-17.1)
        assert abs(lon) > 179.0, f"{lon} is not near the antimeridian"
        assert lon == pytest.approx(-179.75)

    def test_longitudes_are_normalized_before_boxing(self):
        """370° and 10° are the same meridian."""
        assert task_area_center([(0.0, 370.0), (0.0, 20.0)]) == task_area_center(
            [(0.0, 10.0), (0.0, 20.0)]
        )

    def test_wide_but_not_wrapping_span_uses_the_plain_box(self):
        """A gap under 180° leaves the box unwrapped."""
        assert task_area_center([(0.0, -80.0), (0.0, 40.0)]) == (0.0, -20.0)


class TestThePlaneCarriesItsEarthModel:
    """A planar solution and the boundary it is snapped onto share one earth.

    `LocalPlane.around` used the earth model to build its transformers and then
    dropped it, so every consumer took the model a second time and nothing
    checked the two agreed. `boundary_point` solved in the plane it was given
    but snapped with the turnpoint's own model — an FAI-sphere boundary point placed
    from a WGS84 planar solution, silently, whenever they differed.
    """

    def test_the_plane_remembers_the_model_it_was_built_on(self):
        """It is a field now, not an argument the caller re-supplies."""
        assert LocalPlane.around([(46.5, 8.0)], "FAI_SPHERE").earth_model == (
            "FAI_SPHERE"
        )

    def test_the_default_plane_is_wgs84(self):
        """Same default as everywhere else: None means the ellipsoid."""
        assert LocalPlane.around([(46.5, 8.0)]).earth_model is None

    @pytest.mark.parametrize("model", [None, "WGS84", "FAI_SPHERE"])
    def test_the_point_lands_on_the_planes_model(self, model):
        """The plane is the only thing carrying an earth, so it decides."""
        turnpoint = TaskTurnpoint(lat=46.5, lon=8.0, radius=5000)
        plane = LocalPlane.around([turnpoint.center], model)

        point = boundary_point(turnpoint, (46.0, 7.5), (47.0, 8.6), plane)

        assert geodesic_distance(turnpoint.center, point, model) == pytest.approx(
            5000.0, abs=1e-6
        )


class TestTheEarthIsChosenInOnePlace:
    """`earth.py` said the choice is made "once". `plane.py` made it again.

    One module built the two earths as `Geod`s, the other as PROJ CRSes, in a
    two-branch `if` that paired a datum string with a geographic CRS. Adding an
    earth model, or correcting the sphere's radius, meant editing both — and
    only `earth.py` refused a value naming no earth at all.
    """

    def test_the_plane_asks_the_earth_for_its_figure(self):
        """Both halves of a projection come from the module that owns them."""
        from pyxctsk.distance.earth import crs_for_earth_model, datum_proj4

        assert datum_proj4(None) == "+ellps=WGS84"
        assert datum_proj4("FAI_SPHERE") == f"+R={FAI_SPHERE_RADIUS_M}"
        assert crs_for_earth_model() == crs_for_earth_model("WGS84")
        assert crs_for_earth_model("FAI_SPHERE") != crs_for_earth_model("WGS84")

    def test_plane_py_no_longer_names_an_earth(self):
        """The radius and the datum strings lived here as well as next door."""
        source = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "pyxctsk"
            / "distance"
            / "plane.py"
        ).read_text()
        code = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith("#")
        )
        body = code.split('"""', 2)[-1]

        assert "ellps" not in body
        assert "FAI_SPHERE_RADIUS_M" not in body
        assert "epsg" not in body.lower()

    def test_an_unknown_model_is_refused_by_the_projection_too(self):
        """It used to fall through a bool and quietly mean WGS84."""
        with pytest.raises(ValueError, match="not an earth model"):
            LocalPlane.around([(46.5, 8.0)], "WSG84")

    @pytest.mark.parametrize("model", [None, "WGS84", "FAI_SPHERE"])
    def test_the_three_spellings_of_one_earth_share_a_cache_entry(self, model):
        """`canonical` keys the cache, so the plane stops keying it on a bool."""
        from pyxctsk.distance.earth import canonical
        from pyxctsk.distance.plane import local_tm_transformers

        assert local_tm_transformers(46.5, 8.0, canonical(model)) is (
            local_tm_transformers(46.5, 8.0, canonical(model))
        )
