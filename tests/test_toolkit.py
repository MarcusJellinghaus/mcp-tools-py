"""Tests for PythonToolkit: skeleton, describe(), prompt_fragments(), and the test action."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult, Finding

from mcp_tools_py.code_checker_bandit.models import BanditMessage, BanditResult
from mcp_tools_py.toolkit import PythonToolkit, _merge, _result_from_findings
from mcp_tools_py.utils.ruff_parsing import RuffMessage
from mcp_tools_py.utils.tool_context import ToolContext
from tests.conftest import make_command_result

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


def _patch_execute_command_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_execute_command(command: list[str], **kwargs: object) -> object:
        del kwargs
        if command[2] == "--output":  # tach: [binary, "check", "--output", "json"]
            return make_command_result(return_code=0, stdout="")
        return make_command_result(return_code=0, stdout="[]")  # ruff

    monkeypatch.setattr("mcp_tools_py.toolkit.execute_command", fake_execute_command)


def _patch_full_depth_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every `check@full` tool other than mypy/pylint report clean."""
    monkeypatch.setattr(
        "mcp_tools_py.toolkit.run_vulture_check",
        lambda *args, **kwargs: "vulture produced no output.",
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit.run_lint_imports_check_impl",
        lambda *args, **kwargs: "=== PASSED ===\nContracts: 0 kept, 0 broken",
    )
    _patch_execute_command_clean(monkeypatch)
    monkeypatch.setattr(
        "mcp_tools_py.toolkit.parse_ruff_json_output",
        lambda *args, **kwargs: ([], None),
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit.run_bandit_check_impl",
        lambda *args, **kwargs: BanditResult(
            return_code=0, messages=[], errors=[], error=None
        ),
    )


_RUFF_FINDING = RuffMessage(
    code="F401",
    message="'os' imported but unused",
    filename="mod.py",
    line=1,
    column=1,
    end_line=1,
    end_column=9,
    url="",
    fixable=True,
    noqa_row=1,
)
_BANDIT_FINDING = BanditMessage(
    test_id="B102",
    test_name="exec_used",
    issue_severity="MEDIUM",
    issue_confidence="HIGH",
    issue_text="Use of exec detected.",
    filename="mod.py",
    line_number=3,
    more_info="",
    cwe_id=78,
    cwe_link="",
)


class TestRunCheckFull:
    """run() for the `check` action at the `full` depth."""

    def test_clean_project_is_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.findings == []

    def test_vulture_finding_is_degraded_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_vulture_check",
            lambda *args, **kwargs: "mod.py:5: unused function '_x' (60% confidence)",
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].key == "vulture|full"

    def test_tach_violation_is_degraded_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)

        def fake_execute_command(command: list[str], **kwargs: object) -> object:
            del kwargs
            if command[2] == "--output":
                return make_command_result(return_code=1, stdout='{"errors": []}')
            return make_command_result(return_code=0, stdout="[]")

        monkeypatch.setattr(
            "mcp_tools_py.toolkit.execute_command", fake_execute_command
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].key == "tach|full"

    def test_tach_timeout_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)

        def fake_execute_command(command: list[str], **kwargs: object) -> object:
            del kwargs
            if command[2] == "--output":
                return make_command_result(timed_out=True, execution_error="timed out")
            return make_command_result(return_code=0, stdout="[]")

        monkeypatch.setattr(
            "mcp_tools_py.toolkit.execute_command", fake_execute_command
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"

    def test_lint_imports_broken_is_degraded_finding(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_lint_imports_check_impl",
            lambda *args, **kwargs: (
                "=== BROKEN: 1 of 2 contracts failed ===\n"
                "Contracts: 1 kept, 1 broken\n"
                "Broken contracts:\n  - Layered Architecture\n"
            ),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        assert result.findings[0].key == "lint-imports|full"
        assert "BROKEN" in result.findings[0].message

    def test_lint_imports_config_error_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_lint_imports_check_impl",
            lambda *args, **kwargs: (
                "=== ERROR: lint-imports output could not be parsed ==="
            ),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"

    def test_ruff_violation_is_finding_per_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.parse_ruff_json_output",
            lambda *args, **kwargs: ([_RUFF_FINDING], None),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.key == "mod.py|F401|'os' imported but unused"
        assert finding.path == "mod.py"
        assert finding.rule == "F401"

    def test_bandit_finding_is_finding_per_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_bandit_check_impl",
            lambda *args, **kwargs: BanditResult(
                return_code=1, messages=[_BANDIT_FINDING], errors=[], error=None
            ),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.key == "mod.py|B102|Use of exec detected."
        assert finding.path == "mod.py"
        assert finding.rule == "B102"
        assert finding.severity == "MEDIUM"

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
            "mcp_tools_py.toolkit.run_vulture_check",
            lambda *args, **kwargs: calls.append("vulture"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_lint_imports_check_impl",
            lambda *args, **kwargs: calls.append("lint-imports"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.execute_command",
            lambda *args, **kwargs: calls.append("execute_command"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.parse_ruff_json_output",
            lambda *args, **kwargs: calls.append("parse_ruff"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.run_bandit_check_impl",
            lambda *args, **kwargs: calls.append("bandit"),
        )
        monkeypatch.setattr(
            ToolContext,
            "is_tool_available",
            lambda self, tool_name: tool_name != "bandit",
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"
        assert calls == []

    def test_merges_findings_from_two_different_tools(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _MYPY_ERROR_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit.parse_ruff_json_output",
            lambda *args, **kwargs: ([_RUFF_FINDING], None),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 2


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
