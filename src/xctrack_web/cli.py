#!/usr/bin/env python3
"""
CLI interface for XCTrack Web Application
"""
import sys
from pathlib import Path

import click

from .app import XCTrackWebApp
from .server import create_app

# Add the parent directory to sys.path to allow importing xctrack
current_dir = Path(__file__).parent.absolute()
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))


@click.group()
@click.version_option(version="1.0.0")
def main():
    """XCTrack Web Interface - Task visualization and analysis"""
    pass


@main.command()
@click.option("--host", "-h", default="127.0.0.1", help="Host to bind to")
@click.option("--port", "-p", default=5000, type=int, help="Port to bind to")
@click.option("--debug", "-d", is_flag=True, help="Enable debug mode")
@click.option(
    "--tasks-dir", type=click.Path(exists=True), help="Directory containing task files"
)
def serve(host, port, debug, tasks_dir):
    """Start the XCTrack web server"""
    try:
        if create_app:
            app = create_app(tasks_dir=tasks_dir)
        else:
            # Fallback to direct app creation
            web_app = XCTrackWebApp(tasks_dir=tasks_dir)
            app = web_app.app

        click.echo(f"Starting XCTrack Web Server on {host}:{port}")
        if debug:
            click.echo("Debug mode enabled")
        if tasks_dir:
            click.echo(f"Using tasks directory: {tasks_dir}")

        app.run(host=host, port=port, debug=debug)
    except ImportError as e:
        click.echo(f"Error: Missing dependencies. Please install Flask: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error starting server: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--output", "-o", type=click.Path(), help="Output directory for generated files"
)
def install(output):
    """Install XCTrack Web as a service or generate configuration files"""
    if not output:
        output = Path.cwd() / "xctrack-web-config"

    output_path = Path(output)
    output_path.mkdir(exist_ok=True)

    # Generate systemd service file
    service_content = f"""[Unit]
Description=XCTrack Web Interface
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory={Path.cwd()}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart={sys.executable} -m xctrack_web.cli serve --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
"""

    service_file = output_path / "xctrack-web.service"
    service_file.write_text(service_content)

    # Generate nginx configuration
    nginx_content = """server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    client_max_body_size 10M;
}
"""

    nginx_file = output_path / "xctrack-web.nginx"
    nginx_file.write_text(nginx_content)

    # Generate Docker configuration
    dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "-m", "xctrack_web.cli", "serve", "--host", "0.0.0.0", "--port", "5000"]
"""

    dockerfile = output_path / "Dockerfile"
    dockerfile.write_text(dockerfile_content)

    # Generate requirements.txt
    requirements_content = """xctrack>=1.0.0
flask>=2.0.0
werkzeug>=2.0.0
"""

    requirements_file = output_path / "requirements.txt"
    requirements_file.write_text(requirements_content)

    click.echo(f"Configuration files generated in: {output_path}")
    click.echo("Files created:")
    click.echo(f"  - {service_file.name} (systemd service)")
    click.echo(f"  - {nginx_file.name} (nginx configuration)")
    click.echo(f"  - {dockerfile.name} (Docker configuration)")
    click.echo(f"  - {requirements_file.name} (Python dependencies)")


if __name__ == "__main__":
    main()
