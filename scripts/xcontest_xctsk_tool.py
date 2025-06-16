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
    python xcontest_xctsk_tool.py download --codes waku,motu,duna --output results/
    python xcontest_xctsk_tool.py qr --file task.xctsk --output qr.svg
    python xcontest_xctsk_tool.py html --codes waku,motu,duna --output html_pages/
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class XCTSKClient:
    """Client for interacting with XContest XCTSK API."""

    BASE_URL = "https://tools.xcontest.org"

    def __init__(
        self, author: Optional[str] = None, timeout: int = 30, retry_count: int = 3
    ):
        """Initialize the client.

        Args:
            author: Default author name for uploads
            timeout: Request timeout in seconds
            retry_count: Number of retries for failed requests
        """
        self.author = author
        self.timeout = timeout
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=retry_count,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=1,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def upload_task(
        self, xctsk_file: Path, author: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """Upload an XCTSK file and get a task code.

        Args:
            xctsk_file: Path to the XCTSK file
            author: Author name (overrides default)

        Returns:
            Tuple of (task_code, message)
        """
        try:
            with open(xctsk_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return None, f"Error reading file {xctsk_file}: {e}"

        headers = {"Content-Type": "application/json"}

        # Add author header if provided
        upload_author = author or self.author
        if upload_author:
            headers["Author"] = upload_author

        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/xctsk/save",
                json=task_data,
                headers=headers,
                timeout=self.timeout,
            )

            if response.status_code == 200:
                try:
                    # Try to parse as JSON first (new API format)
                    try:
                        response_data = response.json()
                        if (
                            isinstance(response_data, dict)
                            and "taskCode" in response_data
                        ):
                            task_code = response_data["taskCode"]
                            return (
                                task_code,
                                f"Successfully uploaded {xctsk_file.name}, task code: {task_code}",
                            )
                        else:
                            return (
                                None,
                                f"Invalid JSON response format: {response.text}",
                            )
                    except json.JSONDecodeError:
                        # Fallback to old format (plain numeric response)
                        task_code = int(response.text.strip())
                        return (
                            task_code,
                            f"Successfully uploaded {xctsk_file.name}, task code: {task_code}",
                        )
                except ValueError:
                    return None, f"Invalid response format: {response.text}"
            else:
                return (
                    None,
                    f"Upload failed with status {response.status_code}: {response.text}",
                )

        except requests.RequestException as e:
            return None, f"Network error uploading {xctsk_file.name}: {e}"

    def download_task(
        self, task_code: str, output_file: Path, version: int = 1
    ) -> Tuple[bool, str]:
        """Download a task by code.

        Args:
            task_code: The task code to download
            output_file: Path where to save the downloaded task
            version: API version (1 or 2)

        Returns:
            Tuple of (success, message)
        """
        endpoint = (
            f"/api/xctsk/load/{task_code}"
            if version == 1
            else f"/api/xctsk/loadV2/{task_code}"
        )

        try:
            response = self.session.get(
                f"{self.BASE_URL}{endpoint}", timeout=self.timeout
            )

            if response.status_code == 200:
                # Ensure output directory exists
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(response.text)

                # Extract metadata from headers
                metadata = {}
                if "Last-Modified" in response.headers:
                    metadata["last_modified"] = response.headers["Last-Modified"]
                if "Author" in response.headers:
                    metadata["author"] = response.headers["Author"]

                metadata_str = ""
                if metadata:
                    metadata_str = f" (Author: {metadata.get('author', 'Unknown')}, Modified: {metadata.get('last_modified', 'Unknown')})"

                return (
                    True,
                    f"Downloaded task {task_code} to {output_file}{metadata_str}",
                )
            else:
                return (
                    False,
                    f"Download failed with status {response.status_code}: {response.text}",
                )

        except requests.RequestException as e:
            return False, f"Network error downloading task {task_code}: {e}"

    def get_qr_code(self, xctsk_file: Path, output_file: Path) -> Tuple[bool, str]:
        """Get QR code SVG for an XCTSK file.

        Args:
            xctsk_file: Path to the XCTSK file
            output_file: Path where to save the QR code SVG

        Returns:
            Tuple of (success, message)
        """
        try:
            with open(xctsk_file, "r", encoding="utf-8") as f:
                task_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            return False, f"Error reading file {xctsk_file}: {e}"

        try:
            response = self.session.post(
                f"{self.BASE_URL}/api/xctsk/qr",
                json=task_data,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )

            if response.status_code == 200:
                # Ensure output directory exists
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(response.text)

                return True, f"Generated QR code for {xctsk_file.name} -> {output_file}"
            else:
                return (
                    False,
                    f"QR generation failed with status {response.status_code}: {response.text}",
                )

        except requests.RequestException as e:
            return False, f"Network error generating QR for {xctsk_file.name}: {e}"

    def download_html(
        self, task_code: str, output_file: Optional[Path] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """Download HTML page for a task from XContest tools.

        Args:
            task_code: The task code to download HTML for
            output_file: Optional path where to save the HTML content

        Returns:
            Tuple of (success, message, html_content)
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/xctsk/load?taskCode={task_code}",
                timeout=self.timeout,
            )

            if response.status_code == 200:
                html_content = response.text

                if output_file:
                    # Ensure output directory exists
                    output_file.parent.mkdir(parents=True, exist_ok=True)

                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(html_content)

                    return (
                        True,
                        f"Downloaded HTML for task {task_code} to {output_file}",
                        html_content,
                    )
                else:
                    return (
                        True,
                        f"Retrieved HTML for task {task_code}",
                        html_content,
                    )
            else:
                return (
                    False,
                    f"HTML download failed with status {response.status_code}: {response.text}",
                    None,
                )

        except requests.RequestException as e:
            return (
                False,
                f"Network error downloading HTML for task {task_code}: {e}",
                None,
            )


def upload_directory(
    client: XCTSKClient, directory: Path, author: Optional[str] = None
) -> Dict[str, str]:
    """Upload all XCTSK files in a directory.

    Args:
        client: XCTSKClient instance
        directory: Directory containing XCTSK files
        author: Author name for uploads

    Returns:
        Dictionary mapping filenames to task codes
    """
    results = {}
    xctsk_files = list(directory.glob("*.xctsk"))

    if not xctsk_files:
        print(f"No XCTSK files found in {directory}")
        return results

    print(f"Found {len(xctsk_files)} XCTSK files to upload...")

    for i, xctsk_file in enumerate(xctsk_files, 1):
        print(f"[{i}/{len(xctsk_files)}] Uploading {xctsk_file.name}...")

        task_code, message = client.upload_task(xctsk_file, author)
        print(f"  {message}")

        if task_code:
            results[xctsk_file.name] = task_code

        # Add a small delay to be respectful to the server
        if i < len(xctsk_files):
            time.sleep(1)

    return results


def download_tasks(
    client: XCTSKClient, task_codes: List[str], output_dir: Path, version: int = 1
) -> List[str]:
    """Download multiple tasks by code.

    Args:
        client: XCTSKClient instance
        task_codes: List of task codes to download
        output_dir: Output directory
        version: API version (1 or 2)

    Returns:
        List of success messages
    """
    results = []

    print(f"Downloading {len(task_codes)} tasks...")

    for i, task_code in enumerate(task_codes, 1):
        print(f"[{i}/{len(task_codes)}] Downloading task {task_code}...")

        output_file = output_dir / f"task_{task_code}.xctsk"
        success, message = client.download_task(task_code, output_file, version)
        print(f"  {message}")

        if success:
            results.append(message)

        # Add a small delay to be respectful to the server
        if i < len(task_codes):
            time.sleep(1)

    return results


def download_html_tasks(
    client: XCTSKClient, task_codes: List[str], output_dir: Path
) -> List[str]:
    """Download HTML pages for multiple tasks by code.

    Args:
        client: XCTSKClient instance
        task_codes: List of task codes to download HTML for
        output_dir: Output directory

    Returns:
        List of success messages
    """
    results = []

    print(f"Downloading HTML for {len(task_codes)} tasks...")

    for i, task_code in enumerate(task_codes, 1):
        print(f"[{i}/{len(task_codes)}] Downloading HTML for task {task_code}...")

        output_file = output_dir / f"task_{task_code}.html"
        success, message, _ = client.download_html(task_code, output_file)
        print(f"  {message}")

        if success:
            results.append(message)

        # Add a small delay to be respectful to the server
        if i < len(task_codes):
            time.sleep(1)

    return results


def process_all_tasks(
    client: XCTSKClient,
    xctsk_directory: Path,
    html_output_dir: Path,
    author: Optional[str] = None,
    results_file: Optional[Path] = None,
) -> Tuple[Dict[str, str], List[str]]:
    """Upload all XCTSK files and download their HTML pages.

    Args:
        client: XCTSKClient instance
        xctsk_directory: Directory containing XCTSK files
        html_output_dir: Directory to save HTML files
        author: Author name for uploads
        results_file: Optional file to save upload results

    Returns:
        Tuple of (upload_results, html_results)
    """
    print("=== Step 1: Uploading all XCTSK files ===")
    upload_results = upload_directory(client, xctsk_directory, author)

    if not upload_results:
        print("No files were uploaded successfully. Stopping.")
        return {}, []

    # Save upload results if requested
    if results_file:
        results_file.parent.mkdir(parents=True, exist_ok=True)
        with open(results_file, "w") as f:
            json.dump(upload_results, f, indent=2)
        print(f"Upload results saved to {results_file}")

    print(f"\nUpload Summary: {len(upload_results)} files uploaded successfully")
    print("Task codes:")
    for filename, task_code in upload_results.items():
        print(
            f"  {filename}: {task_code}, {client.BASE_URL}/xctsk/load?taskCode={task_code}"
        )

    print("\n=== Step 2: Downloading HTML pages ===")
    task_codes = list(upload_results.values())
    html_results = download_html_tasks(client, task_codes, html_output_dir)

    print(f"\nProcess Summary:")
    print(f"  Uploaded: {len(upload_results)} XCTSK files")
    print(f"  Downloaded: {len(html_results)} HTML pages")

    return upload_results, html_results


def main():
    """Main entry point."""
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
