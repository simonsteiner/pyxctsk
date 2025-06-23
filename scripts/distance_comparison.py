#!/usr/bin/env python3
"""
Comparison script for XCTrack distance calculations.

This script compares the scipy-based optimization method with reference data from JSON files.
Now that the code has been simplified to use only the scipy optimization method,
this tool validates that the results match expected reference values.
"""

import os
import sys
import time
import statistics
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import argparse

# Add the xctrack module to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from xctrack.parser import parse_task
from xctrack.distance import (
    TaskTurnpoint,
    _task_to_turnpoints,
    _find_optimal_cylinder_point,
    optimized_distance,
    distance_through_centers,
)
from geopy.distance import geodesic


def load_all_tasks(tasks_dir: str) -> Dict[str, Any]:
    """Load all .xctsk files from the given directory.

    Args:
        tasks_dir: Directory containing .xctsk files

    Returns:
        Dictionary mapping filename to parsed task objects
    """
    tasks = {}
    tasks_path = Path(tasks_dir)

    if not tasks_path.exists():
        print(f"❌ Tasks directory not found: {tasks_dir}")
        return tasks

    for task_file in tasks_path.glob("*.xctsk"):
        try:
            task = parse_task(str(task_file))
            tasks[task_file.name] = task
            print(f"✅ Loaded task: {task_file.name}")
        except Exception as e:
            print(f"❌ Failed to load {task_file.name}: {e}")

    print(f"\n📊 Successfully loaded {len(tasks)} tasks")
    return tasks


def load_json_metadata(json_dir: str) -> Dict[str, Dict[str, Any]]:
    """Load JSON metadata files containing pre-calculated distances.

    Args:
        json_dir: Directory containing .json files

    Returns:
        Dictionary mapping task name to metadata
    """
    metadata = {}
    json_path = Path(json_dir)

    if not json_path.exists():
        print(f"⚠️  JSON metadata directory not found: {json_dir}")
        return metadata

    for json_file in json_path.glob("task_*.json"):
        try:
            with open(json_file, "r") as f:
                data = json.load(f)

            # Extract task name from filename (remove task_ prefix and .json suffix)
            task_name = json_file.stem.replace("task_", "")

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
                    "task_distance_optimized": meta.get("task_distance_optimized", ""),
                }
                print(f"✅ Loaded metadata: {json_file.name}")
        except Exception as e:
            print(f"❌ Failed to load {json_file.name}: {e}")

    print(f"📊 Successfully loaded {len(metadata)} metadata files")
    return metadata


def test_optimization(
    turnpoints: List[TaskTurnpoint], verbose: bool = False
) -> Dict[str, Any]:
    """Test optimization on a list of turnpoints.

    Args:
        turnpoints: List of TaskTurnpoint objects
        verbose: Whether to print detailed progress

    Returns:
        Dictionary with timing and distance results
    """
    if len(turnpoints) < 2:
        return {
            "total_time": 0.0,
            "avg_time_per_point": 0.0,
            "total_distance": 0.0,
            "num_points": 0,
        }

    start_time = time.time()
    point_times = []
    optimal_points = []

    # Test optimization on each pair of consecutive turnpoints
    for i in range(1, len(turnpoints) - 1):
        prev_point = turnpoints[i - 1].center
        next_point = turnpoints[i + 1].center
        current_tp = turnpoints[i]

        if current_tp.radius > 0:  # Only optimize cylinders, not centers
            point_start = time.time()

            try:
                optimal_point = current_tp.optimal_point(prev_point, next_point)
                optimal_points.append(optimal_point)
            except Exception as e:
                if verbose:
                    print(f"    ⚠️  Error at turnpoint {i}: {e}")
                optimal_points.append(current_tp.center)

            point_time = time.time() - point_start
            point_times.append(point_time)
        else:
            optimal_points.append(current_tp.center)

    total_time = time.time() - start_time

    # Calculate total distance through optimal points
    route_points = [turnpoints[0].center] + optimal_points + [turnpoints[-1].center]
    total_distance = 0.0
    for i in range(len(route_points) - 1):
        total_distance += geodesic(route_points[i], route_points[i + 1]).meters

    return {
        "total_time": total_time,
        "avg_time_per_point": statistics.mean(point_times) if point_times else 0.0,
        "total_distance": total_distance,
        "num_points": len(point_times),
        "point_times": point_times,
    }


