"""API routes for task_viewer Flask app.

Contains all API endpoints (JSON, KML, comparison, airscore).
"""

from flask import Blueprint, Response, abort, jsonify

try:
    from pyxctsk import (
        calculate_task_distances,
        generate_task_geojson,
        parse_task,
        task_to_kml,
    )

    XCTRACK_AVAILABLE = True
except ImportError as e:
    print(f"Warning: xctrack module not available: {e}")
    XCTRACK_AVAILABLE = False

from shared import (
    XCTSK_DIR,
    load_task_data,
    prepare_comparison_data,
)

api_bp = Blueprint("api", __name__)


@api_bp.route("/api/task/<task_name>")
def task_api(task_name: str):
    """Return task data in JSON format via API endpoint.

    Args:
        task_name (str): The name of the task to retrieve.

    Returns:
        Response: Flask JSON response containing task and geojson data, or 404 if not found.

    Raises:
        werkzeug.exceptions.NotFound: If the task data is missing.
    """
    json_data, geojson_data = load_task_data(task_name)

    if not json_data or not geojson_data:
        abort(404)

    return jsonify(
        {"task_name": task_name, "json_data": json_data, "geojson_data": geojson_data}
    )


@api_bp.route("/api/kml/<task_name>.kml")
def kml_task_api(task_name: str):
    """Return KML for a given task as a downloadable file via API endpoint.

    Args:
        task_name (str): The name of the task to retrieve as KML.

    Returns:
        Response: Flask response with KML data and appropriate headers, or error message and status code.
    """
    if not XCTRACK_AVAILABLE:
        return jsonify({"error": "XCTrack module not available"}), 500

    # Load and parse XCTSK file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return jsonify({"error": "XCTSK file not found"}), 404

    try:
        task = parse_task(str(xctsk_path))  # type: ignore
        kml_str = task_to_kml(task)  # type: ignore
        return Response(
            kml_str,
            mimetype="application/vnd.google-earth.kml+xml",
            headers={"Content-Disposition": f"attachment; filename={task_name}.kml"},
        )
    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return (
            jsonify(
                {
                    "error": f"Error generating KML: {str(e)}",
                    "stacktrace": stacktrace,
                }
            ),
            500,
        )


@api_bp.route("/api/compare/<task_name>")
def compare_task_api(task_name: str):
    """Return comparison data in JSON format via API endpoint.

    Args:
        task_name (str): The name of the task to compare.

    Returns:
        Response: Flask JSON response with comparison data, or error message and status code.
    """
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
        task = parse_task(str(xctsk_path))  # type: ignore
        distance_results = calculate_task_distances(task, show_progress=False)  # type: ignore
        xctrack_geojson = generate_task_geojson(task)  # type: ignore
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
