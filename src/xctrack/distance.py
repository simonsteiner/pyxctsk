"""Distance calculation module using WGS84 ellipsoid and route optimization."""

from typing import List, Tuple, Dict, Any
from geopy.distance import geodesic
from pyproj import Geod
from .task import Task

# Configuration constants
DEFAULT_ANGLE_STEP = 5  # Angle step in degrees for perimeter point generation (5-15° for good accuracy/performance balance)

# Initialize WGS84 ellipsoid
geod = Geod(ellps="WGS84")


class TaskTurnpoint:
    """Turnpoint class for distance calculations."""
    
    def __init__(self, lat: float, lon: float, radius: float = 0):
        """Initialize a task turnpoint.
        
        Args:
            lat: Latitude in degrees
            lon: Longitude in degrees
            radius: Cylinder radius in meters
        """
        self.center = (lat, lon)
        self.radius = radius

    def perimeter_points(self, angle_step: int = DEFAULT_ANGLE_STEP) -> List[Tuple[float, float]]:
        """Generate perimeter points around the turnpoint at given angle steps.
        
        Args:
            angle_step: Angle step in degrees
            
        Returns:
            List of (lat, lon) tuples representing points on the cylinder perimeter
        """
        if self.radius == 0:
            return [self.center]
        
        points = []
        for azimuth in range(0, 360, angle_step):
            lon, lat, _ = geod.fwd(self.center[1], self.center[0], azimuth, self.radius)
            points.append((lat, lon))
        return points


def optimized_distance(turnpoints: List[TaskTurnpoint], angle_step: int = DEFAULT_ANGLE_STEP, show_progress: bool = False) -> float:
    """Compute the fully optimized distance through turnpoints using Dynamic Programming.
    
    This algorithm finds the shortest possible route through all turnpoint cylinders
    by computing the optimal path from perimeter to perimeter.
    
    Args:
        turnpoints: List of TaskTurnpoint objects
        angle_step: Angle step in degrees for perimeter point generation
        show_progress: Whether to show progress indicators
        
    Returns:
        Optimized distance in meters
    """
    if len(turnpoints) < 2:
        return 0.0
    
    if show_progress:
        print(f"    🔄 Optimizing route through {len(turnpoints)} turnpoints (angle step: {angle_step}°)...")
    
    # Precompute perimeter points for all turnpoints
    perimeters = [tp.perimeter_points(angle_step) for tp in turnpoints]
    
    if show_progress:
        total_points = sum(len(p) for p in perimeters)
        print(f"    📍 Generated {total_points} perimeter points")
    
    # Initialize distance table: list of dicts for each turnpoint
    # dp[i][point] = minimum distance to reach 'point' on turnpoint i
    dp = [{} for _ in turnpoints]
    dp[0] = {p: 0 for p in perimeters[0]}  # distance from start is 0

    # Fill DP table using dynamic programming
    for i in range(1, len(turnpoints)):
        if show_progress:
            print(f"    ⚡ Processing turnpoint {i+1}/{len(turnpoints)}")
        
        for curr_pt in perimeters[i]:
            min_dist = float("inf")
            # Check all possible previous points
            for prev_pt, prev_dist in dp[i - 1].items():
                leg_distance = geodesic(prev_pt, curr_pt).meters
                total_distance = prev_dist + leg_distance
                if total_distance < min_dist:
                    min_dist = total_distance
            dp[i][curr_pt] = min_dist

    # Find the shortest distance to any point on the last cylinder
    return min(dp[-1].values())


def distance_through_centers(turnpoints: List[TaskTurnpoint]) -> float:
    """Calculate distance through turnpoint centers.
    
    Args:
        turnpoints: List of TaskTurnpoint objects
        
    Returns:
        Distance through centers in meters
    """
    if len(turnpoints) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(turnpoints) - 1):
        a = turnpoints[i].center
        b = turnpoints[i + 1].center
        total += geodesic(a, b).meters
    return total


