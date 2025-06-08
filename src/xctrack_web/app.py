"""Flask web application for XCTrack task visualization - Refactored version."""

from pathlib import Path
from typing import Optional

try:
    from flask import Flask

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    # Check if xctrack is available - actual imports are in respective modules
    import importlib.util

    if importlib.util.find_spec("xctrack") is not None:
        XCTRACK_AVAILABLE = True
    else:
        XCTRACK_AVAILABLE = False
except ImportError:
    XCTRACK_AVAILABLE = False

from .cache_manager import CacheManager
from .task_manager import TaskManager
from .progress_tracker import ProgressTracker
from .routes import RouteHandlers


class XCTrackWebApp:
    """Web application for XCTrack task visualization."""

    def __init__(self, debug: bool = False, tasks_dir: Optional[str] = None):
        """Initialize the web application.

        Args:
            debug: Enable Flask debug mode
            tasks_dir: Directory containing task files
        """
        if not FLASK_AVAILABLE:
            raise ImportError(
                "Flask is required for the web interface. Install with: pip install flask"
            )

        if not XCTRACK_AVAILABLE:
            raise ImportError(
                "XCTrack core module is required. Install with: pip install ../xctrack"
            )

        # Initialize Flask app
        self.app = Flask(
            __name__,
            template_folder=str(Path(__file__).parent / "templates"),
            static_folder=str(Path(__file__).parent / "static"),
        )
        self.app.config["DEBUG"] = debug

        # Set up directories
        if tasks_dir:
            self.task_directory = Path(tasks_dir)
        else:
            # Default to tests directory in the parent project
            self.task_directory = Path(__file__).parent.parent.parent / "tests"

        # Directory for all saved task files (tasks and metadata)
        self.saved_tasks_dir = Path(__file__).parent / "static" / "saved_tasks"
        self.saved_tasks_dir.mkdir(parents=True, exist_ok=True)

        # Separate directory for cache files
        self.cache_dir = Path(__file__).parent / "static" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.cache_manager = CacheManager(self.cache_dir)
        self.task_manager = TaskManager(self.task_directory, self.saved_tasks_dir)
        self.progress_tracker = ProgressTracker()
        self.route_handlers = RouteHandlers(
            self.task_manager, self.cache_manager, self.progress_tracker
        )

        self.setup_routes()

    def setup_routes(self):
        """Setup Flask routes."""

        # Main pages
        self.app.route("/")(self.route_handlers.index)
        self.app.route("/task/<task_code>")(self.route_handlers.view_task)

        # Task API endpoints
        self.app.route("/api/task/<task_code>")(self.route_handlers.api_get_task)
        self.app.route("/api/task/<task_code>/cache-status")(
            self.route_handlers.api_get_cache_status
        )
        self.app.route("/api/task/<task_code>/progress")(
            self.route_handlers.api_get_task_progress
        )
        self.app.route("/api/task/<task_code>/qr")(self.route_handlers.api_get_qr_code)
        self.app.route("/api/task/<task_code>/optimized-route")(
            self.route_handlers.api_get_optimized_route
        )
        self.app.route("/api/task/<task_code>/route-progress")(
            self.route_handlers.api_get_route_progress
        )

        # Upload and file management
        self.app.route("/upload", methods=["POST"])(self.route_handlers.upload_task)

        # Task listing endpoints
        self.app.route("/api/tasks")(self.route_handlers.api_list_tasks)
        self.app.route("/api/saved-tasks")(self.route_handlers.api_list_saved_tasks)
        self.app.route("/api/task/saved/<filename>")(
            self.route_handlers.api_get_saved_task
        )

        # Cache management
        self.app.route("/api/cache/info")(self.route_handlers.api_get_cache_info)

    def run(
        self, host: str = "127.0.0.1", port: int = 5000, debug: Optional[bool] = None
    ):
        """Run the web application."""
        if debug is not None:
            self.app.config["DEBUG"] = debug
        self.app.run(host=host, port=port, debug=self.app.config["DEBUG"])


def create_app(debug: bool = False, task_directory: Optional[str] = None) -> Flask:
    """Create and configure the Flask app."""
    web_app = XCTrackWebApp(debug=debug, task_directory=task_directory)
    return web_app.app
