"""The package layering, asserted rather than described.

`CLAUDE.md` states two rules about how `src/pyxctsk/` is allowed to import
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

#: Every function-local import of one pyxctsk module by another, as
#: "importer -> imported". Not all of them cross a package boundary — the
#: second one does not — but each exists to break an import cycle a convenience
#: method would otherwise create, which is what makes it worth pinning. See the
#: docstring at each site for the cycle it breaks.
EXPECTED_DEFERRED_IMPORTS = {
    # Task.to_qr_code_task: conversion imports model.task to build a Task.
    ("model/task.py", "qrcode.conversion"),
    # QRCodeTask.from_task / .from_task_waypoints / .to_task: conversion
    # imports qrcode.task for QRCodeTask, so this one is a cycle inside the
    # qrcode package rather than between two of them.
    ("qrcode/task.py", "qrcode.conversion"),
}


def _modules() -> list[Path]:
    """Every source file in the package, __init__ files included."""
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path) -> str:
    """Package-relative path, e.g. 'model/task.py'."""
    return path.relative_to(SRC).as_posix()


def _target_module(node: ast.ImportFrom, module_path: Path) -> str | None:
    """Resolve a relative `from ... import` to the pyxctsk module it names.

    Returns the dotted path within pyxctsk (``"qrcode.conversion"``,
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
    return ".".join(full) if full else None


def _target_package(node: ast.ImportFrom, module_path: Path) -> str | None:
    """The top-level pyxctsk package a relative import reaches into.

    ``"qrcode"`` for ``from ..qrcode.conversion import x``. None for
    third-party and standard-library imports.
    """
    target = _target_module(node, module_path)
    return target.split(".")[0] if target else None


def _is_type_checking_guard(node: ast.AST) -> bool:
    """Whether this is an `if TYPE_CHECKING:` / `if typing.TYPE_CHECKING:`.

    Only the guarded body is type-only; an `else:` branch on the same `if` runs
    normally, so the caller skips the body and keeps walking `orelse`.
    """
    if not isinstance(node, ast.If):
        return False
    if isinstance(node.test, ast.Name):
        return node.test.id == "TYPE_CHECKING"
    if isinstance(node.test, ast.Attribute):
        return node.test.attr == "TYPE_CHECKING"
    return False


def _classify_imports(
    tree: ast.Module,
) -> tuple[list[ast.ImportFrom], list[ast.ImportFrom]]:
    """Split a module's `from ... import`s by whether they run on import.

    The question both layer rules ask is "does this execute when the module is
    imported", which is not the same as "is this a direct child of the module".
    A `try:/except ImportError:` at module level, a module-level `if`, and a
    class body all run on import; only a function body defers, and only
    `if TYPE_CHECKING:` never runs at all.

    Args:
        tree: The parsed module.

    Returns:
        `(at_import_time, deferred)`, each in statement order. Bodies guarded by
        `if TYPE_CHECKING:` appear in neither.
    """
    at_import_time: list[ast.ImportFrom] = []
    deferred: list[ast.ImportFrom] = []

    def visit(node: ast.AST, in_function: bool) -> None:
        if isinstance(node, ast.ImportFrom):
            (deferred if in_function else at_import_time).append(node)
            return
        if _is_type_checking_guard(node):
            assert isinstance(node, ast.If)  # narrowed by the guard predicate
            for statement in node.orelse:
                visit(statement, in_function)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            in_function = True
        for child in ast.iter_child_nodes(node):
            visit(child, in_function)

    visit(tree, False)
    return at_import_time, deferred


def _import_time_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Relative imports that run when the module is imported."""
    return _classify_imports(tree)[0]


def _deferred_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Relative imports inside function bodies, which run only when called."""
    return _classify_imports(tree)[1]


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
        for node in _import_time_imports(tree):
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
        for node in _import_time_imports(tree):
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
        for node in _import_time_imports(tree):
            target = _target_package(node, path)
            assert target is None, (
                f"{_rel(path)}:{node.lineno} is treated as a leaf by every "
                f"package but imports {target}"
            )


def test_deferred_imports_are_the_known_cycle_breakers(parsed):
    """Function-local imports inside the packages stay the documented two."""
    found = set()
    for path, tree in parsed:
        package = path.relative_to(SRC).parts[0]
        if package not in ALLOWED:
            continue
        for node in _deferred_imports(tree):
            target = _target_module(node, path)
            if target is None or target.split(".")[0] in LEAVES:
                continue
            found.add((_rel(path), target))

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
    at_import_time, deferred = _classify_imports(ast.parse(dedent(source)))
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


class TestTheFrontDoorNamesTheAnswers:
    """`pyxctsk.__all__` is the whole library's interface, not a sample of it.

    Its export set had no rule: it carried 7 of `pyxctsk.distance`'s 22 names,
    including `distance_through_centers` — documented as "the primitive, not
    the published number" — while `center_distance`, the call that docstring
    tells you to make instead, was absent. It also exported `OptimizedRoute`
    and `task_distances_from` without exporting anything that could build the
    argument, which is why `docs/s7f-distance-reference.md` reached past it.
    """

    #: What a doc, a docstring or a test tells a caller to import from the top
    #: level. Adding a name here without exporting it fails.
    DOCUMENTED = (
        "DistanceReport",
        "MeasuredTask",
        "TaskDrawing",
        "Task",
        "parse_task",
        "center_distance",
        "center_distance_readings",
        "CenterDistanceReading",
        "PROPOSED_READING",
        "GoalLine",
        "TooFewTurnpointsError",
        "TaskValidationError",
        "ValidationRule",
        "calculate_iteratively_refined_route",
        "task_to_turnpoints",
    )

    def test_every_documented_name_is_reachable_from_the_front_door(self):
        """Reaching into a subpackage should be a choice, not a workaround."""
        import pyxctsk

        missing = [n for n in self.DOCUMENTED if not hasattr(pyxctsk, n)]

        assert missing == []
        assert [n for n in self.DOCUMENTED if n not in pyxctsk.__all__] == []

    def test_the_published_reading_travels_with_the_primitive(self):
        """Exporting `distance_through_centers` alone is what misled a caller.

        The primitive stays — it is a real function over `TaskTurnpoint`s — but
        the number a task board publishes has to be reachable beside it.
        """
        import pyxctsk

        if "distance_through_centers" in pyxctsk.__all__:
            assert "center_distance" in pyxctsk.__all__
            assert "CenterDistanceReading" in pyxctsk.__all__

    def test_every_exported_name_resolves(self):
        """`__all__` and the module cannot disagree about what exists."""
        import pyxctsk

        assert [n for n in pyxctsk.__all__ if not hasattr(pyxctsk, n)] == []

    def test_a_route_can_be_built_by_a_caller_who_only_uses_the_front_door(self):
        """`OptimizedRoute` was exported with no exported way to make one."""
        import pyxctsk

        assert hasattr(pyxctsk, "OptimizedRoute")
        assert hasattr(pyxctsk, "MeasuredTask")
        route = pyxctsk.MeasuredTask.from_task(
            pyxctsk.Task(
                task_type=pyxctsk.TaskType.CLASSIC,
                version=1,
                turnpoints=[
                    pyxctsk.Turnpoint(
                        radius=400,
                        waypoint=pyxctsk.Waypoint(
                            name="A", lat=46.0, lon=8.0, alt_smoothed=0
                        ),
                    ),
                    pyxctsk.Turnpoint(
                        radius=400,
                        waypoint=pyxctsk.Waypoint(
                            name="B", lat=46.5, lon=8.5, alt_smoothed=0
                        ),
                    ),
                ],
            )
        ).route

        assert isinstance(route, pyxctsk.OptimizedRoute)


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
            deferred_nodes = set(map(id, _deferred_imports(tree)))
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
