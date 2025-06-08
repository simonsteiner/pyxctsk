"""Cache management for XCTrack web application."""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from xctrack.task import Task


class CacheManager:
    """Handles caching of distance calculations and route data."""

    def __init__(self, cache_dir: Path):
        """Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache for faster access
        self._memory_cache = {}

    def get_task_cache_key(self, task: Task) -> str:
        """Generate a cache key for a task based on its content.

        Args:
            task: The task to generate a cache key for

        Returns:
            A unique cache key string
        """
        # Create a unique identifier based on task turnpoints and properties
        cache_data = {
            "task_type": task.task_type.value,
            "version": task.version,
            "turnpoints": [],
        }

        for tp in task.turnpoints:
            cache_data["turnpoints"].append(
                {
                    "lat": round(
                        tp.waypoint.lat, 6
                    ),  # Round to avoid floating point precision issues
                    "lon": round(tp.waypoint.lon, 6),
                    "radius": tp.radius,
                    "type": tp.type.value if tp.type else None,
                }
            )

        # Create hash from the serialized data
        cache_str = str(sorted(cache_data.items()))
        return hashlib.md5(cache_str.encode()).hexdigest()

    def load_cached_distances(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cached distance calculations from file.

        Args:
            cache_key: The cache key to load

        Returns:
            Cached distance data or None if not found
        """
        # Check memory cache first
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]

        # Check persistent cache
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cache_data = json.load(f)
                    # Verify this is the correct cache by checking cache_key
                    if cache_data.get("cache_key") == cache_key:
                        # Store in memory cache for faster access
                        self._memory_cache[cache_key] = cache_data
                        return cache_data
            except Exception:
                # If cache is corrupted, remove it
                try:
                    cache_file.unlink()
                except Exception:
                    pass

        return None

    def save_cached_distances(
        self, cache_key: str, distance_data: Dict[str, Any]
    ) -> None:
        """Save distance calculations to cache file.

        Args:
            cache_key: The cache key to save under
            distance_data: The distance data to cache
        """
        cache_file = self.cache_dir / f"{cache_key}.json"

        # Add cache_key to the data for identification
        distance_data["cache_key"] = cache_key

        try:
            # Save to memory cache
            self._memory_cache[cache_key] = distance_data

            # Save to persistent cache
            with open(cache_file, "w") as f:
                json.dump(distance_data, f, indent=2)
        except Exception:
            # If we can't save cache, continue without it
            pass

    def is_task_fully_cached(self, cache_key: str) -> bool:
        """Check if a task is fully cached (has both distance and route data).

        Args:
            cache_key: The cache key to check

        Returns:
            True if fully cached, False otherwise
        """
        distance_data = self.load_cached_distances(cache_key)

        return (
            distance_data is not None
            and "route_data" in distance_data
            and cache_key in self._memory_cache
        )

    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about current cache files.

        Returns:
            Dictionary with cache statistics
        """
        cache_files = list(self.cache_dir.glob("*.json"))
        cache_info = {"total_files": len(cache_files), "total_size_mb": 0, "files": []}

        for cache_file in cache_files:
            try:
                size_mb = cache_file.stat().st_size / (1024 * 1024)
                cache_info["total_size_mb"] += size_mb
                cache_info["files"].append(
                    {
                        "name": cache_file.name,
                        "size_mb": round(size_mb, 2),
                        "modified": datetime.fromtimestamp(
                            cache_file.stat().st_mtime
                        ).isoformat(),
                    }
                )
            except Exception:
                continue

        cache_info["total_size_mb"] = round(cache_info["total_size_mb"], 2)
        return cache_info

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._memory_cache.clear()

        # Remove all cache files
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except Exception:
                pass
