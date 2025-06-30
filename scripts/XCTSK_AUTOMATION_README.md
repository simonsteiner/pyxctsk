# XCTSK Automation Tool

This tool automates the upload and download of XCTSK files to/from the XContest tools website (<https://tools.xcontest.org/xctsk/>).

## Features

- **Batch Upload**: Upload multiple XCTSK files from a directory
- **Task Download**: Download tasks by their numeric codes
- **QR Code Generation**: Generate QR codes for XCTSK files
- **Robust Error Handling**: Automatic retries and detailed error messages
- **Metadata Preservation**: Captures author and modification date information

## Installation

First, make sure you have the required dependencies installed:

```bash
# Install the project in development mode (includes requests dependency)
pip install -e ".[dev]"
```

Or install requests separately if not using the full project:

```bash
pip install requests
```

## Usage

### Upload XCTSK Files

Upload all XCTSK files from a directory:

```bash
python xcontest_xctsk_tool.py upload --directory tests/xctsk --author "Your Name"
```

Save upload results to a JSON file:

```bash
python xcontest_xctsk_tool.py upload --directory tests/xctsk --author "Your Name" --results-file upload_results.json
```

### Download Tasks

Download specific tasks by their codes:

```bash
python xcontest_xctsk_tool.py download --codes 12345,67890,13579 --output downloads/
```

Download using API version 2 (QR code format):

```bash
python xcontest_xctsk_tool.py download --codes 12345 --output downloads/ --version 2
```

### Generate QR Codes

Generate a QR code SVG for a single XCTSK file:

```bash
python xcontest_xctsk_tool.py qr --file task_2025-01-19.xctsk --output qr_code.svg
```

## Command Reference

### Global Options

- `--timeout`: Request timeout in seconds (default: 30)
- `--retries`: Number of retries for failed requests (default: 3)

### Upload Command

```bash
python xcontest_xctsk_tool.py upload [OPTIONS]
```

**Options:**

- `--directory, -d`: Directory containing XCTSK files (required)
- `--author, -a`: Author name for uploads
- `--results-file, -r`: File to save upload results in JSON format

### Download Command

```bash
python xcontest_xctsk_tool.py download [OPTIONS]
```

**Options:**

- `--codes, -c`: Comma-separated list of task codes (required)
- `--output, -o`: Output directory (required)
- `--version, -v`: API version (1 or 2, default: 1)

### QR Command

```bash
python xcontest_xctsk_tool.py qr [OPTIONS]
```

**Options:**

- `--file, -f`: XCTSK file (required)
- `--output, -o`: Output SVG file (required)

## API Reference

The script uses the XContest tools REST API:

- **POST** `/api/xctsk/save` - Upload a task (returns numeric code)
- **GET** `/api/xctsk/load/<code>` - Download a task (version 1)
- **GET** `/api/xctsk/loadV2/<code>` - Download a task (version 2, QR format)
- **POST** `/api/xctsk/qr` - Generate QR code SVG

## Examples

### Batch Processing Workflow

1. Upload all your XCTSK files:

```bash
python xcontest_xctsk_tool.py upload --directory tests/xctsk --author "Pilot Name" --results-file codes.json
```

2. Share the codes with others or save for later use

3. Download tasks later:

```bash
# Extract codes from the JSON file and download
python xcontest_xctsk_tool.py download --codes 12345,67890 --output shared_tasks/
```

### QR Code Generation for Multiple Files

```bash
# Generate QR codes for all XCTSK files
for file in tests/xctsk/*.xctsk; do
    basename=$(basename "$file" .xctsk)
    python xcontest_xctsk_tool.py qr --file "$file" --output "qr_codes/qr_$basename.svg"
done
```

## Demo Script

A demonstration script is provided that shows basic usage:

```bash
python xctsk_demo.py
```

This script will:

- Upload a few sample XCTSK files
- Generate QR codes for them
- Download the uploaded tasks
- Save results to JSON files

## Output Files

### Upload Results (JSON)

When using `--results-file`, the upload results are saved in this format:

```json
{
  "task_2025-01-19.xctsk": 12345,
  "task_2025-01-20.xctsk": 67890,
  "task_2025-01-21.xctsk": 13579
}
```

### Downloaded Tasks

Downloaded tasks are saved as `.xctsk` files with metadata preserved in the headers returned by the API.

### QR Codes

QR codes are generated as SVG files that can be displayed in web browsers or converted to other formats.

## Error Handling

The script includes robust error handling:

- **Network errors**: Automatic retries with exponential backoff
- **Invalid files**: Clear error messages for malformed XCTSK files
- **Rate limiting**: Built-in delays between requests to be respectful to the server
- **File system errors**: Automatic directory creation and permission checks

## Rate Limiting

The script includes a 1-second delay between requests to avoid overwhelming the server. For large batch operations, consider running during off-peak hours.

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure `requests` is installed
2. **File not found**: Check that XCTSK files exist and are readable
3. **Network timeouts**: Increase `--timeout` value or check internet connection
4. **Invalid JSON**: Ensure XCTSK files contain valid JSON data

### Debug Mode

For detailed debugging, you can modify the script to add more verbose logging or run individual operations to isolate issues.

## Contributing

This tool is part of the pyxctsk project. Please follow the project's coding standards:

- Format code with `black`
- Sort imports with `isort`
- Run `flake8` for linting
- Add type hints for new functions
