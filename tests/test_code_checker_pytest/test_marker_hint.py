"""Tests for the ``-m`` expression scan and the marker notes."""

from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.marker_hint import (
    RERUN_TIP,
    STRICT_SUGGESTION,
    marker_notes,
    scan_expression,
    unknown_marker_names,
)
from mcp_tools_py.code_checker_pytest.pytest_config import (
    EffectiveConfig,
    effective_config,
)
from mcp_tools_py.toolkit import UNATTENDED_EXCLUDED_MARKERS

_INI = "[tool.pytest.ini_options]\n"
_MARKERS = 'markers = ["integration: slow ones", "slow"]\n'
_STRICT = 'addopts = "--strict-markers"\n'
_UNKNOWN = (
    "ERROR: Unknown marker(s) in '-m' expression: {}. "
    "Use 'pytest --markers' to see available markers."
)
_WRONG = (
    "ERROR: Wrong expression passed to '-m': slow and: "
    "at column 10: expected not OR left parenthesis OR identifier; got end of input"
)
_HINT_UNIT = (
    "`unit` is not registered in the project config. Registered: integration, slow"
)


def _effective(
    root: Path,
    pyproject: str = _INI + _MARKERS,
    markers: list[str] | None = None,
    args: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
) -> EffectiveConfig:
    """Write *pyproject* as pyproject.toml and resolve the effective config."""
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return effective_config(str(root), markers, args or [], env_vars)


class TestScanExpression:
    """Test the names, their negation and the validity of a ``-m`` expression."""

    def test_single_name(self) -> None:
        """A bare name is not negated and valid."""
        assert scan_expression("unit") == ([("unit", False)], True)

    def test_not(self) -> None:
        """One ``not`` negates."""
        assert scan_expression("not unit") == ([("unit", True)], True)

    def test_not_not(self) -> None:
        """Two ``not``s cancel."""
        assert scan_expression("not not unit") == ([("unit", False)], True)

    def test_not_over_parentheses(self) -> None:
        """A ``not`` before parentheses negates the names inside only."""
        names, valid = scan_expression("not (a or b) and c")

        assert names == [("a", True), ("b", True), ("c", False)]
        assert valid

    def test_not_inside_parentheses(self) -> None:
        """A ``not`` inside parentheses ends with them."""
        assert scan_expression("(not a) or b") == ([("a", True), ("b", False)], True)

    def test_kwargs_are_not_names(self) -> None:
        """``name(key=value)`` arguments are skipped."""
        assert scan_expression('mark(key="v", n=1, flag=True)') == (
            [("mark", False)],
            True,
        )

    def test_true_at_top_level_is_a_name(self) -> None:
        """``True`` outside kwargs is a name."""
        assert scan_expression("True") == ([("True", False)], True)

    @pytest.mark.parametrize(
        ("expr", "names"),
        [
            ("a b", ["a", "b"]),
            ("a and", ["a"]),
            ("(a", ["a"]),
            ("a)", ["a"]),
            ("'x'", []),
            ("a $ b", ["a", "b"]),
            ("mark()", ["mark"]),
            ("mark(x)", ["mark"]),
        ],
    )
    def test_invalid(self, expr: str, names: list[str]) -> None:
        """An invalid expression still returns its names."""
        scanned, valid = scan_expression(expr)

        assert [name for name, _ in scanned] == names
        assert not valid

    def test_ident_characters(self) -> None:
        """pytest's identifier characters make one name."""
        assert scan_expression("a.b:c/d[1]+e-f\\g") == (
            [("a.b:c/d[1]+e-f\\g", False)],
            True,
        )


class TestUnknownMarkerNames:
    """Test reading the names from pytest's ``Unknown marker(s)`` line."""

    def test_names(self) -> None:
        """pytest 9's text gives its names, dots kept."""
        assert unknown_marker_names(_UNKNOWN.format("a, b.c")) == ["a", "b.c"]

    def test_no_match(self) -> None:
        """Another line gives no names."""
        assert not unknown_marker_names(_WRONG)


