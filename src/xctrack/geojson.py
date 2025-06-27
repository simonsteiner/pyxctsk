from typing import Dict, List, Optional, Tuple
from .distance import optimized_route_coordinates, _task_to_turnpoints
from .task import GoalType
from pyproj import Geod

# Initialize WGS84 ellipsoid for geographical calculations
geod = Geod(ellps="WGS84")

# Constants for goal line visualization
GOAL_LINE_NUM_POINTS = 20
COORD_TOLERANCE = 1e-9


def _create_turnpoint_feature(turnpoint, index: int) -> Dict:
    """Create a GeoJSON feature for a turnpoint."""
    # Determine color based on turnpoint type
    tp_type = getattr(turnpoint, "type", None)

    if tp_type == "takeoff":
        color = "#204d74"  # takeoff
    elif tp_type in ["SSS", "ESS"]:
        color = "#ac2925"  # SSS and ESS
    elif tp_type == "goal":
        color = "#398439"  # goal
    else:
        color = "#269abc"  # default turnpoint

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [turnpoint.waypoint.lon, turnpoint.waypoint.lat],
        },
        "properties": {
            "name": turnpoint.waypoint.name or f"TP{index+1}",
            "type": "cylinder",
            "radius": turnpoint.radius,
            "description": f"Radius: {turnpoint.radius}m",
            "turnpoint_index": index,
            "tp_type": tp_type,
            "color": color,
            "fillColor": color,
            "fillOpacity": 0.1,
            "weight": 2,
            "opacity": 0.7,
        },
    }


def _create_optimized_route_feature(
    opt_coords: List[Tuple[float, float]],
) -> Optional[Dict]:
    """Create a GeoJSON feature for the optimized route."""
    if len(opt_coords) < 2:
        return None

    # Convert from (lat, lon) to [lon, lat] format for GeoJSON
    opt_coordinates = [[coord[1], coord[0]] for coord in opt_coords]

    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": opt_coordinates,
        },
        "properties": {
            "name": "Optimized Route",
            "type": "optimized_route",
            "color": "#ff4136",
            "weight": 3,
            "opacity": 0.8,
            "arrowheads": True,
            "arrow_color": "#ff4136",
            "arrow_size": 8,
            "arrow_spacing": 100,  # meters between arrows
        },
    }


def _find_previous_turnpoint(turnpoints, last_tp):
    """Find the previous turnpoint with different coordinates from the goal center."""
    for i in range(len(turnpoints) - 2, -1, -1):
        candidate_tp = turnpoints[i]
        # Check if coordinates are different (with small tolerance for floating point comparison)
        if (
            abs(candidate_tp.waypoint.lon - last_tp.waypoint.lon) > COORD_TOLERANCE
            or abs(candidate_tp.waypoint.lat - last_tp.waypoint.lat) > COORD_TOLERANCE
        ):
            return candidate_tp
    return None


def _calculate_goal_line_endpoints(
    last_tp, prev_tp, goal_line_length: float
) -> Tuple[Tuple[float, float], Tuple[float, float], float]:
    """Calculate the endpoints of the goal line and return the forward azimuth."""
    # Calculate bearing from previous turnpoint to goal center
    forward_azimuth, _, _ = geod.inv(
        prev_tp.waypoint.lon,
        prev_tp.waypoint.lat,
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
    )

    # Goal line is perpendicular to the approach direction
    perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
    perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

    half_length = goal_line_length / 2

    lon1, lat1, _ = geod.fwd(
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
        perpendicular_azimuth_1,
        half_length,
    )
    lon2, lat2, _ = geod.fwd(
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
        perpendicular_azimuth_2,
        half_length,
    )

    return (lon1, lat1), (lon2, lat2), forward_azimuth


