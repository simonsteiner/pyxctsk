# Releasing pyxctsk

Follow these steps to publish a new release to PyPI:

1. **Ensure a Clean Working State**
   - All code must be committed and pushed to `main`.
   - All tests must pass: `pytest`
   - Code must be formatted and linted:
     - `flake8 src/ tests/ scripts/ --extend-ignore=E501,E203 --exclude=scripts/task_viewer/airscore_clone`
     - `mypy src/`
     - `isort src/ tests/ scripts/`
     - `black src/ tests/ scripts/`

2. **Update Version and Changelog**
   - Update the version in `pyproject.toml`.
   - Add a new entry to `CHANGELOG.md` with the release date and summary of changes.
   - To see changes since last release: `git log --oneline v0.1.0..HEAD -- src/`

3. **Tag the Release**
   - Create a new git tag matching the version (e.g., `v0.1.0`).
   - Example:

     ```bash
     export VERSION=X.Y.Z
     git commit -m "Release v${VERSION}"
     git tag v${VERSION} -m "Version ${VERSION}"
     git push origin main --tags
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
