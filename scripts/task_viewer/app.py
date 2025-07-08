#!/usr/bin/env python3
"""
Task Viewer - A simple Flask application to display XCTrack task metadata and GeoJSON visualization.
This is a standalone application for testing purposes, to compare xcontest data with generated data.
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from flask import Flask, abort, jsonify, render_template, request

# Add the xctrack module to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from pyxctsk import calculate_task_distances, generate_task_geojson, parse_task

    XCTRACK_AVAILABLE = True
except ImportError as e:
    print(f"Warning: xctrack module not available: {e}")
    XCTRACK_AVAILABLE = False

# Add task_viewer and its subdirectories to path to import AirScore utilities
task_viewer_path = Path(__file__).parent
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
    from airscore_utils import (
        AIRSCORE_AVAILABLE,
        calculate_airscore_distances,
        generate_airscore_geojson,
    )

    # The airscore_utils.py module already checks and sets AIRSCORE_AVAILABLE appropriately
    print(
        f"AirScore distance calculation {'available' if AIRSCORE_AVAILABLE else 'not available (using fallback)'}"
    )
except ImportError as e:
    AIRSCORE_AVAILABLE = False
    print(f"AirScore distance calculation not available: {e}")

app = Flask(__name__)

# Configuration
JSON_DIR = (
    Path(os.path.dirname(os.path.abspath(__file__)))
    / ".."
    / "downloaded_tasks"
    / "json"
)
GEOJSON_DIR = (
    Path(os.path.dirname(os.path.abspath(__file__)))
    / ".."
    / "downloaded_tasks"
    / "geojson"
)
XCTSK_DIR = (
    Path(os.path.dirname(os.path.abspath(__file__)))
    / ".."
    / "downloaded_tasks"
    / "xctsk"
)


@app.route("/")
def index():
    """Render the main page with task selection."""
    tasks = get_available_tasks()
    return render_template(
        "index.html",
        tasks=tasks,
        xctrack_available=XCTRACK_AVAILABLE,
        airscore_available=AIRSCORE_AVAILABLE,
    )


@app.route("/compare")
def compare_index():
    """Render the comparison page with task selection."""
    tasks = get_available_tasks()
    return render_template(
        "compare.html", tasks=tasks, xctrack_available=XCTRACK_AVAILABLE
    )


@app.route("/debug")
def debug_index():
    """Render the debug page with task selection."""
    tasks = get_available_tasks()
    return render_template(
        "debug.html", tasks=tasks, xctrack_available=XCTRACK_AVAILABLE
    )


@app.route("/task/<task_name>")
def show_task(task_name: str):
    """Display visualization and details for a specific task."""
    # Load task data from JSON and GeoJSON files
    json_data, geojson_data = load_task_data(task_name)

    # Check if task data was loaded successfully
    if not json_data or not geojson_data:
        abort(404)

    return render_template(
        "task_view.html",
        task_name=task_name,
        metadata=json_data.get("metadata", {}),
        turnpoints=json_data.get("turnpoints", []),
        geojson=geojson_data,
        airscore_available=AIRSCORE_AVAILABLE,
    )


@app.route("/compare/<task_name>")
def compare_task(task_name: str):
    """Display comparison between downloaded data and xctrack calculations."""
    if not XCTRACK_AVAILABLE:
        abort(500, "XCTrack module not available for calculations")

    # Load original task data
    json_data, geojson_data = load_task_data(task_name)
    if not json_data:
        abort(404, "Task data not found")

    # Load and parse XCTSK file using xctrack module
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        abort(404, "XCTSK file not found")

    try:
        # Parse task using xctrack
        task = parse_task(str(xctsk_path))

        # Calculate distances using xctrack
        distance_results = calculate_task_distances(task, show_progress=False)

        # Generate XCTrack GeoJSON data
        xctrack_geojson = generate_task_geojson(task)

        # Prepare comparison data
        comparison_data = prepare_comparison_data(json_data, distance_results, task)

        return render_template(
            "compare_view.html",
            task_name=task_name,
            comparison=comparison_data,
            original_metadata=json_data.get("metadata", {}),
            original_geojson=geojson_data,
            xctrack_geojson=xctrack_geojson,
            airscore_available=AIRSCORE_AVAILABLE,
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return render_template(
            "compare_view.html",
            task_name=task_name,
            error=f"Error calculating distances: {str(e)}",
            stacktrace=stacktrace,
        )


@app.route("/debug/<task_name>")
def debug_task(task_name: str):
    """Display debug information for generate_task_geojson with focus on goal lines."""
    if not XCTRACK_AVAILABLE:
        abort(500, "XCTrack module not available for calculations")

    # Load original task data
    json_data, geojson_data = load_task_data(task_name)
    if not json_data:
        abort(404, "Task data not found")

    # Load and parse XCTSK file using xctrack module
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        abort(404, "XCTSK file not found")

    try:
        # Parse task using xctrack
        task = parse_task(str(xctsk_path))

        # Generate XCTrack GeoJSON data with debug information
        xctrack_geojson = generate_task_geojson(task)

        return render_template(
            "debug_view.html",
            task_name=task_name,
            task=task,
            original_geojson=geojson_data,
            xctrack_geojson=xctrack_geojson,
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return render_template(
            "debug_view.html",
            task_name=task_name,
            error=f"Error generating debug data: {str(e)}",
            stacktrace=stacktrace,
        )


@app.route("/api/task/<task_name>")
def task_api(task_name: str):
    """API endpoint to get task data in JSON format."""
    json_data, geojson_data = load_task_data(task_name)

    if not json_data or not geojson_data:
        abort(404)

    return jsonify(
        {"task_name": task_name, "json_data": json_data, "geojson_data": geojson_data}
    )


@app.route("/api/compare/<task_name>")
def compare_task_api(task_name: str):
    """API endpoint to get comparison data in JSON format."""
    if not XCTRACK_AVAILABLE:
        return jsonify({"error": "XCTrack module not available"}), 500

    # Load original task data
    json_data, geojson_data = load_task_data(task_name)
    if not json_data:
        return jsonify({"error": "Task data not found"}), 404

    # Load and parse XCTSK file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return jsonify({"error": "XCTSK file not found"}), 404

    try:
        task = parse_task(str(xctsk_path))
        distance_results = calculate_task_distances(task, show_progress=False)
        xctrack_geojson = generate_task_geojson(task)
        comparison_data = prepare_comparison_data(json_data, distance_results, task)

        return jsonify(
            {
                "task_name": task_name,
                "comparison": comparison_data,
                "original_metadata": json_data.get("metadata", {}),
                "original_geojson": geojson_data,
                "xctrack_geojson": xctrack_geojson,
            }
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return (
            jsonify(
                {
                    "error": f"Error calculating distances: {str(e)}",
                    "stacktrace": stacktrace,
                }
            ),
            500,
        )


@app.route("/airscore/<task_name>")
def airscore_task(task_name: str):
    """Display AirScore calculations for a specific task."""
    if not AIRSCORE_AVAILABLE:
        return render_template(
            "airscore_view.html",
            task_name=task_name,
            error="AirScore utilities not available",
        )

    # Load and parse XCTSK file using xctrack module
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        abort(404, "XCTSK file not found")

    try:
        # Parse task using xctrack
        task = parse_task(str(xctsk_path))

        # Calculate distances using AirScore clone
        airscore_results = calculate_airscore_distances(task)

        # Generate AirScore GeoJSON for mapping
        airscore_geojson = generate_airscore_geojson(task, airscore_results)

        return render_template(
            "airscore_view.html",
            task_name=task_name,
            airscore_results=airscore_results,
            airscore_geojson=airscore_geojson,
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return render_template(
            "airscore_view.html",
            task_name=task_name,
            error=f"Error calculating distances: {str(e)}",
            stacktrace=stacktrace,
        )


@app.route("/api/airscore/<task_name>")
def airscore_task_api(task_name: str):
    """API endpoint to get AirScore calculation data in JSON format."""
    if not AIRSCORE_AVAILABLE:
        return jsonify({"error": "AirScore utilities not available"}), 500

    # Load and parse XCTSK file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return jsonify({"error": "XCTSK file not found"}), 404

    try:
        task = parse_task(str(xctsk_path))
        airscore_results = calculate_airscore_distances(task)
        airscore_geojson = generate_airscore_geojson(task, airscore_results)

        return jsonify(
            {
                "task_name": task_name,
                "airscore_results": airscore_results,
                "airscore_geojson": airscore_geojson,
            }
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return (
            jsonify(
                {
                    "error": f"Error calculating distances: {str(e)}",
                    "stacktrace": stacktrace,
                }
            ),
            500,
        )


def get_available_tasks() -> List[str]:
    """Get list of available task names from JSON directory."""
    tasks = []

    # Find all JSON files in the JSON directory
    if JSON_DIR.exists():
        json_files = list(JSON_DIR.glob("*.json"))
        for file in json_files:
            task_name = file.stem
            if (GEOJSON_DIR / f"{task_name}.geojson").exists():
                tasks.append(task_name)

    return sorted(tasks)


def load_task_data(task_name: str) -> Tuple[Optional[Dict], Optional[Dict]]:
    """Load task data from JSON and GeoJSON files."""
    json_path = JSON_DIR / f"{task_name}.json"
    geojson_path = GEOJSON_DIR / f"{task_name}.geojson"

    json_data = None
    geojson_data = None

    # Load JSON data
    if json_path.exists():
        try:
            with open(json_path, "r") as f:
                json_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            app.logger.error(f"Error loading JSON file {json_path}: {e}")

    # Load GeoJSON data
    if geojson_path.exists():
        try:
            with open(geojson_path, "r") as f:
                geojson_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            app.logger.error(f"Error loading GeoJSON file {geojson_path}: {e}")

    return json_data, geojson_data


def prepare_comparison_data(original_data: Dict, xctrack_results: Dict, task) -> Dict:
    """Prepare comparison data between original and xctrack calculations."""
    comparison = {
        "summary": {
            "original_center_km": original_data["metadata"].get(
                "distance_through_centers_km", 0
            ),
            "original_optimized_km": original_data["metadata"].get(
                "distance_optimized_km", 0
            ),
            "xctrack_center_km": xctrack_results.get("center_distance_km", 0),
            "xctrack_optimized_km": xctrack_results.get("optimized_distance_km", 0),
        },
        "turnpoints": [],
    }

    # Calculate differences for summary
    center_diff = (
        comparison["summary"]["xctrack_center_km"]
        - comparison["summary"]["original_center_km"]
    )
    opt_diff = (
        comparison["summary"]["xctrack_optimized_km"]
        - comparison["summary"]["original_optimized_km"]
    )

    comparison["summary"]["center_difference_km"] = center_diff
    comparison["summary"]["optimized_difference_km"] = opt_diff
    comparison["summary"]["center_difference_percent"] = (
        (center_diff / comparison["summary"]["original_center_km"] * 100)
        if comparison["summary"]["original_center_km"] > 0
        else 0
    )
    comparison["summary"]["optimized_difference_percent"] = (
        (opt_diff / comparison["summary"]["original_optimized_km"] * 100)
        if comparison["summary"]["original_optimized_km"] > 0
        else 0
    )

    # Compare turnpoint by turnpoint
    original_tps = original_data.get("turnpoints", [])
    xctrack_tps = xctrack_results.get("turnpoints", [])

    for i, orig_tp in enumerate(original_tps):
        tp_comparison = {
            "index": i + 1,
            "name": orig_tp.get("Name", f"TP{i+1}"),
            "type": orig_tp.get("Type", ""),
            "radius_m": orig_tp.get("Radius (m)", 0),
            "original": {
                "center_km": orig_tp.get("Distance (km)", 0),
                "optimized_km": orig_tp.get("Optimized (km)", 0),
            },
            "xctrack": {
                "center_km": 0,
                "optimized_km": 0,
            },
        }

        # Find corresponding xctrack turnpoint
        if i < len(xctrack_tps):
            xctrack_tp = xctrack_tps[i]
            tp_comparison["xctrack"]["center_km"] = xctrack_tp.get(
                "cumulative_center_km", 0
            )
            tp_comparison["xctrack"]["optimized_km"] = xctrack_tp.get(
                "cumulative_optimized_km", 0
            )

        # Calculate differences
        center_diff = (
            tp_comparison["xctrack"]["center_km"]
            - tp_comparison["original"]["center_km"]
        )
        opt_diff = (
            tp_comparison["xctrack"]["optimized_km"]
            - tp_comparison["original"]["optimized_km"]
        )

        tp_comparison["differences"] = {
            "center_km": center_diff,
            "optimized_km": opt_diff,
            "center_percent": (
                (center_diff / tp_comparison["original"]["center_km"] * 100)
                if tp_comparison["original"]["center_km"] > 0
                else 0
            ),
            "optimized_percent": (
                (opt_diff / tp_comparison["original"]["optimized_km"] * 100)
                if tp_comparison["original"]["optimized_km"] > 0
                else 0
            ),
        }

        comparison["turnpoints"].append(tp_comparison)

    return comparison


if __name__ == "__main__":
    app.run(debug=True, port=5001)
