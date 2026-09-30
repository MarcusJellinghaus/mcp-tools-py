"""Tests for the ruff import-sorting runner."""

import json
import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.formatter import common, ruff_runner
from mcp_tools_py.formatter.ruff_runner import per_file_ignores_notice, run_ruff_imports
from mcp_tools_py.utils.subprocess_runner import CommandResult
from tests.conftest import make_command_result

_RUFF_BINARY = "/tool-env/bin/ruff"
_EXECUTE = "mcp_tools_py.formatter.ruff_runner.execute_command"
_JSON_ARGV = [_RUFF_BINARY, "check", "--select", "I", "--no-fix"]
_JSON_ARGV += ["--output-format", "json", "src"]


@pytest.fixture(autouse=True)
def _fixed_formatter_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the ruff binary, independent of the interpreter running the suite."""
    monkeypatch.setattr(
        ruff_runner, "formatter_binary", MagicMock(return_value=_RUFF_BINARY)
    )


@pytest.fixture(autouse=True)
def _fixed_version_line(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Pin the version banner so no test spawns a `--version` subprocess."""
    mock = MagicMock(return_value="ruff 0.0.0")
    monkeypatch.setattr(ruff_runner, "version_line", mock)
    return mock


def _use_real_ruff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ruff_runner, "formatter_binary", common.formatter_binary)
    monkeypatch.setattr(ruff_runner, "version_line", common.version_line)


def _diagnostic(
    project_dir: Path,
    *parts: str,
    code: str | None = "I001",
    fixable: bool = True,
) -> dict[str, object]:
    """A ruff check JSON diagnostic with ruff's absolute filename."""
    fix = {
        "applicability": "safe",
        "edits": [],
        "message": "Organize imports",
    }
    return {
        "cell": None,
        "code": code,
        "end_location": {"column": 1, "row": 2},
        "filename": os.path.join(str(project_dir), *parts),
        "fix": fix if fixable else None,
        "location": {"column": 1, "row": 1},
        "message": "Import block is un-sorted or un-formatted",
        "noqa_row": 1,
        "url": None,
    }


def _syntax(
    project_dir: Path, code: str | None = "invalid-syntax"
) -> dict[str, object]:
    return _diagnostic(project_dir, "src", "bad.py", code=code, fixable=False)


def _json(*diagnostics: dict[str, object]) -> str:
    return json.dumps(list(diagnostics))


def _argvs(mock_exec: MagicMock) -> list[list[str]]:
    return [list(c[0][0]) for c in mock_exec.call_args_list]


def _write_pyproject(project_dir: Path, body: str) -> None:
    (project_dir / "pyproject.toml").write_text(textwrap.dedent(body), encoding="utf-8")


@patch(_EXECUTE)
def test_check_mode_single_json_invocation(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path), check_only=True)

    assert _argvs(mock_exec) == [_JSON_ARGV]


@pytest.mark.parametrize("check_only", [True, False])
@patch(_EXECUTE)
def test_json_run_carries_no_fix(
    mock_exec: MagicMock, check_only: bool, tmp_path: Path
) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path), check_only=check_only)

    assert "--no-fix" in _argvs(mock_exec)[0]


@patch(_EXECUTE)
def test_write_mode_two_invocations(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    argvs = _argvs(mock_exec)
    assert argvs[0] == _JSON_ARGV
    assert argvs[1] == [_RUFF_BINARY, "check", "--select", "I", "--fix", "src"]
    assert "--no-fix" not in argvs[1]
    assert "--output-format" not in argvs[1]


@patch(_EXECUTE)
def test_ignores_python_executable(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result()

    run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))
    expected = _argvs(mock_exec)
    mock_exec.reset_mock()
    run_ruff_imports("/nonexistent/python", ["src"], str(tmp_path))

    assert _argvs(mock_exec) == expected


