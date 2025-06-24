from typing import Dict
from .distance import optimized_route_coordinates, _task_to_turnpoints


def generate_task_geojson(task) -> Dict:
    """Generate GeoJSON data from XCTrack task object."""
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
                "name": tp.waypoint.name or f"TP{i+1}",
                "type": "cylinder",
                "radius": tp.radius,
                "description": f"Radius: {tp.radius}m",
                "turnpoint_index": i,
            },
        }
        features.append(point_feature)

    # Convert task to TaskTurnpoint objects
    task_turnpoints = _task_to_turnpoints(task)

    # Get optimized route coordinates
    opt_coords = optimized_route_coordinates(task_turnpoints, task.turnpoints)

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
                "name": "Optimized Route",
                "type": "optimized_route",
                "stroke": "#ff4136",
                "stroke-width": 3,
                "stroke-opacity": 0.8,
            },
        }
        features.append(opt_line_feature)

    return {"type": "FeatureCollection", "features": features}
