"""Unit tests for the Ding–Xie–Jiang alternating route optimizer.

These tests exercise the planar GetOptPi primitive (crossing vs. reflection
cases) and the alternating odd/even optimization core directly, plus the
TurnpointGeometry seam that lets the optimizer run against lightweight fakes.
"""

import math
from dataclasses import dataclass

import pytest
from pyproj import CRS, Transformer

from pyxctsk.distance import OptimizedRoute
from pyxctsk.distance.route_optimization import (
    _INITIAL_PLACEMENTS,
    _boundary_toward,
    _optimize_plane_points,
    _place_at_centers,
    _place_chained_backward,
    _place_chained_forward,
    _polyline_length,
    _sweep_to_convergence,
    calculate_iteratively_refined_route,
)
from pyxctsk.distance.turnpoint import (
    EarthModelLike,
    LocalPlane,
    TaskTurnpoint,
    TurnpointGeometry,
    geodesic_distance,
    ltm_scale_factor,
    plane_optimal_point,
    task_area_center,
)


@dataclass
class FakeTurnpoint:
    """A minimal TurnpointGeometry stand-in for seam tests.

    It declares ``earth_model`` because the protocol does. It did not, and the
    optimizer read the attribute anyway through a ``getattr`` default — so this
    fake satisfied ``isinstance`` while getting a different distance for
    identical geometry than a ``TaskTurnpoint`` would.

    It declares no ``goal_type`` for the same reason in reverse: the protocol
    no longer does, because nothing in the optimizer reads one. A LINE goal is
    a zero-radius circle by the time it gets here, which ``task_to_turnpoints``
    arranges and this fake can express with ``radius=0``.
    """

    center: tuple[float, float]
    radius: float = 0.0
    earth_model: EarthModelLike = None


def test_fake_turnpoint_satisfies_protocol():
    """FakeTurnpoint and TaskTurnpoint should satisfy the TurnpointGeometry seam."""
    assert isinstance(FakeTurnpoint((0.0, 0.0)), TurnpointGeometry)
    assert isinstance(TaskTurnpoint(0.0, 0.0), TurnpointGeometry)


def test_the_protocol_declares_exactly_what_the_optimizer_reads():
    """Neither more nor less: both directions have been wrong here.

    Too few: ``calculate_iteratively_refined_route`` picks the route's earth
    model off the first turnpoint, and did it with a ``getattr`` against a
    protocol declaring three attributes whose docstring said "only three
    things" — so a fake satisfying ``isinstance`` got a different distance for
    identical geometry.

    Too many: ``goal_type`` was declared because ``plane_circle`` read it to
    collapse a LINE goal to a zero-radius circle. That rule belongs to
    ``task_to_turnpoints``, which builds the cylinders, and stating it in both
    places left three modules disagreeing about which one owned it. A LINE goal
    now arrives already carrying ``radius=0``, nothing in the optimizer reads
    the goal type, and an interface declaring a value nothing reads misleads a
    caller as much as one omitting a value it needs.
    """
    assert set(TurnpointGeometry.__annotations__) == {
        "center",
        "radius",
        "earth_model",
    }


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


class TestPlaneOptimalPoint:
    """The planar GetOptPi primitive (Ding et al. Algorithm 1)."""

    def test_zero_radius_returns_center(self):
        """A zero-radius circle collapses to its center."""
        assert plane_optimal_point((0, 0), (10, 0), (5.0, 5.0), 0.0) == (5.0, 5.0)

    def test_crossing_both_outside(self):
        """When the segment crosses the circle, the point adds no length."""
        p = plane_optimal_point((-10.0, 0.0), (10.0, 0.0), (0.0, 0.0), 2.0)
        # Entry intersection along the segment from prev.
        assert p[0] == pytest.approx(-2.0, abs=1e-9)
        assert p[1] == pytest.approx(0.0, abs=1e-9)

    def test_crossing_prev_inside(self):
        """With the previous point inside, the point is the segment-circle intersection."""
        p = plane_optimal_point((1.0, 0.0), (10.0, 0.0), (0.0, 0.0), 5.0)
        assert p == (pytest.approx(5.0), pytest.approx(0.0, abs=1e-9))

    def test_crossing_next_inside(self):
        """With the next point inside, the point is the segment-circle intersection."""
        p = plane_optimal_point((10.0, 0.0), (1.0, 0.0), (0.0, 0.0), 5.0)
        assert p == (pytest.approx(5.0), pytest.approx(0.0, abs=1e-9))

    def test_reflection_both_outside(self):
        """A symmetric no-crossing setup yields the reflection (bisector) point."""
        p = plane_optimal_point((-10.0, 10.0), (10.0, 10.0), (0.0, 0.0), 2.0)
        # By symmetry the optimal boundary point is straight "up" toward the pair.
        assert p[0] == pytest.approx(0.0, abs=1e-6)
        assert p[1] == pytest.approx(2.0, abs=1e-6)

    def test_reflection_both_inside(self):
        """Both neighbours inside (concentric case): the point stays on the boundary.

        This is the mandatory "out and back" of touching semantics — the same
        behaviour XCTrack exhibits for concentric turnpoints of different radii.
        """
        p = plane_optimal_point((0.5, 0.0), (0.25, 0.0), (0.0, 0.0), 5.0)
        assert math.hypot(*p) == pytest.approx(5.0, abs=1e-9)
        # By symmetry about the x-axis the optimum lies on it.
        assert p[0] == pytest.approx(5.0, abs=1e-6)

    def test_optimum_is_boundary_minimum(self):
        """The returned point must beat every sampled boundary point."""
        prev, nxt, center, radius = (-7.0, 3.0), (9.0, 6.0), (1.0, -2.0), 4.0

        def total(point):
            return math.hypot(point[0] - prev[0], point[1] - prev[1]) + math.hypot(
                point[0] - nxt[0], point[1] - nxt[1]
            )

        best = plane_optimal_point(prev, nxt, center, radius)
        for k in range(720):
            theta = math.pi * k / 360.0
            sample = (
                center[0] + radius * math.cos(theta),
                center[1] + radius * math.sin(theta),
            )
            assert total(best) <= total(sample) + 1e-6


