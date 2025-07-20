"""API routes for the Task Viewer Flask app.

Provides endpoints for task data retrieval, KML export, comparison, and task listing.
"""

from flask import Blueprint, Response, abort, jsonify, make_response

try:
    from pyxctsk import (
        calculate_task_distances,
        generate_qrcode_image,
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

api_bp: Blueprint = Blueprint("api", __name__)


def json_error(message: str, status: int = 500, **kwargs) -> tuple:
    """Return a standardized JSON error response.

    Args:
        message (str): Error message.
        status (int): HTTP status code.
        **kwargs: Additional fields to include in the response.

    Returns:
        tuple: (Flask JSON response, status code)
    """
    payload = {"error": message}
    payload.update(kwargs)
    return jsonify(payload), status


@api_bp.route("/api/qrcode_image/<task_name>.png")
def qrcode_image(task_name: str) -> Response | tuple[Response, int]:
    """Return a PNG QR code image for the given task.

    Args:
        task_name (str): Name of the task whose QR code to generate.

    Returns:
        Response: Flask response with PNG image of the QR code, or error message and status code.

    Raises:
        werkzeug.exceptions.NotFound: If the task or QR code string is missing.
    """

    # Always generate QR code string from .xctsk file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return json_error(".xctsk file not found for this task", 404)
    try:
        from pyxctsk import parse_task

        task = parse_task(str(xctsk_path))
        if hasattr(task, "to_qr_code_task"):
            qr_task = task.to_qr_code_task()
            qr_string = qr_task.to_string()
        else:
            return json_error("Task object does not support QR code generation", 500)
    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return json_error(
            f"Error generating QR code string from task: {str(e)}",
            500,
            stacktrace=stacktrace,
        )

    try:
        img = generate_qrcode_image(qr_string, size=512)
        from io import BytesIO

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        response = make_response(buf.getvalue())
        response.mimetype = "image/png"
        response.headers["Content-Disposition"] = f"inline; filename={task_name}.png"
        return response
    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return json_error(
            f"Error generating QR code image: {str(e)}", 500, stacktrace=stacktrace
        )


@api_bp.route("/api/task/<task_name>")
def task_api(task_name: str) -> Response:
    """Return task data in JSON format for a given task.

    Args:
        task_name (str): Name of the task to retrieve.

    Returns:
        Response: Flask JSON response with task and geojson data, or 404 if not found.

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
def kml_task_api(task_name: str) -> Response | tuple[Response, int]:
    """Return KML for a given task as a downloadable file via API endpoint.

    Args:
        task_name (str): The name of the task to retrieve as KML.

    Returns:
        Response: Flask response with KML data and appropriate headers, or error message and status code.
    """
    if not XCTRACK_AVAILABLE:
        return json_error("XCTrack module not available", 500)

    # Load and parse XCTSK file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return json_error("XCTSK file not found", 404)

    try:
        task = parse_task(str(xctsk_path))  # type: ignore
        kml_str = task_to_kml(task)  # type: ignore
        response = make_response(kml_str)
        response.mimetype = "application/vnd.google-earth.kml+xml"
        response.headers["Content-Disposition"] = (
            f"attachment; filename={task_name}.kml"
        )
        return response
    except Exception as e:
        import traceback

        stacktrace = traceback.format_exc()
        return json_error(f"Error generating KML: {str(e)}", 500, stacktrace=stacktrace)


@api_bp.route("/api/compare/<task_name>")
def compare_task_api(task_name: str) -> Response | tuple[Response, int]:
    """Return comparison data in JSON format via API endpoint.

    Args:
        task_name (str): The name of the task to compare.

    Returns:
        Response: Flask JSON response with comparison data, or error message and status code.
    """
    if not XCTRACK_AVAILABLE:
        return json_error("XCTrack module not available", 500)

    # Load original task data
    json_data, geojson_data = load_task_data(task_name)
    if not json_data:
        return json_error("Task data not found", 404)

    # Load and parse XCTSK file
    xctsk_path = XCTSK_DIR / f"{task_name}.xctsk"
    if not xctsk_path.exists():
        return json_error("XCTSK file not found", 404)

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
        return json_error(
            f"Error calculating distances: {str(e)}", 500, stacktrace=stacktrace
        )


@api_bp.route("/api/list_tasks")
def list_tasks_api() -> Response | tuple[Response, int]:
    """Return a list of available task base names (without extension).

    Returns:
        Response: Flask JSON response with task names or error with status code.
    """
    try:
        # List all .xctsk files in XCTSK_DIR
        task_files: list[str] = [
            f.stem for f in XCTSK_DIR.glob("*.xctsk") if f.is_file()
        ]
        return jsonify({"tasks": sorted(task_files)})
    except Exception as e:
        return json_error(f"Error listing tasks: {str(e)}", 500)
