# General Copilot Instructions

- Do not implement unnecessary fallbacks or extra features. However, advise on best practices or possible improvements where relevant.
- If requirements are unclear, ask for clarification before proceeding.
- Prioritize simplicity and maintainability in all solutions.
- Assume scripts or commands will be run manually unless automation is explicitly requested.

## Copilot Instructions for XCTrack Project

## Project Context
This is a Python project implementing XCTrack's task format.
The project includes QR code generation and parsing capabilities.
The project has both CLI and web interface components.

## Development Environment
Always use a virtual environment for development.
Use fish shell syntax for all terminal commands.
Install in editable mode with dev dependencies using `pip install -e ".[dev]"`.
Activate virtual environment with `source venv/bin/activate.fish`.

## Code Structure
Main source code is in `src/xctrack/` directory.
Web interface code is in `src/xctrack_web/` directory.
Test files are located in `tests/` directory.

## Testing
Use pytest for all testing.
Run tests frequently during development.
Test files follow pattern: `test_*.py` in `tests/` directory.
Sample task files for testing have `.xctsk` extension.

## Code Quality
Format code with black before committing.
Sort imports with isort before committing.
Run flake8 for linting checks.
Use mypy for type checking.

## Key Files
`task.py` handles core task functionality.
`parser.py` handles XCTrack file parsing.
`qrcode_task.py` manages QR code operations.
`distance.py` performs distance calculations.
`cli.py` provides command-line interface.

## Python Requirements
Target Python 3.8+ compatibility.
Follow PEP 8 style guidelines.
Use type hints for function parameters and returns.
Write docstrings for public functions and classes.