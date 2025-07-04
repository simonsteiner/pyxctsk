# Releasing pyxctsk

Follow these steps to publish a new release to PyPI:

1. **Ensure a Clean Working State**
   - All code must be committed and pushed to `main`.
   - All tests must pass: `pytest`
   - Code must be formatted and linted:
     - `black src/ tests/`
     - `isort src/ tests/`
     - `flake8 src/ tests/  --extend-ignore E501`
     - `mypy src/`

2. **Update Version and Changelog**
   - Update the version in `pyproject.toml`.
   - Add a new entry to `CHANGELOG.md` with the release date and summary of changes.

3. **Tag the Release**
   - Create a new git tag matching the version (e.g., `v0.1.0`).
   - Example:

     ```bash
     export VERSION=X.Y.Z
     git commit -m "Release v${VERSION}"
     git tag v${VERSION} -m "Version ${VERSION}"
     ```

4. **Publish to PyPI**
   - Publishing is handled automatically by GitHub Actions when a tag is pushed.
   - Ensure `PYPI_API_TOKEN` is set in the repository secrets.

5. **Verify Release**
   - Check the [PyPI project page](https://pypi.org/project/pyxctsk/) for the new version.
   - Optionally, test installation:

     ```bash
     python3 -m venv venv-test
     source venv-test/bin/activate
     pip install pyxctsk
     ```

## Notes

- Only push tags for finalized releases.
- For test uploads, use TestPyPI and manual build/upload steps.
