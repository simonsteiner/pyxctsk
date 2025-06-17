import json
import logging
import os
import re
from bs4 import BeautifulSoup
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


class TaskDataExtractor:
    """Class to handle XCTrack task data extraction from HTML files"""

    def __init__(self, output_base_dir: str = "downloaded_tasks"):
        """Initialize with output directory structure"""
        self.output_dirs = {
            "html_cleaned": os.path.join(output_base_dir, "html_cleaned"),
            "json": os.path.join(output_base_dir, "json"),
            "geojson": os.path.join(output_base_dir, "geojson"),
        }

        # Create output directories
        for directory in self.output_dirs.values():
            os.makedirs(directory, exist_ok=True)

    def preprocess_html(self, html: str) -> BeautifulSoup:
        """Preprocess HTML by removing embedded base64 images"""
        soup = BeautifulSoup(html, "html.parser")

        # Remove embedded base64 images
        for img in soup.find_all("img", src=True):
            if img["src"].startswith("data:image/svg+xml;base64,"):
                img.decompose()

        return soup

    def save_cleaned_html(self, soup: BeautifulSoup, original_filename: str) -> str:
        """Save the cleaned HTML to a new file"""
        output_path = os.path.join(self.output_dirs["html_cleaned"], original_filename)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(str(soup))

        logger.info(f"Saved cleaned HTML to: {output_path}")
        return output_path

    def extract_task_metadata(self, html: str) -> Dict[str, Any]:
        """Extract all metadata from the HTML task details"""
        soup = BeautifulSoup(html, "html.parser")
        dt_elements = soup.find_all("dt")
        dd_elements = soup.find_all("dd")

        metadata = {}

        # Extract all metadata from definition list
        for i, dt in enumerate(dt_elements):
            if i < len(dd_elements):
                key = dt.get_text(strip=True).rstrip(":")
                value = dd_elements[i].get_text(strip=True)

                # Special handling for task distance
                if key == "Task distance":
                    metadata["task_distance_through_centers"] = value

                    # Check for optimized distance in next entry
                    if i + 1 < len(dd_elements) and not dt_elements[i + 1].get_text(
                        strip=True
                    ):
                        metadata["task_distance_optimized"] = dd_elements[
                            i + 1
                        ].get_text(strip=True)
                else:
                    # Convert key to snake_case
                    key = key.lower().replace(" ", "_")
                    metadata[key] = value

        # Extract distance values as numbers
        self._extract_distance_values(metadata)

        return metadata

    def _extract_distance_values(self, metadata: Dict[str, Any]) -> None:
        """Helper to extract numerical distance values from metadata strings"""
        distance_keys = [
            ("task_distance_through_centers", "distance_through_centers_km"),
            ("task_distance_optimized", "distance_optimized_km"),
        ]

        for source_key, target_key in distance_keys:
            if source_key in metadata:
                text_value = metadata[source_key]
                numeric_value = "".join(
                    c for c in text_value if c.isdigit() or c == "."
                )
                metadata[target_key] = float(numeric_value) if numeric_value else 0.0

    def extract_turnpoints(self, html: str) -> List[Dict[str, Any]]:
        """Extract turnpoint data from the task HTML"""
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="table")
        turnpoints = []

        if not table:
            logger.warning("No table found with class 'table'")
            return []

        # Find table headers
        headers = self._extract_table_headers(table)
        if not headers:
            return []

        # Extract table rows
        tbody = table.find("tbody")
        if not tbody:
            logger.warning("Table has no tbody element")
            return []

        rows = tbody.find_all("tr")
        logger.info(f"Found {len(rows)} rows in table")

        for row in rows:
            turnpoint = self._process_turnpoint_row(row, headers)
            if turnpoint:
                turnpoints.append(turnpoint)

        logger.info(f"Extracted {len(turnpoints)} turnpoints from table")
        return turnpoints

    def _extract_table_headers(self, table: BeautifulSoup) -> List[str]:
        """Extract headers from a table element"""
        thead = table.find("thead")
        if not thead:
            logger.warning("Table has no thead element")
            return []

        header_row = thead.find("tr")
        if not header_row:
            logger.warning("Table header row not found")
            return []

        th_elements = header_row.find_all("th")
        if not th_elements:
            logger.warning("No header cells found in header row")
            return []

        headers = [
            th.get_text(strip=True) for th in th_elements if th.get_text(strip=True)
        ]
        if not headers:
            logger.warning("No valid headers found in table")
            return []

        logger.info(f"Found table headers: {headers}")
        return headers

    def _process_turnpoint_row(
        self, row: BeautifulSoup, headers: List[str]
    ) -> Optional[Dict[str, Any]]:
        """Process a single turnpoint row from the table"""
        # Skip rows with no content
        if not row.contents:
            return None

        # Collect all cells from the row (th for the first column, td for the rest)
        cells = []
        th = row.find("th")
        if th and th.get_text(strip=True):
            cells.append(th)

        tds = row.find_all("td")
        cells.extend(tds)

        # Skip empty rows
        if not cells or not any(cell.get_text(strip=True) for cell in cells):
            return None

        # Make sure we have enough cells for the headers
        if len(cells) < len(headers):
            logger.warning(
                f"Row has {len(cells)} cells but expected {len(headers)} cells (skipping)"
            )
            return None

        # Only use the cells that match our headers
        cells = cells[: len(headers)]

        # Extract row data
        entry = self._extract_cell_values(cells, headers)

        # Add specific type information based on row class if Type is empty
        self._set_turnpoint_type(entry, row)

        return entry if entry else None

    def _extract_cell_values(
        self, cells: List[BeautifulSoup], headers: List[str]
    ) -> Dict[str, Any]:
        """Extract and convert values from cells based on headers"""
        entry = {}

        for i, header in enumerate(headers):
            if i >= len(cells):
                break

            text = cells[i].get_text(strip=True)
            if not text:
                continue

            try:
                if header == "#":
                    entry[header] = int(text)
                elif header == "Radius (m)":
                    # Remove 'm' suffix if present
                    text = text.replace("m", "")
                    entry[header] = int(text)
                elif header in ["Distance (km)", "Optimized (km)"]:
                    # Remove 'km' suffix if present
                    text = text.replace("km", "")
                    entry[header] = float(text)
                else:
                    entry[header] = text
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Error parsing value '{text}' for header '{header}': {e}"
                )
                entry[header] = text

        return entry

    def _set_turnpoint_type(self, entry: Dict[str, Any], row: BeautifulSoup) -> None:
        """Set the turnpoint type based on row class or defaults"""
        if "Type" in entry and not entry["Type"]:
            row_class = row.get("class", [])
            row_title = row.get("title", "")

            if "table-primary" in row_class:
                if "Start of speed section" in row_title:
                    entry["Type"] = "SSS"
                elif "End of speed section" in row_title:
                    entry["Type"] = "ESS"
            elif "table-danger" in row_class:
                entry["Type"] = "Goal"
            else:
                entry["Type"] = "Turnpoint"
        elif "Type" in entry.keys() and "Type" not in entry:
            entry["Type"] = "Turnpoint"

    def extract_geojson(self, html: str) -> Optional[Dict[str, Any]]:
        """Extract GeoJSON data from JavaScript in the HTML file"""
        # Look for the geojson variable definition in the script
        # This pattern handles both single-line and multi-line GeoJSON definitions
        geojson_pattern = (
            r'var\s+geojson\s*=\s*(\{\s*"type"\s*:\s*"FeatureCollection".+?});'
        )
        geojson_match = re.search(geojson_pattern, html, re.DOTALL)

        if not geojson_match:
            logger.warning("No GeoJSON data found in the HTML")
            return None

        try:
            # Extract and clean the raw JSON string
            geojson_str = geojson_match.group(1)
            geojson_str = re.sub(
                r",\s*([}\]])", r"\1", geojson_str
            )  # Remove trailing commas

            # Parse the JSON string into a Python dictionary
            geojson_data = json.loads(geojson_str)

            # Validate the GeoJSON structure
            if self._validate_geojson(geojson_data):
                return geojson_data

            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing GeoJSON data: {e}")
            # Debug information to help diagnose JSON parsing errors
            logger.debug(f"JSON extract starts with: {geojson_str[:100]}...")
            logger.debug(f"JSON extract ends with: ...{geojson_str[-100:]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error processing GeoJSON: {e}")
            return None

    def _validate_geojson(self, geojson_data: Any) -> bool:
        """Validate GeoJSON data structure"""
        if not isinstance(geojson_data, dict):
            logger.warning(
                f"GeoJSON data is not a dictionary, got {type(geojson_data)}"
            )
            return False

        if "type" not in geojson_data or geojson_data["type"] != "FeatureCollection":
            logger.warning(
                "GeoJSON data does not appear to be a valid FeatureCollection"
            )
            return False

        if "features" not in geojson_data or not isinstance(
            geojson_data["features"], list
        ):
            logger.warning("GeoJSON data does not have a valid features list")
            return False

        return True

    def save_data_to_file(
        self, data: Dict[str, Any], filename: str, data_type: str
    ) -> Optional[str]:
        """Save data to a file (JSON or GeoJSON)"""
        if data_type not in ["json", "geojson"]:
            logger.error(f"Invalid data type: {data_type}")
            return None

        # Type-specific validation
        if data_type == "geojson" and not self._validate_geojson(data):
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

    def extract_task_data(
        self, html_content: str
    ) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
        """Extract all task data from HTML content"""
        # Extract metadata
        metadata = self.extract_task_metadata(html_content)

        # Extract turnpoints
        logger.info("Extracting turnpoints...")
        turnpoints = self.extract_turnpoints(html_content)

        # Extract GeoJSON data
        logger.info("Extracting GeoJSON data...")
        geojson_data = self.extract_geojson(html_content)

        # Combine data into a complete task object
        task_data = {"metadata": metadata, "turnpoints": turnpoints}

        return task_data, geojson_data

    def process_html_file(self, file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """Process a single HTML file and extract task data"""
        filename = os.path.basename(file_path)
        logger.info(f"Processing {filename}")

        try:
            # Read the HTML file
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            logger.info(f"File size: {len(html_content)} bytes")

            # Extract task data
            task_data, geojson_data = self.extract_task_data(html_content)

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
        """Display extracted task information for debugging/monitoring"""
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
        """Process all HTML files in a directory"""
        files_processed = 0

        for filename in sorted(os.listdir(directory_path)):
            if filename.endswith(".html"):
                if max_files is not None and files_processed >= max_files:
                    break

                file_path = os.path.join(directory_path, filename)
                logger.info(f"\n--- Processing {filename} ---")

                self.process_html_file(file_path)
                files_processed += 1

    def preprocess_directory(self, directory_path: str) -> None:
        """Preprocess all HTML files in a directory (clean and save)"""
        for filename in sorted(os.listdir(directory_path)):
            if filename.endswith(".html"):
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
    # extractor.preprocess_directory("downloaded_tasks/html")
    # print("\n==== PREPROCESSING HTML FILES ====")
    # print("Preprocessed HTML files saved to:", extractor.output_dirs["html_cleaned"])

    print("\n==== PROCESSING HTML FILES ====")
    print("Processing HTML files and saving JSON and GeoJSON...")

    # Process a couple of files first (for testing)
    extractor.process_directory(
        "downloaded_tasks/html_cleaned",
        # comment out max_files to process all files
        # max_files=2,
    )
