"""Tests for PythonToolkit's `check` action, at each depth."""

from pathlib import Path

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.code_checker_bandit.models import BanditMessage, BanditResult
from mcp_tools_py.code_checker_deptry.runners import DeptryMessage, DeptryResult
from mcp_tools_py.toolkit import PythonToolkit
from mcp_tools_py.utils.ruff_parsing import RuffMessage
from mcp_tools_py.utils.tool_context import ToolContext
from tests.conftest import make_command_result

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
            "mcp_tools_py.toolkit_checks.run_mypy_check",
            lambda *args, **kwargs: calls.append("mypy"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.get_pylint_results",
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

    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.execute_command", fake_execute_command
    )


def _patch_full_depth_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every `check@full` tool other than mypy/pylint report clean."""
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_vulture_check",
        lambda *args, **kwargs: "vulture produced no output.",
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_lint_imports_check_impl",
        lambda *args, **kwargs: "=== PASSED ===\nContracts: 0 kept, 0 broken",
    )
    _patch_execute_command_clean(monkeypatch)
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.parse_ruff_json_output",
        lambda *args, **kwargs: ([], None),
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_bandit_check_impl",
        lambda *args, **kwargs: BanditResult(
            return_code=0, messages=[], errors=[], error=None
        ),
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
        lambda *args, **kwargs: DeptryResult(return_code=0, messages=[]),
    )


def _deptry_message(module: str) -> DeptryMessage:
    return DeptryMessage(
        code="DEP002",
        message=f"'{module}' defined as a dependency but not used in the codebase",
        module=module,
        file="pyproject.toml",
        line=None,
        column=None,
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
            "mcp_tools_py.toolkit_checks.run_vulture_check",
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
            "mcp_tools_py.toolkit_checks.execute_command", fake_execute_command
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
            "mcp_tools_py.toolkit_checks.execute_command", fake_execute_command
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
            "mcp_tools_py.toolkit_checks.run_lint_imports_check_impl",
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
            "mcp_tools_py.toolkit_checks.run_lint_imports_check_impl",
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
            "mcp_tools_py.toolkit_checks.parse_ruff_json_output",
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
            "mcp_tools_py.toolkit_checks.run_bandit_check_impl",
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

    def test_deptry_findings_have_one_key_per_module(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
            lambda *args, **kwargs: DeptryResult(
                return_code=1,
                messages=[_deptry_message("requests"), _deptry_message("click")],
            ),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert [finding.key for finding in result.findings] == [
            "pyproject.toml|DEP002|requests",
            "pyproject.toml|DEP002|click",
        ]
        assert result.findings[0].path == "pyproject.toml"
        assert result.findings[0].rule == "DEP002"

    def test_deptry_error_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        _patch_full_depth_clean(monkeypatch)
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
            lambda *args, **kwargs: DeptryResult(
                return_code=2, messages=[], error="deptry exited with code 2"
            ),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"

    def test_deptry_targets_exclude_tests(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        (tmp_path / "tests").mkdir()
        _patch_full_depth_clean(monkeypatch)
        captured: list[list[str]] = []

        def fake_deptry(
            python_executable: str,
            project_dir: str,
            target_directories: list[str],
            **kwargs: object,
        ) -> DeptryResult:
            del python_executable, project_dir, kwargs
            captured.append(target_directories)
            return DeptryResult(return_code=0, messages=[])

        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_deptry_check_impl", fake_deptry
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        PythonToolkit().run(request)

        assert captured == [["src"]]

    def test_deptry_unavailable_is_error_and_runs_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        calls: list[str] = []
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_mypy_check",
            lambda *args, **kwargs: calls.append("mypy"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
            lambda *args, **kwargs: calls.append("deptry"),
        )
        monkeypatch.setattr(
            ToolContext,
            "is_tool_available",
            lambda self, tool_name: tool_name != "deptry",
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"
        assert calls == []

    def test_deptry_not_run_at_standard_depth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        calls: list[str] = []
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
            lambda *args, **kwargs: calls.append("deptry"),
        )
        request = ActionRequest(
            action="check", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert calls == []

    def test_unavailable_tool_short_circuits_before_running_anything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_check_project(tmp_path, _CLEAN_SRC)
        calls: list[str] = []
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_mypy_check",
            lambda *args, **kwargs: calls.append("mypy"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.get_pylint_results",
            lambda *args, **kwargs: calls.append("pylint"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_vulture_check",
            lambda *args, **kwargs: calls.append("vulture"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_lint_imports_check_impl",
            lambda *args, **kwargs: calls.append("lint-imports"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.execute_command",
            lambda *args, **kwargs: calls.append("execute_command"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.parse_ruff_json_output",
            lambda *args, **kwargs: calls.append("parse_ruff"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_bandit_check_impl",
            lambda *args, **kwargs: calls.append("bandit"),
        )
        monkeypatch.setattr(
            "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
            lambda *args, **kwargs: calls.append("deptry"),
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
            "mcp_tools_py.toolkit_checks.parse_ruff_json_output",
            lambda *args, **kwargs: ([_RUFF_FINDING], None),
        )
        request = ActionRequest(
            action="check", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 2
