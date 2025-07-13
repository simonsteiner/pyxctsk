"""Tests for optimized distance calculations compared to reference data.

This file contains tests that compare the distance optimization algorithms
with reference data from JSON files.
"""

import json
import os
import statistics
import time

import pytest
from pyxctsk.distance import (
    calculate_iteratively_refined_route,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.parser import parse_task
from pyxctsk.task_distances import _task_to_turnpoints


@pytest.fixture(scope="session")
def tasks_dir():
    """Get the directory with task files."""
    # tests/data/reference_tasks/xctsk
    return os.path.join(os.path.dirname(__file__), "data", "reference_tasks", "xctsk")


@pytest.fixture(scope="session")
def json_dir():
    """Get the directory with JSON reference data."""
    # tests/data/reference_tasks/json
    return os.path.join(os.path.dirname(__file__), "data", "reference_tasks", "json")


@pytest.fixture(scope="session")
def task_files(tasks_dir):
    """Load all task files."""
    tasks = {}

    if not os.path.exists(tasks_dir):
        pytest.skip(f"Tasks directory not found: {tasks_dir}")

    for task_file in os.listdir(tasks_dir):
        if task_file.endswith(".xctsk"):
            file_path = os.path.join(tasks_dir, task_file)
            try:
                task = parse_task(file_path)
                tasks[task_file] = task
            except Exception as e:
                print(f"Failed to load {task_file}: {e}")

    if not tasks:
        pytest.skip("No tasks found to analyze")

    return tasks


@pytest.fixture(scope="session")
def json_metadata(json_dir):
    """Load JSON metadata files containing pre-calculated distances."""
    metadata = {}

    if not os.path.exists(json_dir):
        return metadata

    for json_file in os.listdir(json_dir):
        if json_file.startswith("task_") and json_file.endswith(".json"):
            file_path = os.path.join(json_dir, json_file)
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)

                # Extract task name from filename (remove task_ prefix and .json suffix)
                task_name = os.path.splitext(json_file)[0].replace("task_", "")

                # Extract relevant metadata
                if "metadata" in data:
                    meta = data["metadata"]
                    metadata[task_name] = {
                        "file_name": meta.get("file_name", task_name),
                        "distance_through_centers_km": meta.get(
                            "distance_through_centers_km", 0.0
                        ),
                        "distance_optimized_km": meta.get("distance_optimized_km", 0.0),
                        "task_distance_through_centers": meta.get(
                            "task_distance_through_centers", ""
                        ),
                        "task_distance_optimized": meta.get(
                            "task_distance_optimized", ""
                        ),
                    }
            except Exception as e:
                print(f"Failed to load {json_file}: {e}")

    return metadata


def _calculate_optimized_distance(task_name, task, verbose=False):
    """Helper function to calculate optimized distance.

    This is NOT a test function, but a helper used by the tests.
    """
    # Convert to TaskTurnpoint objects
    turnpoints = _task_to_turnpoints(task)

    if len(turnpoints) < 2:
        pytest.skip(f"Insufficient turnpoints ({len(turnpoints)})")

    # Calculate baseline center distance
    center_distance = distance_through_centers(turnpoints)

    start_time = time.time()

    try:
        # Always use optimized_distance with default parameters
        distance = optimized_distance(
            turnpoints,
            show_progress=verbose,
        )

        # Get route coordinates if needed for analysis
        _, route_points = calculate_iteratively_refined_route(
            turnpoints,
            show_progress=False,
        )
    except Exception as e:
        if verbose:
            print(f"Error in optimization: {e}")
        # Fall back to basic center-to-center calculation
        route_points = [tp.center for tp in turnpoints]
        distance = distance_through_centers(turnpoints)

    total_time = time.time() - start_time

    # Create result dictionary
    result = {
        "total_time": total_time,
        "total_distance": distance,
        "num_points": len(turnpoints),
        "route_points": route_points,
        "method": "optimized_distance",
    }

    return result, center_distance


def get_task_info(task_name, task, result, center_distance, json_metadata=None):
    """Get task information for reporting."""
    # Convert to TaskTurnpoint objects
    turnpoints = _task_to_turnpoints(task)

    # Add task metadata including JSON reference data if available
    task_info = {
        "name": task_name,
        "num_turnpoints": len(turnpoints),
        "center_distance_km": center_distance / 1000,
        "turnpoint_radii": [tp.radius for tp in turnpoints],
    }

    # Add JSON metadata if available
    if json_metadata:
        # Extract task name without .xctsk extension for JSON lookup
        lookup_name = task_name.replace(".xctsk", "")

        # If the lookup name starts with 'task_', remove that prefix too
        if lookup_name.startswith("task_"):
            lookup_name = lookup_name.replace("task_", "")

        if lookup_name in json_metadata:
            meta = json_metadata[lookup_name]
            task_info.update(
                {
                    "json_center_distance_km": meta.get(
                        "distance_through_centers_km", 0.0
                    ),
                    "json_optimized_distance_km": meta.get(
                        "distance_optimized_km", 0.0
                    ),
                    "json_task_distance_centers": meta.get(
                        "task_distance_through_centers", ""
                    ),
                    "json_task_distance_optimized": meta.get(
                        "task_distance_optimized", ""
                    ),
                }
            )

    return task_info


