"""The package layering, asserted rather than described.

`AGENTS.md` states two rules about how `src/pyxctsk/` is allowed to import
itself. Both were prose until this file, and both have already been broken once
each — the second one broke `import pyxctsk` outright:

1. **Dependencies run one way.** `model` depends on nothing, `qrcode` and
   `distance` depend on `model`, `export` depends on `model` and `distance`.
2. **Modules import sibling submodules directly**, never through their own
   package's `__init__`, so a partially-initialized package cannot fail an
   import halfway through.

Both rules are about what happens when a module is imported, so the imports
checked against them are the ones that *run at import time* — wherever they sit
in the file. A relative import inside a module-level ``try:/except
ImportError:``, inside any other module-level ``if``, or directly in a class
body all run on import and are all checked. Imports under ``if TYPE_CHECKING:``
and inside function bodies are the deliberate escape hatches — a conversion
method on the model has to reach the QR format somehow — and the point is that
they stay rare and visible, not that they never happen.
The two function-local ones that exist today are pinned by name in
:data:`EXPECTED_DEFERRED_IMPORTS`, so adding a third is a decision someone has
to make on purpose. Both break a cycle; only one of them crosses a package
boundary, which is why that check is about deferred imports generally rather
than cross-package ones.
"""

import ast
from pathlib import Path
from textwrap import dedent

import pytest

from tests.import_scan import (
    SRC,
    classify_imports,
    deferred_imports,
    import_time_imports,
    modules,
    rel_path,
    target_module,
    target_package,
)

#: What each package is allowed to import from the rest of pyxctsk.
ALLOWED: dict[str, set[str]] = {
    "model": set(),
    "qrcode": {"model"},
    "distance": {"model"},
    "export": {"model", "distance"},
}

#: Top-level modules with no internal dependencies, free for anyone to import.
#: `test_leaf_modules_are_leaves` keeps this honest.
LEAVES = {"exceptions", "metadata"}

#: Every function-local import of one pyxctsk module by another, as
#: "importer -> imported". Not all of them cross a package boundary — the
#: second one does not — but each exists to break an import cycle a convenience
#: method would otherwise create, which is what makes it worth pinning. See the
#: docstring at each site for the cycle it breaks.
EXPECTED_DEFERRED_IMPORTS = {
    # Task.to_qr_code_task: conversion imports model.task to build a Task.
    ("model/task.py", "qrcode.conversion"),
    # QRCodeTask.to_task: conversion
    # imports qrcode.task for QRCodeTask, so this one is a cycle inside the
    # qrcode package rather than between two of them.
    ("qrcode/task.py", "qrcode.conversion"),
}


@pytest.fixture(scope="module")
def parsed() -> list[tuple[Path, ast.Module]]:
    """Every module in the package, parsed once."""
    return [(path, ast.parse(path.read_text())) for path in modules()]


def test_dependencies_run_one_way(parsed):
    """No package imports another it is not allowed to depend on."""
    violations = []
    for path, tree in parsed:
        rel = rel_path(path)
        package = path.relative_to(SRC).parts[0]
        if package not in ALLOWED:  # top-level module: may import anything
            continue
        for node in import_time_imports(tree):
            target = target_package(node, path)
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
        for node in import_time_imports(tree):
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
                violations.append(f"{rel_path(path)}:{node.lineno}")

    assert not violations, (
        "these import their own package's __init__ instead of a sibling "
        "submodule:\n  " + "\n  ".join(violations)
    )


def test_leaf_modules_are_leaves(parsed):
    """Modules everyone is allowed to import must not import back."""
    for path, tree in parsed:
        if path.parent != SRC or path.stem not in LEAVES:
            continue
        for node in import_time_imports(tree):
            target = target_package(node, path)
            assert target is None, (
                f"{rel_path(path)}:{node.lineno} is treated as a leaf by every "
                f"package but imports {target}"
            )


def test_deferred_imports_are_the_known_cycle_breakers(parsed):
    """Function-local imports inside the packages stay the documented two."""
    found = set()
    for path, tree in parsed:
        package = path.relative_to(SRC).parts[0]
        if package not in ALLOWED:
            continue
        for node in deferred_imports(tree):
            target = target_module(node, path)
            if target is None or target.split(".")[0] in LEAVES:
                continue
            found.add((rel_path(path), target))

    assert found == EXPECTED_DEFERRED_IMPORTS, (
        "function-local imports inside the packages changed.\n"
        f"  found:    {sorted(found)}\n"
        f"  expected: {sorted(EXPECTED_DEFERRED_IMPORTS)}\n"
        "Each one breaks a cycle; add it to EXPECTED_DEFERRED_IMPORTS with a "
        "reason, or find a way not to need it."
    )


def _classified(source: str) -> tuple[list[str], list[str]]:
    """Classify a source snippet, as the module names in each category.

    Args:
        source: Module source, indented for readability and dedented here.

    Returns:
        `(at_import_time, deferred)` as the dotted module each import names.
    """
    at_import_time, deferred = classify_imports(ast.parse(dedent(source)))
    return (
        [node.module or "" for node in at_import_time],
        [node.module or "" for node in deferred],
    )


