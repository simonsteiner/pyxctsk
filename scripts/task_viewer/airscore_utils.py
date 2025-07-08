#!/usr/bin/env python3
"""
Utilities to integrate AirScore clone calculations into the task viewer.
This module adapts the AirScore clone code to work with the task viewer without
requiring the full AirScore dependencies.
"""

import math
import sys
from pathlib import Path
from typing import Any, Dict, List

from geopy.distance import geodesic

# Add the parent directory to the path to import from airscore_clone
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))  # Also add current directory to path


# Define our own Turnpoint class based on the one from igc_lib
class Turnpoint:
    """A single turnpoint in a task.

    Attributes:
        lat: a float, latitude in degrees
        lon: a float, longitude in degrees
        radius: a float, radius of cylinder or line in meters
        type: type of turnpoint; "launch", "speed", "waypoint", "endspeed", "goal"
        shape: "line" or "circle"
        how: "entry" or "exit"
        altitude: altitude in meters
        name: name of the turnpoint
    """

    def __init__(
        self,
        lat=None,
        lon=None,
        radius=None,
        type="waypoint",
        shape="circle",
        how="entry",
        altitude=None,
        name=None,
        num=None,
        description=None,
        wpt_id=None,
        rwp_id=None,
    ):
        self.lat = lat
        self.lon = lon
        self.radius = radius
        self.type = type
        self.shape = shape
        self.how = how
        self.altitude = altitude
        self.name = name
        self.num = num
        self.description = description
        self.wpt_id = wpt_id
        self.rwp_id = rwp_id

    def in_radius(self, other, tolerance=0, min_tol=0):
        """Check if another point is within this turnpoint's radius plus tolerance"""
        dist = geodesic((self.lat, self.lon), (other.lat, other.lon)).meters
        return dist <= (self.radius + tolerance)


# Define minimal implementations needed for AirScore calculations
def distance(p1, p2, method=None):
    """Simple geodesic distance calculation between two points in meters"""
    return geodesic((p1.lat, p1.lon), (p2.lat, p2.lon)).meters


