"""Tests for the shared short-option splitter and its callers."""

from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.pytest_config import (
    EffectiveConfig,
    _option_spans,
    effective_config,
)
from mcp_tools_py.code_checker_pytest.utils import (
    SHOW_OUTPUT_NOTE,
    sanitize_extra_args,
    split_short_group,
)


def _effective(root: Path, args: list[str]) -> EffectiveConfig:
    """Resolve the effective config of *args* with an empty pytest table."""
    (root / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\n", encoding="utf-8"
    )
    return effective_config(str(root), None, args, None)


class TestSplitShortGroup:
    """split_short_group reads a group letter by letter."""

    @pytest.mark.parametrize(
        "arg,expected",
        [
            ("-svrw", ("sv", "r", "w")),
            ("-vkrs", ("v", "k", "rs")),
            ("-pno:cacheprovider", ("", "p", "no:cacheprovider")),
            ("-vWerror", ("v", "W", "error")),
            ("-xvs", ("xvs", None, "")),
            ("-m", ("", "m", "")),
        ],
    )
    def test_split(self, arg: str, expected: tuple[str, str | None, str]) -> None:
        """A value-taking letter ends the group; the rest is its value."""
        assert split_short_group(arg) == expected


class TestSanitizeShortGroups:
    """sanitize_extra_args strips s and v from any short group."""

    def test_svrw_keeps_report_chars(self) -> None:
        """-svrw becomes -rw and sets show_output and verbosity."""
        result = sanitize_extra_args(["-svrw"], None)
        assert result.cleaned_args == ["-rw"]
        assert result.verbosity == 1
        assert result.show_output is True
        assert result.notes == [SHOW_OUTPUT_NOTE]

    @pytest.mark.parametrize("arg", ["-rs", "-rfEs", "-ktest_s", "-xktest_pass"])
    def test_s_inside_value_is_not_s(self, arg: str) -> None:
        """An s after a value-taking letter is part of its value."""
        result = sanitize_extra_args([arg], None)
        assert result.cleaned_args == [arg]
        assert result.show_output is False
        assert result.verbosity == 2

    @pytest.mark.parametrize("arg,cleaned", [("-vrs", ["-rs"]), ("-vkrs", ["-krs"])])
    def test_v_before_value_letter_extracted(
        self, arg: str, cleaned: list[str]
    ) -> None:
        """A v before the value letter sets verbosity; the rest is kept."""
        result = sanitize_extra_args([arg], None)
        assert result.cleaned_args == cleaned
        assert result.verbosity == 1
        assert result.show_output is False

    @pytest.mark.parametrize(
        "arg,cleaned,verbosity", [("-xvs", ["-x"], 1), ("-qs", ["-q"], 2)]
    )
    def test_switch_groups_kept(
        self, arg: str, cleaned: list[str], verbosity: int
    ) -> None:
        """Pure switch groups behave as before."""
        result = sanitize_extra_args([arg], None)
        assert result.cleaned_args == cleaned
        assert result.verbosity == verbosity
        assert result.show_output is True


class TestEffectiveConfigShortGroups:
    """effective_config reads tracked options inside short groups (#294)."""

    def test_p_value_holding_n_is_not_numprocesses(self, tmp_path: Path) -> None:
        """The n inside -pno:cacheprovider is part of the -p value."""
        effective = _effective(tmp_path, ["-pno:cacheprovider"])
        assert effective.numprocesses is False

    def test_w_value_sets_nothing(self, tmp_path: Path) -> None:
        """-vWerror tracks no option."""
        effective = _effective(tmp_path, ["-vWerror"])
        assert effective.numprocesses is False
        assert effective.m is None
        assert effective.k is None

    def test_group_with_separate_value(self, tmp_path: Path) -> None:
        """-xm slow gives -m slow."""
        effective = _effective(tmp_path, ["-xm", "slow"])
        assert effective.m is not None
        assert effective.m.value == "slow"

    def test_group_separate_value_then_positional(self, tmp_path: Path) -> None:
        """The separate value is consumed; the positional after it is not."""
        effective = _effective(tmp_path, ["-xm", "slow", "tests/x.py"])
        assert effective.m is not None
        assert effective.m.value == "slow"
        assert effective.k is None

    def test_group_with_inline_value(self, tmp_path: Path) -> None:
        """-vkrs gives -k rs."""
        effective = _effective(tmp_path, ["-vkrs"])
        assert effective.k is not None
        assert effective.k.value == "rs"

    def test_inline_n(self, tmp_path: Path) -> None:
        """-nauto turns numprocesses on."""
        assert _effective(tmp_path, ["-nauto"]).numprocesses is True

    def test_equals_value(self, tmp_path: Path) -> None:
        """-m=slow gives slow."""
        effective = _effective(tmp_path, ["-m=slow"])
        assert effective.m is not None
        assert effective.m.value == "slow"


class TestOptionSpansPositionals:
    """Positionals holding value-option letters are not options."""

    @pytest.mark.parametrize(
        "token", ["tests/test_markers.py", "tests/test_numbers.py", "markers"]
    )
    def test_positional_gives_no_span(self, token: str) -> None:
        """A token without a leading dash never yields a span."""
        assert not _option_spans([token])

    def test_positionals_track_nothing(self, tmp_path: Path) -> None:
        """effective_config with such positionals tracks no -m or -n."""
        effective = _effective(
            tmp_path, ["tests/test_markers.py", "tests/test_numbers.py", "markers"]
        )
        assert effective.m is None
        assert effective.numprocesses is False
