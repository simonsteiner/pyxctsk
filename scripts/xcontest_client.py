"""
The XContest XCTSK REST API client and the batch loops built on it.

`XCTSKClient` makes one request per call; `upload_directory`, `download_tasks`,
`download_html_tasks` and `process_all_tasks` loop over many, pausing between
requests. The command line is `xcontest_xctsk_tool.py`.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def safe_path(path: Path) -> Path:
    """Resolve a path the tool was given, refusing one outside the working directory.

    Args:
        path (Path): A file path from the command line, or built from one.

    Returns:
        Path: The canonical path.

    Raises:
        ValueError: If the path resolves outside the directory the tool runs in.
    """
    resolved = os.path.realpath(path)
    base_dir = os.path.realpath(os.getcwd())
    if resolved != base_dir and not resolved.startswith(base_dir + os.sep):
        raise ValueError(f"path {str(path)!r} is outside the allowed directory")
    return Path(resolved)


class XCTSKClient:
    """
    Client for interacting with the XContest XCTSK API.

    Handles upload, download, QR code generation, and HTML retrieval for XCTSK tasks via the XContest REST API.
    """

    BASE_URL = "https://tools.xcontest.org"

    def __init__(
        self, author: Optional[str] = None, timeout: int = 30, retry_count: int = 3
    ):
        """
        Initializes the XCTSKClient.

        Args:
            author (Optional[str]): Default author name for uploads.
            timeout (int): Request timeout in seconds.
            retry_count (int): Number of retries for failed requests.
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
        self.session.mount("https://", adapter)

    def upload_task(
        self, xctsk_file: Path, author: Optional[str] = None
    ) -> Tuple[Optional[str], str]:
        """
        Uploads an XCTSK file to the XContest API and retrieves the task code.

        Args:
            xctsk_file (Path): Path to the XCTSK file.
            author (Optional[str]): Author name (overrides default).

        Returns:
            Tuple[Optional[str], str]: Tuple of (task_code, message). task_code is None if upload fails.

        Raises:
            None. All exceptions are caught and returned as part of the message.
        """
        try:
            with open(safe_path(xctsk_file), "r", encoding="utf-8") as f:
                task_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
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
        """
        Downloads a task by code from the XContest API.

        Args:
            task_code (str): The task code to download.
            output_file (Path): Path where to save the downloaded task.
            version (int): API version (1 or 2).

        Returns:
            Tuple[bool, str]: Tuple of (success, message).

        Raises:
            None. All exceptions are caught and returned as part of the message.
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
                output_path = safe_path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f:
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
        """
        Generates a QR code SVG for an XCTSK file using the XContest API.

        Args:
            xctsk_file (Path): Path to the XCTSK file.
            output_file (Path): Path where to save the QR code SVG.

        Returns:
            Tuple[bool, str]: Tuple of (success, message).

        Raises:
            None. All exceptions are caught and returned as part of the message.
        """
        try:
            with open(safe_path(xctsk_file), "r", encoding="utf-8") as f:
                task_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
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
                output_path = safe_path(output_file)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f:
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
        """
        Downloads the HTML page for a task from XContest tools.

        Args:
            task_code (str): The task code to download HTML for.
            output_file (Optional[Path]): Optional path where to save the HTML content.

        Returns:
            Tuple[bool, str, Optional[str]]: Tuple of (success, message, html_content).

        Raises:
            None. All exceptions are caught and returned as part of the message.
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
                    output_path = safe_path(output_file)
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(output_path, "w", encoding="utf-8") as f:
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
    """
    Uploads all XCTSK files in a directory to the XContest API.

    Args:
        client (XCTSKClient): XCTSKClient instance.
        directory (Path): Directory containing XCTSK files.
        author (Optional[str]): Author name for uploads.

    Returns:
        Dict[str, str]: Dictionary mapping filenames to task codes.
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
    """
    Downloads multiple tasks by code from the XContest API.

    Args:
        client (XCTSKClient): XCTSKClient instance.
        task_codes (List[str]): List of task codes to download.
        output_dir (Path): Output directory.
        version (int): API version (1 or 2).

    Returns:
        List[str]: List of success messages for each downloaded task.
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
    """
    Downloads HTML pages for multiple tasks by code from the XContest API.

    Args:
        client (XCTSKClient): XCTSKClient instance.
        task_codes (List[str]): List of task codes to download HTML for.
        output_dir (Path): Output directory.

    Returns:
        List[str]: List of success messages for each downloaded HTML page.
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
    """
    Uploads all XCTSK files in a directory and downloads their HTML pages.

    Args:
        client (XCTSKClient): XCTSKClient instance.
        xctsk_directory (Path): Directory containing XCTSK files.
        html_output_dir (Path): Directory to save HTML files.
        author (Optional[str]): Author name for uploads.
        results_file (Optional[Path]): Optional file to save upload results.

    Returns:
        Tuple[Dict[str, str], List[str]]: Tuple of (upload_results, html_results).
    """
    print("=== Step 1: Uploading all XCTSK files ===")
    upload_results = upload_directory(client, xctsk_directory, author)

    if not upload_results:
        print("No files were uploaded successfully. Stopping.")
        return {}, []

    # Save upload results if requested
    if results_file:
        results_path = safe_path(results_file)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        with open(results_path, "w") as f:
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

    print("\nProcess Summary:")
    print(f"  Uploaded: {len(upload_results)} XCTSK files")
    print(f"  Downloaded: {len(html_results)} HTML pages")

    return upload_results, html_results