def calcBearing(lat1, lon1, lat2, lon2):
    """Calculate bearing between two points"""
    # Simple bearing calculation
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - math.sin(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.cos(math.radians(lon2 - lon1))
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360


def opt_wp(p1, p2, p3, r2):
    """Simplified optimization function for waypoint"""
    # In this simplified implementation, we optimize based on the bearing
    if p3 is None:
        # If there's no next point, just return the current turnpoint
        return Turnpoint(
            lat=p2.lat,
            lon=p2.lon,
            type="optimised",
            radius=0,
            shape="optimised",
            how="optimised",
        )

    # Calculate bearings
    p2_to_p1 = calcBearing(p2.lat, p2.lon, p1.lat, p1.lon)
    p2_to_p3 = calcBearing(p2.lat, p2.lon, p3.lat, p3.lon)

    # Calculate angle between the two bearings
    angle = abs(p2_to_p1 - p2_to_p3)
    if angle > 180:
        angle = 360 - angle

    # Bisect the angle
    angle = angle / 2

    # Determine the best direction (bisector of the angle)
    if abs((p2_to_p1 - p2_to_p3 + 360) % 360) < 180:
        final_bearing = (p2_to_p1 + angle) % 360
    else:
        final_bearing = (p2_to_p1 - angle) % 360

    # Calculate the point on the cylinder at the specified radius and bearing
    # Using simple distance approximation (not perfect but adequate for this purpose)
    distance_per_degree = 111000  # rough meters per degree
    lat_change = r2 * math.cos(math.radians(final_bearing)) / distance_per_degree
    lon_change = (
        r2
        * math.sin(math.radians(final_bearing))
        / (distance_per_degree * math.cos(math.radians(p2.lat)))
    )

    new_lat = p2.lat + lat_change
    new_lon = p2.lon + lon_change

    return Turnpoint(
        lat=new_lat,
        lon=new_lon,
        type="optimised",
        radius=0,
        shape="optimised",
        how="optimised",
    )


def opt_goal(p1, p2):
    """Simplified optimization function for goal"""
    # For a line goal, we find the nearest point on the goal line
    if p2.shape == "line":
        # Calculate the heading from p1 to p2
        bearing = calcBearing(p1.lat, p1.lon, p2.lat, p2.lon)

        # Calculate the point on the cylinder at the specified radius and bearing
        distance_per_degree = 111000  # rough meters per degree
        lat_change = p2.radius * math.cos(math.radians(bearing)) / distance_per_degree
        lon_change = (
            p2.radius
            * math.sin(math.radians(bearing))
            / (distance_per_degree * math.cos(math.radians(p2.lat)))
        )

        new_lat = p2.lat - lat_change  # Go opposite direction from the center
        new_lon = p2.lon - lon_change

        return Turnpoint(
            lat=new_lat,
            lon=new_lon,
            type=p2.type,
            radius=0,
            shape="optimised",
            how="optimised",
        )
    else:
        # For a cylinder goal, use the standard optimization
        return opt_wp(p1, p2, None, p2.radius)


# Track if real AirScore functions are available
AIRSCORE_AVAILABLE = False

# Try to import the real implementations from AirScore
try:
    # Import the needed functions from airscore_clone
    from airscore_clone.route import Turnpoint as AirscoreTurnpoint
    from airscore_clone.route import calcBearing as airscore_calcBearing
    from airscore_clone.route import distance as airscore_distance
    from airscore_clone.route import opt_goal as airscore_opt_goal
    from airscore_clone.route import opt_wp as airscore_opt_wp

    # Replace our minimal implementations with the real ones
    Turnpoint = AirscoreTurnpoint
    distance = airscore_distance
    calcBearing = airscore_calcBearing
    opt_wp = airscore_opt_wp
    opt_goal = airscore_opt_goal

    AIRSCORE_AVAILABLE = True
    print("Successfully loaded AirScore modules")
except ImportError as e:
    print(f"Warning: Using simplified AirScore implementation: {e}")
    # We'll continue with our minimal implementations


# No fallback for geo - we either use the proper implementation or don't use it at all


def convert_xctrack_to_airscore_turnpoints(task) -> List[Turnpoint]:
    """Convert XCTrack task turnpoints to AirScore turnpoints for calculation."""
    airscore_tps = []

    for i, tp in enumerate(task.turnpoints):
        tp_type = "launch"  # Default type

        if i == 0:
            tp_type = "launch"
        elif hasattr(tp, "is_start") and tp.is_start:
            tp_type = "speed"
        elif hasattr(tp, "is_goal") and tp.is_goal:
            tp_type = "goal"
        elif hasattr(tp, "is_ess") and tp.is_ess:
            tp_type = "endspeed"
        else:
            tp_type = "waypoint"

        # Determine how (entry/exit)
        how = "entry"
        if hasattr(tp, "exit") and tp.exit:
            how = "exit"

        # Determine shape (circle/line)
        shape = "circle"
        if hasattr(tp, "line") and tp.line:
            shape = "line"

        airscore_tp = Turnpoint(
            lat=tp.waypoint.lat,
            lon=tp.waypoint.lon,
            radius=tp.radius,
            type=tp_type,
            shape=shape,
            how=how,
            altitude=tp.waypoint.altitude if hasattr(tp.waypoint, "altitude") else None,
            name=tp.waypoint.name if hasattr(tp.waypoint, "name") else f"TP{i+1}",
        )
        airscore_tps.append(airscore_tp)

    return airscore_tps


def calculate_airscore_distances(task) -> Dict[str, Any]:
    """Calculate distances using AirScore clone algorithms."""
    # Convert task to AirScore format
    airscore_tps = convert_xctrack_to_airscore_turnpoints(task)

    # Calculate center distance
    center_distances = []
    cumulative_center_distance = 0
    for i in range(1, len(airscore_tps)):
        dist = distance(airscore_tps[i - 1], airscore_tps[i])
        center_distances.append(dist)
        cumulative_center_distance += dist

    # Use AirScore Task class - no fallback
    # Import the AirScore Task class
    from airscore_clone.task import Task as AirscoreTask

    # print("Using AirScore Task class for optimization")
    # Create a Task object
    airscore_task = AirscoreTask()
    airscore_task.turnpoints = airscore_tps

    # Calculate optimized route using Task methods
    # Get projection
    airscore_task.create_projection()
    # print("Calculating task optimised distance...")
    airscore_task.calculate_task_length()
    airscore_task.calculate_optimised_task_length()
    # print(f"Task Opt. Route: {round(airscore_task.opt_dist / 1000, 4)} Km")

    # Get optimized turnpoints and distances
    optimized_turnpoints = airscore_task.optimised_turnpoints
    cumulative_optimized_distance = airscore_task.opt_dist

    # Calculate leg distances
    optimized_distances = []
    for i in range(1, len(optimized_turnpoints)):
        dist = distance(optimized_turnpoints[i - 1], optimized_turnpoints[i])
        optimized_distances.append(dist)

    # Build turnpoint result data
    turnpoint_results = []
    for i, tp in enumerate(airscore_tps):
        cumulative_center = sum(center_distances[:i]) if i > 0 else 0
        cumulative_optimized = sum(optimized_distances[:i]) if i > 0 else 0

        turnpoint_results.append(
            {
                "index": i,
                "name": tp.name if hasattr(tp, "name") else f"TP{i+1}",
                "type": tp.type,
                "radius": tp.radius,
                "how": tp.how,
                "shape": tp.shape,
                "lat": tp.lat,
                "lon": tp.lon,
                "leg_center_m": center_distances[i - 1] if i > 0 else 0,
                "cumulative_center_m": cumulative_center,
                "cumulative_center_km": cumulative_center / 1000,
                "leg_optimized_m": optimized_distances[i - 1] if i > 0 else 0,
                "cumulative_optimized_m": cumulative_optimized,
                "cumulative_optimized_km": cumulative_optimized / 1000,
            }
        )

    # Get coordinates of optimized route for mapping
    opt_coordinates = []
    for tp in optimized_turnpoints:
        opt_coordinates.append((tp.lat, tp.lon))

    return {
        "center_distance_m": cumulative_center_distance,
        "center_distance_km": cumulative_center_distance / 1000,
        "optimized_distance_m": cumulative_optimized_distance,
        "optimized_distance_km": cumulative_optimized_distance / 1000,
        "turnpoints": turnpoint_results,
        "optimized_coordinates": opt_coordinates,
    }


def generate_airscore_geojson(task, airscore_results: Dict) -> Dict:
    """Generate GeoJSON from AirScore calculation results."""
    features = []

    # Add turnpoints as point features with cylinders
    for i, tp in enumerate(task.turnpoints):
        # Point feature for the turnpoint
        point_feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [tp.waypoint.lon, tp.waypoint.lat],
            },
            "properties": {
                "name": (
                    tp.waypoint.name if hasattr(tp.waypoint, "name") else f"TP{i+1}"
                ),
                "type": "cylinder",
                "radius": tp.radius,
                "description": f"Radius: {tp.radius}m",
                "turnpoint_index": i,
            },
        }
        features.append(point_feature)

    # Add optimized route from AirScore calculations
    opt_coords = airscore_results.get("optimized_coordinates", [])

    if len(opt_coords) >= 2:
        # Convert from (lat, lon) to [lon, lat] format for GeoJSON
        opt_coordinates = [[coord[1], coord[0]] for coord in opt_coords]

        opt_line_feature = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": opt_coordinates,
            },
            "properties": {
                "name": "AirScore Optimized Route",
                "type": "airscore_optimized_route",
                "stroke": "#ff9900",  # Different color from xctrack optimized route
                "stroke-width": 3,
                "stroke-opacity": 0.8,
            },
        }
        features.append(opt_line_feature)

    return {"type": "FeatureCollection", "features": features}