@patch(_EXECUTE)
def test_files_changed_from_fixable_precheck(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    stdout = _json(
        _diagnostic(tmp_path, "src", "a.py"), _diagnostic(tmp_path, "src", "a.py")
    )
    mock_exec.side_effect = [
        make_command_result(return_code=1, stdout=stdout),
        make_command_result(stdout="Found 2 errors (2 fixed, 0 remaining).\n"),
    ]

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    assert result.success is True
    assert result.files_changed == ["src/a.py"]


@patch(_EXECUTE)
def test_check_mode_fails_on_unfixable(mock_exec: MagicMock, tmp_path: Path) -> None:
    stdout = _json(_diagnostic(tmp_path, "src", "a.py", fixable=False))
    mock_exec.return_value = make_command_result(return_code=1, stdout=stdout)

    result = run_ruff_imports(
        "/usr/bin/python", ["src"], str(tmp_path), check_only=True
    )

    assert result.files_changed == []
    assert result.success is False


def test_real_ruff_sorts_imports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_real_ruff(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    unsorted = src / "a.py"
    unsorted.write_text("import sys\nimport os\n", encoding="utf-8")

    result = run_ruff_imports("/nonexistent/python", ["src"], str(tmp_path))

    assert unsorted.read_text(encoding="utf-8") == "import os\nimport sys\n"
    assert result.files_changed == ["src/a.py"]
    assert result.success is True


@pytest.mark.parametrize("code", ["invalid-syntax", None])
@patch(_EXECUTE)
def test_syntax_error_still_runs_fix(
    mock_exec: MagicMock, code: str | None, tmp_path: Path
) -> None:
    stdout = _json(_syntax(tmp_path, code), _diagnostic(tmp_path, "src", "a.py"))
    mock_exec.side_effect = [
        make_command_result(return_code=1, stdout=stdout),
        make_command_result(return_code=1, stdout="Found 2 errors (1 fixed).\n"),
    ]

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    assert mock_exec.call_count == 2
    assert result.unparsable_files == ["src/bad.py"]
    assert "src/bad.py" not in result.files_changed
    assert result.success is False


def test_real_ruff_syntax_error_sorts_other_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _use_real_ruff(monkeypatch)
    src = tmp_path / "src"
    src.mkdir()
    good = src / "good.py"
    good.write_text("import sys\nimport os\n", encoding="utf-8")
    (src / "bad.py").write_text("def f(:\n", encoding="utf-8")

    result = run_ruff_imports("/nonexistent/python", ["src"], str(tmp_path))

    assert good.read_text(encoding="utf-8") == "import os\nimport sys\n"
    assert result.unparsable_files == ["src/bad.py"]
    assert result.success is False


@patch(_EXECUTE)
def test_malformed_json_skips_fix(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.return_value = make_command_result(return_code=1, stdout="[not json")

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    assert mock_exec.call_count == 1
    assert result.success is False
    assert "Failed to parse ruff JSON output" in result.output
    assert result.unparsable_files == []


@pytest.mark.parametrize("check_only", [True, False])
@patch(_EXECUTE)
def test_precheck_exit_2(
    mock_exec: MagicMock, check_only: bool, tmp_path: Path
) -> None:
    stderr = "ruff failed\n  Cause: unknown field `bogus` in [tool.ruff]\n"
    mock_exec.return_value = make_command_result(return_code=2, stderr=stderr)

    result = run_ruff_imports(
        "/usr/bin/python", ["src"], str(tmp_path), check_only=check_only
    )

    assert mock_exec.call_count == 1
    assert result.success is False
    assert "unknown field `bogus`" in result.output
    assert result.files_changed == []


@patch(_EXECUTE)
def test_fix_run_exit_2(mock_exec: MagicMock, tmp_path: Path) -> None:
    stdout = _json(_diagnostic(tmp_path, "src", "a.py"), _syntax(tmp_path))
    mock_exec.side_effect = [
        make_command_result(return_code=1, stdout=stdout),
        make_command_result(return_code=2, stderr="ruff failed: fix run broke\n"),
    ]

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    assert result.success is False
    assert "fix run broke" in result.output
    assert result.files_changed == []
    assert result.unparsable_files == []


@patch(_EXECUTE)
def test_check_mode_output_is_rendered(mock_exec: MagicMock, tmp_path: Path) -> None:
    stdout = _json(
        _diagnostic(tmp_path, "src", "a.py"), _diagnostic(tmp_path, "src", "b.py")
    )
    mock_exec.return_value = make_command_result(return_code=1, stdout=stdout)

    result = run_ruff_imports(
        "/usr/bin/python", ["src"], str(tmp_path), check_only=True
    )

    lines = result.output.splitlines()
    assert lines[0] == "ruff 0.0.0"
    assert any("src/a.py" in line and "I001" in line for line in lines)
    assert any("src/b.py" in line and "I001" in line for line in lines)
    assert '"filename"' not in result.output
    assert mock_exec.call_count == 1


@patch(_EXECUTE)
def test_write_mode_output_is_fix_text(mock_exec: MagicMock, tmp_path: Path) -> None:
    mock_exec.side_effect = [
        make_command_result(),
        make_command_result(stdout="All checks passed!\n"),
    ]

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    assert "All checks passed!" in result.output


@patch(_EXECUTE)
def test_missing_binary(
    mock_exec: MagicMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(ruff_runner, "formatter_binary", MagicMock(return_value=None))

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    mock_exec.assert_not_called()
    assert result.success is False
    assert "ruff is not available" in result.output


@pytest.mark.parametrize(
    "fix_result",
    [
        make_command_result(timed_out=True, execution_error="timed out"),
        make_command_result(execution_error="FileNotFoundError: ruff"),
    ],
    ids=["timed_out", "execution_error"],
)
@patch(_EXECUTE)
def test_fix_run_failure_has_no_banner(
    mock_exec: MagicMock,
    _fixed_version_line: MagicMock,
    fix_result: CommandResult,
    tmp_path: Path,
) -> None:
    stdout = _json(_syntax(tmp_path))
    mock_exec.side_effect = [
        make_command_result(return_code=1, stdout=stdout),
        fix_result,
    ]

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    _fixed_version_line.assert_not_called()
    assert result.success is False
    assert result.unparsable_files == []
    assert result.files_changed == []
    assert "ruff 0.0.0" not in result.output
    assert result.output.startswith("ruff check ")


@patch(_EXECUTE)
def test_per_file_ignores_notice_in_output(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    _write_pyproject(
        tmp_path,
        """\
        [tool.ruff.lint.per-file-ignores]
        "tests/**" = ["I001"]
        """,
    )
    mock_exec.return_value = make_command_result()

    result = run_ruff_imports("/usr/bin/python", ["src", "tests"], str(tmp_path))

    assert "tests/**" in result.output
    assert "under tests;" in result.output


@pytest.mark.parametrize(
    "body",
    [
        "[project]\nname = 'x'\n",
        '[tool.ruff.lint.per-file-ignores]\n"src/**" = ["E501"]\n',
        '[tool.ruff.lint.per-file-ignores]\n"src/**" = ["INP001"]\n',
        '[tool.ruff.lint.per-file-ignores]\n"*.py" = ["I001"]\n',
        '[tool.ruff.lint.per-file-ignores]\n"**/test_*.py" = ["I"]\n',
        "invalid toml {{{{",
    ],
    ids=["no_ignores", "non_i", "inp001", "star_py", "globstar", "malformed"],
)
def test_no_notice(body: str, tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(body, encoding="utf-8")

    assert per_file_ignores_notice(str(tmp_path), ["src", "tests"]) == ""


@patch(_EXECUTE)
def test_malformed_pyproject_step_still_runs(
    mock_exec: MagicMock, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text("invalid toml {{{{", encoding="utf-8")
    mock_exec.return_value = make_command_result()

    result = run_ruff_imports("/usr/bin/python", ["src"], str(tmp_path))

    assert result.success is True


@pytest.mark.parametrize(
    ("key", "target", "expected"),
    [
        ("tests2/**", "tests", False),
        ("src/sub/**", "src", True),
        ("src/**", "src/sub", True),
        ("src\\**", "src", True),
    ],
)
def test_notice_overlap_by_component(
    key: str, target: str, expected: bool, tmp_path: Path
) -> None:
    _write_pyproject(
        tmp_path,
        f"""\
        [tool.ruff.lint.per-file-ignores]
        {json.dumps(key)} = ["I"]
        """,
    )

    assert bool(per_file_ignores_notice(str(tmp_path), [target])) is expected


@pytest.mark.parametrize("codes", ['["ALL"]', '["I"]', '["E501", "I001"]'])
def test_notice_legacy_table_and_codes(codes: str, tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path,
        f"""\
        [tool.ruff.per-file-ignores]
        "src/**" = {codes}
        """,
    )

    assert per_file_ignores_notice(str(tmp_path), ["src"]) != ""
