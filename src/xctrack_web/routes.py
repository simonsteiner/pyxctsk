"""Flask routes for XCTrack web application."""

import base64
from io import BytesIO
from threading import Timer

try:
    from flask import render_template, request, jsonify

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    from xctrack.parser import parse_task
    from xctrack.utils import generate_qr_code, QR_CODE_SUPPORT

    XCTRACK_AVAILABLE = True
except ImportError:
    XCTRACK_AVAILABLE = False


class RouteHandlers:
    """Handles all Flask route endpoints."""

    def __init__(self, task_manager, cache_manager, progress_tracker):
        """Initialize route handlers.

        Args:
            task_manager: TaskManager instance
            cache_manager: CacheManager instance
            progress_tracker: ProgressTracker instance
        """
        self.task_manager = task_manager
        self.cache_manager = cache_manager
        self.progress_tracker = progress_tracker

    def index(self):
        """Main page."""
        return render_template("index.html")

    def view_task(self, task_code: str):
        """View a task by code."""
        return render_template("task.html", task_code=task_code)

    def api_get_task(self, task_code: str):
        """API endpoint to get task data."""
        try:
            # Try to load the task file first
            task_file = self.task_manager.find_task_file(task_code)

            if task_file and task_file.exists():
                with open(task_file, "r") as f:
                    task_data = f.read()
                task = parse_task(task_data)

                # Check if we have complete cached data
                cache_key = self.cache_manager.get_task_cache_key(task)
                is_fully_cached = self.cache_manager.is_task_fully_cached(cache_key)

                if is_fully_cached:
                    # Return cached data immediately without progress tracking
                    result = self.task_manager.task_to_dict(task, self.cache_manager)
                    return jsonify(result)
                else:
                    # Need to calculate data, so show progress
                    self.progress_tracker.set_progress(
                        task_code,
                        "Loading task file...",
                        10,
                        "Task found, checking cache",
                    )
                    self.progress_tracker.set_progress(
                        task_code,
                        "Parsing task data...",
                        30,
                        "Reading and validating task format",
                    )
                    self.progress_tracker.set_progress(
                        task_code,
                        "Converting to web format...",
                        50,
                        "Preparing task for processing",
                    )

                    result = self.task_manager.task_to_dict(
                        task, self.cache_manager, self.progress_tracker, task_code
                    )

                    self.progress_tracker.set_progress(
                        task_code, "Task processing complete", 100, "Ready to display"
                    )
                    # Clear progress after a short delay
                    Timer(
                        2.0, lambda: self.progress_tracker.clear_progress(task_code)
                    ).start()

                    return jsonify(result)
            else:
                self.progress_tracker.clear_progress(task_code)
                return jsonify({"error": "Task not found"}), 404
        except Exception as e:
            self.progress_tracker.clear_progress(task_code)
            return jsonify({"error": str(e)}), 500

    def api_get_cache_status(self, task_code: str):
        """API endpoint to check if task data is fully cached."""
        try:
            # Try to load the task file
            task_file = self.task_manager.find_task_file(task_code)

            if task_file and task_file.exists():
                with open(task_file, "r") as f:
                    task_data = f.read()
                task = parse_task(task_data)

                # Check if we have complete cached data
                cache_key = self.cache_manager.get_task_cache_key(task)
                distance_data = self.cache_manager.load_cached_distances(cache_key)
                is_fully_cached = self.cache_manager.is_task_fully_cached(cache_key)

                return jsonify(
                    {
                        "fully_cached": is_fully_cached,
                        "has_distance_data": distance_data is not None,
                        "has_route_data": distance_data is not None
                        and "route_data" in distance_data,
                    }
                )
            else:
                return jsonify({"error": "Task not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def api_get_task_progress(self, task_code: str):
        """API endpoint to get task loading progress."""
        progress = self.progress_tracker.get_progress(task_code)
        return jsonify(progress)

    def api_get_qr_code(self, task_code: str):
        """API endpoint to get QR code for a task."""
        try:
            if not QR_CODE_SUPPORT:
                return jsonify({"error": "QR code support not available"}), 500

            # Load task
            task = self.task_manager.load_task(task_code)
            if not task:
                return jsonify({"error": "Task not found"}), 404

            # Generate QR code
            qr_task = task.to_qr_code_task()
            qr_string = qr_task.to_string()
            qr_image = generate_qr_code(qr_string, size=512)

            # Convert to base64
            img_buffer = BytesIO()
            qr_image.save(img_buffer, format="PNG")
            img_buffer.seek(0)
            img_b64 = base64.b64encode(img_buffer.getvalue()).decode()

            return jsonify(
                {
                    "qr_code": f"data:image/png;base64,{img_b64}",
                    "qr_string": qr_string,
                }
            )
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def upload_task(self):
        """Upload and parse a task file."""
        try:
            if "file" not in request.files:
                return jsonify({"error": "No file uploaded"}), 400

            file = request.files["file"]
            if file.filename == "":
                return jsonify({"error": "No file selected"}), 400

            # Parse the uploaded task
            task_data = file.read()
            task = parse_task(task_data)
            task_dict = self.task_manager.task_to_dict(task, self.cache_manager)

            # Save the task file
            save_info = self.task_manager.save_uploaded_task(
                task_data, file.filename, task
            )

            # Save metadata
            cache_key = self.cache_manager.get_task_cache_key(task)
            self.task_manager.save_task_metadata(
                save_info, file.filename, task_dict, cache_key
            )

            # Add the saved file info to the response
            task_dict["saved_as"] = save_info["filename"]
            task_dict["saved_timestamp"] = save_info["timestamp"]

            return jsonify(task_dict)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def api_list_tasks(self):
        """API endpoint to list available tasks."""
        try:
            # Load sample tasks from tests directory
            sample_tasks = self.task_manager.get_sample_tasks(self.cache_manager)

            # Load saved tasks from metadata
            saved_tasks = self.task_manager.get_saved_tasks()

            # Combine both lists
            all_tasks = sample_tasks + saved_tasks

            return jsonify({"tasks": all_tasks})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def api_list_saved_tasks(self):
        """API endpoint to list only saved tasks."""
        try:
            saved_tasks = self.task_manager.get_saved_tasks()
            return jsonify({"tasks": saved_tasks})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def api_get_saved_task(self, filename: str):
        """API endpoint to get saved task data."""
        try:
            task_file = self.task_manager.saved_tasks_dir / filename

            if task_file.exists() and task_file.suffix == ".xctsk":
                with open(task_file, "r") as f:
                    task_data = f.read()
                task = parse_task(task_data)
                return jsonify(self.task_manager.task_to_dict(task, self.cache_manager))
            else:
                return jsonify({"error": "Saved task not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def api_get_optimized_route(self, task_code: str):
        """API endpoint to get optimized route coordinates for a task."""
        try:
            # Initialize progress for route calculation
            route_id = f"{task_code}_route"
            self.progress_tracker.set_progress(
                route_id, "Loading task for route optimization...", 10
            )

            # Load task
            task = self.task_manager.load_task(task_code)
            if not task:
                self.progress_tracker.clear_progress(route_id)
                return jsonify({"error": "Task not found"}), 404

            # Check cache first
            cache_key = self.cache_manager.get_task_cache_key(task)
            distance_data = self.cache_manager.load_cached_distances(cache_key)

            if distance_data and "route_data" in distance_data:
                # Return cached route data
                self.progress_tracker.clear_progress(route_id)
                return jsonify(distance_data["route_data"])
            else:
                # Calculate route data if not cached
                self.progress_tracker.set_progress(
                    route_id,
                    "Calculating optimized route...",
                    50,
                    "Computing optimal path between turnpoints",
                )

                print(f"Calculating optimized route for task {task_code}...")
                route_data = self.task_manager.calculate_and_cache_route_data(
                    task,
                    cache_key,
                    self.cache_manager,
                    self.progress_tracker,
                    angle_step=10,
                    task_code=task_code,
                )

                # Update cache if it exists
                if distance_data:
                    distance_data["route_data"] = route_data
                    self.cache_manager.save_cached_distances(cache_key, distance_data)

                self.progress_tracker.clear_progress(route_id)
                return jsonify(route_data)
        except Exception as e:
            self.progress_tracker.clear_progress(f"{task_code}_route")
            return jsonify({"error": str(e)}), 500

    def api_get_route_progress(self, task_code: str):
        """API endpoint to get route calculation progress."""
        progress = self.progress_tracker.get_progress(f"{task_code}_route")
        return jsonify(progress)

    def api_get_cache_info(self):
        """API endpoint to get cache information."""
        try:
            cache_info = self.cache_manager.get_cache_info()
            return jsonify(cache_info)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
