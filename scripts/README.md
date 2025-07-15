# XCTSK Task Processing Scripts

Python automation scripts for extracting, converting, and managing paragliding/hang gliding competition tasks in the XCTrack format. These tools enable batch processing of competition task data, conversion between formats, and integration with the XContest tools API.

The scripts support workflows for extracting QR codes from HTML exports, parsing task metadata and turnpoints, and automating upload/download operations with the XContest web service. Designed for technical users working with large sets of competition tasks based on the XCTSK and XContest formats.

## Common Workflows

1. **Upload and Download**: Use `xcontest_xctsk_tool.py process` to upload XCTSK files and download HTML pages
2. **Extract Data**: Run `extract_task_data.py` to parse HTML exports into structured data
3. **Extract QR Codes**: Use `extract_qr_from_html.py` to decode QR codes from HTML files
4. **Validate**: Run test scripts to verify distance calculations and QR code generation

## Scripts

### `xcontest_xctsk_tool.py`

CLI tool for batch uploading XCTSK files, downloading tasks and HTML pages, and downloading QR codes via the XContest REST API from <https://tools.xcontest.org/xctsk/>. Implements retry logic, rate limiting, and metadata preservation with support for both v1 and v2 API endpoints.

#### REST API Endpoints

All operations use the XContest tools REST API:

- **POST `/api/xctsk/qr`**
  - Upload a `.xctsk` file (Content-Type: `application/json`)
  - Returns: QR code as SVG image
  - Used by the `qr` command to generate QR codes server-side

- **POST `/api/xctsk/save`**
  - Upload a `.xctsk` file (Content-Type: `application/json`)
  - Returns: Numeric task code
  - Add header `Author:` to specify uploader (ASCII only)

- **GET `/api/xctsk/load/<task code>`**
  - Download task by code
  - Returns: `.xctsk` file
  - Response headers: `Last-modified`, `Author`

- **GET `/api/xctsk/loadV2/<task code>`**
  - Download task by code (version 2, QR code format)
  - Returns: QR code data

#### One-Command Processing

Process all XCTSK files and download HTML pages:

```bash
python xcontest_xctsk_tool.py process --author "Your Name"
```

- Uploads all `.xctsk` files from `xctsk_files/`
- Downloads HTML for each task to `downloaded_tasks/html/`
- Saves upload results to `upload_results.json`

#### Individual Commands

- **Upload**: `python xcontest_xctsk_tool.py upload --directory xctsk_files --author "Your Name"`
  - `--directory, -d`: Directory containing XCTSK files (required)
  - `--author, -a`: Author name for uploads
  - `--results-file, -r`: File to save upload results in JSON format

- **Download tasks**: `python xcontest_xctsk_tool.py download --codes abcd,efgh --output downloaded_tasks/xctsk`
  - `--codes, -c`: Comma-separated list of task codes (required)
  - `--output, -o`: Output directory (required)
  - `--version, -v`: API version (1 or 2, default: 1)

- **Download HTML**: `python xcontest_xctsk_tool.py html --codes abcd,efgh --output downloaded_tasks/html`
  - `--codes, -c`: Comma-separated list of task codes (required)
  - `--output, -o`: Output directory (required)

- **Download QR code**: `python xcontest_xctsk_tool.py qr --file task.xctsk --output qr.svg`
  - `--file, -f`: XCTSK file (required)
  - `--output, -o`: Output SVG file (required)
  - Uploads the XCTSK file to XContest API and downloads the generated QR code SVG

#### Notes

- Built-in 1s delay between requests (rate limiting)
- All commands support `--timeout` (default: 30s) and `--retries` (default: 3)
- For troubleshooting, ensure `requests` is installed and files are valid

### `extract_task_data.py`

Parses XCTrack HTML exports in `downloaded_tasks/html_cleaned`, removes embedded images, and extracts task metadata, turnpoints, and embedded GeoJSON. Outputs cleaned HTML, structured JSON, and GeoJSON for downstream analysis or visualization using BeautifulSoup for robust HTML parsing with validation for distance and coordinate fields.

#### Usage

```bash
# Process all HTML files in downloaded_tasks/html_cleaned directory
python extract_task_data.py
```

#### Output Structure

- `downloaded_tasks/html_cleaned/`: HTML files with images removed
- `downloaded_tasks/json/`: Structured task data in JSON format
- `downloaded_tasks/geojson/`: Map data for visualization

### `extract_qr_from_html.py`

Locates base64-encoded SVG QR codes in HTML files, decodes and converts them to images, and extracts QR data using OpenCV and pyzbar. Supports batch processing, intermediate PNG output, and error handling for malformed images.

#### Usage Examples

```bash
# Process a single HTML file
python extract_qr_from_html.py downloaded_tasks/html/task_bevo.html

# Process all HTML files in a directory
python extract_qr_from_html.py downloaded_tasks/html/*.html

# Save intermediate PNG images
python extract_qr_from_html.py downloaded_tasks/html/*.html -o output_images
```

#### Output Files

- QR code images: `downloaded_tasks/qrcode/[filename].png`
- Decoded text: `downloaded_tasks/qrcode/[filename].txt`

### `test_distance_calculations.py`

Validation script that compares optimized distance calculations with reference data from JSON files. Tests the accuracy of the pyxctsk distance calculation engine against known values.

### `test_qrcode_generation.py`

Test script for QR code generation functionality. Generates QR codes for XCTSK files and compares them with expected results, testing both string generation and PNG image output.

### `check_qr_deps.py`

Dependency checker for QR code functionality. Verifies that Pillow, pyzbar, and the zbar system library are installed, providing OS-specific installation instructions if dependencies are missing.

## Project Structure

```text
scripts/
├── xcontest_xctsk_tool.py      # XContest API integration
├── extract_task_data.py        # HTML to JSON/GeoJSON conversion
├── extract_qr_from_html.py     # QR code extraction from HTML
├── test_distance_calculations.py  # Distance calculation validation
├── test_qrcode_generation.py   # QR code generation testing
├── check_qr_deps.py           # Dependency verification
└── downloaded_tasks/          # Output directory structure
    ├── html/                  # Original HTML files
    ├── html_cleaned/          # Processed HTML files
    ├── json/                  # Extracted task data
    ├── geojson/              # Map visualization data
    └── qrcode/               # QR code images and text
```
