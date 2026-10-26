"""
Parse an XContest task page's HTML into task data and GeoJSON.

`extract_task_data` is the entry point: metadata and turnpoints from the page's
tables, GeoJSON from its embedded JavaScript. `extract_task_data.py` reads the
pages and writes what this returns.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_task_data(
    html_content: str,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Extracts all task data (metadata, turnpoints, GeoJSON) from HTML content.

    Args:
        html_content (str): HTML content of the task file.

    Returns:
        Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
            - Task data dictionary (metadata and turnpoints)
            - GeoJSON dictionary or None
    """
    # Extract metadata
    metadata = extract_task_metadata(html_content)

    # Extract turnpoints
    logger.info("Extracting turnpoints...")
    turnpoints = extract_turnpoints(html_content)

    # Extract GeoJSON data
    logger.info("Extracting GeoJSON data...")
    geojson_data = extract_geojson(html_content)

    # Combine data into a complete task object
    task_data = {"metadata": metadata, "turnpoints": turnpoints}

    return task_data, geojson_data


def extract_task_metadata(html: str) -> Dict[str, Any]:
    """Extracts all task metadata from the HTML task details section.

    Args:
        html (str): HTML content of the task file.

    Returns:
        Dict[str, Any]: Dictionary of extracted metadata fields.
    """
    soup = BeautifulSoup(html, "html.parser")
    dt_elements = soup.find_all("dt")
    dd_elements = soup.find_all("dd")

    metadata = {}

    # Extract all metadata from definition list
    for i, dt in enumerate(dt_elements):
        dt_text = dt.get_text(strip=True)
        if not dt_text:
            continue  # Skip if dt is empty
        if i < len(dd_elements):
            key = dt_text.rstrip(":")
            value = dd_elements[i].get_text(strip=True)

            # Special handling for task distance
            if key == "Task distance":
                metadata["task_distance_through_centers"] = value

                # Check for optimized distance in next entry
                if i + 1 < len(dd_elements) and not dt_elements[i + 1].get_text(
                    strip=True
                ):
                    metadata["task_distance_optimized"] = dd_elements[i + 1].get_text(
                        strip=True
                    )
            else:
                # Convert key to snake_case
                key = key.lower().replace(" ", "_")
                metadata[key] = value

    # Extract distance values as numbers
    _extract_distance_values(metadata)

    return metadata


def _extract_distance_values(metadata: Dict[str, Any]) -> None:
    """Extracts numerical distance values from metadata strings in-place.

    Args:
        metadata (Dict[str, Any]): Metadata dictionary to update.
    """
    distance_keys = [
        ("task_distance_through_centers", "distance_through_centers_km"),
        ("task_distance_optimized", "distance_optimized_km"),
    ]

    for source_key, target_key in distance_keys:
        if source_key in metadata:
            text_value = metadata[source_key]
            numeric_value = "".join(c for c in text_value if c.isdigit() or c == ".")
            metadata[target_key] = float(numeric_value) if numeric_value else 0.0


def extract_turnpoints(html: str) -> List[Dict[str, Any]]:
    """Extracts turnpoint data from the task HTML table.

    Args:
        html (str): HTML content of the task file.

    Returns:
        List[Dict[str, Any]]: List of turnpoint dictionaries.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="table")
    turnpoints = []

    if not table:
        logger.warning("No table found with class 'table'")
        return []

    # Find table headers
    headers = _extract_table_headers(table)
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
        turnpoint = _process_turnpoint_row(row, headers)
        if turnpoint:
            turnpoints.append(turnpoint)

    logger.info(f"Extracted {len(turnpoints)} turnpoints from table")
    return turnpoints


def _extract_table_headers(table: BeautifulSoup) -> List[str]:
    """Extracts header names from a table element.

    Args:
        table (BeautifulSoup): Table element containing headers.

    Returns:
        List[str]: List of header names.
    """
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

    headers = [th.get_text(strip=True) for th in th_elements if th.get_text(strip=True)]
    if not headers:
        logger.warning("No valid headers found in table")
        return []

    logger.info(f"Found table headers: {headers}")
    return headers


def _process_turnpoint_row(
    row: BeautifulSoup, headers: List[str]
) -> Optional[Dict[str, Any]]:
    """Processes a single turnpoint row from the table.

    Args:
        row (BeautifulSoup): Table row element.
        headers (List[str]): List of header names.

    Returns:
        Optional[Dict[str, Any]]: Dictionary of turnpoint data, or None if invalid.
    """
    # Skip rows with no content
    if not row.contents:
        return None

    # Collect all cells from the row (th for the first column, td for the rest)
    cells = []
    th = row.find("th")
    if th is not None:
        th_text = th.get_text(strip=True)
        if th_text:
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
    entry = _extract_cell_values(cells, headers)

    # Add specific type information based on row class if Type is empty
    _set_turnpoint_type(entry, row)

    return entry if entry else None


def _extract_cell_values(
    cells: List[BeautifulSoup], headers: List[str]
) -> Dict[str, Any]:
    """Extracts and converts values from table cells based on headers.

    Args:
        cells (List[BeautifulSoup]): List of cell elements.
        headers (List[str]): List of header names.

    Returns:
        Dict[str, Any]: Dictionary of extracted cell values.
    """
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
            logger.warning(f"Error parsing value '{text}' for header '{header}': {e}")
            entry[header] = text

    return entry


def _set_turnpoint_type(entry: Dict[str, Any], row: BeautifulSoup) -> None:
    """Sets the turnpoint type based on row class or defaults.

    Args:
        entry (Dict[str, Any]): Turnpoint entry to update.
        row (BeautifulSoup): Table row element.
    """
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


def extract_geojson(html: str) -> Optional[Dict[str, Any]]:
    """Extracts GeoJSON data from JavaScript embedded in the HTML file.

    Args:
        html (str): HTML content of the task file.

    Returns:
        Optional[Dict[str, Any]]: Parsed GeoJSON dictionary, or None if not found/invalid.

    Raises:
        json.JSONDecodeError: If GeoJSON is found but cannot be parsed.
    """
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
        if validate_geojson(geojson_data):
            return geojson_data

        return None
    except json.JSONDecodeError as e:
        logger.exception(f"Error parsing GeoJSON data: {e}")
        # Debug information to help diagnose JSON parsing errors
        logger.debug(f"JSON extract starts with: {geojson_str[:100]}...")
        logger.debug(f"JSON extract ends with: ...{geojson_str[-100:]}")
        return None
    except Exception as e:
        logger.exception(f"Unexpected error processing GeoJSON: {e}")
        return None


def validate_geojson(geojson_data: Any) -> bool:
    """Validates the structure of GeoJSON data.

    Args:
        geojson_data (Any): GeoJSON data to validate.

    Returns:
        bool: True if valid FeatureCollection, False otherwise.
    """
    if not isinstance(geojson_data, dict):
        logger.warning(f"GeoJSON data is not a dictionary, got {type(geojson_data)}")
        return False

    if "type" not in geojson_data or geojson_data["type"] != "FeatureCollection":
        logger.warning("GeoJSON data does not appear to be a valid FeatureCollection")
        return False

    if "features" not in geojson_data or not isinstance(geojson_data["features"], list):
        logger.warning("GeoJSON data does not have a valid features list")
        return False

    return True
