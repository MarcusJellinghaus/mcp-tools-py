"""Tests for the identity that tells two coverage selections apart."""

import json
from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.coverage import selection_identity
from mcp_tools_py.code_checker_pytest.pytest_config import effective_config

_INI = "[tool.pytest.ini_options]\n"


def _identity(
    root: Path,
    pyproject: str = _INI,
    markers: list[str] | None = None,
    args: list[str] | None = None,
    path_args: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
) -> str:
    """Write *pyproject* as pyproject.toml and build the selection identity."""
    root.mkdir(exist_ok=True)
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    effective = effective_config(str(root), markers, args or [], env_vars)
    return selection_identity(markers, effective, args or [], path_args or [], env_vars)


def _addopts(value: str) -> str:
    """Return an ini_options table with *value* as its ``addopts`` string."""
    return f'{_INI}addopts = "{value}"\n'


class TestSelectionIdentity:
    """Test which differences between two runs make them different selections."""

    def test_is_a_json_string(self, tmp_path: Path) -> None:
        """The identity holds the selection's parts, with nothing else in rest."""
        identity = _identity(
            tmp_path,
            markers=["slow"],
            args=["-k", "foo", "--lf", "a.py"],
            path_args=["a.py"],
        )

        assert json.loads(identity) == ["slow", "foo", ["a.py"], ["--lf"], "", None]

    def test_arg_order_does_not_matter(self, tmp_path: Path) -> None:
        """The same args in a different order give the same identity."""
        assert _identity(
            tmp_path, args=["--lf", "-x", "a.py", "b.py"], path_args=["a.py", "b.py"]
        ) == _identity(
            tmp_path, args=["b.py", "-x", "a.py", "--lf"], path_args=["b.py", "a.py"]
        )

    def test_marker_order_does_not_matter(self, tmp_path: Path) -> None:
        """The markers parameter is sorted before joining."""
        assert _identity(tmp_path, markers=["a", "b"]) == _identity(
            tmp_path, markers=["b", "a"]
        )

    def test_m_and_k_are_not_interchangeable(self, tmp_path: Path) -> None:
        """-m a -k b selects something else than -m b -k a."""
        assert _identity(tmp_path, args=["-m", "a", "-k", "b"]) != _identity(
            tmp_path, args=["-m", "b", "-k", "a"]
        )

    def test_attached_and_separate_values_are_the_same(self, tmp_path: Path) -> None:
        """-mX and -m X name the same selection."""
        assert _identity(tmp_path, args=["-mslow", "-kfoo"]) == _identity(
            tmp_path, args=["-m", "slow", "-k", "foo"]
        )

    def test_equals_and_separate_values_are_the_same(self, tmp_path: Path) -> None:
        """-m=X and -m X name the same selection."""
        assert _identity(tmp_path, args=["-m=slow", "-k=foo"]) == _identity(
            tmp_path, args=["-m", "slow", "-k", "foo"]
        )

    @pytest.mark.parametrize("arg", ["--ignore=x", "--deselect=y", "--lf"])
    def test_narrowing_args_make_it_distinct(self, tmp_path: Path, arg: str) -> None:
        """An arg that changes what runs changes the identity."""
        assert _identity(tmp_path, args=[arg]) != _identity(tmp_path)

    @pytest.mark.parametrize(
        "arg", ["--cov=src", "--cov-report=term", "--cov-branch", "--cov-fail-under=9"]
    )
    def test_cov_args_do_not_make_it_distinct(self, tmp_path: Path, arg: str) -> None:
        """Coverage flags change what is measured, not which tests run."""
        assert _identity(tmp_path, args=[arg]) == _identity(tmp_path)

    @pytest.mark.parametrize("flag", ["-m", "-k"])
    def test_addopts_value_counts(self, tmp_path: Path, flag: str) -> None:
        """A selection coming from addopts is part of the identity."""
        assert _identity(tmp_path, _addopts(f"{flag} slow")) != _identity(tmp_path)

    def test_addopts_list_value_counts(self, tmp_path: Path) -> None:
        """A list addopts -m is part of the identity."""
        listed = f'{_INI}addopts = ["-m", "not slow"]\n'

        assert _identity(tmp_path, listed) == _identity(
            tmp_path, args=["-m", "not slow"]
        )

    @pytest.mark.parametrize("flag", ["-m", "-k"])
    def test_command_line_wins_over_addopts(self, tmp_path: Path, flag: str) -> None:
        """An addopts value overridden on the command line doesn't count."""
        assert _identity(
            tmp_path, _addopts(f"{flag} slow"), args=[flag, "fast"]
        ) == _identity(tmp_path, args=[flag, "fast"])

    def test_markers_parameter_wins_over_addopts(self, tmp_path: Path) -> None:
        """The markers parameter overrides an addopts -m."""
        assert _identity(tmp_path, _addopts("-m slow"), ["fast"]) == _identity(
            tmp_path, markers=["fast"]
        )

    def test_not_read_makes_it_distinct(self, tmp_path: Path) -> None:
        """A run whose pytest config is not read is its own selection."""
        not_read = tmp_path / "not_read"
        not_read.mkdir()
        (not_read / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

        assert _identity(not_read) != _identity(tmp_path / "read")

    def test_env_values_make_it_distinct(self, tmp_path: Path) -> None:
        """Different env values give different identities."""
        assert _identity(tmp_path, env_vars={"STAGE": "one"}) != _identity(
            tmp_path, env_vars={"STAGE": "two"}
        )

    def test_env_order_does_not_matter(self, tmp_path: Path) -> None:
        """The env is compared by content."""
        assert _identity(tmp_path, env_vars={"A": "1", "B": "2"}) == _identity(
            tmp_path, env_vars={"B": "2", "A": "1"}
        )

    def test_no_env_value_in_clear(self, tmp_path: Path) -> None:
        """The identity is saved to disk, so it must not contain secrets."""
        identity = _identity(tmp_path, env_vars={"TOKEN": "hunter2"})

        assert "hunter2" not in identity
        assert "TOKEN" not in identity
