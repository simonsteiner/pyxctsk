from bs4 import BeautifulSoup
import os
import json
import re


def preprocess_html(html):
    """Preprocess HTML by removing embedded base64 images"""
    soup = BeautifulSoup(html, "html.parser")

    # Remove embedded base64 images
    for img in soup.find_all("img", src=True):
        if img["src"].startswith("data:image/svg+xml;base64,"):
            img.decompose()

    return soup


def save_cleaned_html(
    soup, original_filename, output_dir="downloaded_tasks/html_cleaned"
):
    """Save the cleaned HTML to a new file"""
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, original_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    print(f"Saved cleaned HTML to: {output_path}")
    return output_path


# Example usage for a directory
def preprocess_directory(directory_path):
    for filename in sorted(os.listdir(directory_path)):
        if filename.endswith(".html"):
            with open(
                os.path.join(directory_path, filename), "r", encoding="utf-8"
            ) as f:
                html_content = f.read()

            # Preprocess HTML to remove base64 images
            cleaned_soup = preprocess_html(html_content)
            # Save cleaned HTML
            save_cleaned_html(cleaned_soup.prettify(), filename)


# preprocess_directory("downloaded_tasks/html")


def extract_task_metadata(html):
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
                    metadata["task_distance_optimized"] = dd_elements[i + 1].get_text(
                        strip=True
                    )
            else:
                # Convert key to snake_case
                key = key.lower().replace(" ", "_")
                metadata[key] = value

    # Extract distance values as numbers
    if "task_distance_through_centers" in metadata:
        through_centers_text = metadata["task_distance_through_centers"]
        through_centers_value = "".join(
            c for c in through_centers_text if c.isdigit() or c == "."
        )
        metadata["distance_through_centers_km"] = (
            float(through_centers_value) if through_centers_value else 0.0
        )

    if "task_distance_optimized" in metadata:
        optimized_text = metadata["task_distance_optimized"]
        optimized_value = "".join(c for c in optimized_text if c.isdigit() or c == ".")
        metadata["distance_optimized_km"] = (
            float(optimized_value) if optimized_value else 0.0
        )

    return metadata


def extract_task_distances_from_dl(html):
    """Legacy function kept for backward compatibility"""
    metadata = extract_task_metadata(html)

    if "distance_through_centers_km" in metadata:
        result = {"through_centers": metadata["distance_through_centers_km"]}

        if "distance_optimized_km" in metadata:
            result["optimized"] = metadata["distance_optimized_km"]

        return result

    return None


def extract_turnpoints(html):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="table")
    turnpoints = []

    if not table:
        print("No table found with class 'table'")
        return []

    # Find the table header row and extract headers
    thead = table.find("thead")
    if not thead:
        print("Table has no thead element")
        return []

    header_row = thead.find("tr")
    if not header_row:
        print("Table header row not found")
        return []

    th_elements = header_row.find_all("th")
    if not th_elements:
        print("No header cells found in header row")
        return []

    # Only use headers from the header row, not all th elements in the table
    headers = [th.get_text(strip=True) for th in th_elements if th.get_text(strip=True)]
    if not headers:
        print("No valid headers found in table")
        return []

    print(f"Found table headers: {headers}")

    # Check if tbody exists
    tbody = table.find("tbody")
    if not tbody:
        print("Table has no tbody element")
        return []

    rows = tbody.find_all("tr")
    print(f"Found {len(rows)} rows in table")

    for row in rows:
        # Skip rows with no content
        if not row.contents:
            continue

        # Collect all cells from the row (th for the first column, td for the rest)
        cells = []
        th = row.find("th")
        if th and th.get_text(strip=True):
            cells.append(th)

        tds = row.find_all("td")
        cells.extend(tds)

        # Skip empty rows
        if not cells or not any(cell.get_text(strip=True) for cell in cells):
            continue

        # Make sure we have enough cells for the headers
        if len(cells) < len(headers):
            print(
                f"Row has {len(cells)} cells but expected {len(headers)} cells (skipping)"
            )
            continue

        # Only use the cells that match our headers
        cells = cells[: len(headers)]

        # Extract row data
        entry = {}

        # Process each cell
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
                print(f"Error parsing value '{text}' for header '{header}': {e}")
                entry[header] = text

        # Add specific type information based on row class if Type is empty
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
        elif "Type" in headers and "Type" not in entry:
            entry["Type"] = "Turnpoint"

        if entry:
            turnpoints.append(entry)

    print(f"Extracted {len(turnpoints)} turnpoints from table")
    return turnpoints


def extract_geojson(html):
    """Extract GeoJSON data from JavaScript in the HTML file"""
    # Look for the geojson variable definition in the script
    # This pattern handles both single-line and multi-line GeoJSON definitions
    geojson_pattern = (
        r'var\s+geojson\s*=\s*(\{\s*"type"\s*:\s*"FeatureCollection".+?});'
    )
    geojson_match = re.search(geojson_pattern, html, re.DOTALL)

    if not geojson_match:
        print("No GeoJSON data found in the HTML")
        return None

    try:
        # Extract the raw JSON string
        geojson_str = geojson_match.group(1)

        # Clean up the string to handle potential JavaScript formatting issues
        # Remove any trailing commas in arrays or objects (invalid in strict JSON)
        geojson_str = re.sub(r",\s*([}\]])", r"\1", geojson_str)

        # Parse the JSON string into a Python dictionary
        geojson_data = json.loads(geojson_str)

        # Validate the structure of the GeoJSON data
        if not isinstance(geojson_data, dict):
            print(
                f"Warning: GeoJSON data is not a dictionary, got {type(geojson_data)}"
            )
            return None

        if "type" not in geojson_data or geojson_data["type"] != "FeatureCollection":
            print(
                "Warning: GeoJSON data does not appear to be a valid FeatureCollection"
            )
            return None

        if "features" not in geojson_data or not isinstance(
            geojson_data["features"], list
        ):
            print("Warning: GeoJSON data does not have a valid features list")
            return None

        # All validation passed, return the data
        return geojson_data
    except json.JSONDecodeError as e:
        print(f"Error parsing GeoJSON data: {e}")
        # Debug information to help diagnose JSON parsing errors
        print(f"JSON extract starts with: {geojson_str[:100]}...")
        print(f"JSON extract ends with: ...{geojson_str[-100:]}")
        return None
    except Exception as e:
        print(f"Unexpected error processing GeoJSON: {e}")
        return None


