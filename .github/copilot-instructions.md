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
  - Basic tests in `test_basic.py`
  - Distance calculation tests in `test_distance*.py` files
  - Visual output tests create files in `tests/visual_output/`
- Test data in `.xctsk` files in the `tests/` directory

## Code Quality
- Pre-commit hooks run: flake8, mypy, isort, black
- Run manually: `.venv/bin/pre-commit run --all-files`
- Strict mypy type checking enforced

## Key Integration Points
- CLI entry point in `cli.py` with Click command structure
- QR code generation requires Pillow and qrcode libraries
- QR code parsing requires pyzbar library
- Distance calculations use geopy, pyproj and scipy