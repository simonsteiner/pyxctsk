"""
XCTrack Web Interface

A web-based visual interface for analyzing XCTrack task files.
This module provides a Flask-based web application for uploading, visualizing,
and analyzing paragliding competition tasks.

Requires the xctrack core module for task parsing and analysis.
"""

try:
    from .app import XCTrackWebApp
    from .server import create_app, run_development_server, run_production_server

    _web_available = True
except ImportError:
    _web_available = False
    XCTrackWebApp = None
    create_app = None
    run_development_server = None
    run_production_server = None

__version__ = "1.0.0"
__all__ = [
    "XCTrackWebApp",
    "create_app",
    "run_development_server",
    "run_production_server",
    "web_available",
]


def web_available():
    """Check if web interface dependencies are available"""
    return _web_available
