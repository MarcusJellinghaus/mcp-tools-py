"""Describe the interpreter running this script, as one line of JSON.

Standard library only — see the package docstring for why.
"""

import importlib.metadata
import importlib.util
import json
import platform
import sys

_USAGE = "usage: probe.py info [MODULE ...]"


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


def main(argv: list[str]) -> int:
    """Run the subcommand named in ``argv`` and write its JSON to stdout.

    Args:
        argv: Full argument vector, with the script path at ``argv[0]``.

    Returns:
        0 on success, 2 when no known subcommand was given.
    """
    if len(argv) < 2 or argv[1] != "info":
        print(_USAGE, file=sys.stderr)
        return 2
    json.dump(_info(argv[2:]), sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
