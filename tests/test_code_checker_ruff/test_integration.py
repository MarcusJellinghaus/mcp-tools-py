"""End-to-end ruff runner tests against a real ruff binary and project config."""

from pathlib import Path

import pytest

from mcp_tools_py.code_checker_ruff.runners import (
    run_ruff_check_impl,
    run_ruff_fix_impl,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment

pytestmark = pytest.mark.integration

# F401 (unused import) is fixable, E741 (ambiguous name) is not.
_SOURCE = "import os\nl = 1\n"
_SELECT = ["F401", "E741"]


def _ruff() -> str:
    ruff = PythonEnvironment.resolve().binary("ruff")
    if ruff is None:
        pytest.skip("ruff is not installed next to the interpreter")
    return str(ruff)


def _project(tmp_path: Path, config: str) -> Path:
    """Write a project whose ruff config asks for fixes on every run."""
    (tmp_path / "pyproject.toml").write_text(f"[tool.ruff]\n{config}\n")
    (tmp_path / "src").mkdir()
    source = tmp_path / "src" / "a.py"
    source.write_bytes(_SOURCE.encode())
    return source


@pytest.mark.parametrize("config", ["fix = true", "fix-only = true"])
def test_check_does_not_modify_files(tmp_path: Path, config: str) -> None:
    source = _project(tmp_path, config)

    run_ruff_check_impl(_ruff(), str(tmp_path), ["src"], select=_SELECT)

    assert source.read_bytes().decode() == _SOURCE


@pytest.mark.parametrize("config", ["fix = true", "fix-only = true"])
def test_fix_reports_fixed_and_remaining(tmp_path: Path, config: str) -> None:
    source = _project(tmp_path, config)

    result = run_ruff_fix_impl(_ruff(), str(tmp_path), ["src"], select=_SELECT)

    assert "a.py" in result
    assert "E741" in result
    assert "import os" not in source.read_bytes().decode()