class TestMarkerNotes:
    """Test the ERROR line, the hint, the suggestion and the rerun tip."""

    def test_unregistered_exit_5(self, tmp_path: Path) -> None:
        """An unregistered name on exit 5 gets the hint and the suggestion."""
        effective = _effective(tmp_path, markers=["unit"])

        assert marker_notes(effective, 5, None) == [_HINT_UNIT, STRICT_SUGGESTION]

    def test_builtin_is_registered(self, tmp_path: Path) -> None:
        """A built-in marker is not reported."""
        effective = _effective(tmp_path, markers=["skip"])

        assert not marker_notes(effective, 5, None)

    def test_negated_non_strict(self, tmp_path: Path) -> None:
        """Without strict markers a negated name doesn't count."""
        effective = _effective(tmp_path, markers=["not unit"])

        assert not marker_notes(effective, 5, None)

    def test_double_negation_counts(self, tmp_path: Path) -> None:
        """``not not unit`` is not negated."""
        effective = _effective(tmp_path, markers=["not not unit"])

        assert marker_notes(effective, 5, None) == [_HINT_UNIT, STRICT_SUGGESTION]

    def test_all_registered(self, tmp_path: Path) -> None:
        """Registered names get no hint."""
        effective = _effective(tmp_path, markers=["integration or slow"])

        assert not marker_notes(effective, 5, None)

    def test_no_m(self, tmp_path: Path) -> None:
        """A run without ``-m`` gets no notes."""
        assert not marker_notes(_effective(tmp_path), 5, None)

    def test_unrelated_exit_4(self, tmp_path: Path) -> None:
        """An exit 4 without a marker error gets no notes."""
        effective = _effective(tmp_path, markers=["unit"])

        assert not marker_notes(effective, 4, None)

    def test_several_names_deduplicated(self, tmp_path: Path) -> None:
        """Several names are listed once each, in order."""
        effective = _effective(tmp_path, markers=["a or b or a"])

        assert marker_notes(effective, 5, None)[0] == (
            "`a`, `b` are not registered in the project config. "
            "Registered: integration, slow"
        )

    def test_unknown_marker_exit_4(self, tmp_path: Path) -> None:
        """The names come from pytest's message; strict config, no suggestion."""
        effective = _effective(
            tmp_path, _INI + _MARKERS + _STRICT, markers=["unit or other"]
        )
        error = _UNKNOWN.format("unit")

        assert marker_notes(effective, 4, error) == [error, _HINT_UNIT]

    def test_wrong_expression_registered_names(self, tmp_path: Path) -> None:
        """A syntax error with registered names shows only pytest's line."""
        effective = _effective(tmp_path, markers=["slow and"])

        assert marker_notes(effective, 4, _WRONG) == [_WRONG]

    def test_exit_3_strict_under_xdist(self, tmp_path: Path) -> None:
        """Exit 3 with strict on and ``-n`` gets the hint and the tip."""
        effective = _effective(
            tmp_path, _INI + _MARKERS + _STRICT, markers=["unit"], args=["-n", "4"]
        )

        assert marker_notes(effective, 3, None) == [_HINT_UNIT, RERUN_TIP]

    def test_exit_3_non_strict_under_xdist(self, tmp_path: Path) -> None:
        """Exit 3 without strict gets only the tip."""
        effective = _effective(tmp_path, markers=["unit"], args=["-n", "4"])

        assert marker_notes(effective, 3, None) == [RERUN_TIP]

    @pytest.mark.parametrize("args", [["-n", "0"], []])
    def test_exit_3_without_xdist(self, tmp_path: Path, args: list[str]) -> None:
        """Exit 3 without ``-n`` in effect gets no tip."""
        effective = _effective(tmp_path, markers=["a and"], args=args)

        assert RERUN_TIP not in marker_notes(effective, 3, None)

    def test_env_turns_strict_off(self, tmp_path: Path) -> None:
        """``PYTEST_ADDOPTS`` turning strict off: negated names don't count."""
        effective = _effective(
            tmp_path,
            _INI + _MARKERS + _STRICT,
            markers=["not unit"],
            env_vars={"PYTEST_ADDOPTS": "-o strict_markers=false"},
        )

        assert not marker_notes(effective, 5, None)

    def test_env_off_project_on_no_suggestion(self, tmp_path: Path) -> None:
        """The suggestion follows the project config alone."""
        effective = _effective(
            tmp_path,
            _INI + _MARKERS + _STRICT,
            markers=["unit"],
            env_vars={"PYTEST_ADDOPTS": "-o strict_markers=false"},
        )

        assert marker_notes(effective, 5, None) == [_HINT_UNIT]

    def test_table_strict_no_suggestion(self, tmp_path: Path) -> None:
        """Table ``strict_markers = true`` counts as project strict."""
        effective = _effective(
            tmp_path, _INI + _MARKERS + "strict_markers = true\n", markers=["unit"]
        )

        assert marker_notes(effective, 5, None) == [_HINT_UNIT]

    @pytest.mark.parametrize("args", [[], ["-c", "x.ini"]])
    def test_config_not_read(self, tmp_path: Path, args: list[str]) -> None:
        """No hint when the config is not read; the ERROR line stays."""
        if not args:
            (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        effective = _effective(tmp_path, markers=["unit"], args=args)
        error = _UNKNOWN.format("unit")

        assert marker_notes(effective, 4, error) == [error]
        assert not marker_notes(effective, 5, None)

    def test_config_not_read_rerun_tip(self, tmp_path: Path) -> None:
        """The rerun tip shows even when the config is not read."""
        (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        effective = _effective(tmp_path, markers=["unit"], args=["-n", "2"])

        assert marker_notes(effective, 3, None) == [RERUN_TIP]

    def test_registers_none(self, tmp_path: Path) -> None:
        """A project without markers says so."""
        effective = _effective(tmp_path, _INI, markers=["unit"])

        assert marker_notes(effective, 5, None)[0] == (
            "`unit` is not registered in the project config. "
            "The project config registers none."
        )

    def test_toolkit_unattended_contract(self, tmp_path: Path) -> None:
        """The toolkit's unattended call stays quiet on exit 5."""
        effective = _effective(
            tmp_path,
            _INI + _MARKERS + _STRICT,
            markers=list(UNATTENDED_EXCLUDED_MARKERS),
            args=["-o", "strict_markers=false"],
        )

        assert not marker_notes(effective, 5, None)
