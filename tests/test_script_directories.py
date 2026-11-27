"""`[tool.mcp-tools-py] script-directories` in resolve_target_directories.

The formatter, ruff, pylint and mypy add the listed folders to the source and
test folders; vulture and bandit validate the key but add nothing.  Every
invalid value is returned as an error string, never raised, because the
toolkit does not catch exceptions from the resolver.
"""

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import get_args

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.code_checker_deptry.runners import DeptryResult
from mcp_tools_py.code_checker_tach.runners import TachResult
from mcp_tools_py.toolkit import PythonToolkit
from mcp_tools_py.utils.project_config import (
    TargetTool,
    resolve_coverage_source,
    resolve_source_directories,
    resolve_target_directories,
    resolve_test_paths,
)

ALL_TOOLS: tuple[TargetTool, ...] = get_args(TargetTool)
SCRIPT_TOOLS: tuple[TargetTool, ...] = ("formatter", "ruff", "pylint", "mypy")
NON_SCRIPT_TOOLS: tuple[TargetTool, ...] = ("vulture", "bandit")
PREFIX = "Error resolving target directories: [tool.mcp-tools-py] script-directories: "
_ABS_PLACEHOLDER = "<abs>/tools"


def _toml_array(values: Sequence[str]) -> str:
    return json.dumps(list(values))


def _scripts(value: object) -> str:
    """A `[tool.mcp-tools-py]` table setting `script-directories` to *value*."""
    return f"[tool.mcp-tools-py]\nscript-directories = {json.dumps(value)}\n"


