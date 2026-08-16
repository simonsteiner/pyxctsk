#!/usr/bin/env python3
"""
Comparison script for task distance calculation methods.

This script compares distance calculations from four different optimization methods:
1. pyxctsk (native implementation)
2. AirScore (external library)
3. ChatGPT-generated optimization function
4. Gemini-generated optimization function

The results are compared against pre-calculated reference values from JSON
files to validate accuracy and performance.
"""

import argparse
import json
import statistics
import sys
import time
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# --- Path Setup ---
# Add the pyxctsk module to the Python path for direct import.
# This allows running the script from the 'scripts/comparison' directory.
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


# --- AirScore Integration ---
try:
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
    calculate_airscore_distances = None  # type: ignore[assignment]
    print(f"AirScore distance calculation not available: {e}")


# --- Imports for Gemini and ChatGPT ---
path_opt_path = Path(__file__).parent / "path_opt"
sys.path.insert(0, str(path_opt_path))
# Only probe for availability here; get_chatgpt_result and get_gemini_result import
# the symbols they need locally, since the two modules export clashing names.
CHATGPT_AVAILABLE = find_spec("path_opt.pg_path_opt_chatgpt") is not None
print(
    f"ChatGPT path optimization {'available' if CHATGPT_AVAILABLE else 'not available'}."
)

GEMINI_AVAILABLE = find_spec("path_opt.pg_path_opt_gemini") is not None
print(
    f"Gemini path optimization {'available' if GEMINI_AVAILABLE else 'not available'}."
)


# --- Data Loading ---


def load_all_tasks(tasks_dir: str) -> Dict[str, Any]:
    """Loads all .xctsk files from the specified directory.

    Args:
        tasks_dir (str): Directory containing .xctsk files.

    Returns:
        Dict[str, Any]: Dictionary mapping filename to parsed task objects.
    """
    tasks: Dict[str, Any] = {}
    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        print(f"❌ Tasks directory not found: {tasks_dir}")
        return tasks

    task_files = sorted(list(tasks_path.glob("*.xctsk")))
    print(f"🔎 Found {len(task_files)} task files in '{tasks_dir}'")
    for task_file in task_files:
        try:
            tasks[task_file.name] = parse_task(str(task_file))
        except Exception as e:
            print(f"❌ Failed to load {task_file.name}: {e}")

    print(f"✅ Successfully loaded {len(tasks)} tasks.")
    return tasks


def load_json_metadata(json_dir: str) -> Dict[str, Dict[str, Any]]:
    """Loads JSON metadata files containing pre-calculated distances.

    Args:
        json_dir (str): Directory containing .json files.

    Returns:
        Dict[str, Dict[str, Any]]: Dictionary mapping task name to metadata.
    """
    metadata: Dict[str, Dict[str, Any]] = {}
    json_path = Path(json_dir)
    if not json_path.exists():
        print(f"⚠️ JSON metadata directory not found: {json_dir}")
        return metadata

    json_files = sorted(list(json_path.glob("task_*.json")))
    print(f"🔎 Found {len(json_files)} JSON files in '{json_dir}'")
    for json_file in json_files:
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            # Extract task name from filename (remove task_ prefix and .json suffix)
            task_name = json_file.stem.replace("task_", "")
            if "metadata" in data:
                metadata[task_name] = data["metadata"]
        except Exception as e:
            print(f"❌ Failed to load {json_file.name}: {e}")

    print(f"✅ Successfully loaded {len(metadata)} metadata files.")
    return metadata


# --- Calculation Methods ---


def run_calculation(
    name: str, calculation_func: Callable[[], Dict[str, Any]], verbose: bool = False
) -> Dict[str, Any]:
    """Generic wrapper to run a calculation, time it, and handle errors."""
    if verbose:
        print(f"  🧮 Running {name} calculation...")
    start_time = time.time()
    try:
        result = calculation_func()
        result["total_time"] = time.time() - start_time
        if verbose:
            distance_km = result.get("total_distance", 0) / 1000
            print(
                f"    ✅ Success! Time: {result['total_time']:.4f}s, Distance: {distance_km:.2f}km"
            )
        return result
    except Exception as e:
        total_time = time.time() - start_time
        if verbose:
            print(f"    ❌ Error in {name} calculation: {e}")
        return {"error": str(e), "total_time": total_time}


def get_pyxctsk_result(
    turnpoints: List[TaskTurnpoint], show_progress: bool
) -> Dict[str, Any]:
    """Calculates the optimized distance using the pyxctsk library."""
    distance = optimized_distance(turnpoints, show_progress=show_progress)
    _, route_points = calculate_iteratively_refined_route(
        turnpoints, show_progress=False
    )
    return {
        "total_distance": distance,
        "route_points": route_points,
    }


