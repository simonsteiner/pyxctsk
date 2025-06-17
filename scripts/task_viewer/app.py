#!/usr/bin/env python3
"""
Task Viewer - A simple Flask application to display XCTrack task metadata and GeoJSON visualization.
This is a standalone application for testing purposes, to compare xcontest data with generated data.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from flask import Flask, render_template, request, jsonify, abort

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


@app.route("/api/task/<task_name>")
def task_api(task_name: str):
    """API endpoint to get task data in JSON format."""
    json_data, geojson_data = load_task_data(task_name)

    if not json_data or not geojson_data:
        abort(404)

    return jsonify(
        {"task_name": task_name, "json_data": json_data, "geojson_data": geojson_data}
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


if __name__ == "__main__":
    app.run(debug=True, port=5001)