class TestDistanceCalculations:
    """Test suite for distance calculations compared to reference data."""

    @pytest.mark.parametrize(
        "task_name", ["task_mega.xctsk", "task_duna.xctsk", "task_wovi.xctsk"]
    )
    def test_specific_tasks(self, task_name, task_files, json_metadata):
        """Test specific tasks by name."""
        # Skip if task not found
        if task_name not in task_files:
            pytest.skip(f"Task {task_name} not found")

        task = task_files[task_name]

        print(f"\nTesting specific task: {task_name}")

        # Run pyxctsk optimization
        pyxctsk_result, center_distance = _calculate_optimized_distance(task_name, task)

        # Get task info
        task_info = get_task_info(
            task_name, task, pyxctsk_result, center_distance, json_metadata
        )

        # If we have JSON reference data, assert that we're close to it
        if "json_optimized_distance_km" in task_info:
            ref_distance_km = task_info["json_optimized_distance_km"]
            pyxctsk_distance_km = pyxctsk_result["total_distance"] / 1000

            # Check that our distance is within a reasonable threshold of the reference
            threshold = 0.01  # 1% threshold (actual differences are typically below 1%)
            percent_diff = abs(pyxctsk_distance_km - ref_distance_km) / ref_distance_km

            # Print detailed comparison
            print(f"  Reference distance: {ref_distance_km:.2f}km")
            print(f"  Pyxctsk distance:   {pyxctsk_distance_km:.2f}km")
            print(
                f"  Difference:         {abs(pyxctsk_distance_km - ref_distance_km):.2f}km ({percent_diff:.1%})"
            )
            print(f"  Threshold:          {threshold:.1%}")

            assert percent_diff < threshold, (
                f"Distance {pyxctsk_distance_km:.2f}km differs by {percent_diff:.1%} from "
                f"reference {ref_distance_km:.2f}km (threshold: {threshold:.1%})"
            )

    def test_all_tasks_with_reference(self, task_files, json_metadata):
        """Test all tasks that have reference data."""
        results = []
        print("\n\n---- Task Comparison Results ----")

        for task_name, task in task_files.items():
            # Skip tasks without turnpoints
            turnpoints = _task_to_turnpoints(task)
            if len(turnpoints) < 2:
                continue

            # Extract task name without .xctsk extension for JSON lookup
            lookup_name = task_name.replace(".xctsk", "")
            if lookup_name.startswith("task_"):
                lookup_name = lookup_name.replace("task_", "")

            # Skip if no reference data
            if lookup_name not in json_metadata:
                continue

            # Run pyxctsk optimization
            pyxctsk_result, center_distance = _calculate_optimized_distance(
                task_name, task
            )

            # Get task info
            task_info = get_task_info(
                task_name, task, pyxctsk_result, center_distance, json_metadata
            )

            # Only include tasks with reference data
            if "json_optimized_distance_km" in task_info:
                ref_distance_km = task_info["json_optimized_distance_km"]
                pyxctsk_distance_km = pyxctsk_result["total_distance"] / 1000

                # Store result for statistics
                diff_km = abs(pyxctsk_distance_km - ref_distance_km)
                # Avoid division by zero
                if ref_distance_km > 0:
                    diff_percent = (diff_km / ref_distance_km) * 100
                    percent_display = f"({diff_percent:.2f}%)"
                else:
                    diff_percent = 0
                    percent_display = "(N/A - ref distance is zero)"

                # Print comparison info for each task
                print(f"Task: {task_name}")
                print(f"  - Reference distance: {ref_distance_km:.2f} km")
                print(f"  - Pyxctsk distance:   {pyxctsk_distance_km:.2f} km")
                print(f"  - Difference:         {diff_km:.2f} km {percent_display}")
                print(f"  - Turnpoints:         {len(turnpoints)}")
                print()

                results.append(
                    {
                        "task_name": task_name,
                        "ref_distance_km": ref_distance_km,
                        "pyxctsk_distance_km": pyxctsk_distance_km,
                        "center_distance_km": center_distance / 1000,
                        "num_turnpoints": len(turnpoints),
                    }
                )

        # Skip if no results
        if not results:
            pytest.skip("No tasks with reference data found")

        # Filter out tasks with zero reference distance
        valid_results = [r for r in results if r["ref_distance_km"] > 0]

        # Calculate statistics only on valid results
        pyxctsk_diffs = [
            abs(r["pyxctsk_distance_km"] - r["ref_distance_km"]) for r in valid_results
        ]
        avg_pyxctsk_diff = statistics.mean(pyxctsk_diffs)

        # Assert that the average difference is within a reasonable threshold
        avg_ref_distance = statistics.mean(
            [r["ref_distance_km"] for r in valid_results]
        )
        threshold = 0.01  # Reduced from 0.25 (25%) to 0.01 (1%) as actual difference is only ~0.4%
        percent_diff = avg_pyxctsk_diff / avg_ref_distance

        # Print summary statistics
        print("---- Summary Statistics ----")
        print(f"Total tasks analyzed: {len(results)}")
        print(f"Tasks with valid reference distances: {len(valid_results)}")
        if len(results) != len(valid_results):
            print(
                f"Tasks with zero reference excluded: {len(results) - len(valid_results)}"
            )
        print(f"Average reference distance: {avg_ref_distance:.2f} km")
        print(f"Average absolute difference: {avg_pyxctsk_diff:.2f} km")
        print(f"Difference as percentage: {percent_diff:.1%}")
        print(f"Threshold: {threshold:.1%}")
        print("---------------------------\n")

        assert percent_diff < threshold, (
            f"Average distance difference {avg_pyxctsk_diff:.2f}km is {percent_diff:.1%} of "
            f"reference distance {avg_ref_distance:.2f}km (threshold: {threshold:.1%})"
        )
