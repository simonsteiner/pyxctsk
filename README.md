# pyxctsk

A Python implementation of XCTrack's task format for paragliding and hang gliding competitions. This library enables parsing, manipulation, and visualization of XCTrack task files used to define competition routes.

`pyxctsk` provides a comprehensive toolkit for working with the XCTrack task specification, including reading/writing task files, generating QR codes for task sharing, and performing distance calculations on competition routes.

The library implements the full XCTrack Competition Interfaces specification, ensuring compatibility with the XCTrack mobile app and other tools in the paragliding competition ecosystem.

## Technical Highlights

- **Immutable Data Model**: Core domain objects use Python's dataclasses with strict validation to ensure task integrity ([task.py](./src/pyxctsk/task.py))
- **Advanced Distance Calculation**: Implements sophisticated route optimization algorithms to accurately calculate task distances with iterative refinement to avoid look-ahead bias ([distance.py](./src/pyxctsk/distance.py), [route_optimization.py](./src/pyxctsk/route_optimization.py))
- **Efficient QR Code Representation**: Implements XCTrack's compact QR code format with polyline compression for efficient task sharing via small QR codes that work well in direct sunlight ([qrcode_task.py](./src/pyxctsk/qrcode_task.py))
- **Flexible Parsing Pipeline**: Single entry point that intelligently detects and parses multiple input formats (JSON, URL, QR code image) ([parser.py](./src/pyxctsk/parser.py))
- **Type Safety**: Comprehensive type hints throughout the codebase with strict mypy enforcement

## Dependencies and Libraries

### Core

- **click**: Command-line interface framework for the CLI tools
- **geopy**: Geographic calculations for distance and point manipulation
- **polyline**: Polyline encoding/decoding for compact coordinate representation
- **pyproj**: Projection calculations for accurate distance measurements
- **scipy**: Scientific computing library used for route optimization algorithms

### Optional

- **Pillow**: Image processing for QR code generation and parsing
- **qrcode**: QR code generation
- **pyzbar**: QR code parsing from images

### Development

- **pytest**: Testing framework
- **black**, **flake8**, **isort**, **mypy**: Code quality and formatting tools

## Project Structure

```text
.
├── src/
│   └── pyxctsk/           # Core package implementation
│       ├── __init__.py    # Package exports
│       ├── task.py        # Core data models
│       ├── parser.py      # Input format parser
│       ├── distance.py    # Distance calculation interface
│       ├── qrcode_task.py # QR code format implementation
│       └── ...
├── tests/                 # Test suite
│   ├── test_basic.py
│   ├── test_distance.py
│   └── ...
├── scripts/               # Utility scripts
├── pyproject.toml         # Project configuration
└── README.md
```

- `src/pyxctsk/`: Core library implementation with immutable data models and parsing logic
- `tests/`: Comprehensive test suite with basic tests and specialized distance calculation tests
- `scripts/`: Utility scripts for automation and testing

## Installation

### Core Library Only

```bash
pip install pyxctsk
```

### Development Installation

```bash
git clone https://github.com/simonsteiner/pyxctsk.git
cd pyxctsk

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install core library in development mode with dev dependencies
pip install -e ".[dev]"

# Run tests
python -m pytest

# Run single test with parameter
# -s: disables output capturing, allowing print statements and other outputs to be shown in the terminal.
# -vv: increases verbosity, providing more detailed test results.
python pytest -s tests/test_qrcode.py -vv

# (Optional) To check QR code dependencies, run:
python scripts/check_qr_deps.py
```

### Code Quality & Formatting

The project uses pre-commit hooks to maintain code quality:

```bash
# Install pre-commit hooks
.venv/bin/pre-commit install

# Run hooks manually
.venv/bin/pre-commit run --all-files
```

## Usage Examples

```python
from pyxctsk import parse_task, Task, TaskType, Turnpoint, Waypoint

# Parse from file, URL, or QR code
task = parse_task('task.xctsk')              # From .xctsk file
task = parse_task('XCTSK:{...}')             # From XCTrack URL
task = parse_task('qr_code.png')             # From QR code image

# Access task data
print(f"Task type: {task.task_type}")
print(f"Number of turnpoints: {len(task.turnpoints)}")

# Create a new task
task = Task(
    task_type=TaskType.CLASSIC,
    version=1,
    turnpoints=[
        Turnpoint(
            radius=1000,
            waypoint=Waypoint(
                name="TP01", lat=46.5, lon=8.0, alt_smoothed=1000
            )
        )
    ]
)

# Save as JSON
with open('task.xctsk', 'w') as f:
    f.write(task.to_json())

# Generate QR code
from pyxctsk.qrcode_image import generate_qrcode_image

qr_task = task.to_qr_code_task()
qr_image = generate_qrcode_image(qr_task.to_string())
qr_image.save('task_qr.png')
```

## Command Line Interface

The `pyxctsk` CLI enables conversion and inspection of XCTrack task files in multiple formats, with strict error handling and clear messaging.

**Parameter Options:**

- `--format [json|kml|png|qrcode-json]`  
  Output format.  
  - `json`: Standard JSON representation  
  - `kml`: KML for mapping tools  
  - `png`: QR code image (PNG)  
  - `qrcode-json`: Compact QR string (XCTSK: URL)  
  Default: `json`
- `--output, -o <file>`  
  Output file (default: stdout). For `png`, writes a PNG image; for others, writes text.
- `<input_file>`  
  Input file (optional). If omitted, reads from stdin. Accepts `.xctsk` files or QR code images.

**Examples:**

```bash
# Convert task to different formats
pyxctsk convert task.xctsk --format json                  # JSON output
pyxctsk convert task.xctsk --format kml -o task.kml       # KML output
pyxctsk convert task.xctsk --format png -o qr.png         # QR code image
pyxctsk convert task.xctsk --format qrcode-json           # XCTSK: URL string

# Parse from different inputs
pyxctsk convert qr_code.png --format json                 # From QR image
cat task.xctsk | pyxctsk convert --format kml             # From stdin
```

**Supported formats:**

- Input: `.xctsk` (XCTrack task files), QR code image (PNG)
- Output: JSON, KML, QR code (PNG or XCTSK: URL string)

See the CLI startup message (`pyxctsk --help` or running the CLI with no arguments) for a quick summary of options and supported formats.

## Requirements

- Python 3.8+
- Optional dependencies can be installed with extras:
  - `pip install pyxctsk[dev]` for development tools
  - `pip install pyxctsk[web]` for web interface components
  - `pip install pyxctsk[analysis]` for analysis tools

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Original Implementation

This Python library is based on the Go implementation by Tom Payne:
<https://github.com/twpayne/go-xctrack>
