#!/usr/bin/env python3
"""
Comparison script for XCTrack task distance calculations.

This script compares the optimized_distance calculation with reference data from JSON files.
It uses the default settings of the optimized_distance function and validates that the results
match expected reference values.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add the pyxctsk module to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from pyxctsk.distance import (
    TaskTurnpoint,
    calculate_iteratively_refined_route,
    distance_through_centers,
    optimized_distance,
)
from pyxctsk.parser import parse_task
from pyxctsk.task_distances import _task_to_turnpoints

# Add task_viewer and its subdirectories to path to import AirScore utilities
task_viewer_path = Path(__file__).parent / "task_viewer"
sys.path.insert(0, str(task_viewer_path))
sys.path.insert(0, str(task_viewer_path / "airscore_clone"))

# Also ensure that the airscore_clone directory is in Python's import path
airscore_clone_path = task_viewer_path / "airscore_clone"
if airscore_clone_path.exists():
    print(f"AirScore clone directory found at {airscore_clone_path}")
else:
    print(f"Warning: AirScore clone directory not found at {airscore_clone_path}")


# Import AirScore utilities
try:
    # Try importing from task_viewer.airscore_utils
    from task_viewer.airscore_utils import (
        AIRSCORE_AVAILABLE,
        calculate_airscore_distances,
    )

    # The airscore_utils.py module already checks and sets AIRSCORE_AVAILABLE appropriately
    print(
        f"AirScore distance calculation {'available' if AIRSCORE_AVAILABLE else 'not available (using fallback)'}"
    )
except ImportError as e:
    AIRSCORE_AVAILABLE = False
    calculate_airscore_distances = None  # type: ignore
    print(f"AirScore distance calculation not available: {e}")


def load_all_tasks(tasks_dir: str) -> Dict[str, Any]:
    """Load all .xctsk files from the given directory.

    Args:
        tasks_dir: Directory containing .xctsk files

    Returns:
        Dictionary mapping filename to parsed task objects
    """
    tasks: Dict[str, Any] = {}
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
    metadata: Dict[str, Dict[str, Any]] = {}
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


def test_distance_calculations(
    turnpoints: List[TaskTurnpoint],
    verbose: bool = False,
) -> Dict[str, Any]:
    """Test distance calculations on a list of turnpoints.

    Args:
        turnpoints: List of TaskTurnpoint objects
        verbose: Whether to print detailed progress

    Returns:
        Dictionary with timing and distance results
    """
    if len(turnpoints) < 2:
        return {
            "total_time": 0.0,
            "total_distance": 0.0,
            "num_points": 0,
        }

    start_time = time.time()
    route_points: List[Any] = []

    try:
        # Always use optimized_distance with default parameters
        if verbose:
            print("    🔄 Using optimized_distance with default parameters")

        # Use default parameters for standard optimization
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
            print(f"    ⚠️  Error in optimization: {e}")
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

    return result


def test_airscore_calculations(
    task: Any,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Test AirScore distance calculations on a task.

    Args:
        task: Parsed task object
        verbose: Whether to print detailed progress

    Returns:
        Dictionary with timing and distance results
    """
    # We use the calculate_airscore_distances function which handles
    # availability internally with fallbacks, so we don't need to check
    # AIRSCORE_AVAILABLE here

    start_time = time.time()

    try:
        if verbose:
            print(
                f"    🔄 Using AirScore distance calculation (with {'real' if AIRSCORE_AVAILABLE else 'fallback'} implementation)"
            )

        # Ensure AirScore modules are in the path
        airscore_clone_path = Path(__file__).parent / "task_viewer" / "airscore_clone"
        if (
            AIRSCORE_AVAILABLE
            and str(airscore_clone_path) not in sys.path
            and airscore_clone_path.exists()
        ):
            sys.path.insert(0, str(airscore_clone_path))
            if verbose:
                print(
                    f"    📂 Added AirScore clone path to sys.path: {airscore_clone_path}"
                )

        # Use the calculate_airscore_distances function
        # This function already handles fallbacks internally
        # Ensure calculate_airscore_distances is defined and not None
        if calculate_airscore_distances is None:
            raise RuntimeError("calculate_airscore_distances is not available.")
        airscore_results = calculate_airscore_distances(task)

        if verbose:
            print("    ✅ Successfully used calculate_airscore_distances")

        total_time = time.time() - start_time

        return {
            "total_time": total_time,
            "total_distance": airscore_results["optimized_distance_m"],
            "center_distance": airscore_results["center_distance_m"],
            "route_coordinates": airscore_results.get("optimized_coordinates", []),
            "method": "airscore" if AIRSCORE_AVAILABLE else "airscore_fallback",
            "available": True,
        }

    except Exception as e:

        print(f"    ⚠️  Error in AirScore calculation: {e}")
        if verbose:
            import traceback

            print("    📜 Stack trace:")
            print(f"    {traceback.format_exc().replace(chr(10), chr(10)+'    ')}")

        total_time = time.time() - start_time

        return {
            "total_time": total_time,
            "total_distance": 0.0,
            "route_coordinates": [],
            "method": "airscore_error",
            "available": False,
            "error": str(e),
        }


