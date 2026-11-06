"""Integration tests for mypy in the MCP server."""

import sys
import tempfile
from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.code_checker_mypy import get_mypy_prompt, run_mypy_check
from mcp_tools_py.code_checker_mypy.reporting import MYPY_FAILURE_PREFIX
from mcp_tools_py.server import ToolServer
from mcp_tools_py.toolkit import PythonToolkit

_EARLY_STOP = "mypy exited with code 2, more errors may appear after these are fixed"

_CRASH_PLUGIN = """\
from mypy.plugin import Plugin


class P(Plugin):
    def get_function_hook(self, fullname):
        if fullname.endswith(".boom"):
            raise RuntimeError("boom")
        return None


def plugin(version):
    return P
"""


def _write_files(project_dir: Path, files: dict[str, str]) -> None:
    """Write `files`, a mapping of relative path to content, under `project_dir`."""
    for relative_path, content in files.items():
        path = project_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def _write_plugin_crash_project(project_dir: Path) -> None:
    """Write a project whose plugin crashes after `reveal_type` was reported."""
    _write_files(
        project_dir,
        {
            "pyproject.toml": '[tool.mypy]\nplugins = ["crash_plugin.py"]\n',
            "crash_plugin.py": _CRASH_PLUGIN,
            "src/a_first.py": "reveal_type(1)\n",
            "src/z_last.py": (
                "from a_first import *\ndef boom() -> None: ...\nboom()\n"
            ),
        },
    )


def test_mypy_tool_registration() -> None:
    """Test that mypy tool is registered in the server."""
    server = ToolServer(project_dir=Path("."), python_executable=None)

    # Check that the server has an mcp instance
    assert hasattr(server, "mcp")
    assert server.mcp is not None

    # The server delegates tool registration to CheckerTools
    # Verify the mcp instance exists (tools are registered via CheckerTools)
    assert hasattr(server, "mcp")


def test_mypy_with_test_files() -> None:
    """Test running mypy on test files with known type issues."""
    # Create a temporary directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_types.py"
        test_file.write_text("""
def add(a: int, b: int) -> int:
    return a + b

# This should cause a type error
result = add("string", 42)

# Another type error
def greet(name: str) -> str:
    return f"Hello, {name}"

greet(123)  # Type error: expected str, got int
""")

        result = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )

        # Should find type errors
        assert result.return_code == 1
        assert len(result.messages) > 0

        # Check for arg-type errors
        error_codes = {msg.code for msg in result.messages if msg.code}
        assert "arg-type" in error_codes


def test_mypy_with_clean_code() -> None:
    """Test running mypy on clean code with no type errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        clean_file = Path(tmpdir) / "clean_code.py"
        clean_file.write_text("""
from typing import List, Optional

def add(a: int, b: int) -> int:
    \"\"\"Add two integers.\"\"\"
    return a + b

def process_list(items: List[str]) -> Optional[str]:
    \"\"\"Process a list of strings.\"\"\"
    if items:
        return items[0]
    return None

# Correct usage
result: int = add(1, 2)
first_item: Optional[str] = process_list(["hello", "world"])
""")

        result = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )

        # Should find no errors
        assert result.return_code == 0
        assert len(result.messages) == 0


def test_mypy_handles_import_errors() -> None:
    """Test that mypy handles import errors gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import_error_file = Path(tmpdir) / "import_error.py"
        import_error_file.write_text("""
import non_existent_module  # This module doesn't exist

def process_data() -> None:
    non_existent_module.do_something()
""")

        result = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )

        # Should find import error
        assert result.return_code == 1
        assert len(result.messages) > 0

        # Check for import error
        has_import_error = any(
            "import" in (msg.code or "") or "import" in msg.message.lower()
            for msg in result.messages
        )
        assert has_import_error


def test_mypy_with_multiple_files() -> None:
    """Test running mypy on multiple files in a directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create multiple Python files
        file1 = Path(tmpdir) / "module1.py"
        file1.write_text("""
def func1(x: int) -> str:
    return str(x)
""")

        file2 = Path(tmpdir) / "module2.py"
        file2.write_text("""
from module1 import func1