def get_airscore_result(task: Any) -> Dict[str, Any]:
    """Calculates the optimized distance using the AirScore library."""
    if calculate_airscore_distances is None:
        raise RuntimeError("AirScore function not available.")
    airscore_results = calculate_airscore_distances(task)
    return {
        "total_distance": airscore_results["optimized_distance_m"],
        "center_distance": airscore_results["center_distance_m"],
        "route_points": airscore_results.get("optimized_coordinates", []),
    }


def get_chatgpt_result(turnpoints: List[TaskTurnpoint]) -> Dict[str, Any]:
    """Calculates the optimized distance using the ChatGPT-generated function."""
    if not CHATGPT_AVAILABLE:
        raise RuntimeError("ChatGPT path optimization not available.")
    from geographiclib.geodesic import Geodesic
    from path_opt.pg_path_opt_chatgpt import Gate, optimize_path

    gates = [
        Gate(center=(tp.center[0], tp.center[1]), radius=tp.radius) for tp in turnpoints
    ]
    geod = Geodesic.WGS84
    route_cgpt, dist_cgpt = optimize_path(gates, geod)
    return {
        "total_distance": dist_cgpt,
        "route_points": route_cgpt,
    }


def get_gemini_result(turnpoints: List[TaskTurnpoint]) -> Dict[str, Any]:
    """Calculates the optimized distance using the Gemini-generated function."""
    if not GEMINI_AVAILABLE:
        raise RuntimeError("Gemini path optimization not available.")
    from geographiclib.geodesic import Geodesic
    from path_opt.pg_path_opt_gemini import Gate, Point, optimize_path

    gates = [
        Gate("circle", center=Point(tp.center[0], tp.center[1]), radius=tp.radius)
        for tp in turnpoints
    ]
    geod = Geodesic.WGS84
    route_gemini, dist_gemini = optimize_path(gates, geod)
    return {
        "total_distance": dist_gemini,
        "route_points": route_gemini,
    }


# --- Core Comparison Logic ---


def compare_task_distances(
    task_name: str,
    task: Any,
    json_metadata: Optional[Dict[str, Any]] = None,
    verbose: bool = False,
    use_airscore: bool = True,
) -> Optional[Dict[str, Any]]:
    """
    Compares optimization results from all methods for a single task.
    Returns a dictionary with all results or None if the task is skipped.
    """
    if verbose:
        print(f"\n🔄 Analyzing task: {task_name}")

    turnpoints = _task_to_turnpoints(task)
    if len(turnpoints) < 2:
        if verbose:
            print(f"  ⚠️ Skipping {task_name}: Task has fewer than 2 turnpoints.")
        return None

    center_distance = distance_through_centers(turnpoints)
    if verbose:
        print(
            f"  📏 {len(turnpoints)} turnpoints, center-to-center distance: {center_distance / 1000:.2f}km"
        )

    # --- Run all calculations ---
    results: Dict[str, Any] = {"task_info": {}}

    results["pyxctsk"] = run_calculation(
        "pyxctsk", lambda: get_pyxctsk_result(turnpoints, verbose), verbose
    )
    if CHATGPT_AVAILABLE:
        results["chatgpt"] = run_calculation(
            "ChatGPT", lambda: get_chatgpt_result(turnpoints), verbose
        )
    if GEMINI_AVAILABLE:
        results["gemini"] = run_calculation(
            "Gemini", lambda: get_gemini_result(turnpoints), verbose
        )

    if use_airscore and AIRSCORE_AVAILABLE:
        results["airscore"] = run_calculation(
            "AirScore", lambda: get_airscore_result(task), verbose
        )

    # --- Compile final result dictionary ---
    task_info = {
        "name": task_name,
        "num_turnpoints": len(turnpoints),
        "center_distance_km": center_distance / 1000,
    }

    # Add JSON reference data if available
    if json_metadata:
        lookup_name = task_name.replace(".xctsk", "").replace("task_", "")
        if lookup_name in json_metadata:
            ref_meta = json_metadata[lookup_name]
            ref_km = ref_meta.get("distance_optimized_km")
            if ref_km is not None:
                ref_km = float(ref_km)
            task_info["json_optimized_distance_km"] = ref_km
            if verbose:
                if ref_km is not None:
                    print(f"  📊 Found JSON reference distance: {ref_km:.2f}km")
                else:
                    print(
                        f"  ⚠️ JSON metadata for '{lookup_name}' has no "
                        "'distance_optimized_km'"
                    )
        elif verbose:
            print(f"  ⚠️ No JSON metadata found for '{lookup_name}'")

    results["task_info"] = task_info
    return results


# --- Results Analysis and Display ---


