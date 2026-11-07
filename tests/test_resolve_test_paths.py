"""Tests for resolve_test_paths in mcp_tools_py.utils.project_config."""

from pathlib import Path

import pytest

from mcp_tools_py.utils.project_config import resolve_test_paths


def _pyproject(testpaths: str) -> str:
    return f"[tool.pytest.ini_options]\ntestpaths = {testpaths}\n"


@pytest.mark.parametrize(
    ("test_folder", "pyproject", "folders", "expected_paths", "has_note"),
    [
        ("checks", _pyproject('["tests"]'), ["tests"], ["checks"], False),
        (None, None, [], ["tests"], False),
        (None, "[tool.pytest.ini_options]\n", [], ["tests"], False),
        (None, _pyproject("[]"), ["checks"], ["tests"], False),
        (None, _pyproject('"checks"'), ["checks"], ["tests"], False),
        (None, _pyproject('["checks"]'), ["checks", "tests"], ["checks"], False),
        (
            None,
            _pyproject('["tests", "integration"]'),
            ["tests", "integration"],
            ["tests", "integration"],
            False,
        ),
        (
            None,
            _pyproject('["pkgs/*/tests"]'),
            ["pkgs/b/tests", "pkgs/a/tests"],
            ["pkgs/a/tests", "pkgs/b/tests"],
            False,
        ),
        (None, _pyproject('["**/tests"]'), ["pkgs/a/tests"], ["pkgs/a/tests"], False),
        (None, _pyproject('["nope", "checks"]'), ["checks"], ["checks"], False),
        (None, _pyproject('["nope"]'), ["tests"], ["tests"], True),
        (None, _pyproject('["nope"]'), [], ["tests"], True),
    ],
)
def test_resolve_test_paths(
    tmp_path: Path,
    test_folder: str | None,
    pyproject: str | None,
    folders: list[str],
    expected_paths: list[str],
    has_note: bool,
) -> None:
    """Paths and note follow the explicit folder, then testpaths, then 'tests'."""
    if pyproject is not None:
        (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    for folder in folders:
        (tmp_path / folder).mkdir(parents=True)

    paths, note = resolve_test_paths(str(tmp_path), test_folder)

    assert [Path(p).as_posix() for p in paths] == expected_paths
    if has_note:
        assert note is not None
        assert "nope" in note
        assert "tests" in note
    else:
        assert note is None


def test_invalid_toml_without_folder_raises(tmp_path: Path) -> None:
    """Invalid pyproject.toml propagates as ValueError when resolving."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest\n", encoding="utf-8")

    with pytest.raises(ValueError):
        resolve_test_paths(str(tmp_path), None)


def test_invalid_toml_with_folder_is_not_read(tmp_path: Path) -> None:
    """An explicit folder never reads pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[tool.pytest\n", encoding="utf-8")

    assert resolve_test_paths(str(tmp_path), "checks") == (["checks"], None)
