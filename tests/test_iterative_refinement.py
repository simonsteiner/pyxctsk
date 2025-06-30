"""Tests for iterative refinement in route optimization."""

import pytest
from geopy.distance import geodesic

from pyxctsk.distance import (
    TaskTurnpoint,
    _compute_optimal_route_dp,
    calculate_iteratively_refined_route,
    optimized_distance,
    optimized_route_coordinates,
)


def create_test_turnpoints(offset=0.0):
    """Create test turnpoints with different cylinder sizes."""
    # Create turnpoints for a simple task with large cylinders
    # to demonstrate the look-ahead bias issue
    return [
        TaskTurnpoint(lat=47.0, lon=8.0, radius=0),  # Takeoff (point)
        TaskTurnpoint(lat=47.1, lon=8.1, radius=1000),  # TP1 with 1km radius
        TaskTurnpoint(lat=47.2, lon=8.2 + offset, radius=2000),  # TP2 with 2km radius
        TaskTurnpoint(lat=47.3, lon=8.3, radius=1000),  # TP3 with 1km radius
        TaskTurnpoint(lat=47.4, lon=8.4, radius=0),  # Goal (point)
    ]


# def test_iterative_refinement_improves_distance():
#     """Test that iterative refinement improves the route optimization."""
#     # Create a challenging test case where look-ahead bias would be significant
#     # by offsetting one of the turnpoints from the direct line
#     turnpoints = create_test_turnpoints(offset=0.05)

#     # Calculate distance using the single-pass approach (one iteration)
#     single_pass_distance, single_pass_route = calculate_iteratively_refined_route(
#         turnpoints, num_iterations=1, show_progress=False, return_path=True
#     )

#     # Calculate distance using multiple iterations of refinement
#     refined_distance, refined_route = calculate_iteratively_refined_route(
#         turnpoints, num_iterations=3, show_progress=False
#     )

#     # The iterative refinement should produce a shorter route
#     assert refined_distance <= single_pass_distance

#     # Verify that both routes include the correct number of points
#     assert len(single_pass_route) == len(turnpoints)
#     assert len(refined_route) == len(turnpoints)

#     # Ensure the refined route's start and end points match the centers
#     # of the first and last turnpoints
#     assert refined_route[0] == turnpoints[0].center
#     assert refined_route[-1] == turnpoints[-1].center


def test_iterative_refinement_with_api_functions():
    """Test iterative refinement using the public API functions."""
    turnpoints = create_test_turnpoints(offset=0.05)

    # Calculate distances with different numbers of iterations
    single_pass_distance = optimized_distance(
        turnpoints, num_iterations=1, show_progress=False
    )

    refined_distance = optimized_distance(
        turnpoints, num_iterations=3, show_progress=False
    )

    # Get route coordinates for visualization/verification
    single_pass_route = optimized_route_coordinates(turnpoints, num_iterations=1)

    refined_route = optimized_route_coordinates(turnpoints, num_iterations=3)

    # The iterative refinement should produce a shorter route
    assert refined_distance <= single_pass_distance

    # Both routes should include all turnpoints
    assert len(single_pass_route) == len(turnpoints)
    assert len(refined_route) == len(turnpoints)


def test_convergence_of_iterations():
    """Test that iterative refinement converges reasonably quickly."""
    turnpoints = create_test_turnpoints(offset=0.05)

    # Calculate distance with varying number of iterations
    distances = []

    for num_iter in range(1, 6):
        distance, _ = calculate_iteratively_refined_route(
            turnpoints, num_iterations=num_iter, show_progress=False
        )
        distances.append(distance)

    # Distances should improve or remain the same (never get worse)
    for i in range(1, len(distances)):
        assert distances[i] <= distances[i - 1]

    # After a few iterations, the improvement should be minimal
    # (indicating convergence)
    if len(distances) >= 3:
        relative_improvement = (distances[1] - distances[-1]) / distances[1]
        # The relative improvement after first iteration should be small
        # typically less than 1%
        assert relative_improvement < 0.01
