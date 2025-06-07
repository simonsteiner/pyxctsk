# XCTrack Web Interface

A modern web interface for analyzing and visualizing XCTrack competition task files (.xctsk format). This module provides a Flask-based web application that complements the core `xctrack` Python library.

## Features

- **Interactive Task Visualization**: View tasks on interactive maps with Leaflet.js
- **Task Analysis**: Detailed turnpoint information, distances, and statistics
- **QR Code Generation**: Generate XCTrack-compatible QR codes for task sharing
- **File Upload**: Upload and analyze .xctsk task files via web interface
- **Multiple Export Formats**: Export tasks as JSON, KML, and other formats
- **Responsive Design**: Works on desktop and mobile devices
- **RESTful API**: Programmatic access to task data and analysis

## Installation

### From Source

1. Clone the repository:

```bash
git clone https://github.com/simon/python-xctrack.git
cd python-xctrack/src/xctrack-web
```

2. Install dependencies:

```bash
pip install -e .
```

### Using pip

```bash
pip install xctrack-web
```

## Quick Start

### Command Line Interface

Start the development server:

```bash
xctrack-web serve
```

Start with custom settings:

```bash
xctrack-web serve --host 0.0.0.0 --port 8080 --debug
```

Specify a directory containing task files:

```bash
xctrack-web serve --tasks-dir /path/to/tasks
```

### Python API

```python
from xctrack_web.server import create_app

# Create Flask application
app = create_app(tasks_dir='/path/to/tasks')

# Run development server
app.run(debug=True)
```

### Production Deployment

Generate configuration files for production deployment:

```bash
xctrack-web install --output /etc/xctrack-web
```

This creates:

- `xctrack-web.service` - systemd service file
- `xctrack-web.nginx` - nginx reverse proxy configuration
- `Dockerfile` - Docker container configuration
- `requirements.txt` - Python dependencies

## Web Interface

### Home Page

- Upload task files via drag-and-drop or file picker
- Browse sample tasks
- Quick task analysis overview

### Task Detail Page

- Interactive map with turnpoints and task line
- Detailed turnpoint table with distances and types
- Task information and statistics
- QR code generation for XCTrack
- Export options (JSON, KML)

## API Endpoints

### Task Analysis

- `GET /api/task/{task_code}` - Get task data and analysis
- `GET /api/task/{task_code}/qr` - Generate QR code for task
- `POST /upload` - Upload and analyze task file

### Task Management

- `GET /task/{task_code}` - View task detail page
- `GET /` - Main interface

## Configuration

The web interface can be configured via environment variables or configuration files:

```python
config = {
    'TASKS_DIR': '/path/to/task/files',
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB max upload
    'SECRET_KEY': 'your-secret-key-here',
}

app = create_app(config=config)
```

## Dependencies

### Core Dependencies

- `xctrack>=1.0.0` - XCTrack task parsing and analysis
- `flask>=2.0.0` - Web framework
- `werkzeug>=2.0.0` - WSGI utilities

### Frontend Dependencies (CDN)

- Bootstrap 5.1.3 - UI framework
- Leaflet 1.9.4 - Interactive maps
- Font Awesome 6.0.0 - Icons

## Development

### Project Structure

```sh
xctrack-web/
├── __init__.py          # Package initialization
├── app.py              # Main Flask application class
├── server.py           # Server creation and configuration
├── cli.py              # Command line interface
├── templates/          # Jinja2 HTML templates
│   ├── index.html      # Main page template
│   └── task.html       # Task detail template
├── static/             # Static files (CSS, JS, images)
└── pyproject.toml      # Package configuration
```

### Running Tests

```bash
cd /path/to/python-xctrack
python -m pytest tests/ -v
```

### Code Style

The project uses Black for code formatting:

```bash
black xctrack-web/
```

## Docker Deployment

Build and run with Docker:

```bash
# Build image
docker build -t xctrack-web .

# Run container
docker run -p 5000:5000 -v /path/to/tasks:/app/tasks xctrack-web
```

## System Service

Install as a systemd service:

```bash
# Generate service file
xctrack-web install --output /tmp/config

# Copy service file
sudo cp /tmp/config/xctrack-web.service /etc/systemd/system/

# Enable and start service
sudo systemctl enable xctrack-web
sudo systemctl start xctrack-web
```

## Integration with XCTrack Core

This web interface depends on the core `xctrack` library for task parsing and analysis:

```python
from xctrack import XCTrackTask
from xctrack.qrcode_task import generate_task_qr_code

# The web interface uses these core functions:
task = XCTrackTask.from_file('task.xctsk')
qr_code = generate_task_qr_code(task)
```

## Browser Compatibility

- Chrome/Chromium 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Related Projects

- [xctrack](../xctrack/) - Core XCTrack task parsing library
- [XCTrack](https://xctrack.org/) - Official XCTrack navigation app