class TestBoundaryToward:
    """The nearest-boundary rule, used both to place points and to finish."""

    def test_outside(self):
        """From outside, the nearest boundary point lies on the inbound radial."""
        assert _boundary_toward((0.0, 0.0, 3.0), (10.0, 0.0)) == (
            pytest.approx(3.0),
            pytest.approx(0.0),
        )

    def test_inside(self):
        """From inside, the point moves radially out to the boundary."""
        p = _boundary_toward((0.0, 0.0, 3.0), (1.0, 0.0))
        assert p == (pytest.approx(3.0), pytest.approx(0.0))

    def test_zero_radius(self):
        """A zero-radius circle collapses to its center."""
        assert _boundary_toward((5.0, 5.0, 0.0), (10.0, 0.0)) == (5.0, 5.0)

    def test_a_target_at_the_center_has_no_direction(self):
        """The one input with no answer: any boundary point is as near.

        Pinned because the two copies of this function that used to exist both
        chose +x, and a caller relying on it would not have noticed if one
        had changed.
        """
        assert _boundary_toward((0.0, 0.0, 3.0), (0.0, 0.0)) == (3.0, 0.0)


class TestAlternatingOptimizer:
    """The odd/even alternating sweep core (Ding et al. Algorithm 2)."""

    def test_collinear_circles_converge_to_straight_line(self):
        """Circles on a line: the optimal path is the straight segment."""
        circles = [
            (0.0, 0.0, 0.0),
            (10_000.0, 0.0, 1_000.0),
            (20_000.0, 0.0, 2_000.0),
            (30_000.0, 0.0, 0.0),
        ]
        points = _optimize_plane_points(circles, max_sweeps=100)
        # Middle circles are crossed by the straight line, so the total path
        # equals the end-to-end distance minus the final radius... here the
        # last circle has zero radius, so it is exactly the full 30 km.
        assert _polyline_length(points) == pytest.approx(30_000.0, abs=0.1)
        for point, circle in zip(points[1:-1], circles[1:-1]):
            assert point[1] == pytest.approx(0.0, abs=1e-6)
            assert abs(point[0] - circle[0]) == pytest.approx(circle[2], abs=1e-6)

    def test_convergence_stops_below_epsilon(self):
        """More sweeps than needed must not change the result beyond epsilon."""
        circles = [
            (0.0, 0.0, 0.0),
            (10_000.0, 5_000.0, 3_000.0),
            (20_000.0, -4_000.0, 2_000.0),
            (35_000.0, 2_000.0, 4_000.0),
            (45_000.0, 0.0, 400.0),
        ]
        short = _polyline_length(_optimize_plane_points(circles, max_sweeps=50))
        long = _polyline_length(_optimize_plane_points(circles, max_sweeps=500))
        assert abs(short - long) <= 0.1

    def test_start_point_stays_fixed(self):
        """The route must start at the first circle's center (takeoff center)."""
        circles = [(0.0, 0.0, 5_000.0), (20_000.0, 0.0, 1_000.0)]
        points = _optimize_plane_points(circles, max_sweeps=10)
        assert points[0] == (0.0, 0.0)


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


