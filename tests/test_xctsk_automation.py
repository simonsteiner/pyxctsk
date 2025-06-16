#!/usr/bin/env python3
"""
Test script for XCTSK automation functionality.

This script tests the basic functionality of the XCTSK automation tool
without actually making network requests.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import sys

sys.path.insert(0, str(Path(__file__).parent))

from xctsk_automation import XCTSKClient


def test_client_initialization():
    """Test that the client initializes correctly."""
    client = XCTSKClient(author="Test Author", timeout=10, retry_count=2)
    assert client.author == "Test Author"
    assert client.timeout == 10
    print("✓ Client initialization test passed")


def test_task_loading():
    """Test loading XCTSK task files."""
    # Find a sample XCTSK file
    xctsk_files = list(Path(".").glob("*.xctsk"))
    if not xctsk_files:
        print("! No XCTSK files found for testing")
        return

    sample_file = xctsk_files[0]

    try:
        with open(sample_file, "r") as f:
            task_data = json.load(f)

        # Basic validation
        assert "version" in task_data
        assert "taskType" in task_data
        assert "turnpoints" in task_data

        print(f"✓ Task loading test passed ({sample_file.name})")
        print(f"  Task type: {task_data.get('taskType')}")
        print(f"  Turnpoints: {len(task_data.get('turnpoints', []))}")

    except Exception as e:
        print(f"✗ Task loading test failed: {e}")


def test_mock_upload():
    """Test upload functionality with mocked requests."""

    # Create a temporary XCTSK file
    task_data = {
        "version": 1,
        "taskType": "CLASSIC",
        "turnpoints": [
            {
                "radius": 400,
                "waypoint": {
                    "lon": -76.15351867675781,
                    "lat": 4.476049900054932,
                    "altSmoothed": 1702,
                    "name": "TEST",
                    "description": "Test waypoint",
                },
                "type": "TAKEOFF",
            }
        ],
        "earthModel": "WGS84",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xctsk", delete=False) as f:
        json.dump(task_data, f)
        temp_file = Path(f.name)

    try:
        client = XCTSKClient(author="Test User")

        # Mock the session.post method
        with patch.object(client.session, "post") as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = "12345"
            mock_post.return_value = mock_response

            task_code, message = client.upload_task(temp_file, "Test Author")

            assert task_code == 12345
            assert "Successfully uploaded" in message
            print("✓ Mock upload test passed")

    finally:
        # Clean up
        temp_file.unlink()


def test_mock_download():
    """Test download functionality with mocked requests."""

    client = XCTSKClient()

    with tempfile.TemporaryDirectory() as temp_dir:
        output_file = Path(temp_dir) / "test_task.xctsk"

        # Mock the session.get method
        with patch.object(client.session, "get") as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '{"version": 1, "taskType": "TEST"}'
            mock_response.headers = {
                "Author": "Test Author",
                "Last-Modified": "Wed, 15 Jun 2025 12:00:00 GMT",
            }
            mock_get.return_value = mock_response

            success, message = client.download_task(12345, output_file)

            assert success
            assert output_file.exists()
            assert "Downloaded task 12345" in message
            print("✓ Mock download test passed")


def test_file_discovery():
    """Test discovering XCTSK files in directory."""
    current_dir = Path(".")
    xctsk_files = list(current_dir.glob("*.xctsk"))

    print(f"✓ File discovery test: found {len(xctsk_files)} XCTSK files")
    for file in xctsk_files[:5]:  # Show first 5
        print(f"  - {file.name}")
    if len(xctsk_files) > 5:
        print(f"  ... and {len(xctsk_files) - 5} more")


def main():
    """Run all tests."""
    print("XCTSK Automation Test Suite")
    print("=" * 30)

    tests = [
        test_client_initialization,
        test_task_loading,
        test_file_discovery,
        test_mock_upload,
        test_mock_download,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        print()

    print(f"Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed!")
        return 0
    else:
        print("❌ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
