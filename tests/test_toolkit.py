"""Tests for PythonToolkit: skeleton, describe(), prompt_fragments(), and the test action."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult, Finding

from mcp_tools_py.toolkit import PythonToolkit, _merge, _result_from_findings
from mcp_tools_py.utils.tool_context import ToolContext

_EXPECTED_ACTIONS = {
    "format": ["apply", "check"],
    "check": ["quick", "standard", "full"],
    "test": ["quick", "standard", "full"],
}
_EXPECTED_PERMISSIONS = {
    "format": {
        "apply": ["mcp__mcp-tools-py__run_format_code"],
        "check": ["mcp__mcp-tools-py__run_format_code"],
    },
    "check": {
        "quick": ["mcp__mcp-tools-py__run_mypy_check"],
        "standard": [
            "mcp__mcp-tools-py__run_mypy_check",
            "mcp__mcp-tools-py__run_pylint_check",
        ],
        "full": [
            "mcp__mcp-tools-py__run_mypy_check",
            "mcp__mcp-tools-py__run_pylint_check",
            "mcp__mcp-tools-py__run_vulture_check",
            "mcp__mcp-tools-py__run_lint_imports_check",
            "mcp__mcp-tools-py__run_tach_check",
            "mcp__mcp-tools-py__run_ruff_check",
            "mcp__mcp-tools-py__run_bandit_check",
        ],
    },
    "test": {
        "quick": ["mcp__mcp-tools-py__run_pytest_check"],
        "standard": ["mcp__mcp-tools-py__run_pytest_check"],
        "full": ["mcp__mcp-tools-py__run_pytest_check"],
    },
}


def _write_passing_project(project_dir: Path) -> None:
    (project_dir / "tests").mkdir(parents=True)
    (project_dir / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n"
    )


def _write_failing_project(project_dir: Path) -> None:
    (project_dir / "tests").mkdir(parents=True)
    (project_dir / "tests" / "test_fail.py").write_text(
        "def test_fails():\n    assert 1 == 2\n"
    )


def _write_empty_project(project_dir: Path) -> None:
    (project_dir / "tests").mkdir(parents=True)
    (project_dir / "tests" / "__init__.py").write_text("")


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


def _write_coverage_project(project_dir: Path) -> None:
    (project_dir / "src" / "pkg").mkdir(parents=True)
    (project_dir / "src" / "pkg" / "__init__.py").write_text("")
    (project_dir / "src" / "pkg" / "mod.py").write_text(
        "def covered(x):\n    return x + 1\n"
    )
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_mod.py").write_text(
        "from pkg.mod import covered\n\n\ndef test_covered():\n    assert covered(1) == 2\n"
    )
    (project_dir / "pyproject.toml").write_text(
        "[tool.setuptools.packages.find]\n"
        'where = ["src"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
        'pythonpath = ["src"]\n'
    )


_CLEAN_SRC = '''"""Module docstring."""


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
_MYPY_ERROR_SRC = '''"""Module docstring."""


def add(a: int, b: int) -> str:
    """Add two numbers."""
    return a + b
'''
_PYLINT_ISSUE_SRC = '''"""Module docstring."""

import os


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b
'''
_BOTH_ISSUES_SRC = '''"""Module docstring."""

import os


def add(a: int, b: int) -> str:
    """Add two numbers."""
    return a + b
'''


def _write_check_project(project_dir: Path, source: str) -> None:
    src_dir = project_dir / "src"
    src_dir.mkdir()
    (src_dir / "mod.py").write_text(source)


class TestDescribe:
    """describe() must return the final, complete ToolkitInfo."""

    def test_returns_exact_toolkit_info(self) -> None:
        info = PythonToolkit().describe({})

        assert info.actions == _EXPECTED_ACTIONS
        assert info.params_schema == {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        }
        assert info.llm_permissions == _EXPECTED_PERMISSIONS


class TestPromptFragments:
    """prompt_fragments() must contribute the three Python-specific slots."""

    def test_contains_required_keys(self) -> None:
        fragments = PythonToolkit().prompt_fragments()

        assert set(fragments) == {
            "language_context",
            "check_instructions",
            "fix.check",
        }
        assert fragments["language_context"]
        assert fragments["check_instructions"]

    def test_fix_check_has_no_mypy_output_placeholder(self) -> None:
        fragments = PythonToolkit().prompt_fragments()

        assert "[mypy_output]" not in fragments["fix.check"]
        assert "Mypy output" not in fragments["fix.check"]
        assert "mypy type errors" in fragments["fix.check"]


class TestResultFromFindings:
    """Unit tests for the one generic helper this step needs."""

    def test_error_wins(self) -> None:
        result = _result_from_findings(
            error="boom", findings=[], ok_summary="ok", findings_summary="bad"
        )

        assert result.status == "error"
        assert result.summary == "boom"
        assert result.findings == []

    def test_findings_build_fix_text(self) -> None:
        finding = Finding(key="a", message="broke", path="a.py", rule="E1")

        result = _result_from_findings(
            error=None,
            findings=[finding],
            ok_summary="ok",
            findings_summary="1 issue",
        )

        assert result.status == "findings"
        assert result.summary == "1 issue"
        assert result.findings == [finding]
        assert "a.py" in result.fix_text
        assert "broke" in result.fix_text

    def test_no_error_no_findings_is_ok(self) -> None:
        result = _result_from_findings(
            error=None, findings=[], ok_summary="all good", findings_summary="bad"
        )

        assert result.status == "ok"
        assert result.summary == "all good"
        assert result.findings == []


class TestRunTest:
    """run() for the `test` action, at each depth."""

    def test_quick_passing_project_is_ok(self, tmp_path: Path) -> None:
        _write_passing_project(tmp_path)
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.findings == []

    def test_standard_failing_project_is_findings(self, tmp_path: Path) -> None:
        _write_failing_project(tmp_path)
        request = ActionRequest(
            action="test", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.key.endswith("test_fail.py::test_fails")
        assert finding.path is not None and finding.path.endswith("test_fail.py")
        assert result.fix_text

    def test_no_tests_collected_is_skipped(self, tmp_path: Path) -> None:
        _write_empty_project(tmp_path)
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "skipped"
        assert result.findings == []

    def test_full_depth_sets_raw_coverage_digest(self, tmp_path: Path) -> None:
        pytest.importorskip("pytest_cov")
        _write_coverage_project(tmp_path)
        request = ActionRequest(
            action="test", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.raw
        assert "stmts" in result.raw

    def test_unknown_action_raises(self, tmp_path: Path) -> None:
        request = ActionRequest(
            action="bogus", depth="quick", project_dir=tmp_path, params={}
        )

        with pytest.raises(NotImplementedError):
            PythonToolkit().run(request)


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


class TestMerge:
    """Unit tests for `_merge`'s worst-status-wins semantics."""

    def test_ok_and_ok_is_ok(self) -> None:
        merged = _merge(
            [
                ActionResult(status="ok", summary="a"),
                ActionResult(status="ok", summary="b"),
            ]
        )

        assert merged.status == "ok"
        assert merged.findings == []

    def test_ok_and_findings_is_findings_with_concatenated_findings(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        merged = _merge(
            [
                ActionResult(status="ok", summary="a"),
                ActionResult(status="findings", summary="b", findings=[finding]),
            ]
        )

        assert merged.status == "findings"
        assert merged.findings == [finding]
        assert merged.fix_text

    def test_findings_and_error_is_error(self) -> None:
        finding = Finding(key="f1", message="broke", path="a.py")
        merged = _merge(
            [
                ActionResult(status="findings", summary="a", findings=[finding]),
                ActionResult(status="error", summary="boom"),
            ]
        )

        assert merged.status == "error"

    def test_skipped_with_nothing_worse_stays_at_the_worse_of_the_two(self) -> None:
        merged_ok = _merge(
            [
                ActionResult(status="skipped", summary="a"),
                ActionResult(status="ok", summary="b"),
            ]
        )
        finding = Finding(key="f1", message="broke", path="a.py")
        merged_findings = _merge(
            [
                ActionResult(status="skipped", summary="a"),
                ActionResult(status="findings", summary="b", findings=[finding]),
            ]
        )

        assert merged_ok.status == "ok"
        assert merged_findings.status == "findings"


class TestRunCheck:
    """run() for the `check` action, at each depth."""

    def test_quick_clean_project_is_ok(self, tmp_path: Path) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        request = ActionRequest(
            action="check", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.findings == []

    def test_quick_type_error_is_findings(self, tmp_path: Path) -> None:
        _write_check_project(tmp_path, _MYPY_ERROR_SRC)
        request = ActionRequest(
            action="check", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.key.count("|") == 2
        assert finding.path is not None and finding.path.endswith("mod.py")

    def test_standard_merges_mypy_clean_pylint_issue(self, tmp_path: Path) -> None:
        _write_check_project(tmp_path, _PYLINT_ISSUE_SRC)
        request = ActionRequest(
            action="check", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1

    def test_standard_both_tools_failing_concatenates_findings(
        self, tmp_path: Path
    ) -> None:
        _write_check_project(tmp_path, _BOTH_ISSUES_SRC)
        request = ActionRequest(
            action="check", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 2

    def test_unavailable_tool_short_circuits_before_running_anything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        calls: list[str] = []
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_mypy_check",
            lambda *args, **kwargs: calls.append("mypy"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.get_pylint_results",
            lambda *args, **kwargs: calls.append("pylint"),
        )
        monkeypatch.setattr(
            ToolContext,
            "is_tool_available",
            lambda self, tool_name: tool_name != "pylint",
        )
        request = ActionRequest(
            action="check", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"
        assert calls == []


class TestActionResultValidation:
    """ActionResult's own status-validation rules, exercised directly."""

    def test_unknown_status_raises(self) -> None:
        with pytest.raises(ValueError):
            ActionResult(status="bogus", summary="x")  # type: ignore[arg-type]

    def test_findings_status_with_no_findings_raises(self) -> None:
        with pytest.raises(ValueError):
            ActionResult(status="findings", summary="x", findings=[])

    def test_ok_status_with_findings_raises(self) -> None:
        finding = Finding(key="f1", message="broke")
        with pytest.raises(ValueError):
            ActionResult(status="ok", summary="x", findings=[finding])

    def test_skipped_status_with_findings_raises(self) -> None:
        finding = Finding(key="f1", message="broke")
        with pytest.raises(ValueError):
            ActionResult(status="skipped", summary="x", findings=[finding])