def compare_with_reference(
    task_name: str,
    task: Any,
    json_metadata: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Compare optimization results with reference data.

    Args:
        task_name: Name of the task file
        task: Parsed task object
        json_metadata: Optional JSON metadata for reference
        verbose: Whether to print detailed progress

    Returns:
        Dictionary with comparison results
    """
    if verbose:
        print(f"\n🔄 Analyzing task: {task_name}")

    # Convert to TaskTurnpoint objects
    turnpoints = _task_to_turnpoints(task)

    if len(turnpoints) < 2:
        if verbose:
            print(
                f"  ⚠️  Skipping {task_name}: insufficient turnpoints ({len(turnpoints)})"
            )
        return None

    # Calculate baseline center distance
    center_distance = distance_through_centers(turnpoints)

    if verbose:
        print(
            f"  📏 {len(turnpoints)} turnpoints, center distance: {center_distance/1000:.2f}km"
        )

    # Test optimization
    if verbose:
        print(f"  🧮 Running optimization...")

    result = test_optimization(turnpoints, verbose)

    if verbose:
        savings = (center_distance - result["total_distance"]) / 1000
        print(f"    ⏱️  Time: {result['total_time']:.4f}s")
        print(
            f"    📐 Distance: {result['total_distance']/1000:.2f}km (saves {savings:.2f}km)"
        )

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

        if verbose:
            print(f"  🔍 Looking for JSON data for: '{lookup_name}' (from {task_name})")
            print(f"  🔍 Available JSON keys: {list(json_metadata.keys())}")

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

            if verbose:
                print(
                    f"  📊 JSON reference - Center: {meta.get('distance_through_centers_km', 0):.1f}km, "
                    f"Optimized: {meta.get('distance_optimized_km', 0):.1f}km"
                )
        else:
            if verbose:
                print(f"  ⚠️  No JSON metadata found for '{lookup_name}'")

    return {"optimization": result, "task_info": task_info}


def analyze_results(all_results: List[Dict[str, Any]]) -> None:
    """Analyze and display comparison results with reference data.

    Args:
        all_results: List of task comparison results
    """
    print("\n" + "=" * 80)
    print("🏆 OPTIMIZATION COMPARISON WITH REFERENCE DATA")
    print("=" * 80)

    # Filter out None results
    valid_results = [r for r in all_results if r is not None]

    if not valid_results:
        print("❌ No valid results to analyze")
        return

    # Summary statistics
    print(f"\n📊 SUMMARY STATISTICS ({len(valid_results)} tasks analyzed)")
    print("-" * 80)

    times = [r["optimization"]["total_time"] for r in valid_results]
    distances = [r["optimization"]["total_distance"] for r in valid_results]

    print(f"  ⏱️  Average time per task: {statistics.mean(times):.4f}s")
    print(f"  ⏱️  Median time per task: {statistics.median(times):.4f}s")
    print(f"  ⏱️  Min/Max time: {min(times):.4f}s / {max(times):.4f}s")
    print(f"  📐 Average distance: {statistics.mean(distances)/1000:.2f}km")
    print(f"  📐 Distance std dev: {statistics.stdev(distances)/1000:.3f}km")

    # Add JSON comparison if available
    has_json_data = any(
        "json_optimized_distance_km" in result["task_info"] for result in valid_results
    )

    if has_json_data:
        print(f"\n📊 JSON REFERENCE DATA COMPARISON")
        print("-" * 80)
        print(f"Comparing against pre-calculated reference distances from JSON files:")

        # Calculate differences against JSON reference data
        json_diffs_optimization = []

        for result in valid_results:
            task_info = result["task_info"]
            if "json_optimized_distance_km" in task_info:
                json_opt_km = task_info["json_optimized_distance_km"]
                opt_km = result["optimization"]["total_distance"] / 1000
                json_diffs_optimization.append(abs(opt_km - json_opt_km))

        if json_diffs_optimization:
            print(f"Average difference vs JSON reference optimized distance:")
            print(f"  🔸 Difference: {statistics.mean(json_diffs_optimization):.2f}km")

    # Detailed task-by-task results
    print(f"\n📋 DETAILED TASK RESULTS")
    print("-" * 80)

    # Check if any tasks have JSON data
    tasks_with_json = [
        r for r in valid_results if "json_optimized_distance_km" in r["task_info"]
    ]
    print(
        f"{len(tasks_with_json)} tasks have JSON data out of {len(valid_results)} total"
    )

    if tasks_with_json:
        print(
            f"{'Task':<15} {'TPs':<4} {'Center':<8} {'JSON Ref':<10} {'Optimized':<8} {'Diff':<8} {'Time':<8}"
        )
        print(
            f"{'Name':<15} {'#':<4} {'(km)':<8} {'Opt (km)':<10} {'(km)':<9} {'(km)':<8} {'(s)':<8}"
        )
        print("-" * 80)
    else:
        print(f"{'Task':<15} {'TPs':<4} {'Center':<8} {'Optimized':<8} {'Time':<8}")
        print(f"{'Name':<15} {'#':<4} {'(km)':<8} {'(km)':<8} {'(s)':<8}")
        print("-" * 80)

    for result in valid_results:
        task_name = result["task_info"]["name"][:14]
        num_tps = result["task_info"]["num_turnpoints"]
        center_km = result["task_info"]["center_distance_km"]

        optimization_km = result["optimization"]["total_distance"] / 1000
        optimization_time = result["optimization"]["total_time"]

        if "json_optimized_distance_km" in result["task_info"]:
            json_opt_km = result["task_info"]["json_optimized_distance_km"]
            diff_km = optimization_km - json_opt_km
            sign = "+" if diff_km > 0 else "-" if diff_km < 0 else " "
            print(
                f"{task_name:<15} {num_tps:<4} {center_km:<8.2f} {json_opt_km:<10.2f} "
                f"{optimization_km:.2f} {sign}{abs(diff_km):<7.2f} "
                f"{optimization_time:.3f}s"
            )
        else:
            if (
                tasks_with_json
            ):  # If some tasks have JSON data, show N/A for those that don't
                print(
                    f"{task_name:<15} {num_tps:<4} {center_km:<8.2f} {'N/A':<10} "
                    f"{optimization_km:.2f} {'N/A':<8} "
                    f"{optimization_time:.3f}s"
                )
            else:
                print(
                    f"{task_name:<15} {num_tps:<4} {center_km:<8.2f} "
                    f"{optimization_km:.2f} {optimization_time:.3f}s"
                )


def main():
    """Main function to run the optimization comparison with reference data."""
    parser = argparse.ArgumentParser(
        description="Compare XCTrack optimization with reference data"
    )
    parser.add_argument(
        "--tasks-dir",
        default="downloaded_tasks/xctsk",
        help="Directory containing .xctsk files (default: downloaded_tasks/xctsk)",
    )
    parser.add_argument(
        "--json-dir",
        default="downloaded_tasks/json",
        help="Directory containing .json metadata files (default: downloaded_tasks/json)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed progress during analysis"
    )
    parser.add_argument(
        "--limit", type=int, help="Limit number of tasks to analyze (for testing)"
    )

    args = parser.parse_args()

    print("🚀 XCTrack Optimization Comparison with Reference Data")
    print("=" * 80)

    # Load all tasks
    tasks = load_all_tasks(args.tasks_dir)

    # Load JSON metadata if available
    metadata = load_json_metadata(args.json_dir)

    if not tasks:
        print("❌ No tasks found to analyze")
        return

    # Limit tasks if requested
    if args.limit:
        task_items = list(tasks.items())[: args.limit]
        tasks = dict(task_items)
        print(f"🔍 Limited analysis to {len(tasks)} tasks")

    # Run comparison on all tasks
    all_results = []

    print(f"\n🔄 Starting analysis of {len(tasks)} tasks...")

    for i, (task_name, task) in enumerate(tasks.items(), 1):
        if not args.verbose:
            print(f"Progress: {i}/{len(tasks)} - {task_name}", end="\r")

        try:
            result = compare_with_reference(task_name, task, metadata, args.verbose)
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"\n❌ Error analyzing {task_name}: {e}")

    if not args.verbose:
        print()  # New line after progress indicator

    # Analyze and display results
    analyze_results(all_results)

    print(f"\n✅ Analysis complete! Processed {len(all_results)} tasks successfully.")


if __name__ == "__main__":
    main()
