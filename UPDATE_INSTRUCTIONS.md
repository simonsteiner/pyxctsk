# Update Instructions

Quick guide for updating dependencies and maintaining the pyxctsk project.

## Prerequisites

Sync the environment (creates `.venv` and installs everything):

```bash
cd /Users/simon/DEV/git/pyxctsk
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
        "click>=8.2.0",
        "geopy>=2.4.0",
        "Pillow>=11.0.0",
        "polyline>=2.0.0",
        "pyproj>=3.7.0",
        "pyzbar>=0.1.9",
        "qrcode[pil]>=8.0.0",
        "scipy>=1.16.0",
    ]
    ```

   After editing `pyproject.toml`, run `uv lock` to refresh `uv.lock`.

5. **Test**: `uv sync --all-extras && uv run pytest`

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
from PIL import Image; from pyzbar import pyzbar; print('✓ QR code reading')
"
```

## Maintenance Schedule

- **Monthly**: Check security updates, update dev dependencies
- **Quarterly**: Update main dependencies, check deprecated features
- **Before releases**: Update all dependencies, run full test suite

## Version History

| Date | Updated Packages | Notes |
|------|------------------|-------|
| 2025-07-21 | click, geopy, polyline, pyproj, qrcode, beautifulsoup4, mypy, pytest, pytest-cov, requests, matplotlib, numpy | Dependency update: main and optional packages bumped to latest stable versions |
| 2025-07-08 | scipy, click, geopy, Pillow, pyproj, qrcode | Initial dependency audit and updates |
