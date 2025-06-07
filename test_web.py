#!/usr/bin/env python3
"""Test script for XCTrack Web Interface"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from xctrack_web.app import XCTrackWebApp

def test_web_app():
    """Test the web application functionality"""
    print("🧪 Testing XCTrack Web Interface...")
    
    try:
        # Create app
        app = XCTrackWebApp(tasks_dir='tests')
        print("✅ Flask app created successfully")
        print(f"📁 Task directory: {app.task_directory}")
        print(f"🛣️  Routes: {len(app.app.url_map._rules)}")
        
        # Test with test client
        with app.app.test_client() as client:
            # Test homepage
            response = client.get('/')
            print(f"✅ Homepage: {response.status_code}")
            
            # Test tasks list
            response = client.get('/api/tasks')
            print(f"✅ Tasks API: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                tasks = data.get('tasks', [])
                print(f"   📋 Found {len(tasks)} tasks")
                for task in tasks:
                    print(f"   - {task.get('name', 'Unknown')}: {task.get('distance', 0)} km")
            
            # Test specific task
            response = client.get('/api/task/meta')
            print(f"✅ Meta task API: {response.status_code}")
            if response.status_code == 200:
                data = response.get_json()
                print(f"   📊 Task type: {data.get('taskType', 'Unknown')}")
                print(f"   📏 Distance: {data.get('stats', {}).get('totalDistance', 0)} km")
                print(f"   📍 Turnpoints: {data.get('stats', {}).get('turnpointCount', 0)}")
            
            # Test task page
            response = client.get('/task/meta')
            print(f"✅ Task page: {response.status_code}")
            
        print("\n🎉 All tests passed! The web interface is working correctly.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == '__main__':
    success = test_web_app()
    sys.exit(0 if success else 1)
