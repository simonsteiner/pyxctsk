# General Copilot Instructions

## 1. Simplicity First

- Do **not** add fallbacks, features, or configuration unless explicitly requested.
- Recommend best practices **only** when relevant and clearly optional.

## 2. Clarify Before Acting

- If requirements are ambiguous, **ask for clarification** before proceeding.

## 3. Prioritize Maintainability

- Keep code clean, minimal, and easy to understand.
- Use meaningful names; avoid over-engineering.

## 4. Manual Execution Assumed

- Assume all scripts/commands are run manually unless automation is **explicitly requested**.

## 5. Use Project Virtual Environment

- Always use the local Python environment `.venv/bin/python` instead of `python`.

## 6. Avoid Unnecessary Configuration

- Do not introduce complexity without clear need or request.

## 7. Comment Clearly

- Use concise comments to explain non-obvious logic or complex sections of code.


## Copilot Instructions for pyxctsk Project

## Project Context
This is a Python project implementing XCTrack's task format.
The project includes QR code generation and parsing capabilities.
The project has both CLI and web interface components.

## Development Environment
Always use a virtual environment for development.
Use fish shell syntax for all terminal commands.
Install in editable mode with dev dependencies using `pip install -e ".[dev]"`.
Activate virtual environment with `source .venv/bin/activate.fish`.

## Code Structure
Main source code is in `src/pyxctsk/` directory.
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