# Update Instructions

Quick guide for updating dependencies and maintaining the pyxctsk project.

## Prerequisites

Sync the environment (creates `.venv` and installs everything):

```bash
cd /home/simon/DEV/git/pyxctsk
uv sync --all-extras
```

## Updating Dependencies

### Update Process

1. **Check outdated packages**: `uv pip list --outdated`
2. **Bump everything within the declared ranges**: `uv lock --upgrade`
3. **Bump a single package**: `uv lock --upgrade-package scipy`
4. **Update pyproject.toml** if you want to raise the minimum versions, e.g.:

    ```toml
    dependencies = [
        "click>=8.4.2",
        "geopy>=2.5.0",
        "Pillow>=12.3.0",
        "pyproj>=3.7.2",
        "qrcode[pil]>=8.2",
        "scipy>=1.17.1",
        "simplekml>=1.3.6",
        "zxing-cpp>=3.1.1",
    ]
    ```

   The same applies to `[project.optional-dependencies]` (`web`, `analysis`) and
   the `dev` `[dependency-groups]`. The convention here is that a floor names the
   version the suite is actually run against, so raising floors is a step in the
   update, not a separate decision.

   After editing `pyproject.toml`, run `uv lock` to refresh `uv.lock`.

5. **Test**: `uv sync --all-extras && uv run pytest`
6. **Re-run the checkers whenever `ruff` or `mypy` moved** — a tool bump changes
   what they report, and neither shows up in the test suite:

    ```bash
    uv run ruff check --fix src/ tests/ scripts/
    uv run ruff format src/ tests/ scripts/
    uv run mypy --config-file mypy.ini src/
    ```

   Note that `ruff format` reaches beyond `*.py`: since 0.16 it also formats
   Python code blocks inside Markdown, so a docs file can turn up in the diff.
   The lefthook hooks are globbed to `*.py` and won't catch that.

### Check Latest Versions

```bash
uv pip index versions [package_name]
```

## Development Dependencies

```bash
# Install the dev group plus the web and analysis extras
uv sync --all-extras
```

## Troubleshooting

**Common Issues:**

- **Import errors / stale environment**: Re-sync with `uv sync --all-extras`
- **Rebuild from scratch**: `rm -rf .venv && uv sync --all-extras`
- **Missing dependencies**: Ensure scipy is installed

**Quick verification test:**

```bash
uv run python -c "
from scipy.optimize import fminbound; print('✓ scipy.optimize')
from PIL import Image; import zxingcpp; print('✓ QR code reading')
"
```

## Maintenance Schedule

- **Monthly**: Check security updates, update dev dependencies
- **Quarterly**: Update main dependencies, check deprecated features
- **Before releases**: Update all dependencies, run full test suite

## Version History

| Date | Updated Packages | Notes |
|------|------------------|-------|
| 2026-08-18 | geopy, Pillow, zxing-cpp, matplotlib, mypy, ruff, coverage, lefthook, certifi, charset-normalizer, numpy, packaging, pygments, soupsieve, typing-extensions | `uv lock --upgrade`; all declared floors (runtime, extras, dev) raised to the versions the suite is run against. mypy 1.x → 2.3.1 and zxing-cpp 2.x → 3.1.1 are major bumps, both clean. ruff 0.16 reformatted one Markdown code block. 682 passed, 18 skipped |
| 2025-07-21 | click, geopy, polyline, pyproj, qrcode, beautifulsoup4, mypy, pytest, pytest-cov, requests, matplotlib, numpy | Dependency update: main and optional packages bumped to latest stable versions |
| 2025-07-08 | scipy, click, geopy, Pillow, pyproj, qrcode | Initial dependency audit and updates |
