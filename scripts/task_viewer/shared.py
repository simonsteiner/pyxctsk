"""Shared utilities and blueprints for the Task Viewer Flask app."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app

# Configuration
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / ".." / "downloaded_tasks"
JSON_DIR = BASE_DIR / "json"
GEOJSON_DIR = BASE_DIR / "geojson"
XCTSK_DIR = BASE_DIR / "xctsk"


def get_available_tasks() -> List[str]:
    """Get list of available task names present in all required formats.

    Returns:
        list[str]: Sorted list of task names that have JSON, GeoJSON, and XCTSK files.
    """
    json_files = (
        set(f.stem for f in JSON_DIR.glob("*.json")) if JSON_DIR.exists() else set()
    )
    geojson_files = (
        set(f.stem for f in GEOJSON_DIR.glob("*.geojson"))
        if GEOJSON_DIR.exists()
        else set()
    )
    xctsk_files = (
        set(f.stem for f in XCTSK_DIR.glob("*.xctsk")) if XCTSK_DIR.exists() else set()
    )
    # Only include tasks that have all three files
    return sorted(json_files & geojson_files & xctsk_files)


def load_task_data(
    task_name: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Load task data from JSON and GeoJSON files.

    Args:
        task_name (str): The name of the task to load.

    Returns:
        Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
            A tuple containing the JSON data and GeoJSON data, or None if loading fails.

    Raises:
        None. Errors are logged and None is returned if loading fails.
    """
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
            current_app.logger.error(f"Error loading JSON file {json_path}: {e}")

    # Load GeoJSON data
    if geojson_path.exists():
        try:
            with open(geojson_path, "r") as f:
                geojson_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            current_app.logger.error(f"Error loading GeoJSON file {geojson_path}: {e}")

    return json_data, geojson_data


def prepare_comparison_data(
    original_data: Dict[str, Any], xctrack_results: Dict[str, Any], task: Any
) -> Dict[str, Any]:
    """Prepare comparison data between original and xctrack calculations.

    Args:
        original_data (Dict[str, Any]): The original task data loaded from JSON.
        xctrack_results (Dict[str, Any]): The results from XCTrack calculations.
        task (Any): The parsed task object.

    Returns:
        Dict[str, Any]: Dictionary containing summary and turnpoint comparison data.
    """
    comparison: Dict[str, Any] = {
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
