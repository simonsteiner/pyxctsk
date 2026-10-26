#!/usr/bin/env python3
"""
XCTrack XCTSK File Upload/Download Automation Script

This script automates the upload and download of XCTSK files to/from
https://tools.xcontest.org/xctsk/ using their REST API.

Usage:
    # Simplified one-command operation:
    python xcontest_xctsk_tool.py process --author "Your Name"

    # Individual operations:
    python xcontest_xctsk_tool.py upload --directory xctsk_files --author "Your Name"
    python xcontest_xctsk_tool.py download --codes waku,motu,duna --output downloaded_tasks/xctsk
    python xcontest_xctsk_tool.py qr --file task.xctsk --output qr.svg
    python xcontest_xctsk_tool.py html --codes waku,motu,duna --output downloaded_tasks/html
"""

import argparse
import json
import sys
from pathlib import Path

from xcontest_client import (
    XCTSKClient,
    download_html_tasks,
    download_tasks,
    process_all_tasks,
    upload_directory,
)


def main():
    """
    Main entry point for the XCTSK automation script.

    Parses command-line arguments and dispatches to the appropriate command handler.

    Returns:
        int: Exit code (0 for success, 1 for error).
    """
    parser = argparse.ArgumentParser(
        description="Automate upload/download of XCTSK files to/from XContest tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Process all tasks (upload XCTSK files and download HTML):
    python xcontest_xctsk_tool.py process --author "John Doe"
    python xcontest_xctsk_tool.py process --xctsk-dir custom/path --html-output output/html --author "John Doe"

  Upload all XCTSK files in a directory:
    python xcontest_xctsk_tool.py upload --directory xctsk_files --author "John Doe"

  Download specific tasks:
    python xcontest_xctsk_tool.py download --codes waku,motu,duna --output results/

  Generate QR code for a task:
    python xcontest_xctsk_tool.py qr --file task.xctsk --output qr.svg
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Upload command
    upload_parser = subparsers.add_parser("upload", help="Upload XCTSK files")
    upload_parser.add_argument(
        "--directory",
        "-d",
        type=Path,
        required=True,
        help="Directory containing XCTSK files",
    )
    upload_parser.add_argument(
        "--author", "-a", type=str, help="Author name for uploads"
    )
    upload_parser.add_argument(
        "--results-file",
        "-r",
        type=Path,
        help="File to save upload results (JSON format)",
    )

    # Download command
    download_parser = subparsers.add_parser("download", help="Download tasks by code")
    download_parser.add_argument(
        "--codes",
        "-c",
        type=str,
        required=True,
        help="Comma-separated list of task codes",
    )
    download_parser.add_argument(
        "--output", "-o", type=Path, required=True, help="Output directory"
    )
    download_parser.add_argument(
        "--version",
        "-v",
        type=int,
        choices=[1, 2],
        default=1,
        help="API version (1 or 2)",
    )

    # QR code command
    qr_parser = subparsers.add_parser("qr", help="Generate QR code for XCTSK file")
    qr_parser.add_argument("--file", "-f", type=Path, required=True, help="XCTSK file")
    qr_parser.add_argument(
        "--output", "-o", type=Path, required=True, help="Output SVG file"
    )

    # HTML download command
    html_parser = subparsers.add_parser("html", help="Download HTML pages for tasks")
    html_parser.add_argument(
        "--codes",
        "-c",
        type=str,
        required=True,
        help="Comma-separated list of task codes",
    )
    html_parser.add_argument(
        "--output", "-o", type=Path, required=True, help="Output directory"
    )

    # Process command - upload all and download HTML
    process_parser = subparsers.add_parser(
        "process", help="Upload all XCTSK files and download their HTML pages"
    )
    process_parser.add_argument(
        "--xctsk-dir",
        "-x",
        type=Path,
        default=Path(__file__).parent / "xctsk_files",
        help="Directory containing XCTSK files (default: xctsk_files)",
    )
    process_parser.add_argument(
        "--html-output",
        "-o",
        type=Path,
        default=Path(__file__).parent / "downloaded_tasks" / "html",
        help="Directory to save HTML files (default: downloaded_tasks/html)",
    )
    process_parser.add_argument(
        "--author", "-a", type=str, help="Author name for uploads"
    )
    process_parser.add_argument(
        "--results-file",
        "-r",
        type=Path,
        default=Path(__file__).parent / "upload_results.json",
        help="File to save upload results (JSON format) (default: upload_results.json)",
    )

    # Global options
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of retries for failed requests (default: 3)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Create client
    client = XCTSKClient(timeout=args.timeout, retry_count=args.retries)

    try:
        if args.command == "upload":
            if not args.directory.exists():
                print(f"Error: Directory {args.directory} does not exist")
                return 1

            results = upload_directory(client, args.directory, args.author)

            # Print summary
            successful = len(results)
            total = len(list(args.directory.glob("*.xctsk")))
            print(f"\nUpload Summary: {successful}/{total} files uploaded successfully")

            if results:
                print("\nTask codes:")
                for filename, task_code in results.items():
                    print(f"  {filename}: {task_code}")

            # Save results to file if requested
            if args.results_file:
                args.results_file.parent.mkdir(parents=True, exist_ok=True)
                with open(args.results_file, "w") as f:
                    json.dump(results, f, indent=2)
                print(f"\nResults saved to {args.results_file}")

        elif args.command == "download":
            try:
                task_codes = [code.strip() for code in args.codes.split(",")]
            except ValueError:
                print("Error: Invalid task codes format. Use comma-separated codes.")
                return 1

            results = download_tasks(client, task_codes, args.output, args.version)

            print(
                f"\nDownload Summary: {len(results)}/{len(task_codes)} tasks downloaded successfully"
            )

        elif args.command == "qr":
            if not args.file.exists():
                print(f"Error: File {args.file} does not exist")
                return 1

            success, message = client.get_qr_code(args.file, args.output)
            print(message)

            if not success:
                return 1

        elif args.command == "html":
            try:
                task_codes = [code.strip() for code in args.codes.split(",")]
            except ValueError:
                print("Error: Invalid task codes format. Use comma-separated codes.")
                return 1

            results = download_html_tasks(client, task_codes, args.output)

            print(
                f"\nHTML Download Summary: {len(results)}/{len(task_codes)} tasks downloaded successfully"
            )

        elif args.command == "process":
            if not args.xctsk_dir.exists():
                print(f"Error: Directory {args.xctsk_dir} does not exist")
                return 1

            upload_results, html_results = process_all_tasks(
                client, args.xctsk_dir, args.html_output, args.author, args.results_file
            )

            if not upload_results:
                print("No files were processed successfully")
                return 1

        elif args.command == "process":
            if not args.directory.exists():
                print(f"Error: Directory {args.directory} does not exist")
                return 1
            if not args.html_output.exists():
                print(f"Error: HTML output directory {args.html_output} does not exist")
                return 1

            process_all_tasks(
                client, args.directory, args.html_output, args.author, args.results_file
            )

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
