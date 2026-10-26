import json
import logging
import os
from typing import Any, Dict, Optional, Tuple

from bs4 import BeautifulSoup
from task_html_parser import extract_task_data, validate_geojson

"""
Extract and convert XCTrack task data from HTML files to structured JSON and GeoJSON formats.

This script provides the TaskDataExtractor class, which cleans
paragliding/hang gliding competition task pages from XCTrack HTML exports and saves
what `task_html_parser` extracts from them (metadata, turnpoints and the GeoJSON
embedded in their JavaScript) to clean HTML, JSON, and GeoJSON files in a
structured directory.

Usage:
    Run as a script to process all HTML files in the input directory (downloaded_tasks/html_cleaned):
        python scripts/extract_task_data.py
"""
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TaskDataExtractor:
    """Extracts XCTrack task data from HTML files into structured formats.

    Handles the file I/O, the logging of what was found and the directory loops; the
    parsing of metadata, turnpoints and GeoJSON is `task_html_parser`'s.
    """

    def __init__(self, output_base_dir: str = "downloaded_tasks"):
        """Initializes the extractor with output directory structure.

        Args:
            output_base_dir (str): Base directory for output files.
        """
        self.output_dirs = {
            "html_cleaned": os.path.join(output_base_dir, "html_cleaned"),
            "json": os.path.join(output_base_dir, "json"),
            "geojson": os.path.join(output_base_dir, "geojson"),
        }

        # Create output directories
        for directory in self.output_dirs.values():
            os.makedirs(directory, exist_ok=True)

    def preprocess_html(self, html: str) -> BeautifulSoup:
        """Removes embedded base64 images from HTML content.

        Args:
            html (str): Raw HTML content.

        Returns:
            BeautifulSoup: Parsed and cleaned HTML soup.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Remove embedded base64 images
        for img in soup.find_all("img", src=True):
            if img["src"].startswith("data:image/svg+xml;base64,"):
                img.decompose()

        return soup

    def save_cleaned_html(self, soup: BeautifulSoup, original_filename: str) -> str:
        """Saves cleaned HTML to a file in the output directory.

        Args:
            soup (BeautifulSoup): Cleaned HTML soup.
            original_filename (str): Name of the original HTML file.

        Returns:
            str: Path to the saved cleaned HTML file.
        """
        output_path = os.path.join(self.output_dirs["html_cleaned"], original_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        logger.info(f"Saved cleaned HTML to: {output_path}")
        return output_path

    def save_data_to_file(
        self, data: Dict[str, Any], filename: str, data_type: str
    ) -> Optional[str]:
        """Saves data to a file (JSON or GeoJSON) in the appropriate output directory.

        Args:
            data (Dict[str, Any]): Data to save.
            filename (str): Original filename (used for output name).
            data_type (str): Either 'json' or 'geojson'.

        Returns:
            Optional[str]: Path to the saved file, or None if error/invalid.
        """
        if data_type not in ["json", "geojson"]:
            logger.error(f"Invalid data type: {data_type}")
            return None

        # Type-specific validation
        if data_type == "geojson" and not validate_geojson(data):
            return None

        try:
            # Create output filename based on input filename
            base_name = os.path.splitext(os.path.basename(filename))[0]
            file_extension = ".json" if data_type == "json" else ".geojson"
            output_path = os.path.join(
                self.output_dirs[data_type], f"{base_name}{file_extension}"
            )

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Data saved to: {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error saving {data_type} file: {e}")
            return None

    def process_html_file(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Processes a single HTML file and extracts task data, saving JSON and GeoJSON.

        Args:
            file_path (str): Path to the HTML file to process.

        Returns:
            Tuple[Optional[str], Optional[str]]: Paths to saved JSON and GeoJSON files, or None if error.
        """
        filename = os.path.basename(file_path)
        logger.info(f"Processing {filename}")

        try:
            # Read the HTML file
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            logger.info(f"File size: {len(html_content)} bytes")

            # Extract task data
            task_data, geojson_data = extract_task_data(html_content)

            # Display extracted information
            self._display_task_info(task_data, geojson_data)

            # Save data to files
            json_path = self.save_data_to_file(task_data, filename, "json")
            geojson_path = None
            if geojson_data:
                geojson_path = self.save_data_to_file(geojson_data, filename, "geojson")

            return json_path, geojson_path
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
            return None, None

    def _display_task_info(
        self, task_data: Dict[str, Any], geojson_data: Optional[Dict[str, Any]]
    ) -> None:
        """Displays extracted task information for debugging and monitoring.

        Args:
            task_data (Dict[str, Any]): Extracted task data (metadata and turnpoints).
            geojson_data (Optional[Dict[str, Any]]): Extracted GeoJSON data, if any.
        """
        metadata = task_data.get("metadata", {})
        turnpoints = task_data.get("turnpoints", [])

        # Display metadata
        if metadata:
            logger.info("Task Metadata:")
            for key, value in metadata.items():
                if key in ["distance_through_centers_km", "distance_optimized_km"]:
                    logger.info(f"  {key}: {float(value):.1f}km")
                else:
                    logger.info(f"  {key}: {value}")
        else:
            logger.info("No metadata found")

        # Display turnpoints
        if turnpoints:
            logger.info(f"Found {len(turnpoints)} turnpoints:")
            for tp in turnpoints:
                logger.info(f"  {tp}")
        else:
            logger.info("No turnpoints extracted")

        # Display GeoJSON info
        if geojson_data:
            feature_count = len(geojson_data.get("features", []))
            logger.info(f"GeoJSON data found with {feature_count} features")
        else:
            logger.info("No GeoJSON data found")

    def process_directory(
        self, directory_path: str, max_files: Optional[int] = None
    ) -> None:
        """Processes all HTML files in a directory, extracting and saving data for each.

        Args:
            directory_path (str): Path to directory containing HTML files.
            max_files (Optional[int]): Maximum number of files to process (for testing).

        Returns:
            None
        """
        files_processed = 0

        for filename in sorted(os.listdir(directory_path)):
            if filename.endswith(".html"):
                if max_files is not None and files_processed >= max_files:
                    break

                file_path = os.path.join(directory_path, filename)
                logger.info(f"\n\n--- Processing {filename} ---")

                self.process_html_file(file_path)
                files_processed += 1

    def preprocess_directory(self, directory_path: str) -> None:
        """Preprocesses all HTML files in a directory by cleaning and saving them, skipping files already cleaned.

        Args:
            directory_path (str): Path to directory containing HTML files.

        Returns:
            None
        """
        for filename in sorted(os.listdir(directory_path)):
            if filename.endswith(".html"):
                cleaned_path = os.path.join(self.output_dirs["html_cleaned"], filename)
                if os.path.exists(cleaned_path):
                    logger.info(f"Skipping {filename}: cleaned file already exists.")
                    continue
                file_path = os.path.join(directory_path, filename)
                with open(file_path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                # Preprocess HTML to remove base64 images
                cleaned_soup = self.preprocess_html(html_content)
                # Save cleaned HTML
                self.save_cleaned_html(cleaned_soup.prettify(), filename)


if __name__ == "__main__":
    print("\n==== PROCESSING HTML FILES AND SAVING JSON AND GEOJSON ====")

    extractor = TaskDataExtractor()

    # Preprocess HTML files to remove base64 images
    print("\n==== PREPROCESSING HTML FILES ====")
    print("Cleaned HTML files saved to:", extractor.output_dirs["html_cleaned"])
    print("Preprocessing HTML files...")
    extractor.preprocess_directory("downloaded_tasks/html")

    print("\n==== PROCESSING HTML FILES ====")
    print("Processing HTML files and saving JSON and GeoJSON...\n")

    # Process a couple of files first (for testing)
    extractor.process_directory(
        "downloaded_tasks/html_cleaned",
        # comment out max_files to process all files
        # max_files=2,
    )
