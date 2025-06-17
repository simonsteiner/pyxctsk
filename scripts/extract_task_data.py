from bs4 import BeautifulSoup
import os
import json


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


def extract_task_distances_from_dl(html):
    soup = BeautifulSoup(html, "html.parser")
    dt_elements = soup.find_all("dt")
    dd_elements = soup.find_all("dd")

    task_distance_index = None
    for i, dt in enumerate(dt_elements):
        # print(dt.get_text(strip=True))
        if "Task distance" in dt.get_text():
            task_distance_index = i
            break

    if task_distance_index is not None:
        through_centers_text = dd_elements[task_distance_index].get_text(strip=True)
        # Extract only the number (assuming format like "128.7km")
        through_centers_value = "".join(
            c for c in through_centers_text if c.isdigit() or c == "."
        )
        through_centers = float(through_centers_value) if through_centers_value else 0.0

        optimized = None
        if task_distance_index + 1 < len(dd_elements):
            optimized_text = dd_elements[task_distance_index + 1].get_text(strip=True)
            if optimized_text:
                # Extract only the number (assuming format like "94.1km")
                optimized_value = "".join(
                    c for c in optimized_text if c.isdigit() or c == "."
                )
                optimized = float(optimized_value) if optimized_value else 0.0

        return {"through_centers": through_centers, "optimized": optimized}

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


# Example usage for a directory
def process_directory(directory_path, max_files=None):
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

                # Extract task data from the HTML
                distance = extract_task_distances_from_dl(html)
                if distance:
                    print("Task Distance:")
                    print(
                        f"{distance.get('through_centers', 0):.1f}km (through centers)"
                    )
                    if distance.get("optimized") is not None:
                        print(f"{distance.get('optimized', 0):.1f}km (optimized)")
                    else:
                        print("Not available (optimized)")
                else:
                    print("No distance information found")

                print("\nExtracting turnpoints...")
                turnpoints = extract_turnpoints(html)

                if turnpoints:
                    print(f"Found {len(turnpoints)} turnpoints:")
                    for tp in turnpoints:
                        print(tp)
                else:
                    print("No turnpoints extracted")

                    # For debugging - Check table structure
                    soup = BeautifulSoup(html, "html.parser")
                    tables = soup.find_all("table")
                    print(f"Number of tables found: {len(tables)}")
                    for i, table in enumerate(tables):
                        print(f"Table {i+1} classes: {table.get('class', 'No class')}")

                files_processed += 1

            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue


print("\n==== TESTING CLEANED HTML FILES ====")
process_directory("downloaded_tasks/html_cleaned", max_files=2)

# Uncomment to process all files in the directory
# print("\n==== PROCESSING ALL FILES ====")
# process_directory("downloaded_tasks/html_cleaned")
