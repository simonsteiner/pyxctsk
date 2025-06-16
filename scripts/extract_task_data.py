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
    soup, original_filename, output_dir="downloaded_tasks/html_cleaned2"
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


preprocess_directory("downloaded_tasks/html")


def extract_task_data_from_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Extract task distance
    task_distances = []
    for dt, dd in zip(soup.find_all("dt"), soup.find_all("dd")):
        if "Task distance" in dt.get_text():
            task_distances.append(dd.get_text(strip=True))

    # Extract turnpoints (look for tables with lat/lon or named rows)
    turnpoints = []
    tables = soup.find_all("table")
    for table in tables:
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if "name" in headers and "lat" in headers and "lon" in headers:
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 3:
                    name = cells[headers.index("name")].get_text(strip=True)
                    lat = float(cells[headers.index("lat")].get_text(strip=True))
                    lon = float(cells[headers.index("lon")].get_text(strip=True))
                    turnpoints.append(
                        {
                            "type": "Feature",
                            "geometry": {"type": "Point", "coordinates": [lon, lat]},
                            "properties": {"name": name},
                        }
                    )

    geojson = {"type": "FeatureCollection", "features": turnpoints}

    return {"task_distances": task_distances, "geojson": geojson, "cleaned_soup": soup}


def extract_task_distances_from_dl(html):
    soup = BeautifulSoup(html, "html.parser")
    dt_elements = soup.find_all("dt")
    dd_elements = soup.find_all("dd")

    task_distance_index = None
    for i, dt in enumerate(dt_elements):
        if "Task distance" in dt.get_text():
            task_distance_index = i
            break

    if task_distance_index is not None:
        through_centers = dd_elements[task_distance_index].get_text(strip=True)
        optimized = dd_elements[task_distance_index + 1].get_text(strip=True)
        return {"through_centers": through_centers, "optimized": optimized}

    return None


# Example usage for a directory
def process_directory(directory_path, max_files=None):
    files_processed = 0
    for filename in sorted(os.listdir(directory_path)):
        if filename.endswith(".html"):
            if max_files is not None and files_processed >= max_files:
                break

            with open(
                os.path.join(directory_path, filename), "r", encoding="utf-8"
            ) as f:
                html_content = f.read()

            # Preprocess HTML to remove base64 images
            cleaned_soup = preprocess_html(html_content)
            # Save cleaned HTML
            save_cleaned_html(cleaned_soup, filename)

            # Extract task data from the cleaned HTML
            result = extract_task_data_from_html(html_content)

            print(f"\n--- {filename} ---")
            print("Task Distances:", result["task_distances"])
            print("GeoJSON:", json.dumps(result["geojson"], indent=2))
            files_processed += 1


# Process only the first 2 files for testing
process_directory("downloaded_tasks/html", max_files=2)

# Process all files in the directory
# process_directory("downloaded_tasks/html")