def calculate_task_distances(task: Task, angle_step: int = DEFAULT_ANGLE_STEP, show_progress: bool = False) -> Dict[str, Any]:
    """Calculate both center and optimized distances for a task.
    
    Args:
        task: Task object
        angle_step: Angle step in degrees for optimization
        show_progress: Whether to show progress indicators
        
    Returns:
        Dictionary containing distance calculations and turnpoint details
    """
    # Convert to TaskTurnpoint objects
    turnpoints = []
    for tp in task.turnpoints:
        task_tp = TaskTurnpoint(
            lat=tp.waypoint.lat,
            lon=tp.waypoint.lon,
            radius=tp.radius
        )
        turnpoints.append(task_tp)
    
    if len(turnpoints) < 2:
        return {
            'center_distance_km': 0.0,
            'optimized_distance_km': 0.0,
            'savings_km': 0.0,
            'savings_percent': 0.0,
            'turnpoints': []
        }
    
    if show_progress:
        print("  📏 Calculating center distance...")
    
    # Calculate distances
    center_dist = distance_through_centers(turnpoints)
    
    if show_progress:
        print(f"  ✅ Center distance: {center_dist/1000.0:.1f}km")
        print("  🎯 Starting optimization...")
    
    opt_dist = optimized_distance(turnpoints, angle_step=angle_step, show_progress=show_progress)
    
    if show_progress:
        print(f"  ✅ Optimized distance: {opt_dist/1000.0:.1f}km")
    
    # Convert to kilometers
    center_km = center_dist / 1000.0
    opt_km = opt_dist / 1000.0
    
    # Calculate savings
    savings_km = center_km - opt_km
    savings_percent = (savings_km / center_km * 100) if center_km > 0 else 0.0
    
    if show_progress:
        print(f"  📊 Calculating cumulative distances for {len(turnpoints)} turnpoints...")
    
    # Calculate cumulative distances for each turnpoint
    turnpoint_details = []
    for i, (tp, task_tp) in enumerate(zip(task.turnpoints, turnpoints)):
        cumulative_center = 0.0
        cumulative_opt = 0.0
        
        if i > 0:
            if show_progress and i > 1:  # Skip progress for first couple as they're fast
                print(f"    🔄 Turnpoint {i+1}/{len(turnpoints)}")
            
            # Calculate cumulative distances to this turnpoint
            partial_turnpoints = turnpoints[:i+1]
            cumulative_center = distance_through_centers(partial_turnpoints) / 1000.0
            cumulative_opt = optimized_distance(partial_turnpoints, angle_step=angle_step, show_progress=False) / 1000.0
        
        turnpoint_details.append({
            'index': i,
            'name': tp.waypoint.name,
            'lat': tp.waypoint.lat,
            'lon': tp.waypoint.lon,
            'radius': tp.radius,
            'type': tp.type.value if tp.type else '',
            'cumulative_center_km': round(cumulative_center, 1),
            'cumulative_optimized_km': round(cumulative_opt, 1)
        })
    
    if show_progress:
        print("  ✅ All calculations complete")
    
    return {
        'center_distance_km': round(center_km, 1),
        'optimized_distance_km': round(opt_km, 1),
        'savings_km': round(savings_km, 1),
        'savings_percent': round(savings_percent, 1),
        'turnpoints': turnpoint_details,
        'optimization_angle_step': angle_step
    }


def calculate_cumulative_distances(turnpoints: List[TaskTurnpoint], index: int, angle_step: int = DEFAULT_ANGLE_STEP) -> Tuple[float, float]:
    """Calculate cumulative distances up to a specific turnpoint index.
    
    Args:
        turnpoints: List of TaskTurnpoint objects
        index: Index of the turnpoint (0-based)
        angle_step: Angle step for optimization calculations
        
    Returns:
        Tuple of (center_distance_km, optimized_distance_km)
    """
    if index == 0 or len(turnpoints) <= 1:
        return 0.0, 0.0
    
    partial_turnpoints = turnpoints[:index+1]
    center_dist = distance_through_centers(partial_turnpoints) / 1000.0
    opt_dist = optimized_distance(partial_turnpoints, angle_step=angle_step, show_progress=False) / 1000.0
    
    return center_dist, opt_dist
