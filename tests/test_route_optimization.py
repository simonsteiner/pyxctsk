"""Unit tests for the route-optimization dynamic program via its seam.

These tests exercise the DP core (_compute_optimal_route_with_beam_search and
backtracking) through the TurnpointGeometry protocol using a lightweight fake
turnpoint. Because the algorithm depends only on `center` and
`optimal_point()`, it can be tested without geodesic math, scipy, or real
coordinates — the point of the geometry seam.
"""

from dataclasses import dataclass

from pyxctsk.route_optimization import (
    _backtrack_path,
    _compute_optimal_route_with_beam_search,
    _init_dp_structure,
)
from pyxctsk.turnpoint import TaskTurnpoint, TurnpointGeometry


@dataclass
class FakeTurnpoint:
    """A TurnpointGeometry adapter that always returns a fixed point.

    This stands in for the real (geodesic) TaskTurnpoint so the DP can be
    tested in isolation. ``optimal_point`` ignores its arguments and returns
    ``center``, making leg distances exactly the straight-line distance
    between consecutive centers.
    """

    center: tuple[float, float]

    def optimal_point(
        self, prev_point: tuple[float, float], next_point: tuple[float, float]
    ) -> tuple[float, float]:
        """Return the fixed optimal point for this fake turnpoint.

        Args:
            prev_point: Previous point in the route (ignored).
            next_point: Next point in the route (ignored).

        Returns:
            The turnpoint center.
        """
        return self.center


def test_fake_turnpoint_satisfies_protocol():
    """FakeTurnpoint and TaskTurnpoint should satisfy the TurnpointGeometry seam."""
    assert isinstance(FakeTurnpoint((0.0, 0.0)), TurnpointGeometry)
    # The real adapter satisfies the same seam.
    assert isinstance(TaskTurnpoint(0.0, 0.0), TurnpointGeometry)


def test_beam_search_runs_against_fake_geometry():
    """Beam search should run end-to-end against a lightweight geometry adapter."""
    # Three points; with optimal_point == center every route is forced through
    # the centers, so the distance is the sum of the two legs.
    turnpoints = [
        FakeTurnpoint((0.0, 0.0)),
        FakeTurnpoint((0.0, 1.0)),
        FakeTurnpoint((0.0, 2.0)),
    ]

    distance, route = _compute_optimal_route_with_beam_search(
        turnpoints, return_path=True
    )

    assert distance > 0
    assert route[0] == (0.0, 0.0)
    assert route[-1] == (0.0, 2.0)
    assert len(route) == len(turnpoints)


def test_backtrack_reconstructs_full_path():
    """Backtracking should reconstruct the full path from the DP parent pointers."""
    turnpoints = [
        FakeTurnpoint((0.0, 0.0)),
        FakeTurnpoint((0.0, 1.0)),
    ]
    # Build a DP table by hand and confirm backtracking walks it end to end.
    dp = _init_dp_structure(turnpoints)
    dp[1][(0.0, 1.0)] = (111.0, (0.0, 0.0))

    path = _backtrack_path(dp, (0.0, 1.0), turnpoints)

    assert path == [(0.0, 0.0), (0.0, 1.0)]


def test_beam_search_handles_short_input():
    """A single turnpoint should yield zero distance and a 1-point path."""
    distance, route = _compute_optimal_route_with_beam_search(
        [FakeTurnpoint((1.0, 2.0))], return_path=True
    )
    assert distance == 0.0
    assert route == [(1.0, 2.0)]