def analyze_and_display_results(all_results: List[Dict[str, Any]]):
    """Analyzes and displays comparison results in a summary and detailed table."""
    print("\n" + "=" * 80)
    print("🏆 OPTIMIZATION COMPARISON RESULTS")
    print("=" * 80)

    if not all_results:
        print("❌ No valid results to analyze.")
        return

    methods = ["pyxctsk", "chatgpt", "gemini", "airscore"]
    stats: Dict[str, Dict[str, List[float]]] = {
        method: {"times": [], "distances": []} for method in methods
    }

    for res in all_results:
        for method in methods:
            if method in res and "error" not in res[method]:
                stats[method]["times"].append(res[method]["total_time"])
                stats[method]["distances"].append(res[method]["total_distance"])

    # --- Summary Statistics ---
    print(f"\n📊 SUMMARY STATISTICS ({len(all_results)} tasks analyzed)")
    print("-" * 80)

    for method in methods:
        if stats[method]["distances"]:
            print(f"\n🧩 {method.capitalize()} Optimization:")
            times, dists = stats[method]["times"], stats[method]["distances"]
            print(
                f"  ⏱️  Time (avg/med): {statistics.mean(times):.4f}s / {statistics.median(times):.4f}s"
            )
            mean_km = statistics.mean(dists) / 1000
            if len(dists) > 1:
                stdev_km = statistics.stdev(dists) / 1000
                stdev_str = f"{stdev_km:.3f}km"
            else:
                stdev_str = "N/A"
            print(f"  📐 Dist (km, avg/stdev): {mean_km:.2f}km / {stdev_str}")

    # --- Detailed Task-by-Task Table ---
    print("\n📋 DETAILED TASK RESULTS")
    print("-" * 80)

    header = [
        "Task",
        "TPs",
        "Center",
        "Ref Opt",
        "pyxctsk",
        "Δ Ref",
        "ChatGPT",
        "Δ Ref",
        "Gemini",
        "Δ Ref",
        "AirScore",
        "Δ Ref",
        "Time(s)",
    ]
    col_widths = [15, 3, 7, 8, 8, 7, 8, 7, 8, 7, 8, 7, 8]
    header_str = " ".join(f"{h:<{w}}" for h, w in zip(header, col_widths))
    print(header_str)
    print(
        " ".join(
            f"{h:<{w}}"
            for h, w in zip(
                ["Name", "#", "(km)", "(km)"] + ["(km)", "(km)"] * 4 + ["(pyx)"],
                col_widths,
            )
        )
    )
    print("-" * len(header_str))

    for result in all_results:
        info = result["task_info"]
        ref_km = info.get("json_optimized_distance_km")

        row = [
            info["name"][:14],
            str(info["num_turnpoints"]),
            f"{info['center_distance_km']:.2f}",
            f"{ref_km:.2f}" if ref_km is not None else "N/A",
        ]

        # Add results for each method
        for method in methods:
            if method in result and "error" not in result[method]:
                dist_km = result[method]["total_distance"] / 1000
                row.append(f"{dist_km:.2f}")
                if ref_km is not None:
                    diff = dist_km - ref_km
                    row.append(f"{diff:+.2f}")
                else:
                    row.append("N/A")
            else:
                row.extend(["Fail", "N/A"])  # Add placeholders for failed calculations

        # Add timing info (using pyxctsk as the reference time)
        row.append(f"{result['pyxctsk'].get('total_time', 0):.3f}")

        # Print the formatted row
        print(" ".join(f"{item:<{width}}" for item, width in zip(row, col_widths)))


# --- Main Execution ---


def main():
    """Main function to run the command-line tool."""
    parser = argparse.ArgumentParser(
        description="Compare pyxctsk optimization with reference data from other methods.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--tasks-dir",
        default="downloaded_tasks/xctsk",
        help="Directory containing .xctsk files.",
    )
    parser.add_argument(
        "--json-dir",
        default="downloaded_tasks/json",
        help="Directory for reference .json files.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Show detailed progress during analysis."
    )
    parser.add_argument(
        "--limit", type=int, help="Limit the number of tasks to analyze."
    )
    parser.add_argument(
        "--no-airscore",
        action="store_true",
        help="Skip AirScore distance calculations.",
    )
    args = parser.parse_args()

    print("🚀 Starting Task Distance Calculation Comparison")
    print("=" * 80)

    tasks = load_all_tasks(args.tasks_dir)
    metadata = load_json_metadata(args.json_dir)

    if not tasks:
        print("❌ No tasks found to analyze. Exiting.")
        return

    task_items = list(tasks.items())
    if args.limit:
        task_items = task_items[: args.limit]
        print(f"🔍 Limiting analysis to {len(task_items)} tasks.")

    all_results = []
    use_airscore = not args.no_airscore

    print(f"\n🔄 Starting analysis of {len(task_items)} tasks...")
    for i, (task_name, task) in enumerate(task_items, 1):
        if not args.verbose:
            print(f"Progress: {i}/{len(task_items)} - {task_name}", end="\r")

        try:
            result = compare_task_distances(
                task_name, task, metadata, args.verbose, use_airscore
            )
            if result:
                all_results.append(result)
        except Exception as e:
            print(f"\n❌ An unexpected error occurred while analyzing {task_name}: {e}")

    if not args.verbose:
        print("\n")  # New line after progress indicator

    analyze_and_display_results(all_results)

    print(f"\n✅ Analysis complete! Processed {len(all_results)} tasks successfully.")


if __name__ == "__main__":
    main()