def save_task_json(task_data, filename, output_dir="downloaded_tasks/json"):
    """Save task data to a JSON file"""
    os.makedirs(output_dir, exist_ok=True)

    # Create output filename based on input filename
    base_name = os.path.splitext(os.path.basename(filename))[0]
    output_path = os.path.join(output_dir, f"{base_name}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(task_data, f, indent=2)

    print(f"Task data saved to: {output_path}")
    return output_path


def save_geojson(geojson_data, filename, output_dir="downloaded_tasks/geojson"):
    """Save GeoJSON data to a file"""
    print(f"Saving GeoJSON data for {filename}...")

    # Check for variable name conflict (if boolean is passed instead of data)
    if isinstance(geojson_data, bool):
        print(
            "ERROR: Boolean value passed to save_geojson() - possible variable name conflict"
        )
        return None

    if not geojson_data:
        print("No GeoJSON data to save")
        return None

    if not isinstance(geojson_data, dict):
        print(f"Error: GeoJSON data is not a dictionary, got {type(geojson_data)}")
        return None

    # Validate that the geojson_data has the expected structure
    if "type" not in geojson_data or geojson_data["type"] != "FeatureCollection":
        print("Error: GeoJSON data does not appear to be a valid FeatureCollection")
        return None

    if "features" not in geojson_data or not isinstance(geojson_data["features"], list):
        print("Error: GeoJSON data does not have a valid features list")
        return None

    try:
        json_dump = json.dumps(geojson_data, indent=2)
        print(f"GeoJSON dump (first 100 chars): {json_dump[:100]}...")
    except Exception as e:
        print(f"Error creating JSON dump: {e}")
        json_dump = None

    try:
        os.makedirs(output_dir, exist_ok=True)

        # Create output filename based on input filename
        base_name = os.path.splitext(os.path.basename(filename))[0]
        output_path = os.path.join(output_dir, f"{base_name}.geojson")

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, indent=2)

        print(f"GeoJSON data saved to: {output_path}")
        return output_path
    except Exception as e:
        print(f"Error saving GeoJSON file: {e}")
        return None


# Example usage for a directory
def process_directory(
    directory_path,
    max_files=None,
):
    files_processed = 0
    for filename in sorted(os.listdir(directory_path)):
        if filename.endswith(".html"):
            if max_files is not None and files_processed >= max_files:
                break

            file_path = os.path.join(directory_path, filename)
            print(f"\n--- Processing {filename} ---")

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    html = f.read()

                print(f"File size: {len(html)} bytes")

                # Extract all task metadata
                metadata = extract_task_metadata(html)

                # Extract turnpoints
                print("\nExtracting turnpoints...")
                turnpoints = extract_turnpoints(html)

                # Extract GeoJSON data
                print("\nExtracting GeoJSON data...")
                geojson_data = extract_geojson(html)

                # Combine data into a complete task object
                task_data = {"metadata": metadata, "turnpoints": turnpoints}

                # Display information
                if metadata:
                    print("Task Metadata:")
                    for key, value in metadata.items():
                        if key in [
                            "distance_through_centers_km",
                            "distance_optimized_km",
                        ]:
                            print(f"  {key}: {float(value):.1f}km")
                        else:
                            print(f"  {key}: {value}")
                else:
                    print("No metadata found")

                if turnpoints:
                    print(f"\nFound {len(turnpoints)} turnpoints:")
                    for tp in turnpoints:
                        print(f"  {tp}")
                else:
                    print("\nNo turnpoints extracted")
                    # For debugging - Check table structure
                    soup = BeautifulSoup(html, "html.parser")
                    tables = soup.find_all("table")
                    print(f"Number of tables found: {len(tables)}")
                    for i, table in enumerate(tables):
                        print(f"Table {i+1} classes: {table.get('class', 'No class')}")

                save_task_json(task_data, filename)

                if geojson_data is not None:
                    # Make sure geojson_data is a dictionary with features
                    if isinstance(geojson_data, dict) and "features" in geojson_data:
                        try:
                            feature_count = len(geojson_data.get("features", []))
                            print(f"\nGeoJSON data found with {feature_count} features")

                            # Safely get data type and keys
                            print(f"GeoJSON data type: {type(geojson_data)}")
                            if isinstance(geojson_data, dict):
                                print(f"GeoJSON data keys: {list(geojson_data.keys())}")

                            # Save the GeoJSON data
                            save_geojson(geojson_data, filename)
                        except Exception as e:
                            print(f"Error handling GeoJSON data: {e}")
                            print(f"GeoJSON data type: {type(geojson_data)}")
                    else:
                        print(
                            f"\nGeoJSON data found but not in the expected format: {type(geojson_data)}"
                        )
                else:
                    print("\nNo GeoJSON data found in the file")

                files_processed += 1

            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue


if __name__ == "__main__":
    print("\n==== PROCESSING HTML FILES AND SAVING JSON AND GEOJSON ====")

    # Process a couple of files first (for testing)
    process_directory(
        "downloaded_tasks/html_cleaned",
        # comment out max_files to process all files
        max_files=2,
    )