def _project(
    tmp_path: Path,
    extra_toml: str = "",
    dirs: Sequence[str] = ("src", "tests"),
    where: Sequence[str] = ("src",),
    testpaths: Sequence[str] = ("tests",),
) -> str:
    """Write pyproject.toml, create *dirs* plus `tools/`, return the project dir."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.setuptools.packages.find]\n"
        f"where = {_toml_array(where)}\n\n"
        "[tool.pytest.ini_options]\n"
        f"testpaths = {_toml_array(testpaths)}\n\n" + extra_toml,
        encoding="utf-8",
    )
    for name in (*dirs, "tools"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    return str(tmp_path)


@pytest.mark.parametrize("tool", ALL_TOOLS)
@pytest.mark.parametrize("extra_toml", ["", _scripts([])], ids=["missing", "empty"])
def test_no_scripts_gives_source_and_tests(
    tmp_path: Path, tool: TargetTool, extra_toml: str
) -> None:
    project_dir = _project(tmp_path, extra_toml)

    assert resolve_target_directories(project_dir, None, tool) == ["src", "tests"]


@pytest.mark.parametrize("tool", SCRIPT_TOOLS)
def test_script_tools_add_scripts(tmp_path: Path, tool: TargetTool) -> None:
    project_dir = _project(tmp_path, _scripts(["tools"]))

    assert resolve_target_directories(project_dir, None, tool) == [
        "src",
        "tests",
        "tools",
    ]


@pytest.mark.parametrize("tool", NON_SCRIPT_TOOLS)
def test_other_tools_add_no_scripts(tmp_path: Path, tool: TargetTool) -> None:
    project_dir = _project(tmp_path, _scripts(["tools"]))

    assert resolve_target_directories(project_dir, None, tool) == ["src", "tests"]


def test_entry_is_normalised(tmp_path: Path) -> None:
    project_dir = _project(tmp_path, _scripts(["./tools/"]))

    result = resolve_target_directories(project_dir, None, "mypy")

    assert isinstance(result, list)
    assert result[-1] == "tools"


_INVALID_CASES = [
    pytest.param("tools", "must be a list of folder names, got 'tools'", id="str"),
    pytest.param([1], "must be a list of folder names, got [1]", id="int-entry"),
    *(
        pytest.param(
            [entry],
            f"entry {entry!r} must be a folder inside the project",
            id=f"outside-{entry}",
        )
        for entry in ["", ".", "./", "/tools", "..", "tools/..", "../x"]
    ),
    pytest.param(
        [_ABS_PLACEHOLDER], "must be a folder inside the project", id="absolute"
    ),
    pytest.param(["tool"], "folder 'tool' not found", id="missing"),
    pytest.param(["file.py"], "folder 'file.py' not found", id="file"),
    pytest.param(
        ["tools", "tools/sub"], "folders 'tools' and 'tools/sub' overlap", id="nested"
    ),
    pytest.param(
        ["tools", "./tools"], "folders 'tools' and './tools' overlap", id="duplicate"
    ),
    pytest.param(
        ["src"],
        "folder 'src' overlaps source/test folder 'src'; 'src' already covers it",
        id="source",
    ),
    pytest.param(
        ["src/pkg"],
        "folder 'src/pkg' overlaps source/test folder 'src'; 'src' already covers it",
        id="inside-source",
    ),
]


@pytest.mark.parametrize("tool", ALL_TOOLS)
@pytest.mark.parametrize(("value", "detail"), _INVALID_CASES)
def test_invalid_value_is_error(
    tmp_path: Path, tool: TargetTool, value: object, detail: str
) -> None:
    if isinstance(value, list):
        value = [
            str(tmp_path / "tools") if entry == _ABS_PLACEHOLDER else entry
            for entry in value
        ]
    project_dir = _project(tmp_path, _scripts(value), dirs=("src/pkg", "tests"))
    (tmp_path / "tools" / "sub").mkdir()
    (tmp_path / "file.py").write_text("", encoding="utf-8")

    result = resolve_target_directories(project_dir, None, tool)

    assert isinstance(result, str)
    assert result.startswith(PREFIX)
    assert detail in result


def test_containing_a_test_folder_is_error(tmp_path: Path) -> None:
    project_dir = _project(
        tmp_path,
        _scripts(["tools"]),
        dirs=("src", "tools/tests"),
        testpaths=["tools/tests"],
    )

    result = resolve_target_directories(project_dir, None, "mypy")

    assert result == (
        PREFIX + "folder 'tools' overlaps source/test folder 'tools/tests'"
    )


def test_flat_layout_covers_every_script_folder(tmp_path: Path) -> None:
    project_dir = _project(tmp_path, _scripts(["tools"]), where=["."])

    result = resolve_target_directories(project_dir, None, "mypy")

    assert isinstance(result, str)
    assert result.startswith(PREFIX)
    assert "'.' already covers it" in result


def test_auto_folder_not_on_disk_is_no_overlap(tmp_path: Path) -> None:
    project_dir = _project(
        tmp_path, _scripts(["tools"]), dirs=("src",), testpaths=["tools/tests"]
    )

    assert resolve_target_directories(project_dir, None, "mypy") == ["src", "tools"]


def test_scripts_alone(tmp_path: Path) -> None:
    project_dir = _project(tmp_path, _scripts(["tools"]), dirs=())

    assert resolve_target_directories(project_dir, None, "mypy") == ["tools"]
    vulture = resolve_target_directories(project_dir, None, "vulture")
    assert isinstance(vulture, str)
    assert "No target directories found" in vulture


def test_explicit_list_wins(tmp_path: Path) -> None:
    project_dir = _project(tmp_path, _scripts("tools"))

    assert resolve_target_directories(project_dir, ["x"], "mypy") == ["x"]


def test_invalid_toml_is_error(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[tool\n", encoding="utf-8")

    result = resolve_target_directories(str(tmp_path), None, "mypy")

    assert isinstance(result, str)
    assert "Invalid pyproject.toml" in result


def test_other_resolvers_ignore_the_key(tmp_path: Path) -> None:
    project_dir = _project(tmp_path, _scripts("tools"))

    assert resolve_source_directories(project_dir, None) == ["src"]
    assert resolve_coverage_source(project_dir, None) == ["src"]
    assert resolve_test_paths(project_dir, None)[0] == ["tests"]


_WINDOWS_ONLY = pytest.mark.skipif(os.name != "nt", reason="Windows path semantics")


@_WINDOWS_ONLY
@pytest.mark.parametrize(
    ("value", "detail"),
    [
        pytest.param(
            ["C:tools"], "must be a folder inside the project", id="drive-relative"
        ),
        pytest.param(["\\tools"], "must be a folder inside the project", id="rooted"),
        pytest.param(["SRC"], "overlaps source/test folder 'src'", id="case-source"),
        pytest.param(
            ["tools", "Tools"], "folders 'tools' and 'Tools' overlap", id="case-dup"
        ),
    ],
)
def test_windows_invalid_value_is_error(
    tmp_path: Path, value: list[str], detail: str
) -> None:
    project_dir = _project(tmp_path, _scripts(value))

    result = resolve_target_directories(project_dir, None, "mypy")

    assert isinstance(result, str)
    assert result.startswith(PREFIX)
    assert detail in result


@_WINDOWS_ONLY
def test_windows_backslash_is_normalised(tmp_path: Path) -> None:
    project_dir = _project(tmp_path, _scripts(["tools\\"]))

    assert resolve_target_directories(project_dir, None, "mypy") == [
        "src",
        "tests",
        "tools",
    ]


def test_toolkit_check_full_reports_each_target_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each of the five target-directory checks reports the invalid key."""
    _project(tmp_path, _scripts("tools"), dirs=("src",))
    (tmp_path / "src" / "mod.py").write_text("X = 1\n", encoding="utf-8")
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_lint_imports_check_impl",
        lambda *args, **kwargs: "=== PASSED ===\nContracts: 0 kept, 0 broken",
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_tach_check",
        lambda *args, **kwargs: TachResult(None, 0, [], None),
    )
    monkeypatch.setattr(
        "mcp_tools_py.toolkit_checks.run_deptry_check_impl",
        lambda *args, **kwargs: DeptryResult(return_code=0, messages=[]),
    )
    request = ActionRequest(
        action="check", depth="full", project_dir=tmp_path, params={}
    )

    result = PythonToolkit().run(request)

    assert result.status == "error"
    assert result.summary.count("[tool.mcp-tools-py] script-directories") == 5
