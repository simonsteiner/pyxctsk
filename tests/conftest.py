"""Shared test fixtures and configuration for pyxctsk tests."""

from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from pyxctsk import Task, parse_task


def _load_task_from_file(task_file: Path) -> Task:
    """Load a task from a file path, handling both string paths and Path objects."""
    with open(task_file, "r") as f:
        task_data = f.read()
    return parse_task(task_data)


def _ensure_dir_exists(path: Path) -> Path:
    """Ensure directory exists, creating it if necessary."""
    path.mkdir(exist_ok=True, parents=True)
    return path


def _find_xctsk_files(data_dir: Path) -> List[Path]:
    """Find all XCTSK files in the given directory."""
    return list(data_dir.glob("*.xctsk"))


def _stem_to_task_name(filename: str) -> str:
    """Convert filename to task name by removing .xctsk extension."""
    return filename.replace(".xctsk", "")


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Return the path to test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def reference_tasks_dir(test_data_dir: Path) -> Path:
    """Return the path to reference tasks directory."""
    return test_data_dir / "reference_tasks" / "xctsk"


@pytest.fixture(scope="session")
def reference_json_dir(test_data_dir: Path) -> Path:
    """Return the path to reference JSON data directory."""
    return test_data_dir / "reference_tasks" / "json"


@pytest.fixture(scope="session")
def sample_task_files(reference_tasks_dir: Path) -> List[Path]:
    """Return list of available sample task files."""
    if not reference_tasks_dir.exists():
        pytest.skip(f"Reference tasks directory not found: {reference_tasks_dir}")

    task_files = _find_xctsk_files(reference_tasks_dir)
    if not task_files:
        pytest.skip("No sample task files found")

    return task_files


@pytest.fixture(scope="session")
def sample_task(sample_task_files: List[Path]) -> Task:
    """Return a loaded sample task for general testing."""
    # Use the first available task file
    return _load_task_from_file(sample_task_files[0])


@pytest.fixture(scope="session")
def loaded_sample_tasks(sample_task_files: List[Path]) -> Dict[str, Task]:
    """Return dictionary of all loaded sample tasks."""
    tasks = {}
    for task_file in sample_task_files:
        try:
            task = _load_task_from_file(task_file)
            tasks[task_file.stem] = task
        except Exception as e:
            # Log but don't fail - some test files might be invalid
            print(f"Warning: Failed to load {task_file.name}: {e}")

    if not tasks:
        pytest.skip("No valid task files could be loaded")

    return tasks


@pytest.fixture
def output_dir(test_data_dir: Path) -> Path:
    """Create and return output directory for test artifacts."""
    return _ensure_dir_exists(test_data_dir / "visual_output")


@pytest.fixture
def qrcode_test_data(test_data_dir: Path, output_dir: Path) -> Tuple[Path, Path, Path]:
    """Provide standardized test data directory paths for QR code testing.

    Returns:
        Tuple of (xctsk_dir, expected_dir, output_dir) where:
        - xctsk_dir: Directory containing reference .xctsk task files
        - expected_dir: Directory containing expected QR code strings (.txt files)
        - output_dir: Directory for generated QR code images and test artifacts
    """
    xctsk_dir = test_data_dir / "reference_tasks" / "xctsk"
    expected_dir = test_data_dir / "reference_tasks" / "qrcode_string"
    qrcode_output_dir = _ensure_dir_exists(output_dir / "qrcode_test")

    return xctsk_dir, expected_dir, qrcode_output_dir


@pytest.fixture
def sss_output_dir(output_dir: Path) -> Path:
    """Create and return output directory for SSS test artifacts."""
    return _ensure_dir_exists(output_dir / "sss_tests")


@pytest.fixture
def sss_task(loaded_sample_tasks: Dict[str, Task]) -> Task:
    """Load a real SSS task for testing."""
    # Look for a task with SSS in its turnpoints
    for task_name, task in loaded_sample_tasks.items():
        # Check if any turnpoint has SSS type
        for tp in task.turnpoints:
            if tp.type and tp.type.value == "SSS":
                return task

    # Fallback: try specific known SSS task files
    known_sss_files = ["task_fuvu.xctsk", "task_gibe.xctsk"]
    for filename in known_sss_files:
        task_name = _stem_to_task_name(filename)
        if task_name in loaded_sample_tasks:
            return loaded_sample_tasks[task_name]

    pytest.skip("No SSS task found in sample tasks")  # type: ignore[return]
    raise AssertionError("unreachable")


@pytest.fixture
def bevo_task(reference_tasks_dir: Path) -> Task:
    """Return the specific task_bevo.xctsk task for smoke testing."""
    task_file = reference_tasks_dir / "task_bevo.xctsk"
    if not task_file.exists():
        pytest.skip(f"Task file not found: {task_file}")
    return _load_task_from_file(task_file)


@pytest.fixture
def temp_xctsk_file(tmp_path: Path):
    """Create a temporary XCTSK file for testing."""

    def _create_temp_file(content: str, filename: str = "test_task.xctsk") -> Path:
        temp_file = tmp_path / filename
        temp_file.write_text(content)
        return temp_file

    return _create_temp_file


# Alias for backward compatibility
find_xctsk_files = _find_xctsk_files
