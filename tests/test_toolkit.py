"""Tests for PythonToolkit: skeleton, describe(), prompt_fragments(), and the test action."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest, Finding

from mcp_tools_py.toolkit import PythonToolkit, _result_from_findings

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
            action="format", depth="apply", project_dir=tmp_path, params={}
        )

        with pytest.raises(NotImplementedError):
            PythonToolkit().run(request)
