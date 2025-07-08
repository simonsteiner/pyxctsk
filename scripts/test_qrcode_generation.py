#!/usr/bin/env python3
"""Test script for QR code generation and comparison.

This script generates QR codes for all XCTSK files and compares them with expected results.
It tests both the QR code string generation and PNG image generation.

Usage:
    python test_qrcode_generation.py [--xctsk-dir path] [--expected-dir path] [--output-dir path]
"""

import argparse
import sys
from pathlib import Path
from typing import List

# Add the src directory to the path to import pyxctsk
script_dir = Path(__file__).parent
src_dir = script_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from pyxctsk import parse_task  # noqa: E402
from pyxctsk.utils import generate_qr_code  # noqa: E402

try:
    from PIL import Image
    from pyzbar import pyzbar

    QR_CODE_SUPPORT = True
except ImportError:
    Image = None
    pyzbar = None
    QR_CODE_SUPPORT = False
    print("Warning: QR code dependencies (PIL, pyzbar) not available")


class QRCodeTestResult:
    """Result of a QR code test."""

    def __init__(self, task_name: str):
        self.task_name = task_name
        self.xctsk_exists = False
        self.expected_txt_exists = False
        self.expected_png_exists = False
        self.qr_string_generated = False
        self.qr_string_matches = False
        self.qr_png_generated = False
        self.qr_png_parseable = False
        self.roundtrip_success = False
        self.error_message = ""

        # Store actual values for comparison
        self.generated_qr_string = ""
        self.expected_qr_string = ""
        self.generated_png_path = ""


def find_xctsk_files(xctsk_dir: Path) -> List[Path]:
    """Find all XCTSK files in the given directory."""
    return list(xctsk_dir.glob("*.xctsk"))


def test_qr_code_generation(
    xctsk_file: Path, expected_dir: Path, output_dir: Path
) -> QRCodeTestResult:
    """Test QR code generation for a single XCTSK file.

    Args:
        xctsk_file: Path to the XCTSK file
        expected_dir: Directory containing expected QR code results
        output_dir: Directory to save generated QR codes

    Returns:
        QRCodeTestResult with test results
    """
    task_name = xctsk_file.stem
    result = QRCodeTestResult(task_name)

    try:
        # Check if XCTSK file exists
        result.xctsk_exists = xctsk_file.exists()
        if not result.xctsk_exists:
            result.error_message = f"XCTSK file not found: {xctsk_file}"
            return result

        # Check if expected files exist
        expected_txt = expected_dir / f"{task_name}.txt"
        expected_png = expected_dir / f"{task_name}.png"
        result.expected_txt_exists = expected_txt.exists()
        result.expected_png_exists = expected_png.exists()

        # Parse the task
        task = parse_task(str(xctsk_file))

        # Check if original file is in waypoints format by reading it
        is_waypoints_format = False
        original_content = None
        try:
            with open(xctsk_file, "r", encoding="utf-8") as f:
                file_content = f.read().strip()
                # Check if it's the simplified waypoints format
                if file_content.startswith('{"T":"W"') or file_content.startswith(
                    '{\n    "T": "W"'
                ):
                    is_waypoints_format = True
                    original_content = file_content
        except Exception:
            pass

        # Generate QR code string using appropriate format
        if is_waypoints_format and original_content:
            # For waypoints format, use the original content directly to preserve exact polylines
            import json

            # Parse and re-serialize to ensure consistent formatting (compact JSON)
            original_dict = json.loads(original_content)
            generated_qr_string = "XCTSK:" + json.dumps(
                original_dict, separators=(",", ":"), ensure_ascii=False
            )
        else:
            # Use full format serialization
            qr_task = task.to_qr_code_task()
            generated_qr_string = qr_task.to_string()

        result.qr_string_generated = True
        result.generated_qr_string = generated_qr_string

        # Compare with expected QR string if available
        if result.expected_txt_exists:
            with open(expected_txt, "r") as f:
                expected_qr_string = f.read().strip()
            result.expected_qr_string = expected_qr_string
            result.qr_string_matches = generated_qr_string == expected_qr_string

        # Generate QR code PNG if QR code support is available
        if QR_CODE_SUPPORT and Image is not None and pyzbar is not None:
            output_png = output_dir / f"{task_name}_generated.png"
            qr_image = generate_qr_code(generated_qr_string, size=512)
            qr_image.save(output_png, format="PNG")
            result.qr_png_generated = True
            result.generated_png_path = str(output_png)

            # Test if the generated QR code can be parsed back
            try:
                # Read the QR code from the generated image
                image = Image.open(output_png)
                decoded_objects = pyzbar.decode(image)
                if decoded_objects:
                    decoded_string = decoded_objects[0].data.decode("utf-8")
                    result.qr_png_parseable = True

                    # Test roundtrip: parse the decoded string back to a task
                    parse_task(decoded_string)  # Just verify it doesn't crash
                    result.roundtrip_success = True
                else:
                    result.error_message = "Generated QR code could not be decoded"
            except Exception as e:
                result.error_message = f"Failed to parse generated QR code: {e}"

    except Exception as e:
        result.error_message = f"Error processing {task_name}: {e}"

    return result


