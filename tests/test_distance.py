"""Comprehensive tests for distance calculation module."""

import pytest
import os

from xctrack import parse_task
from xctrack.distance import (
    TaskTurnpoint,
    optimized_distance,
    distance_through_centers,
    calculate_task_distances,
    calculate_cumulative_distances,
)


class TestTaskDistanceCalculations:
    """Test distance calculations against known results."""
    
    @pytest.fixture
    def test_data_dir(self):
        """Return the path to test data directory."""
        return os.path.join(os.path.dirname(__file__))
    
    @pytest.fixture
    def expected_results(self):
        """Expected results from task_distance_results.txt."""
        return {
            "task_fuvu.xctsk": {
                "center_distance_km": 149.8,
                "optimized_distance_km": 90.9,
                "turnpoints": [
                    {"name": "S06161", "radius": 1000, "cumulative_center_km": 0.0, "cumulative_optimized_km": 0.0, "type": "TAKEOFF"},
                    {"name": "B43585", "radius": 28000, "cumulative_center_km": 31.4, "cumulative_optimized_km": 3.3, "type": "SSS"},
                    {"name": "B43585", "radius": 12000, "cumulative_center_km": 31.4, "cumulative_optimized_km": 19.4, "type": ""},
                    {"name": "B03136", "radius": 6000, "cumulative_center_km": 90.5, "cumulative_optimized_km": 60.5, "type": ""},
                    {"name": "B22192", "radius": 1000, "cumulative_center_km": 121.4, "cumulative_optimized_km": 84.3, "type": ""},
                    {"name": "B54119", "radius": 11000, "cumulative_center_km": 137.5, "cumulative_optimized_km": 89.4, "type": "ESS"},
                    {"name": "L02087", "radius": 100, "cumulative_center_km": 149.8, "cumulative_optimized_km": 90.9, "type": "GOAL"},
                ]
            },
            "task_jedu.xctsk": {
                "center_distance_km": 149.5,
                "optimized_distance_km": 90.6,
                "turnpoints": [
                    {"name": "B21156", "radius": 400, "cumulative_center_km": 0.0, "cumulative_optimized_km": 0.0, "type": "TAKEOFF"},
                    {"name": "B43585", "radius": 28000, "cumulative_center_km": 31.2, "cumulative_optimized_km": 3.1, "type": "SSS"},
                    {"name": "B43585", "radius": 12000, "cumulative_center_km": 31.2, "cumulative_optimized_km": 19.1, "type": ""},
                    {"name": "B03136", "radius": 6000, "cumulative_center_km": 90.3, "cumulative_optimized_km": 60.2, "type": ""},
                    {"name": "B22192", "radius": 1000, "cumulative_center_km": 121.1, "cumulative_optimized_km": 84.1, "type": ""},
                    {"name": "B54119", "radius": 11000, "cumulative_center_km": 137.2, "cumulative_optimized_km": 89.2, "type": "ESS"},
                    {"name": "L02087", "radius": 100, "cumulative_center_km": 149.5, "cumulative_optimized_km": 90.6, "type": "GOAL"},
                ]
            },
            "task_meta.xctsk": {
                "center_distance_km": 132.2,
                "optimized_distance_km": 69.5,
                "turnpoints": [
                    {"name": "S06161", "radius": 1000, "cumulative_center_km": 0.0, "cumulative_optimized_km": 0.0, "type": "TAKEOFF"},
                    {"name": "B43585", "radius": 28000, "cumulative_center_km": 31.4, "cumulative_optimized_km": 3.4, "type": "SSS"},
                    {"name": "B43585", "radius": 15000, "cumulative_center_km": 31.4, "cumulative_optimized_km": 16.5, "type": ""},
                    {"name": "B25172", "radius": 1000, "cumulative_center_km": 61.5, "cumulative_optimized_km": 31.3, "type": ""},
                    {"name": "B05188", "radius": 600, "cumulative_center_km": 81.7, "cumulative_optimized_km": 50.4, "type": ""},
                    {"name": "B21156", "radius": 400, "cumulative_center_km": 98.1, "cumulative_optimized_km": 65.9, "type": ""},
                    {"name": "B17141", "radius": 15000, "cumulative_center_km": 116.6, "cumulative_optimized_km": 69.0, "type": "ESS"},
                    {"name": "L02087", "radius": 100, "cumulative_center_km": 132.2, "cumulative_optimized_km": 69.5, "type": "GOAL"},
                ]
            }
        }

    def accuracy_status(self, diff: float) -> str:
        """Return accuracy status based on difference."""
        if diff <= 0.2:
            return '✅'
        elif diff <= 1.0:
            return '⚠️'
        else:
            return '❌'

    @pytest.mark.parametrize("task_file", ["task_fuvu.xctsk", "task_jedu.xctsk", "task_meta.xctsk"])
    def test_task_distance_calculations(self, task_file, test_data_dir, expected_results):
        """Test distance calculations for each task file."""
        file_path = os.path.join(test_data_dir, task_file)
        expected = expected_results[task_file]
        
        print(f"\n🧮 Processing {task_file}...")
        
        # Parse the task file
        print("  📖 Parsing task file...")
        task = parse_task(file_path)
        print(f"  ✅ Found {len(task.turnpoints)} turnpoints")
        
        # Calculate distances using the main function
        print("  🎯 Calculating distances (this may take a moment)...")
        results = calculate_task_distances(task, angle_step=5, show_progress=True)  # Use 5° for accuracy with progress
        print("  ✅ Distance calculations complete")
        
        # Test total distances
        center_diff = abs(results['center_distance_km'] - expected['center_distance_km'])
        opt_diff = abs(results['optimized_distance_km'] - expected['optimized_distance_km'])
        
        print(f"\n{task_file}:")
        print(f"Center distance: Expected {expected['center_distance_km']:.1f}km, Got {results['center_distance_km']:.1f}km, Diff {center_diff:.1f}km {self.accuracy_status(center_diff)}")
        print(f"Optimized distance: Expected {expected['optimized_distance_km']:.1f}km, Got {results['optimized_distance_km']:.1f}km, Diff {opt_diff:.1f}km {self.accuracy_status(opt_diff)}")
        
        # Assert total distances are within tolerance
        assert center_diff <= 1.0, f"Center distance diff {center_diff:.1f}km > 1.0km for {task_file}"
        assert opt_diff <= 1.0, f"Optimized distance diff {opt_diff:.1f}km > 1.0km for {task_file}"
        
        # Test turnpoint details
        assert len(results['turnpoints']) == len(expected['turnpoints']), f"Turnpoint count mismatch for {task_file}"
        
        for i, (calculated_tp, expected_tp) in enumerate(zip(results['turnpoints'], expected['turnpoints'])):
            # Test basic properties
            assert calculated_tp['name'] == expected_tp['name'], f"Name mismatch at TP {i+1} for {task_file}"
            assert calculated_tp['radius'] == expected_tp['radius'], f"Radius mismatch at TP {i+1} for {task_file}"
            
            # Test cumulative distances with tolerance
            center_tp_diff = abs(calculated_tp['cumulative_center_km'] - expected_tp['cumulative_center_km'])
            opt_tp_diff = abs(calculated_tp['cumulative_optimized_km'] - expected_tp['cumulative_optimized_km'])
            
            assert center_tp_diff <= 1.0, f"TP {i+1} center distance diff {center_tp_diff:.1f}km > 1.0km for {task_file}"
            assert opt_tp_diff <= 2.0, f"TP {i+1} optimized distance diff {opt_tp_diff:.1f}km > 2.0km for {task_file}"

    def test_optimization_effectiveness(self, test_data_dir, expected_results):
        """Test that optimization actually reduces distance."""
        for task_file, expected in expected_results.items():
            file_path = os.path.join(test_data_dir, task_file)
            task = parse_task(file_path)
            results = calculate_task_distances(task, angle_step=5)
            
            # Optimization should always reduce distance
            assert results['optimized_distance_km'] < results['center_distance_km'], f"Optimization failed to reduce distance for {task_file}"
            
            # Check savings percentage
            savings_percent = (results['center_distance_km'] - results['optimized_distance_km']) / results['center_distance_km'] * 100
            assert savings_percent > 0, f"No savings achieved for {task_file}"
            
            print(f"{task_file}: {savings_percent:.1f}% distance savings")

    def test_edge_cases(self):
        """Test edge cases for distance calculations."""
        # Test empty turnpoint list
        assert optimized_distance([]) == 0.0
        assert distance_through_centers([]) == 0.0
        
        # Test single turnpoint
        single_tp = [TaskTurnpoint(47.0, 8.0, 400)]
        assert optimized_distance(single_tp) == 0.0
        assert distance_through_centers(single_tp) == 0.0
        
        # Test two identical turnpoints
        identical_tps = [
            TaskTurnpoint(47.0, 8.0, 400),
            TaskTurnpoint(47.0, 8.0, 400)
        ]
        center_dist = distance_through_centers(identical_tps)
        opt_dist = optimized_distance(identical_tps)
        
        assert center_dist == 0.0  # Same center points
        assert opt_dist <= center_dist  # Optimization shouldn't increase distance

    def test_zero_radius_turnpoints(self):
        """Test turnpoints with zero radius (exact points)."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 0),    # Zero radius
            TaskTurnpoint(47.1, 8.2, 0),    # Zero radius
            TaskTurnpoint(47.2, 8.4, 0),    # Zero radius
        ]
        
        center_dist = distance_through_centers(turnpoints)
        opt_dist = optimized_distance(turnpoints)
        
        # With zero radius, optimized should equal center distance
        assert abs(center_dist - opt_dist) < 1.0  # Should be very close

    def test_algorithm_consistency(self, test_data_dir):
        """Test that algorithm produces consistent results across multiple runs."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(file_path)
        
        # Run calculation multiple times
        results = []
        for _ in range(3):
            result = calculate_task_distances(task, angle_step=5)
            results.append((result['center_distance_km'], result['optimized_distance_km']))
        
        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert abs(result[0] - first_result[0]) < 0.01, "Center distance not consistent"
            assert abs(result[1] - first_result[1]) < 0.01, "Optimized distance not consistent"

    def test_angle_step_impact(self, test_data_dir):
        """Test impact of different angle steps on optimization accuracy."""
        file_path = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(file_path)
        
        # Test different angle steps
        angle_steps = [5, 10, 15, 30]
        results = {}
        
        for step in angle_steps:
            result = calculate_task_distances(task, angle_step=step)
            results[step] = result['optimized_distance_km']
        
        # Smaller angle steps should generally give better (shorter) optimization
        # But we test that they're all reasonable
        for step, distance in results.items():
            assert 80 <= distance <= 100, f"Distance {distance:.1f}km seems unreasonable for angle step {step}°"
        
        print("\nAngle step impact on task_fuvu.xctsk:")
        for step in angle_steps:
            print(f"  {step}°: {results[step]:.1f}km")


