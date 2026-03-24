"""Jedi-based symbol discovery and reference finding."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

import jedi  # pylint: disable=import-error


def list_symbols(project_dir: Path, file_path: str) -> str:
    """List all top-level symbols in a file.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.

    Returns:
        Formatted string listing symbols, or error message.
    """
    abs_path = project_dir / file_path
    if not abs_path.exists():
        return f"Error: file not found: {file_path}"

    source = abs_path.read_text(encoding="utf-8")
    project = jedi.Project(path=str(project_dir))
    script = jedi.Script(code=source, path=str(abs_path), project=project)

    try:
        names = script.get_names(all_scopes=False, definitions=True)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return f"Error analyzing {file_path}: {exc}"

    # Filter to top-level only: parent must be the module
    top_level = _filter_top_level(names)

    if not top_level:
        return f"No symbols found in {file_path}"

    lines = [f"Symbols in {file_path}:"]
    for name in top_level:
        symbol_type = name.type
        lines.append(f"  {symbol_type}: {name.name} (line {name.line})")

    return "\n".join(lines)


def _filter_top_level(names: List[Any]) -> List[Any]:
    """Filter jedi names to top-level symbols only."""
    result: List[Any] = []
    for name in names:
        parent = name.parent()
        if parent is not None and parent.type == "module":
            result.append(name)
    return result


def find_references(project_dir: Path, file_path: str, symbol_name: str) -> str:
    """Find all references to a symbol across the project.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.
        symbol_name: Name of the top-level symbol.

    Returns:
        Formatted string listing references, or error message.
    """
    abs_path = project_dir / file_path
    if not abs_path.exists():
        return f"Error: file not found: {file_path}"

    source = abs_path.read_text(encoding="utf-8")
    project = jedi.Project(path=str(project_dir))

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
