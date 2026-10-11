# Development setup

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.
Run every tool through `uv run`, which keeps the environment in sync, rather
than activating the venv or calling bare `python`.

## Install

```bash
git clone https://github.com/simonsteiner/pyxctsk.git
cd pyxctsk

# Create the virtual environment and install the project (editable), the dev
# dependency group, and the optional QR image support.
uv sync --all-extras

# Also install dependencies for the repository-only utilities under scripts/.
uv sync --all-extras --group tools

# (Optional) Check that the QR image dependencies import and decode.
uv run python scripts/check_qr_deps.py
```

`.python-version` pins Python 3.11 for local development; the package supports
3.11 and later, and CI verifies 3.11 through 3.14.

## Run the tests

```bash
uv run pytest                                      # full suite
uv run pytest tests/qrcode/test_codec.py -vv -s    # one file: -vv more detail, -s show prints
uv run pytest tests/distance -q                    # one test package
```

## Code quality

[lefthook](https://github.com/evilmartians/lefthook) runs
[ruff](https://docs.astral.sh/ruff/) (lint + format), mypy,
[rumdl](https://rumdl.dev/) (Markdown lint + fix) and cspell on commit:

```bash
# Install the git hooks (one-time)
uv run lefthook install

# Run the pre-commit hooks against staged files
uv run lefthook run pre-commit

# Or run the tools directly
uv run ruff check --fix src/ tests/ scripts/
uv run ruff format src/ tests/ scripts/
uv run mypy src/ tests/
uv run rumdl check .
```

`scripts/verify.sh` runs the whole gate CI runs on every pull request: lockfile,
lint, formatting, types, Markdown, spelling, the built artifacts, the test suite
from the extracted sdist, and a core-only wheel smoke test.

cspell needs Node (`npx`). New domain words go in `cspell-dictionary.txt`.

## Troubleshooting

- **Import errors or a stale environment**: re-sync with `uv sync --all-extras`.
- **The QR image tests fail**: the `qr` extra is missing. `uv sync` without
  `--all-extras`, or a first `uv run` in a fresh checkout, installs the core
  only; re-sync with `uv sync --all-extras`.
- **Rebuild from scratch**: `rm -rf .venv && uv sync --all-extras`.

Quick check that the optional pieces import:

```bash
uv run python -c "
from scipy.optimize import fminbound; print('✓ scipy.optimize')
from PIL import Image; import zxingcpp; print('✓ QR code reading')
"
```

## Related

- [Updating dependencies](updating-dependencies.md)
- [Releasing](releasing.md)
