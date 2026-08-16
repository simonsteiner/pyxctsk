"""The package layering, asserted rather than described.

`CLAUDE.md` states two rules about how `src/pyxctsk/` is allowed to import
itself. Both were prose until this file, and both have already been broken once
each — the second one broke `import pyxctsk` outright:

1. **Dependencies run one way.** `model` depends on nothing, `qrcode` and
   `distance` depend on `model`, `export` depends on `model` and `distance`.
2. **Modules import sibling submodules directly**, never through their own
   package's `__init__`, so a partially-initialized package cannot fail an
   import halfway through.

Only *module-level* imports are checked. Imports under ``if TYPE_CHECKING:``
and inside function bodies are the deliberate escape hatches — a conversion
method on the model has to reach the QR format somehow — and the point of the
rule is that they stay rare and visible, not that they never happen. The two
that exist today are named in :data:`EXPECTED_DEFERRED_IMPORTS`, so adding a
third is a decision someone has to make on purpose.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "pyxctsk"

#: What each package is allowed to import from the rest of pyxctsk.
ALLOWED: dict[str, set[str]] = {
    "model": set(),
    "qrcode": {"model"},
    "distance": {"model"},
    "export": {"model", "distance"},
}

#: Top-level modules with no internal dependencies, free for anyone to import.
#: `test_leaf_modules_are_leaves` keeps this honest.
LEAVES = {"exceptions"}

#: Every function-local import of one pyxctsk package from another, as
#: "module -> package". Each one exists to break a cycle that a convenience
#: method would otherwise create; see the docstring at each site.
EXPECTED_DEFERRED_IMPORTS = {
    ("model/task.py", "qrcode"),  # Task.to_qr_code_task
    ("qrcode/task.py", "qrcode"),  # QRCodeTask.from_task / .to_task
}


def _modules() -> list[Path]:
    """Every source file in the package, __init__ files included."""
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path) -> str:
    """Package-relative path, e.g. 'model/task.py'."""
    return path.relative_to(SRC).as_posix()


def _target_package(node: ast.ImportFrom, module_path: Path) -> str | None:
    """Resolve a relative `from ... import` to the pyxctsk package it names.

    Returns the top-level package or module inside pyxctsk (``"model"``,
    ``"exceptions"``, …), or None for third-party and standard-library imports.
    """
    if node.level == 0:  # absolute import: third-party or stdlib
        return None

    # Directory the import is resolved against: level 1 is the module's own
    # package, level 2 its parent, and so on.
    base = module_path.parent
    for _ in range(node.level - 1):
        base = base.parent

    parts = (node.module or "").split(".") if node.module else []
    resolved = base.relative_to(SRC).as_posix()
    full = [p for p in (resolved.split("/") if resolved != "." else []) + parts if p]
    return full[0] if full else None


def _module_level_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Relative imports that run at import time, in statement order.

    Skips anything inside a function or class body, and anything guarded by
    `if TYPE_CHECKING:` — neither runs when the module is imported.
    """
    found = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            found.append(node)
    return found


def _deferred_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Relative imports inside function bodies."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if isinstance(inner, ast.ImportFrom):
                    found.append(inner)
    return found


@pytest.fixture(scope="module")
def parsed() -> list[tuple[Path, ast.Module]]:
    """Every module in the package, parsed once."""
    return [(path, ast.parse(path.read_text())) for path in _modules()]


def test_dependencies_run_one_way(parsed):
    """No package imports another it is not allowed to depend on."""
    violations = []
    for path, tree in parsed:
        rel = _rel(path)
        package = path.relative_to(SRC).parts[0]
        if package not in ALLOWED:  # top-level module: may import anything
            continue
        for node in _module_level_imports(tree):
            target = _target_package(node, path)
            if target in (None, package) or target in LEAVES:
                continue
            if target not in ALLOWED[package]:
                violations.append(f"{rel}:{node.lineno} imports {target}")

    assert not violations, "layering violations:\n  " + "\n  ".join(violations)


def test_no_module_imports_its_own_package_init(parsed):
    """Inside a package, submodules import each other directly.

    `from . import x` or `from ..qrcode import x` inside the qrcode package
    routes through that package's `__init__`, which may still be executing.
    """
    violations = []
    for path, tree in parsed:
        if path.name == "__init__.py":
            continue
        package = path.relative_to(SRC).parts[0]
        if package not in ALLOWED:
            continue
        for node in _module_level_imports(tree):
            # `from . import x` — the package's own __init__ by definition.
            bare_own_package = node.level == 1 and node.module is None
            # `from ..export import x` / `from ..export.common import x` from
            # inside export: routed through the package rather than the sibling.
            via_own_package = (
                node.level == 2
                and node.module is not None
                and node.module.split(".")[0] == package
            )
            if bare_own_package or via_own_package:
                violations.append(f"{_rel(path)}:{node.lineno}")

    assert not violations, (
        "these import their own package's __init__ instead of a sibling "
        "submodule:\n  " + "\n  ".join(violations)
    )


def test_leaf_modules_are_leaves(parsed):
    """Modules everyone is allowed to import must not import back."""
    for path, tree in parsed:
        if path.parent != SRC or path.stem not in LEAVES:
            continue
        for node in _module_level_imports(tree):
            target = _target_package(node, path)
            assert target is None, (
                f"{_rel(path)}:{node.lineno} is treated as a leaf by every "
                f"package but imports {target}"
            )


def test_deferred_cross_package_imports_are_the_known_ones(parsed):
    """Function-local imports across packages stay the documented two."""
    found = set()
    for path, tree in parsed:
        package = path.relative_to(SRC).parts[0]
        if package not in ALLOWED:
            continue
        for node in _deferred_imports(tree):
            target = _target_package(node, path)
            if target is None or target in LEAVES:
                continue
            found.add((_rel(path), target))

    assert found == EXPECTED_DEFERRED_IMPORTS, (
        "function-local imports across packages changed.\n"
        f"  found:    {sorted(found)}\n"
        f"  expected: {sorted(EXPECTED_DEFERRED_IMPORTS)}\n"
        "Each one breaks a cycle; add it to EXPECTED_DEFERRED_IMPORTS with a "
        "reason, or find a way not to need it."
    )