class TestInitialPlacements:
    """The starting configurations the alternating sweep is run from."""

    CIRCLES = [
        (0.0, 0.0, 0.0),
        (10_000.0, 3_000.0, 2_000.0),
        (20_000.0, -4_000.0, 5_000.0),
        (30_000.0, 0.0, 400.0),
    ]

    @pytest.mark.parametrize("place", _INITIAL_PLACEMENTS, ids=lambda f: f.__name__)
    def test_one_point_per_circle(self, place):
        """Every placement must seed the sweep with a full route."""
        assert len(place(self.CIRCLES)) == len(self.CIRCLES)

    @pytest.mark.parametrize("place", _INITIAL_PLACEMENTS, ids=lambda f: f.__name__)
    def test_the_start_point_is_the_takeoff_centre(self, place):
        """Index 0 is the launch point, never a boundary point."""
        assert place(self.CIRCLES)[0] == (0.0, 0.0)

    def _on_boundary(self, point, circle):
        """Planar distance from the circle's centre, for boundary assertions."""
        cx, cy, radius = circle
        return math.hypot(point[0] - cx, point[1] - cy) == pytest.approx(radius)

    def test_forward_chain_lands_every_later_point_on_its_boundary(self):
        """Chaining from the launch puts each point where the answer lives.

        The centres never can be an answer for a non-zero radius, which is why
        seeding there alone left the sweep in the wrong basin.
        """
        points = _place_chained_forward(self.CIRCLES)

        for point, circle in zip(points[1:], self.CIRCLES[1:]):
            assert self._on_boundary(point, circle)

    def test_backward_chain_seeds_from_the_last_centre(self):
        """It has to start somewhere: the final circle's centre is that seed.

        Every point it then derives — walking back toward the launch — is on a
        boundary; only the seed itself is not.
        """
        points = _place_chained_backward(self.CIRCLES)

        assert points[-1] == (self.CIRCLES[-1][0], self.CIRCLES[-1][1])
        for point, circle in zip(points[1:-1], self.CIRCLES[1:-1]):
            assert self._on_boundary(point, circle)

    def test_centres_placement_is_the_centres(self):
        """The original starting configuration, kept as one of the three."""
        assert _place_at_centers(self.CIRCLES) == [(c[0], c[1]) for c in self.CIRCLES]

    def test_a_zero_radius_circle_collapses_in_every_placement(self):
        """A LINE goal has one possible point wherever it is seeded from."""
        circles = [(0.0, 0.0, 0.0), (10_000.0, 0.0, 1_000.0), (20_000.0, 0.0, 0.0)]
        for place in _INITIAL_PLACEMENTS:
            assert place(circles)[2] == (20_000.0, 0.0)


class TestMultiStart:
    """S7F-04: one start finds *a* local optimum, not the shortest path."""

    #: Two big cylinders either side of the direct line, which is what gives
    #: the sweep more than one basin to fall into.
    CIRCLES = [
        (0.0, 0.0, 0.0),
        (20_000.0, 18_000.0, 17_000.0),
        (40_000.0, -18_000.0, 17_000.0),
        (60_000.0, 0.0, 400.0),
    ]

    def test_the_result_is_the_shortest_of_the_placements(self):
        """Whatever the sweep is seeded with, the shortest survives."""
        shipped = _polyline_length(_optimize_plane_points(self.CIRCLES, max_sweeps=100))

        for place in _INITIAL_PLACEMENTS:
            single = _sweep_to_convergence(
                list(self.CIRCLES), place(self.CIRCLES), 100, 0.1
            )
            assert shipped <= _polyline_length(single) + 1e-9

    def test_placements_are_deterministic_and_ordered(self):
        """The same task must always produce the same route."""
        first = _optimize_plane_points(self.CIRCLES, max_sweeps=100)

        assert _optimize_plane_points(self.CIRCLES, max_sweeps=100) == first


class TestThePlaneCarriesItsEarthModel:
    """A planar solution and the boundary it is snapped onto share one earth.

    `LocalPlane.around` used the earth model to build its transformers and then
    dropped it, so every consumer took the model a second time and nothing
    checked the two agreed. `optimal_point` solved in the plane it was given
    but snapped with `self.earth_model` — an FAI-sphere boundary point placed
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

    def test_the_point_lands_on_the_planes_model_not_the_turnpoints(self):
        """The case the two used to disagree on."""
        turnpoint = TaskTurnpoint(
            lat=46.5, lon=8.0, radius=5000, earth_model="FAI_SPHERE"
        )
        plane = LocalPlane.around([turnpoint.center], "WGS84")

        point = turnpoint.optimal_point((46.0, 7.5), (47.0, 8.6), plane=plane)

        assert geodesic_distance(turnpoint.center, point, "WGS84") == pytest.approx(
            5000.0, abs=1e-6
        )

    @pytest.mark.parametrize("model", [None, "WGS84", "FAI_SPHERE"])
    def test_an_agreeing_plane_is_unchanged(self, model):
        """The ordinary case — plane and turnpoint on one model — still snaps there."""
        turnpoint = TaskTurnpoint(lat=46.5, lon=8.0, radius=5000, earth_model=model)
        plane = LocalPlane.around([turnpoint.center], model)

        point = turnpoint.optimal_point((46.0, 7.5), (47.0, 8.6), plane=plane)

        assert geodesic_distance(turnpoint.center, point, model) == pytest.approx(
            5000.0, abs=1e-6
        )
