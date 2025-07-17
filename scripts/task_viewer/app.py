#!/usr/bin/env python3
"""Task Viewer - A simple Flask application to display XCTrack task metadata and GeoJSON visualization.

This is a standalone application for testing purposes, to compare xcontest data with generated data.
"""

import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union

from api import api_bp
from flask import (
    Blueprint,
    Flask,
    abort,
    render_template,
)
from shared import (
    XCTSK_DIR,
    get_available_tasks,
    load_task_data,
    prepare_comparison_data,
)

# Add the xctrack module to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

# Initialize function variables with proper typing
parse_task: Optional[Callable[[Union[bytes, str]], Any]] = None
calculate_task_distances: Optional[Callable[..., Dict[str, Any]]] = None
generate_task_geojson: Optional[Callable[[Any], Dict[Any, Any]]] = None

try:
    from pyxctsk import (
        calculate_task_distances,
        generate_task_geojson,
        parse_task,
    )

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

# Initialize AirScore function variables with proper typing
calculate_airscore_distances: Optional[Callable[[Any], Dict[str, Any]]] = None
generate_airscore_geojson: Optional[Callable[[Any, Dict[Any, Any]], Dict[Any, Any]]] = (
    None
)

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


task_viewer_bp = Blueprint("task_viewer", __name__)


@task_viewer_bp.route("/")
def index():
    """Render the main page with unified task selection.

    Returns:
        Response: Rendered HTML page for the main index.
    """
    tasks = get_available_tasks()
    return render_template(
        "index.html",
        tasks=tasks,
        xctrack_available=XCTRACK_AVAILABLE,
        airscore_available=AIRSCORE_AVAILABLE,
        url_prefix="task_viewer.",
    )


@task_viewer_bp.route("/compare")
def compare_index():
    """Render the comparison page with unified task selection.

    Returns:
        Response: Rendered HTML page for the comparison index.
    """
    tasks = get_available_tasks()
    return render_template(
        "compare.html",
        tasks=tasks,
        xctrack_available=XCTRACK_AVAILABLE,
        url_prefix="task_viewer.",
    )


@task_viewer_bp.route("/debug")
def debug_index():
    """Render the debug page with unified task selection.

    Returns:
        Response: Rendered HTML page for the debug index.
    """
    tasks = get_available_tasks()
    return render_template(
        "debug.html",
        tasks=tasks,
        xctrack_available=XCTRACK_AVAILABLE,
        url_prefix="task_viewer.",
    )


@task_viewer_bp.route("/task/<task_name>")
def show_task(task_name: str):
    """Display visualization and details for a specific task.

    Args:
        task_name (str): The name of the task to display.

    Returns:
        Response: Rendered HTML page for the task, or 404 if not found.

    Raises:
        werkzeug.exceptions.NotFound: If the task data is missing.
    """
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
        url_prefix="task_viewer.",
    )


@task_viewer_bp.route("/compare/<task_name>")
def compare_task(task_name: str):
    """Display comparison between downloaded data and xctrack calculations.

    Args:
        task_name (str): The name of the task to compare.

    Returns:
        Response: Rendered HTML page with comparison data, or error page if calculation fails.

    Raises:
        werkzeug.exceptions.NotFound: If the task or XCTSK file is missing.
        werkzeug.exceptions.InternalServerError: If the XCTrack module is not available.
    """
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
        task = parse_task(str(xctsk_path))  # type: ignore

        # Calculate distances using xctrack
        distance_results = calculate_task_distances(task, show_progress=False)  # type: ignore

        # Generate XCTrack GeoJSON data
        xctrack_geojson = generate_task_geojson(task)  # type: ignore

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
            url_prefix="task_viewer.",
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return render_template(
            "compare_view.html",
            task_name=task_name,
            error=f"Error calculating distances: {str(e)}",
            stacktrace=stacktrace,
            url_prefix="task_viewer.",
        )


@task_viewer_bp.route("/debug/<task_name>")
def debug_task(task_name: str):
    """Display debug information for generate_task_geojson with focus on goal lines.

    Args:
        task_name (str): The name of the task to debug.

    Returns:
        Response: Rendered HTML page with debug information, or error page if calculation fails.

    Raises:
        werkzeug.exceptions.NotFound: If the task or XCTSK file is missing.
        werkzeug.exceptions.InternalServerError: If the XCTrack module is not available.
    """
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
        task = parse_task(str(xctsk_path))  # type: ignore

        # Generate XCTrack GeoJSON data with debug information
        xctrack_geojson = generate_task_geojson(task)  # type: ignore

        return render_template(
            "debug_view.html",
            task_name=task_name,
            task=task,
            original_geojson=geojson_data,
            xctrack_geojson=xctrack_geojson,
            url_prefix="task_viewer.",
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return render_template(
            "debug_view.html",
            task_name=task_name,
            error=f"Error generating debug data: {str(e)}",
            stacktrace=stacktrace,
            url_prefix="task_viewer.",
        )


@task_viewer_bp.route("/airscore/<task_name>")
def airscore_task(task_name: str):
    """Display AirScore calculations for a specific task.

    Args:
        task_name (str): The name of the task to process with AirScore.

    Returns:
        Response: Rendered HTML page with AirScore results, or error page if calculation fails.
    """
    if not AIRSCORE_AVAILABLE:
        return render_template(
            "airscore_view.html",
            task_name=task_name,
            error="AirScore utilities not available",
            url_prefix="task_viewer.",
        )

    # Load and parse XCTSK file using xctrack module
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        abort(404, "XCTSK file not found")

    try:
        # Parse task using xctrack
        task = parse_task(str(xctsk_path))  # type: ignore

        # Calculate distances using AirScore clone
        airscore_results = calculate_airscore_distances(task)  # type: ignore

        # Generate AirScore GeoJSON for mapping
        airscore_geojson = generate_airscore_geojson(task, airscore_results)  # type: ignore

        return render_template(
            "airscore_view.html",
            task_name=task_name,
            airscore_results=airscore_results,
            airscore_geojson=airscore_geojson,
            url_prefix="task_viewer.",
        )

    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return render_template(
            "airscore_view.html",
            task_name=task_name,
            error=f"Error calculating distances: {str(e)}",
            stacktrace=stacktrace,
            url_prefix="task_viewer.",
        )


def create_app():
    """Create and configure the Flask app instance.

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__)
    app.register_blueprint(task_viewer_bp)
    app.register_blueprint(api_bp)
    return app


if __name__ == "__main__":
    create_app().run(debug=True, port=5001)
