"""
XCTrack Web Server Module

This module provides the main server functionality for the XCTrack web interface.
It creates and configures the Flask application with all necessary routes and settings.
"""

import sys
from pathlib import Path
from typing import Optional

from .app import XCTrackWebApp

# Add parent directory to path for xctrack imports
current_dir = Path(__file__).parent.absolute()
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

try:
    from flask import Flask
except ImportError:
    Flask = None


def create_app(tasks_dir: Optional[str] = None, config: Optional[dict] = None):
    """
    Create and configure the XCTrack Flask application.

    Args:
        tasks_dir: Optional directory containing task files
        config: Optional configuration dictionary

    Returns:
        Flask application instance
    """
    # Create the web application
    web_app = XCTrackWebApp(tasks_dir=tasks_dir)
    app = web_app.app

    # Apply additional configuration if provided
    if config:
        app.config.update(config)

    # Configure for production if needed
    if not app.debug:
        # Production settings
        app.config.update(
            {
                "JSON_SORT_KEYS": False,
                "JSONIFY_PRETTYPRINT_REGULAR": False,
            }
        )

    return app


def run_development_server(
    host: str = "127.0.0.1",
    port: int = 5000,
    debug: bool = True,
    tasks_dir: Optional[str] = None,
):
    """
    Run the development server with specified configuration.

    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
        tasks_dir: Directory containing task files
    """
    app = create_app(tasks_dir=tasks_dir)
    app.run(host=host, port=port, debug=debug)


def run_production_server(
    host: str = "0.0.0.0", port: int = 8080, tasks_dir: Optional[str] = None
):
    """
    Run the production server with optimized settings.

    Args:
        host: Host to bind to
        port: Port to bind to
        tasks_dir: Directory containing task files
    """
    config = {
        "DEBUG": False,
        "TESTING": False,
        "JSON_SORT_KEYS": False,
        "JSONIFY_PRETTYPRINT_REGULAR": False,
    }

    app = create_app(tasks_dir=tasks_dir, config=config)

    # For production, you would typically use a WSGI server like Gunicorn
    # This is just for testing purposes
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    # Run development server if called directly
    run_development_server()
