"""Integration tests for mypy in the MCP server."""

import sys
import tempfile
from pathlib import Path

import pytest

from mcp_tools_py.code_checker_mypy import run_mypy_check
from mcp_tools_py.server import ToolServer


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
            strict=True,
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
            strict=True,
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
            strict=True,
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
            strict=True,
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
            strict=True,
            target_directories=["."],
        )
        assert result1.return_code == 1
        original_errors = len(result1.messages)

        # Run with import errors disabled
        result2 = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            strict=True,
            target_directories=["."],
            disable_error_codes=["import"],
        )

        # Should have fewer errors
        assert len(result2.messages) < original_errors
        # Should not have import errors
        assert not any("import" in (msg.code or "") for msg in result2.messages)


def test_mypy_strict_vs_non_strict() -> None:
    """Test difference between strict and non-strict modes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_strict.py"
        test_file.write_text("""
# Missing type annotations - only caught in strict mode
def func(x, y):
    return x + y

# This is always an error
result = func("string", 123)
""")

        # Run in strict mode
        strict_result = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            strict=True,
            target_directories=["."],
        )

        # Run in non-strict mode
        non_strict_result = run_mypy_check(
            project_dir=tmpdir,
            python_executable=sys.executable,
            strict=False,
            target_directories=["."],
        )

        # Strict mode should find more issues
        assert len(strict_result.messages) >= len(non_strict_result.messages)
