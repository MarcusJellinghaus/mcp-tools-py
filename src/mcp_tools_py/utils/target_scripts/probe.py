"""Describe the interpreter running this script, and resolve names in it.

Standard library only — see the package docstring for why.
"""

import importlib.metadata
import importlib.util
import inspect
import io
import json
import platform
import sys
import types
from typing import Any, Callable, Union, cast

_USAGE = "usage: probe.py info [MODULE ...] | probe.py source IMPORT_PATH MAX_LINES"


def _importable(module_names: list[str]) -> dict[str, bool]:
    """Report whether this interpreter can import each named module.

    Args:
        module_names: Module names to test.

    Returns:
        Mapping of module name to importability.
    """
    result: dict[str, bool] = {}
    for name in module_names:
        try:
            result[name] = importlib.util.find_spec(name) is not None
        except Exception:  # pylint: disable=broad-exception-caught
            # find_spec raises on a malformed name, and propagates whatever a
            # parent package raises on import. Either way the module is unusable.
            result[name] = False
    return result


def _distributions() -> dict[str, str]:
    """Collect the distributions installed in this interpreter.

    Returns:
        Mapping of lowercased distribution name to version.
    """
    result: dict[str, str] = {}
    for dist in importlib.metadata.distributions():
        name = dist.metadata["Name"]
        if name:
            result[name.lower()] = dist.version
    return result


def _info(module_names: list[str]) -> dict[str, object]:
    """Describe this interpreter.

    Args:
        module_names: Module names whose importability the caller asked about.

    Returns:
        The probe blob: version, ``sys.path``, installed distributions and the
        importability of each requested module.
    """
    return {
        "version": platform.python_version(),
        "sys_path": list(sys.path),
        "distributions": _distributions(),
        "importable": _importable(module_names),
    }


def _source(import_path: str, max_lines: int) -> str:
    """Retrieve source code for any importable Python symbol.

    Note: Uses ``importlib.import_module``, which executes module-level code
    as a side effect of importing the target module.

    Args:
        import_path: Dotted import path (e.g. "os.path.join" or "json.JSONEncoder").
        max_lines: Maximum number of source lines to return.

    Returns:
        Source code string, or an error message if resolution fails.
    """
    parts = import_path.split(".")

    # Walk backwards to find the longest importable module prefix
    module: types.ModuleType | None = None
    remaining: list[str] = []
    for i in range(len(parts), 0, -1):
        module_path = ".".join(parts[:i])
        try:
            module = importlib.import_module(module_path)
            remaining = parts[i:]
            break
        except (ImportError, ModuleNotFoundError, ValueError, TypeError):
            continue

    if module is None:
        return f"Module '{import_path}' not found"

    # Walk the remaining attribute chain
    obj: object = module
    for attr_name in remaining:
        try:
            obj = getattr(obj, attr_name)
        except AttributeError:
            module_name = module.__name__
            # List available symbols, sorted, capped at 50, type-annotated
            members = inspect.getmembers(obj)
            symbols: list[str] = []
            for name, value in sorted(members, key=lambda m: m[0]):
                if name.startswith("_"):
                    continue
                kind = type(value).__name__
                if isinstance(value, type):
                    kind = "class"
                elif callable(value):
                    kind = "function"
                elif isinstance(value, types.ModuleType):
                    kind = "module"
                symbols.append(f"  {name} ({kind})")
                if len(symbols) >= 50:
                    break
            symbol_list = "\n".join(symbols)
            return (
                f"'{attr_name}' not found in module '{module_name}'.\n\n"
                f"Available symbols:\n{symbol_list}"
            )

    # Try to get source
    try:
        # obj is resolved via importlib/getattr so it's always an inspectable symbol
        source = inspect.getsource(
            cast(Union[types.ModuleType, type, Callable[..., Any]], obj)
        )
    except (TypeError, OSError):
        name = import_path.split(".")[-1]
        return (
            f"Source not available for '{name}' (built-in/C extension). "
            "Only pure-Python symbols have inspectable source."
        )

    lines = source.splitlines()
    if len(lines) > max_lines:
        truncated = "\n".join(lines[:max_lines])
        total = len(lines)
        return (
            f"{truncated}\n"
            f"... truncated (showing {max_lines} of {total} lines). "
            "Use max_lines to see more."
        )

    return source


def main(argv: list[str]) -> int:
    """Run the subcommand named in ``argv`` and write its result to stdout.

    Args:
        argv: Full argument vector, with the script path at ``argv[0]``.

    Returns:
        0 on success, 2 when no known subcommand was given.
    """
    if len(argv) >= 2 and argv[1] == "info":
        json.dump(_info(argv[2:]), sys.stdout)
        return 0
    if len(argv) == 4 and argv[1] == "source":
        if isinstance(sys.stdout, io.TextIOWrapper):
            # Source is often non-ASCII, and the default encoding is the
            # locale's on Windows.
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdout.write(_source(argv[2], int(argv[3])))
        return 0
    print(_USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