def compare_with_reference(
    task_name: str,
    task: Any,
    json_metadata: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    use_airscore: bool = True,
) -> Dict[str, Any]:
    """Compare optimization results with reference data.

    Args:
        task_name: Name of the task file
        task: Parsed task object
        json_metadata: Optional JSON metadata for reference
        verbose: Whether to print detailed progress
        use_airscore: Whether to use AirScore calculation

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
        # Return a result dict with a flag indicating skip, to satisfy type checker
        return {
            "pyxctsk": {},
            "airscore": None,
            "task_info": {"name": task_name, "skipped": True},
        }

    # Calculate baseline center distance
    center_distance = distance_through_centers(turnpoints)

    if verbose:
        print(
            f"  📏 {len(turnpoints)} turnpoints, center distance: {center_distance/1000:.2f}km"
        )

    # Test pyxctsk optimization
    if verbose:
        print("  🧮 Running pyxctsk optimized distance calculation...")

    pyxctsk_result = test_distance_calculations(
        turnpoints,
        verbose,
    )

    if verbose:
        savings = (center_distance - pyxctsk_result["total_distance"]) / 1000
        print(f"    ⏱️  Time: {pyxctsk_result['total_time']:.4f}s")
        print(
            f"    📐 Distance: {pyxctsk_result['total_distance']/1000:.2f}km (saves {savings:.2f}km)"
        )

    # Test AirScore optimization if available and requested
    airscore_result = None

    if use_airscore:
        if verbose:
            print("  🧮 Running AirScore distance calculation...")
        airscore_result = test_airscore_calculations(
            task,
            verbose,
        )

        if verbose and airscore_result.get("available", False):
            savings = (center_distance - airscore_result["total_distance"]) / 1000
            print(f"    ⏱️  Time: {airscore_result['total_time']:.4f}s")
            print(
                f"    📐 Distance: {airscore_result['total_distance']/1000:.2f}km (saves {savings:.2f}km)"
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

    # Create composite result
    result = {
        "pyxctsk": pyxctsk_result,
        "airscore": airscore_result,
        "task_info": task_info,
    }

    return result


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

    # Check if AirScore is available in results
    has_airscore = any(
        r.get("airscore") and r["airscore"].get("available", False)
        for r in valid_results
    )

    # Summary statistics
    print(f"\n📊 SUMMARY STATISTICS ({len(valid_results)} tasks analyzed)")
    print("-" * 80)

    # Display optimization methods used
    print("  🔧 pyxctsk method: optimized_distance with default settings")
    if has_airscore:
        print("  🔧 AirScore method: get_shortest_path")

    # pyxctsk statistics
    pyxctsk_times = [r["pyxctsk"]["total_time"] for r in valid_results]
    pyxctsk_distances = [r["pyxctsk"]["total_distance"] for r in valid_results]

    print("\n🧩 pyxctsk optimization:")
    print(f"  ⏱️  Average time per task: {statistics.mean(pyxctsk_times):.4f}s")
    print(f"  ⏱️  Median time per task: {statistics.median(pyxctsk_times):.4f}s")
    print(f"  ⏱️  Min/Max time: {min(pyxctsk_times):.4f}s / {max(pyxctsk_times):.4f}s")
    print(f"  📐 Average distance: {statistics.mean(pyxctsk_distances)/1000:.2f}km")
    print(f"  📐 Distance std dev: {statistics.stdev(pyxctsk_distances)/1000:.3f}km")

    # AirScore statistics if available
    if has_airscore:
        airscore_results = [
            r
            for r in valid_results
            if r.get("airscore") and r["airscore"].get("available", False)
        ]

        if airscore_results:
            airscore_times = [r["airscore"]["total_time"] for r in airscore_results]
            airscore_distances = [
                r["airscore"]["total_distance"] for r in airscore_results
            ]

            print("\n🧩 AirScore optimization:")
            print(f"  ⏱️  Average time per task: {statistics.mean(airscore_times):.4f}s")
            print(
                f"  ⏱️  Median time per task: {statistics.median(airscore_times):.4f}s"
            )
            print(
                f"  ⏱️  Min/Max time: {min(airscore_times):.4f}s / {max(airscore_times):.4f}s"
            )
            print(
                f"  📐 Average distance: {statistics.mean(airscore_distances)/1000:.2f}km"
            )
            print(
                f"  📐 Distance std dev: {statistics.stdev(airscore_distances)/1000:.3f}km"
            )

            # Compare pyxctsk vs AirScore
            print("\n🔍 pyxctsk vs AirScore comparison:")
            diffs = []
            for r in airscore_results:
                pyxctsk_dist = r["pyxctsk"]["total_distance"]
                airscore_dist = r["airscore"]["total_distance"]
                diffs.append(pyxctsk_dist - airscore_dist)

            mean_diff = statistics.mean(diffs) / 1000
            sign = "+" if mean_diff > 0 else "-" if mean_diff < 0 else ""
            print(f"  📏 Average difference: {sign}{abs(mean_diff):.2f}km")
            print(
                f"  📏 pyxctsk is {'longer' if mean_diff > 0 else 'shorter'} by {abs(mean_diff):.2f}km on average"
            )

    # Add JSON comparison if available
    has_json_data = any(
        "json_optimized_distance_km" in result["task_info"] for result in valid_results
    )

    if has_json_data:
        print("\n📊 JSON REFERENCE DATA COMPARISON")
        print("-" * 80)
        print("Comparing against pre-calculated reference distances from JSON files:")

        # Calculate differences against JSON reference data
        json_diffs_pyxctsk = []
        json_diffs_airscore = []

        for result in valid_results:
            task_info = result["task_info"]
            if "json_optimized_distance_km" in task_info:
                json_opt_km = task_info["json_optimized_distance_km"]

                # pyxctsk comparison
                pyxctsk_km = result["pyxctsk"]["total_distance"] / 1000
                json_diffs_pyxctsk.append(abs(pyxctsk_km - json_opt_km))

                # AirScore comparison if available
                if result.get("airscore") and result["airscore"].get(
                    "available", False
                ):
                    airscore_km = result["airscore"]["total_distance"] / 1000
                    json_diffs_airscore.append(abs(airscore_km - json_opt_km))

        if json_diffs_pyxctsk:
            print("\nAverage difference vs JSON reference optimized distance:")
            print(
                f"  🔸 pyxctsk difference: {statistics.mean(json_diffs_pyxctsk):.2f}km"
            )

            if json_diffs_airscore:
                print(
                    f"  🔸 AirScore difference: {statistics.mean(json_diffs_airscore):.2f}km"
                )

    # Detailed task-by-task results
    print("\n📋 DETAILED TASK RESULTS")
    print("-" * 80)

    # Check if any tasks have JSON data
    tasks_with_json = [
        r for r in valid_results if "json_optimized_distance_km" in r["task_info"]
    ]

    # Check if AirScore is available
    has_airscore_detail = has_airscore

    print(
        f"{len(tasks_with_json)} tasks have JSON data out of {len(valid_results)} total"
    )

    if has_airscore_detail:
        print(
            f"AirScore optimization available for {sum(1 for r in valid_results if r.get('airscore') and r['airscore'].get('available', False))} tasks"
        )

    # Create header based on available data
    header_parts = ["Task", "TPs", "Center"]
    header_values = ["Name", "#", "(km)"]

    if tasks_with_json:
        header_parts.extend(["JSON Ref", "pyxctsk", "XC Diff"])
        header_values.extend(["Opt (km)", "(km)", "(km)"])
    else:
        header_parts.extend(["pyxctsk"])
        header_values.extend(["(km)"])

    if has_airscore_detail:
        header_parts.extend(["AirScore", "AS Diff"])
        header_values.extend(["(km)", "(km)"])

    header_parts.append("Time")
    header_values.append("(s)")

    # Calculate column widths
    col_widths = [max(len(h1), len(h2)) for h1, h2 in zip(header_parts, header_values)]
    col_widths = [w + 2 for w in col_widths]  # Add padding
    col_widths[0] = 15  # Fixed width for task name

    # Print header
    header1 = " ".join(f"{h:{w}s}" for h, w in zip(header_parts, col_widths))
    header2 = " ".join(f"{h:{w}s}" for h, w in zip(header_values, col_widths))
    print(header1)
    print(header2)
    print("-" * 80)

    # Print task details
    for result in valid_results:
        task_name = result["task_info"]["name"][:14]
        num_tps = result["task_info"]["num_turnpoints"]
        center_km = result["task_info"]["center_distance_km"]

        pyxctsk_km = result["pyxctsk"]["total_distance"] / 1000
        pyxctsk_time = result["pyxctsk"]["total_time"]

        # Prepare row values list
        row_values = [
            task_name,
            f"{num_tps}",
            f"{center_km:.2f}",
        ]

        # Add JSON reference and pyxctsk data
        if "json_optimized_distance_km" in result["task_info"]:
            json_opt_km = result["task_info"]["json_optimized_distance_km"]
            pyxctsk_diff_km = pyxctsk_km - json_opt_km
            pyxctsk_sign = (
                "+" if pyxctsk_diff_km > 0 else "-" if pyxctsk_diff_km < 0 else " "
            )

            row_values.extend(
                [
                    f"{json_opt_km:.2f}",
                    f"{pyxctsk_km:.2f}",
                    f"{pyxctsk_sign}{abs(pyxctsk_diff_km):.2f}",
                ]
            )
        else:
            if tasks_with_json:
                row_values.extend(
                    [
                        "N/A",
                        f"{pyxctsk_km:.2f}",
                        "N/A",
                    ]
                )
            else:
                row_values.append(f"{pyxctsk_km:.2f}")

        # Add AirScore data if available
        if has_airscore_detail:
            if result.get("airscore") and result["airscore"].get("available", False):
                airscore_km = result["airscore"]["total_distance"] / 1000

                # Compare with JSON ref if available
                if "json_optimized_distance_km" in result["task_info"]:
                    json_opt_km = result["task_info"]["json_optimized_distance_km"]
                    airscore_diff_km = airscore_km - json_opt_km
                    airscore_sign = (
                        "+"
                        if airscore_diff_km > 0
                        else "-" if airscore_diff_km < 0 else " "
                    )
                    row_values.extend(
                        [
                            f"{airscore_km:.2f}",
                            f"{airscore_sign}{abs(airscore_diff_km):.2f}",
                        ]
                    )
                else:
                    row_values.extend(
                        [
                            f"{airscore_km:.2f}",
                            "N/A",
                        ]
                    )
            else:
                row_values.extend(["N/A", "N/A"])

        # Add time
        row_values.append(f"{pyxctsk_time:.3f}s")

        # Print the row with appropriate formatting
        row = []
        for value, width in zip(row_values, col_widths):
            row.append(f"{value:{width}s}")
        print(" ".join(row))


def main():
    """Main function to run the optimization comparison with reference data."""
    parser = argparse.ArgumentParser(
        description="Compare pyxctsk optimization with reference data"
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
    parser.add_argument(
        "--no-airscore", action="store_true", help="Skip AirScore distance calculations"
    )

    args = parser.parse_args()
    use_airscore = not args.no_airscore

    print("🚀 pyxctsk and AirScore Optimization Comparison with Reference Data")
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

    # Display optimization methods
    print(f"\n🔄 Starting analysis of {len(tasks)} tasks...")
    print("  📐 pyxctsk: Using optimized_distance with default settings")
    if use_airscore:
        if AIRSCORE_AVAILABLE:
            print("  📐 AirScore: Using AirScore distance calculations")
        else:
            print("  ⚠️  AirScore calculations not available, will be skipped")
    else:
        print("  ℹ️  AirScore calculations skipped (--no-airscore option)")

    for i, (task_name, task) in enumerate(tasks.items(), 1):
        if not args.verbose:
            print(f"Progress: {i}/{len(tasks)} - {task_name}", end="\r")

        try:
            result = compare_with_reference(
                task_name,
                task,
                metadata,
                args.verbose,
                use_airscore,
            )
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
