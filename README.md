# Python XCTrack

A comprehensive Python ecosystem for parsing, analyzing, and visualizing XCTrack task files and formats.

This repository contains two complementary modules:

- **`xctrack`** - Core library for parsing and manipulating XCTrack task files
- **`xctrack-web`** - Web interface for visual task analysis and sharing

## Modules Overview

### XCTrack Core (`src/xctrack/`)

The core Python library providing:

- Reading and writing `.xctsk` task files (JSON format)
- Generating and parsing `XCTSK:` URLs for task sharing
- Creating and decoding QR codes containing task data
- Converting tasks to KML format for visualization
- Command-line interface for format conversion

### XCTrack Web (`src/xctrack-web/`)

A modern web interface providing:

- Interactive task visualization with maps
- Task file upload and analysis
- QR code generation for XCTrack app
- Task sharing and export features
- RESTful API for programmatic access

## Installation

### Core Library Only

```bash
pip install xctrack
```

### Web Interface

```bash
# Install core library first
pip install xctrack

# Then install web interface
cd src/xctrack-web
pip install -e .
```

### Development Installation

#### Setting up Virtual Environment

```bash
git clone https://github.com/simon/python-xctrack.git
cd python-xctrack

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install core library in development mode with dev dependencies
pip install -e ".[dev]"

# Install web interface in development mode (optional)
cd src/xctrack_web
pip install -e .
cd ../..
```

#### Development Workflow

Once your virtual environment is set up:

```bash
# Format code before committing
black src/ tests/
isort src/ tests/

# Run linting
flake8 src/ tests/

# Run type checking
mypy src/

# Run tests
pytest

# Deactivate when done
deactivate
```

#### Verification

```bash
# Test that xctrack is properly installed
xctrack --help

# Run tests to ensure everything works
pytest

# Check code quality tools are available
black --version
isort --version
flake8 --version
mypy --version
```

## Quick Start

### Core Library Usage

```python
from xctrack import parse_task

# From file
task = parse_task('my_task.xctsk')

# From XCTSK: URL
task = parse_task('XCTSK:{"version":1,"taskType":"CLASSIC",...}')

# From QR code image (requires pyzbar and PIL)
task = parse_task('qr_code.png')

print(f"Task type: {task.task_type}")
print(f"Number of turnpoints: {len(task.turnpoints)}")
```

### Web Interface Usage

Start the web server:

```bash
xctrack-web serve
```

Or with custom settings:

```bash
xctrack-web serve --host 0.0.0.0 --port 8080 --debug
```

Then open <http://localhost:5000> in your browser to:

- Upload and analyze .xctsk task files
- View tasks on interactive maps
- Generate QR codes for XCTrack app
- Export tasks in multiple formats

### Command Line Tools

Core XCTrack CLI:

```bash
# Convert task file to JSON
xctrack convert task.xctsk --format json

# Generate QR code
xctrack convert task.xctsk --format png --output qr.png
```

Web interface CLI:

```bash
# Start development server
xctrack-web serve --debug

# Generate deployment files
xctrack-web install --output /etc/xctrack-web
```

### Creating a task

```python
from xctrack import Task, TaskType, Turnpoint, Waypoint

task = Task(
    task_type=TaskType.CLASSIC,
    version=1,
    turnpoints=[
        Turnpoint(
            radius=1000,
            waypoint=Waypoint(
                name="TP01",
                lat=46.5,
                lon=8.0,
                alt_smoothed=1000
            )
        )
    ]
)

# Save as JSON
with open('task.xctsk', 'w') as f:
    f.write(task.to_json())
```

### QR Code Generation

```python
from xctrack.utils import generate_qr_code

# Convert task to QR code format and generate image
qr_task = task.to_qr_code_task()
qr_string = qr_task.to_string()
qr_image = generate_qr_code(qr_string)
qr_image.save('task_qr.png')
```

### KML Export

```python
from xctrack.utils import task_to_kml

kml_content = task_to_kml(task)
with open('task.kml', 'w') as f:
    f.write(kml_content)
```

## Command Line Interface

The package includes a command-line tool for format conversion:

```bash
# Convert task to different formats
python -m xctrack task.xctsk --format json        # JSON output
python -m xctrack task.xctsk --format kml         # KML output  
python -m xctrack task.xctsk --format qrcode-json # XCTSK: URL
python -m xctrack task.xctsk --format png -o qr.png # QR code image

# Parse from different inputs
python -m xctrack qr_code.png --format json       # From QR image
cat task.xctsk | python -m xctrack --format kml   # From stdin
```

## Requirements

- Python 3.8+
- Click (for CLI)
- Optional QR code support:
  - Pillow (PIL) for image generation
  - qrcode for QR code generation  
  - pyzbar for QR code reading from images

## Data Structures

The library provides comprehensive data classes for XCTrack task components:

- `Task`: Main task container
- `Turnpoint`: Individual waypoints with radius and type information
- `Waypoint`: Geographic coordinates and metadata
- `SSS`: Start of speed section configuration
- `Goal`: Goal/finish line configuration  
- `Takeoff`: Takeoff location
- `TimeOfDay`: Time representation with validation

All classes support JSON serialization/deserialization and maintain compatibility with the XCTrack file format.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## AI-Assisted Migration

This Python implementation was migrated from the original Go codebase with the assistance of GitHub Copilot. The migration process involved:

- **AI Model**: Claude 4 Sonnet (via GitHub Copilot Chat)
- **Migration Approach**: Automated code analysis and conversion with human oversight
- **Process**: Complete rewrite maintaining API compatibility and feature parity
- **Validation**: Comprehensive testing against XCTrack Competition Interfaces specification
- **Quality Assurance**: Manual verification of all core functionality and edge cases

The AI assistant analyzed the Go source code structure, understood the XCTrack protocol specifications, and generated equivalent Python implementations while ensuring compatibility with the original format and adding modern Python idioms and type hints.

## Original Go Implementation

This Python library is based on the Go implementation by Tom Payne:
<https://github.com/twpayne/go-xctrack>
