"""Describe the interpreter running this script, and resolve names in it.

Standard library only — see the package docstring for why.
"""

import contextlib
import importlib.machinery
import importlib.metadata
import importlib.util
import inspect
import io
import json
import os.path
import platform
import site
import sys
import sysconfig
import types
from typing import Any, Callable, Union, cast

_USAGE = (
    "usage: probe.py info [MODULE ...] | probe.py source IMPORT_PATH MAX_LINES"
    " | probe.py locate NAME [NAME ...]"
)


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


def _parents(spec: importlib.machinery.ModuleSpec) -> list[str]:
    """Report the directories a found name is importable from.

    Args:
        spec: The spec ``find_spec`` returned for the name.

    Returns:
        One directory per location of a package or namespace portion, the
        containing directory of a plain module, or nothing for a name with no
        file behind it (built-in, frozen or extension-less).
    """
    locations = list(spec.submodule_search_locations or [])
    if locations:
        return [os.path.dirname(location) for location in locations]
    if spec.origin and os.path.isfile(spec.origin):
        return [os.path.dirname(spec.origin)]
    return []


def _normalized(path: str) -> str:
    """Spell `path` so that two spellings of one directory compare equal.

    Args:
        path: A filesystem path.

    Returns:
        The path with redundant separators and, on Windows, letter case
        normalized away.
    """
    return os.path.normcase(os.path.normpath(path))


def _site_dirs() -> list[str]:
    """Collect this interpreter's site and install directories.

    Returns:
        Every install directory reported by ``sysconfig`` or ``site``,
        de-duplicated in that order.  Either source can be absent or unhappy in
        an unusual environment, so each is asked separately and a failure just
        contributes nothing.  The environment's own root is dropped:
        ``site.getsitepackages()`` includes it on Windows, and treating it as an
        install directory would classify every source tree under a venv created
        at the project root as a ``site-packages``.
    """
    candidates: list[str] = []
    try:
        paths = sysconfig.get_paths()
        candidates += [paths.get("purelib", ""), paths.get("platlib", "")]
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        candidates += list(site.getsitepackages())
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    roots = {_normalized(sys.prefix), _normalized(sys.base_prefix)}
    result: list[str] = []
    for candidate in candidates:
        if not candidate or candidate in result:
            continue
        if _normalized(candidate) in roots:
            continue
        result.append(candidate)
    return result


def _locate(names: list[str]) -> dict[str, object]:
    """Where each name in `names` lives, and this interpreter's site directories.

    The site directories are reported so the caller can tell a source tree
    from a `site-packages`, which must never go on PYTHONPATH.  Directories
    stay attributed to the name they were found for, so a caller checking
    several packages can say which one of them a verdict is about.

    Args:
        names: Package or module names to find.

    Returns:
        ``packages``, the directories each name is importable from, keyed by
        name and omitting a name that did not resolve; and ``site_dirs``,
        which describes the interpreter rather than the request.
    """
    packages: dict[str, list[str]] = {}
    for name in names:
        try:
            spec = importlib.util.find_spec(name)
        except Exception:  # pylint: disable=broad-exception-caught
            # As in _importable: a malformed name, or a parent package that
            # raises on import, leaves nothing to locate.
            continue
        if spec is None:
            continue
        found = [parent for parent in _parents(spec) if parent]
        if found:
            packages[name] = found
    return {"packages": packages, "site_dirs": _site_dirs()}


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

    Resolution imports the target module, which runs its top-level code and
    may print.  Such output would land on the stdout the caller reads the
    source from, so stdout is redirected to a throwaway buffer for the
    duration and restored before anything is written.

    Args:
        import_path: Dotted import path (e.g. "os.path.join" or "json.JSONEncoder").
        max_lines: Maximum number of source lines to return.

    Returns:
        Source code string, or an error message if resolution fails.
    """
    with contextlib.redirect_stdout(io.StringIO()):
        return _resolve_source(import_path, max_lines)


def _resolve_source(import_path: str, max_lines: int) -> str:
    """Import the target module and return the requested symbol's source.

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
    if len(argv) >= 3 and argv[1] == "locate":
        json.dump(_locate(argv[2:]), sys.stdout)
        return 0
    print(_USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
