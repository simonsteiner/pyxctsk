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

from flask import Flask, render_template, request, jsonify, abort

# Add the xctrack module to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    import xctrack
    from xctrack import parse_task, calculate_task_distances

    XCTRACK_AVAILABLE = True
except ImportError as e:
    print(f"Warning: xctrack module not available: {e}")
    XCTRACK_AVAILABLE = False

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
    return render_template("index.html", tasks=tasks)


@app.route("/compare")
def compare_index():
    """Render the comparison page with task selection."""
    tasks = get_available_tasks()
    return render_template(
        "compare.html", tasks=tasks, xctrack_available=XCTRACK_AVAILABLE
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

        # Prepare comparison data
        comparison_data = prepare_comparison_data(json_data, distance_results, task)

        return render_template(
            "compare_view.html",
            task_name=task_name,
            comparison=comparison_data,
            original_metadata=json_data.get("metadata", {}),
        )

    except Exception as e:
        abort(500, f"Error calculating distances: {str(e)}")


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
    json_data, _ = load_task_data(task_name)
    if not json_data:
        return jsonify({"error": "Task data not found"}), 404

    # Load and parse XCTSK file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return jsonify({"error": "XCTSK file not found"}), 404

    try:
        task = parse_task(str(xctsk_path))
        distance_results = calculate_task_distances(task, show_progress=False)
        comparison_data = prepare_comparison_data(json_data, distance_results, task)

        return jsonify(
            {
                "task_name": task_name,
                "comparison": comparison_data,
                "original_metadata": json_data.get("metadata", {}),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Error calculating distances: {str(e)}"}), 500


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
