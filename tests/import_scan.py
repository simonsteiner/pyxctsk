"""The AST scan behind the layering tests: which pyxctsk imports run at import time."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "pyxctsk"


def modules() -> list[Path]:
    """Every source file in the package, __init__ files included."""
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def rel_path(path: Path) -> str:
    """Package-relative path, e.g. 'model/task.py'."""
    return path.relative_to(SRC).as_posix()


def target_module(node: ast.ImportFrom, module_path: Path) -> str | None:
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


def target_package(node: ast.ImportFrom, module_path: Path) -> str | None:
    """The top-level pyxctsk package a relative import reaches into.

    ``"qrcode"`` for ``from ..qrcode.conversion import x``. None for
    third-party and standard-library imports.
    """
    target = target_module(node, module_path)
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


def classify_imports(
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


def import_time_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Relative imports that run when the module is imported."""
    return classify_imports(tree)[0]


def deferred_imports(tree: ast.Module) -> list[ast.ImportFrom]:
    """Relative imports inside function bodies, which run only when called."""
    return classify_imports(tree)[1]
