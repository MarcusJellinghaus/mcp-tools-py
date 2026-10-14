"""Tests for PythonToolkit's `format` action, at each depth."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.toolkit import PythonToolkit
from mcp_tools_py.utils.tool_context import ToolContext

_RUFF_PYPROJECT = '[tool.ruff.format]\nquote-style = "double"\n'
# Stdlib-only imports: no first-party/third-party classification can differ.
_FORMATTED_SRC = (
    "import os\n"
    "import sys\n"
    "\n\n"
    "def main() -> None:\n"
    "    print(os.sep, sys.argv)\n"
)
_UNFORMATTED_SRC = "import sys\nimport os\n\n\ndef add( a,b ):\n    return a+b\n"


def _write_ruff_project(project_dir: Path, source: str) -> None:
    (project_dir / "pyproject.toml").write_text(_RUFF_PYPROJECT)
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text(source)


class TestRunFormat:
    """run() for the `format` action, at each depth."""

    def test_apply_on_formatted_project_is_ok(self, tmp_path: Path) -> None:
        _write_ruff_project(tmp_path, _FORMATTED_SRC)
        request = ActionRequest(
            action="format", depth="apply", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.raw
        assert result.findings == []

    def test_apply_with_no_formatter_declared_is_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
        request = ActionRequest(
            action="format", depth="apply", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"

    def test_check_on_unformatted_project_is_findings(self, tmp_path: Path) -> None:
        _write_ruff_project(tmp_path, _UNFORMATTED_SRC)
        request = ActionRequest(
            action="format", depth="check", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.path is not None and finding.path.endswith("mod.py")
        assert result.fix_text

    def test_unavailable_tool_is_error_not_findings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_ruff_project(tmp_path, _UNFORMATTED_SRC)
        monkeypatch.setattr(
            ToolContext, "is_tool_available", lambda self, tool_name: False
        )
        request = ActionRequest(
            action="format", depth="check", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"
        assert result.findings == []
