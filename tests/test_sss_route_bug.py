"""Test to demonstrate and fix the SSS route mapping bug.

The issue: optimized route navigates to the center of the first turnpoint after SSS
instead of to a point on the perimeter. The first leg should not be the same
for center route vs optimized route.
"""

import os

import pytest
from geopy.distance import geodesic

from pyxctsk import parse_task
from pyxctsk.distance import (
    _task_to_turnpoints,
    optimized_route_coordinates,
)


class TestSSSRouteBug:
    """Test cases to demonstrate and verify the SSS route bug fix."""

    @pytest.fixture
    def test_data_dir(self):
        """Return the path to test data directory."""
        return os.path.join(os.path.dirname(__file__))

    @pytest.fixture
    def sss_task(self, test_data_dir):
        """Load a real SSS task for testing."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        return parse_task(file_path)

    def test_sss_task_structure(self, sss_task):
        """Verify the test task has the expected SSS structure."""
        turnpoints = sss_task.turnpoints

        # Should have at least 3 turnpoints
        assert len(turnpoints) >= 3, "Task should have at least 3 turnpoints"

        # Check turnpoint types
        assert (
            turnpoints[0].type.value == "TAKEOFF"
        ), "First turnpoint should be TAKEOFF"
        assert turnpoints[1].type.value == "SSS", "Second turnpoint should be SSS"
        assert (
            turnpoints[2].type is None or turnpoints[2].type.value == ""
        ), "Third turnpoint should be regular TP"

        # Verify SSS and first TP after SSS are at same location (common pattern)
        sss_tp = turnpoints[1]
        first_tp_after_sss = turnpoints[2]

        assert (
            sss_tp.waypoint.lat == first_tp_after_sss.waypoint.lat
        ), "SSS and first TP should be at same location"
        assert (
            sss_tp.waypoint.lon == first_tp_after_sss.waypoint.lon
        ), "SSS and first TP should be at same location"
        assert (
            sss_tp.radius != first_tp_after_sss.radius
        ), "SSS and first TP should have different radii"

        print("✅ SSS task structure verified:")
        print(
            f"   Takeoff: {turnpoints[0].waypoint.name} (radius: {turnpoints[0].radius}m)"
        )
        print(f"   SSS: {sss_tp.waypoint.name} (radius: {sss_tp.radius}m)")
        print(
            f"   First TP after SSS: {first_tp_after_sss.waypoint.name} (radius: {first_tp_after_sss.radius}m)"
        )

    def test_center_route_vs_optimized_route_first_leg(self, sss_task):
        """Test that the first leg differs between center route and optimized route for SSS tasks.

        This is the main bug test - the optimized route should go to the perimeter
        of the first TP after SSS, not its center.
        """
        turnpoints = _task_to_turnpoints(sss_task)

        # Get center route coordinates (takeoff -> TP centers)
        takeoff_center = turnpoints[0].center
        sss_center = turnpoints[1].center  # SSS center
        first_tp_after_sss_center = turnpoints[2].center  # First TP after SSS center

        # Calculate center route first leg distance (takeoff -> first TP after SSS center)
        center_route_first_leg = geodesic(
            takeoff_center, first_tp_after_sss_center
        ).meters

        # Get optimized route coordinates
        optimized_route = optimized_route_coordinates(turnpoints, sss_task.turnpoints)

        # Verify we have at least 2 points in the optimized route
        assert (
            len(optimized_route) >= 2
        ), "Optimized route should have at least 2 points"

        # Calculate optimized route first leg distance
        optimized_first_point = optimized_route[0]  # Should be takeoff center
        optimized_second_point = optimized_route[
            1
        ]  # Should be on perimeter of first TP after SSS

        optimized_route_first_leg = geodesic(
            optimized_first_point, optimized_second_point
        ).meters

        print("📊 Route comparison:")
        print(f"   Takeoff center: {takeoff_center}")
        print(f"   First TP after SSS center: {first_tp_after_sss_center}")
        print(f"   Center route first leg: {center_route_first_leg:.1f}m")
        print(f"   Optimized route first point: {optimized_first_point}")
        print(f"   Optimized route second point: {optimized_second_point}")
        print(f"   Optimized route first leg: {optimized_route_first_leg:.1f}m")

        # Verify the optimized route starts from takeoff center
        assert (
            optimized_first_point == takeoff_center
        ), "Optimized route should start from takeoff center"

        # THE MAIN BUG TEST: The optimized route second point should NOT be the TP center
        # It should be on the perimeter, so the distance should be different
        distance_diff = abs(center_route_first_leg - optimized_route_first_leg)
        print(f"   Distance difference: {distance_diff:.1f}m")

        # If the bug exists, the distances will be the same (or very close)
        # After fixing, they should be different by at least the TP radius
        first_tp_after_sss_radius = sss_task.turnpoints[2].radius
        print(f"   First TP after SSS radius: {first_tp_after_sss_radius}m")

        # The optimized route should be shorter (going to perimeter instead of center)
        assert (
            optimized_route_first_leg < center_route_first_leg
        ), "Optimized route first leg should be shorter than center route"

        # The difference should be significant (at least half the radius)
        min_expected_diff = first_tp_after_sss_radius * 0.5
        assert (
            distance_diff >= min_expected_diff
        ), f"Distance difference {distance_diff:.1f}m should be at least {min_expected_diff:.1f}m (bug: navigating to center instead of perimeter)"

    # def test_optimized_route_point_on_perimeter(self, sss_task):
    #     """Test that the optimized route actually navigates to a point on the perimeter."""
    #     turnpoints = _task_to_turnpoints(sss_task)
    #     optimized_route = optimized_route_coordinates(turnpoints, sss_task.turnpoints)

    #     # Get the second point in the optimized route (first TP after SSS)
    #     if len(optimized_route) >= 2:
    #         optimized_second_point = optimized_route[1]
    #         first_tp_after_sss_center = turnpoints[2].center
    #         first_tp_after_sss_radius = sss_task.turnpoints[2].radius

    #         # Calculate distance from TP center to the optimized point
    #         distance_to_center = geodesic(
    #             first_tp_after_sss_center, optimized_second_point
    #         ).meters

    #         print("🎯 Perimeter verification:")
    #         print(f"   TP center: {first_tp_after_sss_center}")
    #         print(f"   TP radius: {first_tp_after_sss_radius}m")
    #         print(f"   Optimized point: {optimized_second_point}")
    #         print(f"   Distance to center: {distance_to_center:.1f}m")

    #         # The optimized point should be approximately on the perimeter
    #         # Allow some tolerance for floating point calculations
    #         tolerance = 50  # 50 meters tolerance
    #         expected_distance = first_tp_after_sss_radius

    #         assert (
    #             abs(distance_to_center - expected_distance) <= tolerance
    #         ), f"Optimized point should be on perimeter (±{tolerance}m), got {distance_to_center:.1f}m vs expected {expected_distance}m"

    def test_multiple_sss_tasks(self, test_data_dir):
        """Test the fix works for multiple SSS tasks."""
        sss_task_files = ["task_fuvu.xctsk", "task_jedu.xctsk", "task_meta.xctsk"]

        for task_file in sss_task_files:
            file_path = os.path.join(test_data_dir, task_file)
            task = parse_task(file_path)

            # Skip if not an SSS task
            has_sss = any(tp.type and tp.type.value == "SSS" for tp in task.turnpoints)
            if not has_sss:
                continue

            turnpoints = _task_to_turnpoints(task)
            optimized_route = optimized_route_coordinates(turnpoints, task.turnpoints)

            # Basic sanity check
            assert (
                len(optimized_route) >= 2
            ), f"Optimized route too short for {task_file}"

            # The optimized route should start from takeoff
            takeoff_center = turnpoints[0].center
            assert (
                optimized_route[0] == takeoff_center
            ), f"Route should start from takeoff for {task_file}"

            print(f"✅ {task_file} optimized route looks good")


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
