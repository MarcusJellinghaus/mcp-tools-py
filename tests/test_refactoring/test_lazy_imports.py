"""Unit tests guarding lazy import of heavy refactoring dependencies.

jedi, rope and igittigitt are slow to import and are only needed when a
refactoring tool actually runs. Importing them at MCP-server startup would
push startup time toward the limit Claude Code allows before it gives up on
the server, so these tests pin the imports as lazy.

Each test runs in a fresh subprocess because import state is process-global:
once a module is imported in the test runner it stays in sys.modules.
"""

import subprocess
import sys

# Heavy, slow-importing dependencies that must NOT load at server startup.
HEAVY_MODULES = ("jedi", "rope", "igittigitt", "parso")


def _loaded_heavy_modules(import_statement: str) -> list[str]:
    """Return which heavy modules are loaded after running ``import_statement``.

    Args:
        import_statement: Python import code to execute in a fresh interpreter.

    Returns:
        Sorted names of heavy modules present in ``sys.modules`` afterwards.
    """
    code = (
        f"{import_statement}\n"
        "import sys\n"
        f"heavy = {HEAVY_MODULES!r}\n"
        "loaded = sorted({m for m in heavy for k in sys.modules "
        "if k == m or k.startswith(m + '.')})\n"
        "print(','.join(loaded))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip()
    return out.split(",") if out else []


def test_importing_server_does_not_load_heavy_modules() -> None:
    """Importing the MCP server must not pull in jedi/rope/igittigitt/parso."""
    loaded = _loaded_heavy_modules("import mcp_tools_py.server")
    assert loaded == [], f"server import loaded heavy modules: {loaded}"


def test_importing_refactoring_package_does_not_load_heavy_modules() -> None:
    """Importing the refactoring package (done at startup) stays lazy too."""
    loaded = _loaded_heavy_modules("import mcp_tools_py.refactoring")
    assert loaded == [], f"refactoring import loaded heavy modules: {loaded}"


def test_jedi_loads_only_when_a_jedi_tool_runs() -> None:
    """Confirms the lazy import is wired correctly: calling a jedi tool loads jedi."""
    loaded = _loaded_heavy_modules(
        "from mcp_tools_py.refactoring import jedi_tools\n"
        "jedi_tools.list_symbols(__import__('pathlib').Path('.'), 'missing.py')"
    )
    assert "jedi" in loaded