def _generate_semicircle_arc(
    center_lon: float,
    center_lat: float,
    start_azimuth: float,
    end_azimuth: float,
    through_azimuth: float,
    radius: float,
) -> List[List[float]]:
    """Generate arc points for a semi-circle."""
    arc_points = []
    for i in range(GOAL_LINE_NUM_POINTS + 1):  # include endpoint
        if i <= GOAL_LINE_NUM_POINTS // 2:
            # First half: interpolate from start_azimuth to through_azimuth
            t = (i * 2) / GOAL_LINE_NUM_POINTS
            angle_diff = (through_azimuth - start_azimuth) % 360
            if angle_diff > 180:
                angle_diff -= 360
            angle = (start_azimuth + angle_diff * t) % 360
        else:
            # Second half: interpolate from through_azimuth to end_azimuth
            t = ((i - GOAL_LINE_NUM_POINTS // 2) * 2) / GOAL_LINE_NUM_POINTS
            angle_diff = (end_azimuth - through_azimuth) % 360
            if angle_diff > 180:
                angle_diff -= 360
            angle = (through_azimuth + angle_diff * t) % 360

        lon_arc, lat_arc, _ = geod.fwd(center_lon, center_lat, angle, radius)
        arc_points.append([lon_arc, lat_arc])
    return arc_points


def _create_goal_line_features(task) -> List[Dict]:
    """Create goal line and control zone features for LINE type goals."""
    if not (
        task.goal
        and task.goal.type == GoalType.LINE
        and task.turnpoints
        and len(task.turnpoints) >= 2
    ):
        return []

    last_tp = task.turnpoints[-1]
    prev_tp = _find_previous_turnpoint(task.turnpoints, last_tp)

    if prev_tp is None:
        return []

    # Determine goal line length
    goal_line_length = task.goal.line_length
    if goal_line_length is None:
        goal_line_length = float(last_tp.radius * 2)

    # Calculate goal line endpoints and approach direction
    (lon1, lat1), (lon2, lat2), forward_azimuth = _calculate_goal_line_endpoints(
        last_tp, prev_tp, goal_line_length
    )

    features = []

    # Create goal line feature
    goal_line_feature = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": [[lon1, lat1], [lon2, lat2]],
        },
        "properties": {
            "name": "Goal Line",
            "type": "goal_line",
            "length": goal_line_length,
            "description": f"Goal line length: {goal_line_length:.0f}m",
            "stroke": "#00ff00",
            "stroke-width": 4,
            "stroke-opacity": 1.0,
        },
    }
    features.append(goal_line_feature)

    # Create goal line control zone (semi-circle in front of the goal line)
    control_zone_radius = goal_line_length / 2
    perpendicular_azimuth_1 = (forward_azimuth + 90) % 360
    perpendicular_azimuth_2 = (forward_azimuth - 90) % 360

    front_arc_points = _generate_semicircle_arc(
        last_tp.waypoint.lon,
        last_tp.waypoint.lat,
        perpendicular_azimuth_2,
        perpendicular_azimuth_1,
        forward_azimuth,
        control_zone_radius,
    )

    front_semicircle_coords = (
        [[lon2, lat2]] + front_arc_points + [[lon1, lat1], [lon2, lat2]]
    )

    control_zone_feature = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [front_semicircle_coords],
        },
        "properties": {
            "name": "Goal Control Zone",
            "type": "goal_control_zone",
            "radius": control_zone_radius,
            "description": f"Goal control zone radius: {control_zone_radius:.0f}m",
            "fill": "#4ecdc4",
            "fill-opacity": 0.3,
            "stroke": "#00bcd4",
            "stroke-width": 2,
            "stroke-opacity": 0.8,
        },
    }
    features.append(control_zone_feature)

    return features


def _should_skip_last_turnpoint(task) -> bool:
    """Check if the last turnpoint should be skipped for LINE type goals."""
    return (
        task.goal
        and task.goal.type == GoalType.LINE
        and task.turnpoints
        and len(task.turnpoints) >= 2
    )


def generate_task_geojson(task) -> Dict:
    """Generate GeoJSON data from XCTrack task object."""
    features = []

    # Add turnpoints as point features with cylinders
    # Skip the last turnpoint if it's a LINE type goal (goal line replaces it)
    turnpoints_to_render = task.turnpoints
    if _should_skip_last_turnpoint(task):
        turnpoints_to_render = task.turnpoints[:-1]

    # Create turnpoint features
    for i, tp in enumerate(turnpoints_to_render):
        features.append(_create_turnpoint_feature(tp, i))

    # Add optimized route if available
    task_turnpoints = _task_to_turnpoints(task)
    opt_coords = optimized_route_coordinates(task_turnpoints, task.turnpoints)

    opt_route_feature = _create_optimized_route_feature(opt_coords)
    if opt_route_feature:
        features.append(opt_route_feature)

    # Add goal line features for LINE type goals
    goal_features = _create_goal_line_features(task)
    features.extend(goal_features)

    return {"type": "FeatureCollection", "features": features}
