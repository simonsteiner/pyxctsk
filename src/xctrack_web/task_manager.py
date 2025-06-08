"""Task management for XCTrack web application."""

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from xctrack.parser import parse_task
from xctrack.task import Task
from xctrack.distance import (
    calculate_task_distances,
    TaskTurnpoint,
    optimized_route_coordinates,
    optimized_distance,
    calculate_sss_info,
)


class TaskManager:
    """Handles task file operations and management."""

    def __init__(self, task_directory: Path, saved_tasks_dir: Path):
        """Initialize the task manager.
        
        Args:
            task_directory: Directory containing sample task files
            saved_tasks_dir: Directory for saved uploaded tasks
        """
        self.task_directory = task_directory
        self.saved_tasks_dir = saved_tasks_dir
        self.saved_tasks_dir.mkdir(parents=True, exist_ok=True)

    def find_task_file(self, task_code: str) -> Optional[Path]:
        """Find a task file by code.
        
        Args:
            task_code: The task code to search for
            
        Returns:
            Path to the task file or None if not found
        """
        # First try saved tasks (uploaded files)
        if task_code.endswith(".xctsk"):
            # Direct filename lookup for saved tasks
            saved_task_file = self.saved_tasks_dir / task_code
            if saved_task_file.exists():
                return saved_task_file
        else:
            # Try with .xctsk extension for saved tasks
            saved_task_file = self.saved_tasks_dir / f"{task_code}.xctsk"
            if saved_task_file.exists():
                return saved_task_file

        # Try different naming patterns for sample tasks
        patterns = [
            f"task_{task_code}.xctsk",
            f"{task_code}.xctsk",
            "task_meta.xctsk" if task_code == "meta" else None,
        ]

        for pattern in patterns:
            if pattern:
                task_file = self.task_directory / pattern
                if task_file.exists():
                    return task_file

        return None

    def load_task(self, task_code: str) -> Optional[Task]:
        """Load a task by its code.
        
        Args:
            task_code: The task code to load
            
        Returns:
            Parsed Task object or None if not found
        """
        task_file = self.find_task_file(task_code)
        if task_file and task_file.exists():
            with open(task_file, "r") as f:
                task_data = f.read()
            return parse_task(task_data)
        return None

    def save_uploaded_task(self, file_data: bytes, original_filename: str, task: Task) -> Dict[str, str]:
        """Save an uploaded task file and its metadata.
        
        Args:
            file_data: Raw file data
            original_filename: Original filename
            task: Parsed task object
            
        Returns:
            Dictionary with saved file information
        """
        # Generate a unique filename based on timestamp and original filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if original_filename.endswith(".xctsk"):
            base_name = original_filename[:-6]  # Remove .xctsk extension
        else:
            base_name = original_filename

        # Clean the filename
        clean_name = "".join(
            c for c in base_name if c.isalnum() or c in (" ", "-", "_")
        ).rstrip()
        if not clean_name:
            clean_name = "uploaded_task"

        saved_filename = f"{timestamp}_{clean_name}.xctsk"
        saved_file_path = self.saved_tasks_dir / saved_filename

        # Save the original task file
        with open(saved_file_path, "wb") as f:
            f.write(file_data)

        return {
            "filename": saved_filename,
            "timestamp": timestamp,
            "clean_name": clean_name
        }

    def save_task_metadata(self, save_info: Dict[str, str], original_filename: str, 
                          task_dict: Dict[str, Any], cache_key: str) -> None:
        """Save task metadata for quick access.
        
        Args:
            save_info: Save information from save_uploaded_task
            original_filename: Original filename
            task_dict: Task dictionary data
            cache_key: Cache key for the task
        """
        metadata = {
            "filename": save_info["filename"],
            "original_filename": original_filename,
            "upload_time": save_info["timestamp"],
            "task_name": (
                task_dict.get("turnpoints", [{}])[0].get("name", save_info["clean_name"])
                if task_dict.get("turnpoints")
                else save_info["clean_name"]
            ),
            "distance": task_dict["stats"]["totalDistance"],
            "optimized_distance": task_dict["stats"]["totalOptimizedDistance"],
            "turnpoint_count": task_dict["stats"]["turnpointCount"],
            "task_type": task_dict["taskType"],
            "cache_key": cache_key,
        }

        metadata_file = (
            self.saved_tasks_dir / f"{save_info['timestamp']}_{save_info['clean_name']}-metadata.json"
        )
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

    def get_saved_tasks(self) -> List[Dict[str, Any]]:
        """Get list of saved tasks from metadata files.
        
        Returns:
            List of saved task metadata
        """
        saved_tasks = []

        if self.saved_tasks_dir.exists():
            for metadata_file in self.saved_tasks_dir.glob("*-metadata.json"):
                try:
                    with open(metadata_file, "r") as f:
                        metadata = json.load(f)

                    saved_tasks.append(
                        {
                            "code": metadata["filename"],
                            "name": metadata.get(
                                "task_name", metadata["original_filename"]
                            ),
                            "distance": metadata["distance"],
                            "optimizedDistance": metadata["optimized_distance"],
                            "turnpoints": metadata["turnpoint_count"],
                            "type": metadata["task_type"],
                            "source": "uploaded",
                            "upload_time": metadata["upload_time"],
                            "original_filename": metadata["original_filename"],
                        }
                    )
                except Exception:
                    continue

        # Sort by upload time (newest first)
        saved_tasks.sort(key=lambda x: x["upload_time"], reverse=True)
        return saved_tasks

    def get_sample_tasks(self, cache_manager) -> List[Dict[str, Any]]:
        """Get list of sample tasks from the tests directory.
        
        Args:
            cache_manager: Cache manager for distance calculations
            
        Returns:
            List of sample task metadata
        """
        tasks = []

        if self.task_directory.exists():
            for task_file in self.task_directory.glob("*.xctsk"):
                try:
                    with open(task_file, "r") as f:
                        task_data = f.read()
                    task = parse_task(task_data)

                    # Check if we have cached distance data first
                    cache_key = cache_manager.get_task_cache_key(task)
                    distance_data = cache_manager.load_cached_distances(cache_key)

                    if distance_data is None:
                        # Calculate if not cached (with faster settings for listing)
                        distance_data = calculate_task_distances(
                            task, angle_step=15
                        )  # Faster for listings
                        cache_manager.save_cached_distances(cache_key, distance_data)

                    tasks.append(
                        {
                            "code": task_file.stem.replace("task_", ""),
                            "name": f"Task {task_file.stem}",
                            "distance": distance_data["center_distance_km"],
                            "optimizedDistance": distance_data[
                                "optimized_distance_km"
                            ],
                            "savings": distance_data["savings_km"],
                            "savingsPercent": distance_data["savings_percent"],
                            "turnpoints": len(task.turnpoints),
                            "cylinders": sum(
                                1 for tp in task.turnpoints if tp.radius > 0
                            ),
                            "type": task.task_type.value,
                            "source": "sample",
                        }
                    )
                except Exception as e:
                    print(f"Error processing task {task_file}: {e}")
                    continue

        return tasks

    def task_to_dict(self, task: Task, cache_manager, progress_tracker=None, task_code: str = None) -> Dict[str, Any]:
        """Convert a task to a dictionary for JSON serialization.
        
        Args:
            task: The task to convert
            cache_manager: Cache manager for distance calculations
            progress_tracker: Optional progress tracker
            task_code: Optional task code for progress tracking
            
        Returns:
            Dictionary representation of the task
        """
        # Check persistent cache first
        cache_key = cache_manager.get_task_cache_key(task)
        distance_data = cache_manager.load_cached_distances(cache_key)

        if distance_data is None:
            # Calculate distances with faster settings for web interface
            if progress_tracker and task_code:
                progress_tracker.set_progress(task_code, "Calculating distances...", 50, 
                                           f"Processing {len(task.turnpoints)} turnpoints")
            
            print(
                f"Calculating distances for task with {len(task.turnpoints)} turnpoints..."
            )
            distance_data = calculate_task_distances(
                task, angle_step=10
            )  # Use 10° for faster web response

            if progress_tracker and task_code:
                progress_tracker.set_progress(task_code, "Optimizing route...", 70, 
                                           "Finding optimal path between turnpoints")

            # Add optimized route data to cache
            route_data = self.calculate_and_cache_route_data(
                task, cache_key, cache_manager, progress_tracker, angle_step=10, task_code=task_code
            )
            distance_data["route_data"] = route_data

            # Cache the data
            cache_manager.save_cached_distances(cache_key, distance_data)
            print(
                f"Distance calculation complete: {distance_data['center_distance_km']:.1f}km center, {distance_data['optimized_distance_km']:.1f}km optimized"
            )

        # If cache exists but doesn't have route data, calculate and add it
        if "route_data" not in distance_data:
            if progress_tracker and task_code:
                progress_tracker.set_progress(task_code, "Adding route data...", 80, 
                                           "Calculating optimized route coordinates")
            
            print("Adding route data to existing cache...")
            route_data = self.calculate_and_cache_route_data(
                task, cache_key, cache_manager, progress_tracker, angle_step=10, task_code=task_code
            )
            distance_data["route_data"] = route_data
            # Update cache
            cache_manager.save_cached_distances(cache_key, distance_data)

        result = {
            "taskType": task.task_type.value,
            "version": task.version,
            "earthModel": task.earth_model.value if task.earth_model else None,
            "turnpoints": [],
            "stats": {},
        }

        # Add turnpoint data with both basic and optimized distances
        for i, tp in enumerate(task.turnpoints):
            # Get distance data for this turnpoint, handling missing data gracefully
            tp_distance_data = {}
            if i < len(distance_data.get("turnpoints", [])):
                tp_distance_data = distance_data["turnpoints"][i]

            tp_data = {
                "index": i,
                "name": tp.waypoint.name,
                "description": tp.waypoint.description or "",
                "lat": tp.waypoint.lat,
                "lon": tp.waypoint.lon,
                "alt": tp.waypoint.alt_smoothed,
                "radius": tp.radius,
                "type": tp.type.value if tp.type else "",
                "distance": 0,  # Distance from previous turnpoint (basic calculation)
                "cumulative_center_km": tp_distance_data.get("cumulative_center_km", 0),
                "cumulative_optimized_km": tp_distance_data.get(
                    "cumulative_optimized_km", 0
                ),
                # Keep old field names for backwards compatibility
                "cumulative_distance": tp_distance_data.get("cumulative_center_km", 0),
                "cumulative_optimized_distance": tp_distance_data.get(
                    "cumulative_optimized_km", 0
                ),
            }

            # Calculate basic distance from previous turnpoint for compatibility
            if i > 0:
                prev_tp = task.turnpoints[i - 1]
                distance = self._calculate_distance(
                    prev_tp.waypoint.lat,
                    prev_tp.waypoint.lon,
                    tp.waypoint.lat,
                    tp.waypoint.lon,
                )
                tp_data["distance"] = round(distance, 1)

            result["turnpoints"].append(tp_data)

        # Add task configuration
        if task.takeoff:
            result["takeoff"] = {
                "timeOpen": (
                    str(task.takeoff.time_open) if task.takeoff.time_open else None
                ),
                "timeClose": (
                    str(task.takeoff.time_close) if task.takeoff.time_close else None
                ),
            }

        if task.sss:
            result["sss"] = {
                "type": task.sss.type.value,
                "direction": task.sss.direction.value,
                "timeGates": [str(gate) for gate in task.sss.time_gates],
                "timeClose": str(task.sss.time_close) if task.sss.time_close else None,
            }

        if task.goal:
            result["goal"] = {
                "type": task.goal.type.value if task.goal.type else None,
                "deadline": str(task.goal.deadline) if task.goal.deadline else None,
            }

        # Add enhanced statistics with optimized distance calculations
        result["stats"] = {
            "totalDistance": distance_data["center_distance_km"],
            "totalOptimizedDistance": distance_data["optimized_distance_km"],
            "optimizationSavings": distance_data["savings_km"],
            "optimizationSavingsPercent": distance_data["savings_percent"],
            "turnpointCount": len(task.turnpoints),
            "taskType": task.task_type.value,
            "cylinderCount": sum(1 for tp in task.turnpoints if tp.radius > 0),
        }

        return result

    def calculate_and_cache_route_data(
        self, task: Task, cache_key: str, cache_manager, progress_tracker=None, 
        angle_step: int = 10, task_code: str = None
    ) -> Dict[str, Any]:
        """Calculate optimized route data and add it to cache.
        
        Args:
            task: The task to calculate route for
            cache_key: Cache key for the task
            cache_manager: Cache manager instance
            progress_tracker: Optional progress tracker
            angle_step: Angle step for calculations
            task_code: Optional task code for progress tracking
            
        Returns:
            Route data dictionary
        """
        if progress_tracker and task_code:
            progress_tracker.set_progress(task_code, "Preparing route calculation...", 0, 
                                       "Converting turnpoints for optimization")

        # Convert task turnpoints to distance calculation format
        turnpoints = []
        for tp in task.turnpoints:
            task_tp = TaskTurnpoint(tp.waypoint.lat, tp.waypoint.lon, tp.radius)
            turnpoints.append(task_tp)

        if progress_tracker and task_code:
            progress_tracker.set_progress(task_code, "Calculating route coordinates...", 25, 
                                       f"Optimizing path through {len(turnpoints)} turnpoints")

        # Calculate optimized route coordinates
        route_coords = optimized_route_coordinates(
            turnpoints, task_turnpoints=task.turnpoints, angle_step=angle_step
        )

        # Convert to the format expected by the frontend
        route_data = [{"lat": lat, "lon": lon} for lat, lon in route_coords]

        if progress_tracker and task_code:
            progress_tracker.set_progress(task_code, "Calculating optimized distance...", 50, 
                                       "Computing total route distance")

        # Calculate optimized distance
        total_distance = optimized_distance(
            turnpoints, angle_step=angle_step, show_progress=False
        )

        if progress_tracker and task_code:
            progress_tracker.set_progress(task_code, "Checking for SSS information...", 75, 
                                       "Analyzing start sector geometry")

        # Check for SSS and add SSS info if needed
        sss_info = calculate_sss_info(
            task.turnpoints, route_coords, angle_step=angle_step
        )
        takeoff_center = None

        if task.turnpoints:
            takeoff_center = {
                "lat": task.turnpoints[0].waypoint.lat,
                "lon": task.turnpoints[0].waypoint.lon,
            }

        if progress_tracker and task_code:
            progress_tracker.set_progress(task_code, "Finalizing route data...", 90, 
                                       "Preparing route for display")

        route_cache_data = {
            "route": route_data,
            "distance_km": total_distance / 1000.0,
            "angle_step": angle_step,
        }

        if sss_info:
            route_cache_data["sss_info"] = sss_info
            route_cache_data["takeoff_center"] = takeoff_center

        if progress_tracker and task_code:
            progress_tracker.set_progress(task_code, "Route calculation complete", 100, 
                                       f"Optimized route ready ({total_distance/1000:.1f}km)")

        return route_cache_data

    def _calculate_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two coordinates in km using Haversine formula.
        
        Args:
            lat1, lon1: First coordinate
            lat2, lon2: Second coordinate
            
        Returns:
            Distance in kilometers
        """
        # Convert to radians
        lat1_r = math.radians(lat1)
        lon1_r = math.radians(lon1)
        lat2_r = math.radians(lat2)
        lon2_r = math.radians(lon2)

        # Haversine formula
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Earth radius in km
        R = 6371
        return R * c
