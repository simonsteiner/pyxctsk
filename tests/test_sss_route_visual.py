"""Visual test for SSS route mapping bug.

This test creates visual representations (HTML maps) to help verify that
the optimized route navigates to the perimeter of turnpoints, not their centers.
"""

import json
import os

import pytest
from geopy.distance import geodesic

from pyxctsk import parse_task
from pyxctsk.distance import (
    _task_to_turnpoints,
    calculate_task_distances,
    optimized_route_coordinates,
)


class TestSSSRouteVisual:
    """Visual test cases for SSS route optimization."""

    @pytest.fixture
    def test_data_dir(self):
        """Return the path to test data directory."""
        return os.path.join(os.path.dirname(__file__))

    @pytest.fixture
    def output_dir(self, test_data_dir):
        """Create output directory for visual tests."""
        output_path = os.path.join(test_data_dir, "visual_output")
        os.makedirs(output_path, exist_ok=True)
        return output_path

    def create_html_map(self, task, center_route, optimized_route, output_file):
        """Create an HTML map showing both routes."""
        turnpoints = _task_to_turnpoints(task)

        # Calculate bounds for the map
        all_lats = []
        all_lons = []

        # Add turnpoint centers
        for tp in turnpoints:
            all_lats.append(tp.center[0])
            all_lons.append(tp.center[1])

        # Add route points
        for route in [center_route, optimized_route]:
            for point in route:
                all_lats.append(point[0])
                all_lons.append(point[1])

        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)

        # Calculate zoom level based on bounds
        lat_range = max(all_lats) - min(all_lats)
        lon_range = max(all_lons) - min(all_lons)
        max_range = max(lat_range, lon_range)

        if max_range > 1:
            zoom = 8
        elif max_range > 0.1:
            zoom = 10
        elif max_range > 0.01:
            zoom = 12
        else:
            zoom = 14

        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SSS Route Comparison</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
    <style>
        body {{ margin: 0; padding: 20px; font-family: Arial, sans-serif; }}
        #map {{ height: 600px; width: 100%; }}
        .info {{ margin-bottom: 10px; padding: 10px; background: #f0f0f0; border-radius: 5px; }}
        .legend {{ background: white; padding: 10px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
        .legend-item {{ margin: 5px 0; }}
        .legend-color {{ display: inline-block; width: 20px; height: 3px; margin-right: 8px; }}
    </style>
</head>
<body>
    <h1>SSS Route Comparison</h1>
    <div class="info">
        <strong>Task:</strong> {task.name if hasattr(task, 'name') else 'SSS Task'}<br>
        <strong>Purpose:</strong> Compare center route (red) vs optimized route (blue) for SSS tasks.<br>
        <strong>Expected:</strong> Optimized route should go to turnpoint perimeters, not centers.
    </div>
    
    <div id="map"></div>
    
    <script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
    <script>
        var map = L.map('map').setView([{center_lat}, {center_lon}], {zoom});
        
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);
        
        // Add legend
        var legend = L.control({{position: 'topright'}});
        legend.onAdd = function (map) {{
            var div = L.DomUtil.create('div', 'legend');
            div.innerHTML = `
                <h4>Route Legend</h4>
                <div class="legend-item">
                    <span class="legend-color" style="background: red;"></span>
                    Center Route (through TP centers)
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: blue;"></span>
                    Optimized Route (to TP perimeters)
                </div>
                <div class="legend-item">
                    <span class="legend-color" style="background: green;"></span>
                    Turnpoint Centers
                </div>
                <div class="legend-item">
                    <span style="color: rgba(0,0,255,0.3);">○</span>
                    Turnpoint Cylinders
                </div>
            `;
            return div;
        }};
        legend.addTo(map);
"""

        # Add turnpoints with cylinders
        for i, (tp, task_tp) in enumerate(zip(turnpoints, task.turnpoints)):
            lat, lon = tp.center
            radius = tp.radius
            name = task_tp.waypoint.name
            tp_type = task_tp.type.value if task_tp.type else "TP"

            html_content += f"""
        // Turnpoint {i}: {name}
        L.marker([{lat}, {lon}]).addTo(map)
            .bindPopup('<b>{name}</b><br>Type: {tp_type}<br>Radius: {radius}m');
        L.circle([{lat}, {lon}], {{
            color: 'blue',
            fillColor: 'blue',
            fillOpacity: 0.1,
            radius: {radius}
        }}).addTo(map);
"""

        # Add center route
        if len(center_route) >= 2:
            center_route_coords = [[point[0], point[1]] for point in center_route]
            html_content += f"""
        // Center route
        var centerRoute = L.polyline({json.dumps(center_route_coords)}, {{
            color: 'red',
            weight: 3,
            opacity: 0.8
        }}).addTo(map);
"""

        # Add optimized route
        if len(optimized_route) >= 2:
            optimized_route_coords = [[point[0], point[1]] for point in optimized_route]
            html_content += f"""
        // Optimized route
        var optimizedRoute = L.polyline({json.dumps(optimized_route_coords)}, {{
            color: 'blue',
            weight: 3,
            opacity: 0.8
        }}).addTo(map);
"""

        # Add route comparison info
        if len(center_route) >= 2 and len(optimized_route) >= 2:
            center_distance = (
                sum(
                    geodesic(center_route[i], center_route[i + 1]).meters
                    for i in range(len(center_route) - 1)
                )
                / 1000.0
            )

            optimized_distance = (
                sum(
                    geodesic(optimized_route[i], optimized_route[i + 1]).meters
                    for i in range(len(optimized_route) - 1)
                )
                / 1000.0
            )

            savings = center_distance - optimized_distance
            savings_percent = (
                (savings / center_distance * 100) if center_distance > 0 else 0
            )

            html_content += f"""
        // Add distance comparison popup
        var comparisonInfo = L.popup()
            .setLatLng([{center_lat}, {center_lon}])
            .setContent(`
                <h4>Route Comparison</h4>
                <b>Center Route:</b> {center_distance:.2f} km<br>
                <b>Optimized Route:</b> {optimized_distance:.2f} km<br>
                <b>Savings:</b> {savings:.2f} km ({savings_percent:.1f}%)
            `);
"""

        html_content += """
    </script>
</body>
</html>
"""

        # Write HTML file
        with open(output_file, "w") as f:
            f.write(html_content)

    def test_create_visual_sss_comparison(self, test_data_dir, output_dir):
        """Create visual comparison for SSS route optimization."""
        task_file = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(task_file)

        # Verify this is an SSS task
        has_sss = any(tp.type and tp.type.value == "SSS" for tp in task.turnpoints)
        if not has_sss:
            pytest.skip("Not an SSS task")

        turnpoints = _task_to_turnpoints(task)

        # Create center route (through centers, skipping SSS)
        center_route = []
        takeoff_center = turnpoints[0].center
        center_route.append(takeoff_center)

        # Find first TP after SSS
        first_tp_after_sss_index = None
        for i, tp in enumerate(task.turnpoints):
            if tp.type and tp.type.value == "SSS":
                if i + 1 < len(task.turnpoints):
                    first_tp_after_sss_index = i + 1
                break

        if first_tp_after_sss_index:
            # Add centers of turnpoints after SSS
            for i in range(first_tp_after_sss_index, len(turnpoints)):
                center_route.append(turnpoints[i].center)

        # Get optimized route
        optimized_route = optimized_route_coordinates(turnpoints, task.turnpoints)

        # Create HTML map
        output_file = os.path.join(output_dir, "sss_route_comparison.html")
        self.create_html_map(task, center_route, optimized_route, output_file)

        print(f"🗺️  Visual comparison created: {output_file}")
        print("    Open this file in a web browser to see the route comparison")

        # Verify basic properties
        assert (
            len(optimized_route) >= 2
        ), "Optimized route should have at least 2 points"
        assert optimized_route[0] == turnpoints[0].center, "Should start from takeoff"

        # Calculate distances for comparison
        center_distance = (
            sum(
                geodesic(center_route[i], center_route[i + 1]).meters
                for i in range(len(center_route) - 1)
            )
            / 1000.0
        )

        optimized_distance = (
            sum(
                geodesic(optimized_route[i], optimized_route[i + 1]).meters
                for i in range(len(optimized_route) - 1)
            )
            / 1000.0
        )

        print("📊 Distance comparison:")
        print(f"    Center route: {center_distance:.2f} km")
        print(f"    Optimized route: {optimized_distance:.2f} km")
        print(f"    Savings: {center_distance - optimized_distance:.2f} km")

        # The optimized route should be shorter
        assert optimized_distance < center_distance, "Optimized route should be shorter"

    def test_create_multiple_sss_visuals(self, test_data_dir, output_dir):
        """Create visual comparisons for multiple SSS tasks."""
        sss_task_files = ["task_fuvu.xctsk", "task_jedu.xctsk", "task_meta.xctsk"]

        for task_file in sss_task_files:
            file_path = os.path.join(test_data_dir, task_file)
            if not os.path.exists(file_path):
                continue

            task = parse_task(file_path)

            # Skip if not an SSS task
            has_sss = any(tp.type and tp.type.value == "SSS" for tp in task.turnpoints)
            if not has_sss:
                print(f"⏭️  Skipping {task_file} (not an SSS task)")
                continue

            turnpoints = _task_to_turnpoints(task)

            # Create center route
            center_route = []
            takeoff_center = turnpoints[0].center
            center_route.append(takeoff_center)

            # Find first TP after SSS
            first_tp_after_sss_index = None
            for i, tp in enumerate(task.turnpoints):
                if tp.type and tp.type.value == "SSS":
                    if i + 1 < len(task.turnpoints):
                        first_tp_after_sss_index = i + 1
                    break

            if first_tp_after_sss_index:
                for i in range(first_tp_after_sss_index, len(turnpoints)):
                    center_route.append(turnpoints[i].center)

            # Get optimized route
            optimized_route = optimized_route_coordinates(turnpoints, task.turnpoints)

            # Create HTML map
            task_name = os.path.splitext(task_file)[0]
            output_file = os.path.join(output_dir, f"{task_name}_route_comparison.html")
            self.create_html_map(task, center_route, optimized_route, output_file)

            print(f"🗺️  Created visual for {task_file}: {output_file}")

    def test_detailed_route_analysis(self, test_data_dir, output_dir):
        """Create detailed analysis of route optimization."""
        task_file = os.path.join(test_data_dir, "task_fuvu.xctsk")
        task = parse_task(task_file)

        # Get detailed distance calculations
        distance_info = calculate_task_distances(task, show_progress=True)

        # Create analysis report
        report_file = os.path.join(output_dir, "route_analysis.txt")
        with open(report_file, "w") as f:
            f.write("SSS Route Optimization Analysis\n")
            f.write("=" * 50 + "\n\n")

            f.write(f"Task: {task.name if hasattr(task, 'name') else 'SSS Task'}\n")
            f.write(f"Turnpoints: {len(task.turnpoints)}\n\n")

            f.write("Distance Summary:\n")
            f.write(f"  Center distance: {distance_info['center_distance_km']} km\n")
            f.write(
                f"  Optimized distance: {distance_info['optimized_distance_km']} km\n"
            )
            f.write(
                f"  Savings: {distance_info['savings_km']} km ({distance_info['savings_percent']}%)\n\n"
            )

            f.write("Turnpoint Details:\n")
            for tp_info in distance_info["turnpoints"]:
                f.write(f"  {tp_info['index']}: {tp_info['name']}\n")
                f.write(f"    Type: {tp_info['type'] or 'TP'}\n")
                f.write(f"    Radius: {tp_info['radius']}m\n")
                f.write(
                    f"    Cumulative center: {tp_info['cumulative_center_km']} km\n"
                )
                f.write(
                    f"    Cumulative optimized: {tp_info['cumulative_optimized_km']} km\n\n"
                )

        print(f"📊 Detailed analysis created: {report_file}")

        # Verify the optimization is working
        assert distance_info["savings_km"] > 0, "Should have savings from optimization"
        assert (
            distance_info["optimized_distance_km"] < distance_info["center_distance_km"]
        ), "Optimized should be shorter"


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v", "-s"])
