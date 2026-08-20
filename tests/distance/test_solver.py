"""Tests for the pure planar route solver's public seam."""

import math

import pytest

from pyxctsk.distance.solver import optimize_plane_route, plane_optimal_point


def _route_length(points: list[tuple[float, float]]) -> float:
    """Measure an observable planar route without reaching into the solver."""
    return sum(math.dist(start, end) for start, end in zip(points, points[1:]))


class TestPlaneOptimalPoint:
    """The planar GetOptPi primitive (Ding et al. Algorithm 1)."""

    def test_zero_radius_returns_center(self):
        """A zero-radius circle collapses to its center."""
        assert plane_optimal_point((0, 0), (10, 0), (5.0, 5.0), 0.0) == (5.0, 5.0)

    def test_crossing_both_outside(self):
        """When the segment crosses the circle, the point adds no length."""
        point = plane_optimal_point((-10.0, 0.0), (10.0, 0.0), (0.0, 0.0), 2.0)
        assert point[0] == pytest.approx(-2.0, abs=1e-9)
        assert point[1] == pytest.approx(0.0, abs=1e-9)

    def test_crossing_prev_inside(self):
        """A route leaving the circle exits at the segment intersection."""
        point = plane_optimal_point((1.0, 0.0), (10.0, 0.0), (0.0, 0.0), 5.0)
        assert point == (pytest.approx(5.0), pytest.approx(0.0, abs=1e-9))

    def test_crossing_next_inside(self):
        """A route entering the circle uses its first segment intersection."""
        point = plane_optimal_point((10.0, 0.0), (1.0, 0.0), (0.0, 0.0), 5.0)
        assert point == (pytest.approx(5.0), pytest.approx(0.0, abs=1e-9))

    def test_reflection_both_outside(self):
        """A symmetric no-crossing setup yields the bisector point."""
        point = plane_optimal_point((-10.0, 10.0), (10.0, 10.0), (0.0, 0.0), 2.0)
        assert point[0] == pytest.approx(0.0, abs=1e-6)
        assert point[1] == pytest.approx(2.0, abs=1e-6)

    def test_reflection_both_inside(self):
        """Two inside neighbours still produce a boundary point."""
        point = plane_optimal_point((0.5, 0.0), (0.25, 0.0), (0.0, 0.0), 5.0)
        assert math.hypot(*point) == pytest.approx(5.0, abs=1e-9)
        assert point[0] == pytest.approx(5.0, abs=1e-6)

    def test_optimum_is_boundary_minimum(self):
        """The returned point beats every sampled boundary point."""
        previous = (-7.0, 3.0)
        following = (9.0, 6.0)
        center = (1.0, -2.0)
        radius = 4.0

        def total(point: tuple[float, float]) -> float:
            return math.dist(point, previous) + math.dist(point, following)

        best = plane_optimal_point(previous, following, center, radius)
        for step in range(720):
            theta = math.pi * step / 360.0
            sample = (
                center[0] + radius * math.cos(theta),
                center[1] + radius * math.sin(theta),
            )
            assert total(best) <= total(sample) + 1e-6


class TestOptimizePlaneRoute:
    """Route-level behavior independent of placements and sweep internals."""

    def test_collinear_circles_converge_to_straight_line(self):
        """Crossed circles add no distance to a straight route."""
        circles = [
            (0.0, 0.0, 0.0),
            (10_000.0, 0.0, 1_000.0),
            (20_000.0, 0.0, 2_000.0),
            (30_000.0, 0.0, 0.0),
        ]

        points = optimize_plane_route(circles, max_sweeps=100)

        assert _route_length(points) == pytest.approx(30_000.0, abs=0.1)
        for point, circle in zip(points[1:-1], circles[1:-1]):
            assert point[1] == pytest.approx(0.0, abs=1e-6)
            assert abs(point[0] - circle[0]) == pytest.approx(circle[2], abs=1e-6)

    def test_convergence_stops_below_epsilon(self):
        """Extra sweeps do not move a converged route beyond epsilon."""
        circles = [
            (0.0, 0.0, 0.0),
            (10_000.0, 5_000.0, 3_000.0),
            (20_000.0, -4_000.0, 2_000.0),
            (35_000.0, 2_000.0, 4_000.0),
            (45_000.0, 0.0, 400.0),
        ]
        short = _route_length(optimize_plane_route(circles, max_sweeps=50))
        long = _route_length(optimize_plane_route(circles, max_sweeps=500))

        assert abs(short - long) <= 0.1

    def test_start_point_stays_at_takeoff_center(self):
        """The first circle is a start center, not a boundary touch."""
        circles = [(0.0, 0.0, 5_000.0), (20_000.0, 0.0, 1_000.0)]

        assert optimize_plane_route(circles, max_sweeps=10)[0] == (0.0, 0.0)

    def test_consecutive_duplicates_share_a_route_point(self):
        """Duplicate touches remain represented without creating a false leg."""
        circles = [
            (0.0, 0.0, 0.0),
            (10_000.0, 2_000.0, 1_000.0),
            (20_000.0, 0.0, 2_000.0),
            (20_000.0, 0.0, 2_000.0),
            (30_000.0, 0.0, 0.0),
        ]

        points = optimize_plane_route(circles, max_sweeps=100)

        assert len(points) == len(circles)
        assert points[2] == points[3]

    def test_multi_start_route_regression(self):
        """The deep solver preserves the shipped route-level result."""
        circles = [
            (0.0, 0.0, 0.0),
            (20_000.0, 18_000.0, 17_000.0),
            (40_000.0, -18_000.0, 17_000.0),
            (60_000.0, 0.0, 400.0),
        ]

        points = optimize_plane_route(circles, max_sweeps=100)

        assert _route_length(points) == pytest.approx(59_748.3014456, abs=0.1)
        assert optimize_plane_route(circles, max_sweeps=100) == points
