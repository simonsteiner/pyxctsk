#!/usr/bin/env python3
"""Test script for XC/Waypoints simplified format."""

import json
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from pyxctsk.qrcode_task import QRCodeTask, QRCodeTurnpoint, QRCodeTaskType

def test_waypoints_format():
    """Test the XC/Waypoints simplified format."""
    
    # Create a simple waypoints task
    turnpoints = [
        QRCodeTurnpoint(
            lat=46.3028,
            lon=13.8470,
            radius=1000,
            name="Start",
            alt_smoothed=1200,
        ),
        QRCodeTurnpoint(
            lat=46.3128,
            lon=13.8570,
            radius=1000,
            name="WP1",
            alt_smoothed=1300,
        ),
        QRCodeTurnpoint(
            lat=46.3228,
            lon=13.8670,
            radius=1000,
            name="Goal",
            alt_smoothed=1400,
        ),
    ]
    
    task = QRCodeTask(
        version=2,
        task_type=QRCodeTaskType.WAYPOINTS,
        turnpoints=turnpoints,
    )
    
    # Test simplified format
    print("Testing XC/Waypoints simplified format...")
    simplified_json = task.to_waypoints_json()
    print(f"Simplified JSON: {simplified_json}")
    
    # Parse the JSON to verify structure
    data = json.loads(simplified_json)
    print(f"Parsed data: {json.dumps(data, indent=2)}")
    
    # Verify expected structure
    assert "T" in data and data["T"] == "W", f"Expected T=W, got {data.get('T')}"
    assert "V" in data and data["V"] == 2, f"Expected V=2, got {data.get('V')}"
    assert "t" in data and len(data["t"]) == 3, f"Expected 3 turnpoints, got {len(data.get('t', []))}"
    
    # Verify turnpoint structure
    for i, tp in enumerate(data["t"]):
        assert "n" in tp, f"Turnpoint {i} missing name"
        assert "z" in tp, f"Turnpoint {i} missing encoded coordinates"
        assert len(tp) == 2, f"Turnpoint {i} has extra fields: {tp}"
        
    print("✓ All structure checks passed")
    
    # Test round-trip conversion
    print("\nTesting round-trip conversion...")
    parsed_task = QRCodeTask.from_waypoints_json(simplified_json)
    print(f"Parsed task type: {parsed_task.task_type}")
    print(f"Parsed turnpoints: {len(parsed_task.turnpoints)}")
    
    # Verify turnpoints were parsed correctly
    for i, (original, parsed) in enumerate(zip(turnpoints, parsed_task.turnpoints)):
        print(f"Turnpoint {i}: {original.name} -> {parsed.name}")
        print(f"  Original: lat={original.lat:.6f}, lon={original.lon:.6f}")
        print(f"  Parsed:   lat={parsed.lat:.6f}, lon={parsed.lon:.6f}")
        
        # Check if coordinates are reasonably close (polyline encoding is lossy)
        lat_diff = abs(original.lat - parsed.lat)
        lon_diff = abs(original.lon - parsed.lon)
        assert lat_diff < 0.001, f"Lat difference too large: {lat_diff}"
        assert lon_diff < 0.001, f"Lon difference too large: {lon_diff}"
        
    print("✓ Round-trip conversion successful")
    
    # Test URL format
    print("\nTesting URL format...")
    url_string = task.to_waypoints_string()
    print(f"URL string: {url_string}")
    
    assert url_string.startswith("XCTSK:"), "URL should start with XCTSK:"
    
    # Parse from URL
    parsed_from_url = QRCodeTask.from_waypoints_string(url_string)
    assert len(parsed_from_url.turnpoints) == 3, "Should have 3 turnpoints from URL"
    
    print("✓ URL format tests passed")
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_waypoints_format()
