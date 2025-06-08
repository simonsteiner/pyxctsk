"""Progress tracking for long-running operations."""

from datetime import datetime
from typing import Dict, Any


class ProgressTracker:
    """Handles progress tracking for long-running operations."""

    def __init__(self):
        """Initialize the progress tracker."""
        self._progress_data = {}

    def set_progress(self, operation_id: str, message: str, progress: int, details: str = "") -> None:
        """Set progress information for an operation.
        
        Args:
            operation_id: Unique identifier for the operation
            message: Progress message
            progress: Progress percentage (0-100)
            details: Additional details about the current step
        """
        self._progress_data[operation_id] = {
            "message": message,
            "progress": progress,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }

    def get_progress(self, operation_id: str) -> Dict[str, Any]:
        """Get progress information for an operation.
        
        Args:
            operation_id: Unique identifier for the operation
            
        Returns:
            Progress data or default values if not found
        """
        return self._progress_data.get(operation_id, {
            "message": "Operation not found", 
            "progress": 0, 
            "details": ""
        })

    def clear_progress(self, operation_id: str) -> None:
        """Clear progress information for an operation.
        
        Args:
            operation_id: Unique identifier for the operation
        """
        if operation_id in self._progress_data:
            del self._progress_data[operation_id]

    def get_all_progress(self) -> Dict[str, Dict[str, Any]]:
        """Get all current progress data.
        
        Returns:
            Dictionary of all progress data keyed by operation_id
        """
        return self._progress_data.copy()

    def clear_all_progress(self) -> None:
        """Clear all progress data."""
        self._progress_data.clear()
