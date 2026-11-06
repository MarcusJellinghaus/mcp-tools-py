"""Tests for the identity that tells two coverage selections apart."""

import json

import pytest

from mcp_tools_py.code_checker_pytest.coverage import selection_identity


class TestSelectionIdentity:
    """Test which differences between two runs make them different selections."""

    def test_is_a_json_string(self) -> None:
        """The identity holds the selection's parts, with nothing else in rest."""
        identity = selection_identity(
            ["slow"], ["-k", "foo", "--lf", "a.py"], ["a.py"], None, None
        )

        assert json.loads(identity) == ["slow", "foo", ["a.py"], ["--lf"], ""]

    def test_arg_order_does_not_matter(self) -> None:
        """The same args in a different order give the same identity."""
        assert selection_identity(
            None, ["--lf", "-x", "a.py", "b.py"], ["a.py", "b.py"], None, None
        ) == selection_identity(
            None, ["b.py", "-x", "a.py", "--lf"], ["b.py", "a.py"], None, None
        )

    def test_marker_order_does_not_matter(self) -> None:
        """The markers parameter is sorted before joining."""
        assert selection_identity(["a", "b"], [], [], None, None) == selection_identity(
            ["b", "a"], [], [], None, None
        )

    def test_m_and_k_are_not_interchangeable(self) -> None:
        """-m a -k b selects something else than -m b -k a."""
        assert selection_identity(
            None, ["-m", "a", "-k", "b"], [], None, None
        ) != selection_identity(None, ["-m", "b", "-k", "a"], [], None, None)

    def test_attached_and_separate_values_are_the_same(self) -> None:
        """-mX and -m X name the same selection."""
        assert selection_identity(
            None, ["-mslow", "-kfoo"], [], None, None
        ) == selection_identity(None, ["-m", "slow", "-k", "foo"], [], None, None)

    @pytest.mark.parametrize("arg", ["--ignore=x", "--deselect=y", "--lf"])
    def test_narrowing_args_make_it_distinct(self, arg: str) -> None:
        """An arg that changes what runs changes the identity."""
        assert selection_identity(None, [arg], [], None, None) != selection_identity(
            None, [], [], None, None
        )

    @pytest.mark.parametrize(
        "arg", ["--cov=src", "--cov-report=term", "--cov-branch", "--cov-fail-under=9"]
    )
    def test_cov_args_do_not_make_it_distinct(self, arg: str) -> None:
        """Coverage flags change what is measured, not which tests run."""
        assert selection_identity(None, [arg], [], None, None) == selection_identity(
            None, [], [], None, None
        )

    @pytest.mark.parametrize("flag", ["-m", "-k"])
    def test_addopts_value_counts(self, flag: str) -> None:
        """A selection coming from addopts is part of the identity."""
        assert selection_identity(
            None, [], [], f"{flag} slow", None
        ) != selection_identity(None, [], [], None, None)

    @pytest.mark.parametrize("flag", ["-m", "-k"])
    def test_command_line_wins_over_addopts(self, flag: str) -> None:
        """An addopts value overridden on the command line doesn't count."""
        assert selection_identity(
            None, [flag, "fast"], [], f"{flag} slow", None
        ) == selection_identity(None, [flag, "fast"], [], None, None)

    def test_markers_parameter_wins_over_addopts(self) -> None:
        """The markers parameter overrides an addopts -m."""
        assert selection_identity(
            ["fast"], [], [], "-m slow", None
        ) == selection_identity(["fast"], [], [], None, None)

    def test_env_values_make_it_distinct(self) -> None:
        """Different env values give different identities."""
        assert selection_identity(
            None, [], [], None, {"STAGE": "one"}
        ) != selection_identity(None, [], [], None, {"STAGE": "two"})

    def test_env_order_does_not_matter(self) -> None:
        """The env is compared by content."""
        assert selection_identity(
            None, [], [], None, {"A": "1", "B": "2"}
        ) == selection_identity(None, [], [], None, {"B": "2", "A": "1"})

    def test_no_env_value_in_clear(self) -> None:
        """The identity is saved to disk, so it must not contain secrets."""
        identity = selection_identity(None, [], [], None, {"TOKEN": "hunter2"})

        assert "hunter2" not in identity
        assert "TOKEN" not in identity
