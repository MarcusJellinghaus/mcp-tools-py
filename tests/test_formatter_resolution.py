"""Tests for formatter.runner.resolve_steps."""

from pathlib import Path

import pytest

from mcp_tools_py.formatter.runner import resolve_steps

_BLACK = ["isort", "black"]
_RUFF = ["ruff_imports", "ruff_format"]


def _write_pyproject(root: Path, content: str) -> Path:
    path = root / "pyproject.toml"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('[tool.mcp-tools-py]\nformatter = "black"\n', _BLACK),
        ('[tool.mcp-tools-py]\nformatter = "ruff"\n', _RUFF),
        ("[tool.black]\nline-length = 88\n", _BLACK),
        ("[tool.ruff.format]\nquote-style = 'double'\n", _RUFF),
        ("[tool.black]\n\n[tool.ruff.format]\n", None),
        ("[tool.isort]\nprofile = 'black'\n", None),
    ],
    ids=["key-black", "key-ruff", "black-only", "ruff-only", "both", "neither"],
)
def test_resolution(tmp_path: Path, content: str, expected: list[str] | None) -> None:
    _write_pyproject(tmp_path, content)

    if expected is None:
        with pytest.raises(ValueError):
            resolve_steps(tmp_path)
    else:
        assert resolve_steps(tmp_path) == expected


@pytest.mark.parametrize(
    "content",
    ["[tool.black]\n\n[tool.ruff.format]\n", "[project]\nname = 'x'\n"],
    ids=["both", "neither"],
)
def test_error_names_key_and_file(tmp_path: Path, content: str) -> None:
    path = _write_pyproject(tmp_path, content)

    with pytest.raises(ValueError) as excinfo:
        resolve_steps(tmp_path)

    message = str(excinfo.value)
    assert "formatter" in message
    assert "mcp-tools-py" in message
    assert str(path) in message


def test_explicit_key_wins_over_tables(tmp_path: Path) -> None:
    _write_pyproject(
        tmp_path, '[tool.mcp-tools-py]\nformatter = "black"\n\n[tool.ruff.format]\n'
    )

    assert resolve_steps(tmp_path) == _BLACK


def test_unrecognised_formatter_value_raises(tmp_path: Path) -> None:
    _write_pyproject(tmp_path, '[tool.mcp-tools-py]\nformatter = "yapf"\n')

    with pytest.raises(ValueError) as excinfo:
        resolve_steps(tmp_path)

    message = str(excinfo.value)
    assert "yapf" in message
    assert '"black"' in message
    assert '"ruff"' in message


@pytest.mark.parametrize(
    "value",
    ['["ruff"]', '{ name = "ruff" }'],
    ids=["array", "table"],
)
def test_non_string_formatter_value_raises(tmp_path: Path, value: str) -> None:
    path = _write_pyproject(tmp_path, f"[tool.mcp-tools-py]\nformatter = {value}\n")

    with pytest.raises(ValueError) as excinfo:
        resolve_steps(tmp_path)

    message = str(excinfo.value)
    assert "[tool.mcp-tools-py] formatter" in message
    assert str(path) in message


def test_missing_pyproject_is_neither_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="No formatter declared") as excinfo:
        resolve_steps(tmp_path)

    assert str(tmp_path / "pyproject.toml") in str(excinfo.value)
