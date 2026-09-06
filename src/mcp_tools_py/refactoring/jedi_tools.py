"""Jedi-based symbol discovery and reference finding."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Tuple


@lru_cache(maxsize=None)
def _get_project(
    project_dir: str, interpreter: str
) -> Tuple[Optional[Any], Optional[str]]:
    """Build a jedi project that resolves names in `interpreter`.

    The environment is forced here rather than left to `jedi.Script`, which
    is the first caller of `Project.get_environment()`: an unusable
    interpreter must fail inside this try, not later at the call site.
    `get_environment()` memoises on the project, so forcing it costs no
    extra child process.

    Failures are cached alongside successes — a fixed environment needs a
    server restart either way, and this avoids one spawn attempt per call.

    Args:
        project_dir: Absolute path to project root.
        interpreter: Path to the Python interpreter to resolve names in.

    Returns:
        `(project, None)`, or `(None, error_message)` when the environment
        cannot be used.
    """
    import jedi  # pylint: disable=import-error,import-outside-toplevel

    try:
        project = jedi.Project(path=project_dir, environment_path=interpreter)
        project.get_environment()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return None, (
            f"Error: cannot analyse against the Python environment at "
            f"'{interpreter}': {exc}"
        )
    return project, None


def list_symbols(project_dir: Path, file_path: str, interpreter: str) -> str:
    """List all top-level symbols in a file.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.
        interpreter: Path to the Python interpreter to resolve names in.

    Returns:
        Formatted string listing symbols, or error message.
    """
    import jedi  # pylint: disable=import-error,import-outside-toplevel

    abs_path = project_dir / file_path
    if not abs_path.exists():
        return f"Error: file not found: {file_path}"

    source = abs_path.read_text(encoding="utf-8")
    project, error = _get_project(str(project_dir), interpreter)
    if error is not None:
        return error
    script = jedi.Script(code=source, path=str(abs_path), project=project)

    try:
        names = script.get_names(all_scopes=False, definitions=True)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error analyzing {file_path}: {exc}"

    # Filter to top-level definitions only (exclude imports)
    top_level = _filter_top_level(names, exclude_imports=True)

    if not top_level:
        return f"No symbols found in {file_path}"

    lines = [f"Symbols in {file_path}:"]
    for name in top_level:
        symbol_type = name.type
        lines.append(f"  {symbol_type}: {name.name} (line {name.line})")

    return "\n".join(lines)


def _is_import(name: Any) -> bool:
    """Check if a jedi Name originates from an import statement.

    Returns:
        True if the name is part of an `import` or `from ... import`.
    """
    tree_name = getattr(getattr(name, "_name", None), "tree_name", None)
    if tree_name is None:
        return False
    node = tree_name.parent
    while node is not None:
        if node.type in ("import_name", "import_from"):
            return True
        node = node.parent
    return False


def _filter_top_level(names: List[Any], *, exclude_imports: bool = False) -> List[Any]:
    """Filter jedi names to top-level symbols only.

    Returns:
        Names whose parent scope is the module (optionally excluding imports).
    """
    result: List[Any] = []
    for name in names:
        parent = name.parent()
        if parent is not None and parent.type == "module":
            if exclude_imports and _is_import(name):
                continue
            result.append(name)
    return result


def find_references(
    project_dir: Path, file_path: str, symbol_name: str, interpreter: str
) -> str:
    """Find all references to a symbol across the project.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.
        symbol_name: Name of the top-level symbol.
        interpreter: Path to the Python interpreter to resolve names in.

    Returns:
        Formatted string listing references, or error message.
    """
    import jedi  # pylint: disable=import-error,import-outside-toplevel

    abs_path = project_dir / file_path
    if not abs_path.exists():
        return f"Error: file not found: {file_path}"

    source = abs_path.read_text(encoding="utf-8")
    project, error = _get_project(str(project_dir), interpreter)
    if error is not None:
        return error

    # Find the symbol's position using get_names
    script = jedi.Script(code=source, path=str(abs_path), project=project)
    names = script.get_names(all_scopes=False, definitions=True)
    top_level = _filter_top_level(names)

    target = None
    for name in top_level:
        if name.name == symbol_name:
            target = name
            break

    if target is None:
        available = [n.name for n in top_level]
        available_str = ", ".join(available) if available else "(none)"
        return (
            f"Symbol '{symbol_name}' not found in {file_path}.\n"
            f"Available top-level symbols: {available_str}"
        )

    line = target.line
    col = target.column

    try:
        refs = script.get_references(line=line, column=col)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error finding references for '{symbol_name}': {exc}"

    if not refs:
        return f"No references found for '{symbol_name}'"

    lines = [f"References to '{symbol_name}' ({len(refs)} found):"]
    for ref in refs:
        ref_path = ref.module_path
        if ref_path is not None:
            try:
                rel = Path(ref_path).relative_to(project_dir)
            except ValueError:
                rel = Path(ref_path)
        else:
            rel = Path(file_path)
        description = ref.description
        lines.append(f"  {rel}:{ref.line}: {description}")

    return "\n".join(lines)
