# General Copilot Instructions

## Simplicity & Maintainability
- Do **not** add features, fallbacks, or config unless explicitly requested.
- Keep code clean, minimal, and easy to understand. Use meaningful names; avoid over-engineering.
- Use concise comments to explain non-obvious or complex logic.
- Recommend best practices **only** when relevant and clearly optional.

## Clarify Before Acting
- If requirements are ambiguous, **ask for clarification** before proceeding.

## Environment & Execution
- Assume all scripts/commands are run manually unless automation is **explicitly requested**.
- Always use the local Python environment `.venv/bin/python` instead of `python`.
- Do not add new dependencies without updating both `requirements.txt` and `pyproject.toml`.


# pyxctsk Project-Specific Instructions

## Project Context
- Python implementation of XCTrack's task format (paragliding/hang gliding competition tasks)
- Core functionality: parse, generate, manipulate, and visualize XCTrack tasks
- Key features: task format parsing, QR code generation/parsing, distance calculation

## Architecture Overview
- Data models in `task.py` - immutable dataclasses with validation logic
- Parsing pipeline in `parser.py` - handles multiple input formats (JSON, URL, QR code)
- QR code handling: `qrcode_task.py` for compact QR encoding spec implementation
- Distance calculation in multiple modules:
  - `distance.py`: Main interface
  - `route_optimization.py`: Path optimization algorithms
  - `task_distances.py`: Core distance calculations

## Development Environment
- Install in editable mode: `pip install -e ".[dev]"`
- Optional dependencies enabled by extras: `[dev]` for development, `[web]` for web interface

## Code Structure Patterns
- Immutable dataclasses for domain models
- Type hints required for all function parameters and returns
- Enums used for constrained values (e.g., `TaskType`, `TurnpointType`)
- Optional dependencies handled with try/except imports (see QR code support)

## Testing

- Run tests with: `.venv/bin/python -m pytest`
- Test organization:
  - Core and utility tests: `test_core.py`, `test_utils.py`
  - Distance calculation tests: `test_distance_essential.py`, `test_distance_reference.py`
  - Format and parsing tests: `test_geojson.py`, `test_kml.py`, `test_qrcode.py`, `test_sss.py`
  - Visual output tests (if any) create files in `tests/visual_output/`

### Reference Test Data Structure

- All test data is located in `tests/data/reference_tasks`, including `.xctsk` files and other formats.
- Each `.xctsk` file has a corresponding `.json` file containing reference metadata and a QR code string.
- The directory structure is as follows:
  - `xctsk/`: XCTrack task files (`.xctsk`) used as input for both distance and QR code tests.
  - `json/`: JSON files with reference metadata, including pre-calculated distances and QR code strings.
  - `qrcode_string/`: Expected QR code strings in `.txt` files for QR code tests.

### Test Usage

- Test fixtures in `test_distance_reference.py` and related test modules automatically discover and use these files for validation.
- QR code string and image validation is performed by `test_qrcode.py`.
- Visual outputs (e.g., generated QR code images) are saved to `tests/data/visual_output/` during testing.

## Code Quality
- Pre-commit hooks run: flake8, mypy, isort, black
- Run manually: `.venv/bin/pre-commit run --all-files`
- Strict mypy type checking enforced

## Key Integration Points
- CLI entry point in `cli.py` with Click command structure
- QR code generation requires Pillow and qrcode libraries
- QR code parsing requires pyzbar library
- Distance calculations use geopy, pyproj and scipy
        
# Docstring Requirements

All public functions, methods, and classes **must** have docstrings that follow the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings). This includes:

- A one-line summary at the top.
- `Args:` section listing argument names, types, and descriptions.
- `Returns:` section with return type and description (or `None`).
- `Raises:` section for exceptions, if applicable.
- Proper indentation and punctuation.

Private methods (those starting with `_`) must include a docstring if they perform non-trivial logic.

Avoid placeholder or redundant docstrings (e.g., "Returns the value").