def print_summary(results: List[QRCodeTestResult]):
    """Print a summary of test results."""
    total = len(results)
    xctsk_found = sum(1 for r in results if r.xctsk_exists)
    expected_txt_found = sum(1 for r in results if r.expected_txt_exists)
    expected_png_found = sum(1 for r in results if r.expected_png_exists)
    qr_generated = sum(1 for r in results if r.qr_string_generated)
    qr_matches = sum(1 for r in results if r.qr_string_matches)
    png_generated = sum(1 for r in results if r.qr_png_generated)
    png_parseable = sum(1 for r in results if r.qr_png_parseable)
    roundtrip_success = sum(1 for r in results if r.roundtrip_success)
    errors = sum(1 for r in results if r.error_message)

    print(f"\n{'='*60}")
    print("QR CODE GENERATION TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total tasks:              {total}")
    print(f"XCTSK files found:        {xctsk_found}")
    print(f"Expected TXT files:       {expected_txt_found}")
    print(f"Expected PNG files:       {expected_png_found}")
    print(f"QR strings generated:     {qr_generated}")
    print(f"QR strings match expected: {qr_matches}")
    if QR_CODE_SUPPORT:
        print(f"QR PNGs generated:        {png_generated}")
        print(f"QR PNGs parseable:        {png_parseable}")
        print(f"Roundtrip successful:     {roundtrip_success}")
    else:
        print("QR PNG generation:        SKIPPED (dependencies missing)")
    print(f"Errors:                   {errors}")
    print("=" * 60)


def print_detailed_results(results: List[QRCodeTestResult], show_matches: bool = False):
    """Print detailed results for each task."""
    print("\nDETAILED RESULTS:")
    print("-" * 80)

    for result in results:
        status_symbols = []

        if result.xctsk_exists:
            status_symbols.append("✓ XCTSK")
        else:
            status_symbols.append("✗ XCTSK")

        if result.expected_txt_exists:
            status_symbols.append("✓ TXT")
        else:
            status_symbols.append("✗ TXT")

        if result.expected_png_exists:
            status_symbols.append("✓ PNG")
        else:
            status_symbols.append("✗ PNG")

        if result.qr_string_generated:
            if result.qr_string_matches:
                status_symbols.append("✓ MATCH")
            elif result.expected_txt_exists:
                status_symbols.append("✗ MATCH")
            else:
                status_symbols.append("? MATCH")
        else:
            status_symbols.append("✗ GEN")

        if QR_CODE_SUPPORT:
            if result.qr_png_generated:
                status_symbols.append("✓ QR-GEN")
            else:
                status_symbols.append("✗ QR-GEN")

            if result.roundtrip_success:
                status_symbols.append("✓ ROUND")
            else:
                status_symbols.append("✗ ROUND")

        status_line = " ".join(status_symbols)
        print(f"{result.task_name:25} | {status_line}")

        if result.error_message:
            print(f"                          ERROR: {result.error_message}")

        if not result.qr_string_matches and result.expected_txt_exists and show_matches:
            print(
                f"                          EXPECTED: {result.expected_qr_string[:60]}..."
            )
            print(
                f"                          GENERATED: {result.generated_qr_string[:60]}..."
            )


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Test QR code generation for XCTSK files"
    )
    parser.add_argument(
        "--xctsk-dir",
        type=Path,
        default=Path(__file__).parent / "downloaded_tasks" / "xctsk",
        help="Directory containing XCTSK files",
    )
    parser.add_argument(
        "--expected-dir",
        type=Path,
        default=Path(__file__).parent / "downloaded_tasks" / "qrcode",
        help="Directory containing expected QR code results",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "downloaded_tasks" / "qrcode_test_output",
        help="Directory to save generated QR codes",
    )
    parser.add_argument(
        "--show-details",
        action="store_true",
        help="Show detailed results for each task",
    )
    parser.add_argument(
        "--show-mismatches",
        action="store_true",
        help="Show mismatched QR strings (implies --show-details)",
    )

    args = parser.parse_args()

    if args.show_mismatches:
        args.show_details = True

    # Create output directory
    args.output_dir.mkdir(exist_ok=True)

    # Find all XCTSK files
    xctsk_files = find_xctsk_files(args.xctsk_dir)

    if not xctsk_files:
        print(f"No XCTSK files found in {args.xctsk_dir}")
        return 1

    print(f"Found {len(xctsk_files)} XCTSK files in {args.xctsk_dir}")
    print(f"Expected results directory: {args.expected_dir}")
    print(f"Output directory: {args.output_dir}")

    if not QR_CODE_SUPPORT:
        print("\nWarning: QR code image generation will be skipped")
        print("To enable full testing, install: pip install Pillow pyzbar")

    # Test each file
    results = []
    for xctsk_file in sorted(xctsk_files):
        print(f"Processing {xctsk_file.name}...", end=" ", flush=True)
        result = test_qr_code_generation(xctsk_file, args.expected_dir, args.output_dir)
        results.append(result)

        if result.error_message:
            print("ERROR")
        elif result.qr_string_matches:
            print("✓")
        elif result.expected_txt_exists:
            print("✗")
        else:
            print("?")

    # Print results
    print_summary(results)

    if args.show_details:
        print_detailed_results(results, show_matches=args.show_mismatches)

    # Return error code if any tests failed
    failed_tests = [
        r
        for r in results
        if r.error_message or (r.expected_txt_exists and not r.qr_string_matches)
    ]
    if failed_tests:
        print(f"\n{len(failed_tests)} test(s) failed.")
        return 1
    else:
        print("\nAll tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
