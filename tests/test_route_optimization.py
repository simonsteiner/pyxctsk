"""Unit tests for the Ding–Xie–Jiang alternating route optimizer.

These tests exercise the planar GetOptPi primitive (crossing vs. reflection
cases) and the alternating odd/even optimization core directly, plus the
TurnpointGeometry seam that lets the optimizer run against lightweight fakes.
"""

import math
from dataclasses import dataclass

import pytest

from pyxctsk.route_optimization import (
    _closest_circle_point,
    _optimize_plane_points,
    _polyline_length,
    calculate_iteratively_refined_route,
)
from pyxctsk.turnpoint import TaskTurnpoint, TurnpointGeometry, plane_optimal_point


@dataclass
class FakeTurnpoint:
    """A minimal TurnpointGeometry stand-in for seam tests."""

    center: tuple[float, float]
    radius: float = 0.0
    goal_type: str | None = None


def test_fake_turnpoint_satisfies_protocol():
    """FakeTurnpoint and TaskTurnpoint should satisfy the TurnpointGeometry seam."""
    assert isinstance(FakeTurnpoint((0.0, 0.0)), TurnpointGeometry)
    assert isinstance(TaskTurnpoint(0.0, 0.0), TurnpointGeometry)


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


class TestClosestCirclePoint:
    """Nearest-boundary rule used for the final turnpoint."""

    def test_outside(self):
        """From outside, the nearest boundary point lies on the inbound radial."""
        assert _closest_circle_point((10.0, 0.0), (0.0, 0.0, 3.0)) == (
            pytest.approx(3.0),
            pytest.approx(0.0),
        )

    def test_inside(self):
        """From inside, the point moves radially out to the boundary."""
        p = _closest_circle_point((1.0, 0.0), (0.0, 0.0, 3.0))
        assert p == (pytest.approx(3.0), pytest.approx(0.0))

    def test_zero_radius(self):
        """A zero-radius circle collapses to its center."""
        assert _closest_circle_point((10.0, 0.0), (5.0, 5.0, 0.0)) == (5.0, 5.0)


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
    distance, route = calculate_iteratively_refined_route(turnpoints)
    assert distance > 0
    assert len(route) == 3
    assert route[0] == (47.0, 8.0)
    assert route[-1] == (47.0, 8.2)


def test_short_input_handling():
    """Fewer than two turnpoints yields a zero distance and pass-through path."""
    assert calculate_iteratively_refined_route([]) == (0.0, [])
    distance, route = calculate_iteratively_refined_route([FakeTurnpoint((1.0, 2.0))])
    assert distance == 0.0
    assert route == [(1.0, 2.0)]