class TestImportsAreCollectedByWhetherTheyRun:
    """The collector's rule is "runs at import time", not "sits at module level".

    Iterating `tree.body` was a proxy for the first, and the two differ exactly
    where this codebase already lives: `parser.py` and `qrcode/image.py` guard
    their optional dependencies with `try: import … except ImportError:`, so a
    relative import written in that shape used to escape all three layer checks
    while looking checked. A class-body import escaped both collectors at once —
    too nested for the layer checks, not in a function body for the deferred
    check — though it runs on import like any other.
    """

    def test_a_module_level_try_runs_on_import(self):
        """The optional-dependency shape the codebase already uses."""
        assert _classified("""
            try:
                from .qrcode.image import decode
            except ImportError:
                from .exceptions import QRCodeError as decode
        """) == (["qrcode.image", "exceptions"], [])

    def test_any_module_level_branch_runs_on_import(self):
        """`if`/`else` at module level is not a deferral either."""
        assert _classified("""
            import sys

            if sys.version_info >= (3, 12):
                from .model.task import Task
            else:
                from .model.enums import TaskType
        """) == (["model.task", "model.enums"], [])

    def test_a_class_body_runs_on_import(self):
        """A class body executes on import, so its imports are checked."""
        assert _classified("""
            class Codec:
                from .model.rounding import round_half_up
        """) == (["model.rounding"], [])

    def test_type_checking_bodies_run_never(self):
        """Both spellings of the guard, and neither list gets the import."""
        assert _classified("""
            if TYPE_CHECKING:
                from .model.task import Task

            if typing.TYPE_CHECKING:
                from .distance.turnpoint import TaskTurnpoint
        """) == ([], [])

    def test_the_else_of_a_type_checking_guard_still_runs(self):
        """Only the guarded body is type-only; `orelse` is ordinary code."""
        assert _classified("""
            if TYPE_CHECKING:
                from .model.task import Task
            else:
                from .model.enums import TaskType
        """) == (["model.enums"], [])

    def test_a_type_checking_guard_inside_a_function_runs_never(self):
        """The guard wins over the function body, in either order of nesting."""
        assert _classified("""
            def build():
                if TYPE_CHECKING:
                    from .model.task import Task
                from .qrcode.conversion import task_to_qr_code_task
        """) == ([], ["qrcode.conversion"])

    def test_function_and_method_bodies_defer(self):
        """Including a method, which is how both pinned cycle-breakers look."""
        assert _classified("""
            from .model.enums import TaskType


            def convert():
                from .qrcode.conversion import task_to_qr_code_task


            class Task:
                def to_qr_code_task(self):
                    from .qrcode.conversion import task_to_qr_code_task

                async def later(self):
                    from .distance.turnpoint import TaskTurnpoint
        """) == (
            ["model.enums"],
            ["qrcode.conversion", "qrcode.conversion", "distance.turnpoint"],
        )

    def test_import_time_imports_keep_statement_order(self):
        """The layer checks report line numbers, so order has to hold."""
        at_import_time, _ = _classified("""
            from .model.task import Task
            try:
                from .qrcode.image import decode
            except ImportError:
                pass
            from .export.common import TaskDrawing
        """)
        assert at_import_time == ["model.task", "qrcode.image", "export.common"]


class TestTheOptimizerDependencyIsNotPaidUpFront:
    """`import pyxctsk` cost 400 ms, 297 of them scipy.optimize.

    One function in the whole library needs it. A caller that parses a task,
    converts it or draws it never runs that function, and used to pay for the
    import anyway — as did `pyxctsk --help`.
    """

    def test_scipy_is_not_imported_at_import_time(self):
        """Importing the package must not drag in the optimizer's solver.

        Asked of every module in ``src/`` rather than of the one file that
        happens to hold the call — the check used to name
        ``distance/turnpoint.py``, and would have gone quietly green had that
        file been split without anyone noticing.
        """
        module_level: list[str] = []
        deferred: list[str] = []
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text())
            deferred_nodes = set(map(id, deferred_imports(tree)))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if not node.module.startswith("scipy"):
                    continue
                target = deferred if id(node) in deferred_nodes else module_level
                target.append(f"{path.relative_to(SRC)}:{node.module}")

        assert deferred, "scipy is no longer used — has the solver changed?"
        assert not module_level, (
            f"scipy must stay a function-local import: it is 75% of the "
            f"package's import cost and one function needs it. Found at "
            f"module level in {module_level}"
        )
        assert [d.split(":")[1] for d in deferred] == ["scipy.optimize"]

    def test_the_optimizer_still_works_once_it_is_needed(self):
        """Deferring an import must not defer the answer."""
        from pyxctsk.distance.solver import plane_optimal_point

        point = plane_optimal_point((-10.0, 0.0), (10.0, 0.0), (0.0, 5.0), 2.0)

        assert point == pytest.approx((0.0, 3.0), abs=1e-6)