class TestTaskTurnpointClass:
    """Test the TaskTurnpoint class functionality."""
    
    def test_turnpoint_creation(self):
        """Test basic turnpoint creation."""
        tp = TaskTurnpoint(47.0, 8.0, 400)
        assert tp.center == (47.0, 8.0)
        assert tp.radius == 400
    
    def test_perimeter_points_zero_radius(self):
        """Test perimeter points for zero radius turnpoint."""
        tp = TaskTurnpoint(47.0, 8.0, 0)
        points = tp.perimeter_points()
        assert len(points) == 1
        assert points[0] == (47.0, 8.0)
    
    def test_perimeter_points_with_radius(self):
        """Test perimeter points generation for turnpoint with radius."""
        tp = TaskTurnpoint(47.0, 8.0, 1000)  # 1km radius
        points = tp.perimeter_points(angle_step=90)  # 90° steps
        
        assert len(points) == 4  # 0°, 90°, 180°, 270°
        
        # All points should be approximately 1km from center
        from geopy.distance import geodesic
        for point in points:
            distance = geodesic(tp.center, point).meters
            # Allow some tolerance due to WGS84 calculations
            assert abs(distance - 1000) < 50, f"Point {point} is {distance:.1f}m from center, expected ~1000m"
    
    def test_perimeter_points_angle_step(self):
        """Test different angle steps for perimeter points."""
        tp = TaskTurnpoint(47.0, 8.0, 1000)
        
        # Test various angle steps
        for angle_step in [5, 10, 15, 30, 45, 90]:
            points = tp.perimeter_points(angle_step)
            expected_count = 360 // angle_step
            assert len(points) == expected_count, f"Expected {expected_count} points for {angle_step}° step, got {len(points)}"


