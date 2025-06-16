# XContest XCTSK Tool - Simplified Usage

This tool has been simplified to allow easy processing of all XCTSK files in one command.

## Quick Start

```bash
# Upload all XCTSK files from xctsk_files/ and download HTML pages
python3 xcontest_xctsk_tool.py process --author "Your Name"
```

## What It Does

The `process` command will:

1. Upload all `.xctsk` files from `xctsk_files/` directory
2. Get task codes for each uploaded file
3. Download HTML pages for all uploaded tasks to `downloaded_tasks/html/`
4. Save upload results to a JSON file for reference

## Default Directories

- **XCTSK files**: `xctsk_files/` (22 task files)
- **HTML output**: `downloaded_tasks/html/`
- **Results file**: `upload_results.json`

## Custom Directories

You can specify custom directories:

```bash
python3 xcontest_xctsk_tool.py process \
    --xctsk-dir /path/to/xctsk/files \
    --html-output /path/to/html/output \
    --author "Your Name" \
    --results-file /path/to/results.json
```

## Individual Commands (Advanced)

If you need more control, you can still use individual commands:

```bash
# Upload only
python3 xcontest_xctsk_tool.py upload --directory xctsk_files --author "Your Name"

# Download specific task codes
python3 xcontest_xctsk_tool.py download --codes waku,motu,duna --output results/

# Download HTML for specific task codes
python3 xcontest_xctsk_tool.py html --codes waku,motu,duna --output html_pages/

# Generate QR code
python3 xcontest_xctsk_tool.py qr --file task.xctsk --output qr.svg
```

## Output

After running the process command, you'll find:

- Task codes and upload status in the terminal output
- Detailed upload results in `upload_results.json`
- HTML pages for each task in `downloaded_tasks/html/`
- Each HTML file named as `task_[CODE].html`

## Rate Limiting

The script includes built-in delays between requests to be respectful to the XContest servers. This means processing all 22 files will take about 1-2 minutes.
