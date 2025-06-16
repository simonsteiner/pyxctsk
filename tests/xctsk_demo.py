#!/usr/bin/env python3
"""
Example usage of the XCTSK automation script.

This script demonstrates common usage patterns for uploading and downloading
XCTSK files using the XContest tools API.
"""

import json
import os
import sys
from pathlib import Path

# Add the parent directory to Python path to import the automation script
sys.path.insert(0, str(Path(__file__).parent))

from xctsk_automation import XCTSKClient


def demo_upload_and_download():
    """Demonstrate upload and download functionality."""

    # Initialize client
    client = XCTSKClient(author="Demo User", timeout=30)

    # Path to your XCTSK files
    xctsk_dir = Path(".")  # Current directory containing XCTSK files
    xctsk_files = list(xctsk_dir.glob("*.xctsk"))

    if not xctsk_files:
        print("No XCTSK files found in current directory")
        return

    print(f"Found {len(xctsk_files)} XCTSK files")

    # Upload results storage
    upload_results = {}

    # Upload a few files as examples (limit to first 3 to avoid spamming)
    for xctsk_file in xctsk_files[:3]:
        print(f"\nUploading {xctsk_file.name}...")

        task_code, message = client.upload_task(xctsk_file, "Demo Upload")
        print(f"Result: {message}")

        if task_code:
            upload_results[xctsk_file.name] = task_code

            # Generate QR code for this task
            qr_output = Path(f"qr_{xctsk_file.stem}.svg")
            success, qr_message = client.get_qr_code(xctsk_file, qr_output)
            print(f"QR Code: {qr_message}")

    # Save upload results
    if upload_results:
        results_file = Path("upload_results.json")
        with open(results_file, "w") as f:
            json.dump(upload_results, f, indent=2)
        print(f"\nUpload results saved to {results_file}")

        # Demonstrate download (download the tasks we just uploaded)
        print(f"\nDownloading uploaded tasks...")
        download_dir = Path("downloaded_tasks")
        download_dir.mkdir(exist_ok=True)

        for filename, task_code in upload_results.items():
            output_file = download_dir / f"downloaded_{filename}"
            success, message = client.download_task(task_code, output_file)
            print(f"Download: {message}")


def demo_batch_operations():
    """Demonstrate batch upload operations."""

    print("=== Batch Upload Demo ===")

    # This would upload all XCTSK files in the current directory
    # Uncomment to run:

    # from xctsk_automation import upload_directory
    # client = XCTSKClient(author="Batch Demo")
    # results = upload_directory(client, Path("."), "Batch Upload Author")
    # print(f"Batch upload results: {results}")

    print("Batch upload demo disabled (uncomment in source to enable)")


if __name__ == "__main__":
    print("XCTSK Automation Demo")
    print("=" * 30)

    # Check if we have any XCTSK files to work with
    if not list(Path(".").glob("*.xctsk")):
        print("No XCTSK files found in current directory.")
        print("Please run this script from a directory containing .xctsk files")
        print("or copy some .xctsk files to the current directory.")
        sys.exit(1)

    try:
        demo_upload_and_download()
        demo_batch_operations()

        print("\nDemo completed successfully!")
        print("\nGenerated files:")
        for file in Path(".").glob("qr_*.svg"):
            print(f"  - {file}")
        for file in Path(".").glob("upload_results.json"):
            print(f"  - {file}")
        if Path("downloaded_tasks").exists():
            print(f"  - downloaded_tasks/ directory with downloaded files")

    except KeyboardInterrupt:
        print("\nDemo cancelled by user")
    except Exception as e:
        print(f"Demo failed with error: {e}")
        sys.exit(1)