class TestDistanceFunctions:
    """Test individual distance calculation functions."""
    
    def test_distance_through_centers_simple(self):
        """Test simple distance through centers calculation."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 400),
            TaskTurnpoint(47.1, 8.0, 400),  # ~11km north
        ]
        
        distance = distance_through_centers(turnpoints)
        # Should be approximately 11km (0.1 degree latitude ≈ 11km)
        assert 10000 < distance < 12000, f"Expected ~11km, got {distance/1000:.1f}km"
    
    def test_optimized_distance_simple(self):
        """Test simple optimized distance calculation."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 1000),   # 1km radius
            TaskTurnpoint(47.1, 8.0, 1000),   # 1km radius, ~11km north
        ]
        
        center_dist = distance_through_centers(turnpoints)
        opt_dist = optimized_distance(turnpoints, angle_step=10)
        
        # Optimized should be shorter (can save ~2km with 1km radius on each end)
        assert opt_dist < center_dist, "Optimization should reduce distance"
        savings = center_dist - opt_dist
        assert 1000 < savings < 3000, f"Expected ~2km savings, got {savings:.0f}m"
    
    def test_cumulative_distances(self):
        """Test cumulative distance calculation."""
        turnpoints = [
            TaskTurnpoint(47.0, 8.0, 400),
            TaskTurnpoint(47.1, 8.0, 400),
            TaskTurnpoint(47.2, 8.0, 400),
        ]
        
        # Test cumulative to index 1 (second turnpoint)
        center, opt = calculate_cumulative_distances(turnpoints, 1)
        assert center > 0 and opt > 0, "Cumulative distances should be positive"
        assert opt <= center, "Optimized cumulative should not exceed center cumulative"
        
        # Test cumulative to index 2 (third turnpoint)
        center2, opt2 = calculate_cumulative_distances(turnpoints, 2)
        assert center2 > center, "Cumulative should increase with more turnpoints"
        assert opt2 > opt, "Optimized cumulative should increase with more turnpoints"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