# Type error: func1 returns str, not int
result: int = func1(42)
""")

        result = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )

        # Should find type error in module2
        assert result.return_code == 1
        assert any("module2.py" in msg.file for msg in result.messages)


def test_mypy_respects_disable_codes() -> None:
    """Test that mypy respects disabled error codes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_disable.py"
        test_file.write_text("""
import non_existent  # import error

def func(x: int) -> int:
    return x + "string"  # operator error
""")

        # Run without disabling
        result1 = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )
        assert result1.return_code == 1
        original_errors = len(result1.messages)

        # Run with import errors disabled
        result2 = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
            disable_error_codes=["import"],
        )

        # Should have fewer errors
        assert len(result2.messages) < original_errors
        # Should not have import errors
        assert not any("import" in (msg.code or "") for msg in result2.messages)


UNANNOTATED_SOURCE = """
def func(x, y):
    return x + y
"""


def test_mypy_strictness_comes_from_project_config() -> None:
    """The checked project's [tool.mypy] decides strictness, not the server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "unannotated.py").write_text(UNANNOTATED_SOURCE)
        (Path(tmpdir) / "pyproject.toml").write_text("[tool.mypy]\nstrict = true\n")

        configured = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "unannotated.py").write_text(UNANNOTATED_SOURCE)

        unconfigured = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            target_directories=["."],
        )

    assert "no-untyped-def" in {msg.code for msg in configured.messages if msg.code}
    assert unconfigured.messages == []
    assert unconfigured.return_code == 0


def test_mypy_found_twice_reports_early_stop(tmp_path: Path) -> None:
    """A file found under two module names stops mypy, and the report says so."""
    _write_files(
        tmp_path,
        {
            "pyproject.toml": '[tool.mypy]\nmypy_path = "src"\n',
            "src/pkg/__init__.py": "",
            "src/pkg/mod.py": "",
            "src/pkg/cli.py": "import src.pkg\nimport pkg.mod\n",
            "tests/__init__.py": "",
            "tests/test_cli.py": "import src.pkg.cli\nimport pkg.cli\n",
        },
    )
    project_dir = str(tmp_path)
    targets = ["src", "tests"]

    result = run_mypy_check(
        project_dir=project_dir,
        python_executable=sys.executable,
        target_directories=targets,
    )

    assert result.return_code == 2
    assert result.error is None
    assert len(result.messages) == 1
    message = result.messages[0]
    assert message.line == -1
    assert message.code is None
    assert message.hint

    prompt = get_mypy_prompt(project_dir, sys.executable, target_directories=targets)
    assert prompt is not None
    assert prompt.startswith(_EARLY_STOP)
    assert "Source file found twice" in prompt
    assert "Common resolutions include" in prompt
    assert ":-1:-1" not in prompt
    assert "To fix these issues:" not in prompt

    counts_only = get_mypy_prompt(
        project_dir, sys.executable, target_directories=targets, max_issues=0
    )
    assert counts_only is not None
    assert "Source file found twice" in counts_only


def test_mypy_crash_at_import_is_an_error(tmp_path: Path) -> None:
    """A crash while mypy starts exits 1 with no messages, which is a failure."""
    _write_files(
        tmp_path,
        {
            "typing_extensions.py": "raise RuntimeError('shadowed')\n",
            "mod.py": "x: int = 1\n",
        },
    )
    project_dir = str(tmp_path)
    targets = ["mod.py"]

    result = run_mypy_check(
        project_dir=project_dir,
        python_executable=sys.executable,
        target_directories=targets,
    )

    assert result.return_code == 1
    assert result.messages == []
    assert result.error is not None
    assert result.error.startswith("mypy exited with code 1:")
    assert "RuntimeError: shadowed" in result.error

    prompt = get_mypy_prompt(project_dir, sys.executable, target_directories=targets)
    assert prompt is not None
    assert prompt.startswith(MYPY_FAILURE_PREFIX)


def test_mypy_plugin_crash_after_reveal_type_is_an_error(tmp_path: Path) -> None:
    """A note before an internal error must not hide the crash."""
    _write_plugin_crash_project(tmp_path)

    result = run_mypy_check(
        project_dir=str(tmp_path),
        python_executable=sys.executable,
        target_directories=["src"],
    )

    assert result.return_code == 2
    assert result.messages == []
    assert result.error is not None
    assert result.error.startswith("mypy exited with code 2:")
    assert "INTERNAL ERROR" in result.error


def test_toolkit_plugin_crash_after_reveal_type_is_not_ok(tmp_path: Path) -> None:
    """The toolkit `check` action reports the same crash as an error."""
    _write_plugin_crash_project(tmp_path)

    request = ActionRequest(
        action="check", depth="quick", project_dir=tmp_path, params={}
    )
    action = PythonToolkit().run(request)

    assert action.status == "error"
    assert "\n" not in action.summary
    assert "INTERNAL ERROR" in action.raw
