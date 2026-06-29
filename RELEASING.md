# Releasing pyxctsk

Follow these steps to publish a new release to PyPI:

1. **Ensure a Clean Working State**
   - All code must be committed and pushed to `main`.
   - Sync the environment: `uv sync --all-extras`
   - All tests must pass: `uv run pytest`
   - Code must be formatted and linted:
     - `uv run flake8 src/ tests/ scripts/ --extend-ignore=E501,E203 --exclude=scripts/task_viewer/airscore_clone`
     - `uv run mypy src/`
     - `uv run isort src/ tests/ scripts/`
     - `uv run black src/ tests/ scripts/`
     - `uv run pydocstyle src/ tests/ --convention=google`

2. **Update Version and Changelog**
   - Update the version in `pyproject.toml` — this is the single source of truth.
     `pyxctsk.__version__` reads it at runtime via `importlib.metadata`, so there
     is no second place to edit.
   - Run `uv lock` afterwards to refresh `uv.lock`.
   - Add a new entry to `CHANGELOG.md` with the release date and summary of changes.
   - To see changes since last release: `git log --oneline v0.2.0..HEAD -- src/`

3. **Tag the Release**
   - Create a new git tag matching the version (e.g., `v0.3.0`).
   - Example:

     ```bash
     export VERSION=0.3.0
     git commit -m "Release v${VERSION}"
     git tag v${VERSION} -m "Version ${VERSION}"
     git push origin main --tags
     ```

4. **Publish to PyPI**
   - Publishing is handled automatically by GitHub Actions when a tag is pushed.
   - Ensure `PYPI_API_TOKEN` is set in the repository secrets.

5. **Verify Release**
   - Check the [PyPI project page](https://pypi.org/project/pyxctsk/) for the new version.
   - Optionally, test installation in a throwaway environment:

     ```bash
     uvx --from pyxctsk pyxctsk --help
     ```

## Notes

- Only push tags for finalized releases.
- To build and publish manually: `uv build` then `uv publish` (set `UV_PUBLISH_TOKEN`).
- For test uploads, publish to TestPyPI: `uv publish --publish-url https://test.pypi.org/legacy/`.
