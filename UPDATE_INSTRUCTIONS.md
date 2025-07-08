# Update Instructions

Quick guide for updating dependencies and maintaining the pyxctsk project.

## Prerequisites

Activate the virtual environment:

```bash
cd /Users/simon/DEV/git/pyxctsk
source .venv/bin/activate
```

## Updating Dependencies

### Update Process

1. **Check outdated packages**: `pip list --outdated`
2. **Check specific versions**: `pip show click geopy Pillow polyline pyproj pyzbar qrcode scipy`
3. **Update dependencies**: `pip install --upgrade click geopy Pillow polyline pyproj pyzbar qrcode scipy`
4. **Update pyproject.toml** with new minimum versions:

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

5. **Test**: `pip install -e ".[dev]"` and run tests

### Check Latest Versions

```bash
pip index versions [package_name]
```

## Development Dependencies

```bash
# Install with optional dependencies
pip install -e ".[dev,web,analysis]"
```

## Troubleshooting

**Common Issues:**

- **Import errors**: Reinstall with `pip install -e .`
- **Version conflicts**: Use `pip install --upgrade --force-reinstall [package]`
- **Missing dependencies**: Ensure scipy is installed

**Quick verification test:**

```bash
python -c "
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
| 2025-07-08 | scipy, click, geopy, Pillow, pyproj, qrcode | Initial dependency audit and updates |
