"""Tests for the effective pytest config and its ``addopts`` notes."""

import os
from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.pytest_config import (
    ENV_WAY_OUT,
    INI_WAY_OUT,
    EffectiveConfig,
    OptionValue,
    addopts_notes,
    effective_config,
)

_INI = "[tool.pytest.ini_options]\n"


def _effective(
    root: Path,
    pyproject: str = _INI,
    markers: list[str] | None = None,
    args: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
) -> EffectiveConfig:
    """Write *pyproject* as pyproject.toml and resolve the effective config."""
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return effective_config(str(root), markers, args or [], env_vars)


def _addopts(value: str) -> str:
    """Return an ini_options table with *value* as its ``addopts`` string."""
    return f'{_INI}addopts = "{value}"\n'


class TestMarkerOption:
    """Test the effective ``-m`` and ``-k``."""

    @pytest.mark.parametrize("args", [["-m", "X"], ["-mX"], ["-m=X"]])
    def test_spellings_in_extra_args(self, tmp_path: Path, args: list[str]) -> None:
        """All three spellings give the value."""
        effective = _effective(tmp_path, args=args)

        assert effective.m == OptionValue("X", "extra_args")

    def test_markers_joined(self, tmp_path: Path) -> None:
        """``markers`` entries are joined with ``and``."""
        effective = _effective(tmp_path, markers=["a", "b"])

        assert effective.m == OptionValue("a and b", "markers")

    def test_extra_args_after_markers_wins(self, tmp_path: Path) -> None:
        """An ``extra_args`` ``-mX`` comes after the markers ``-m``."""
        effective = _effective(tmp_path, markers=["a"], args=["-mX"])

        assert effective.m == OptionValue("X", "extra_args")

    def test_empty_markers_adds_nothing(self, tmp_path: Path) -> None:
        """``markers=[]`` adds no ``-m``."""
        effective = _effective(tmp_path, _addopts("-m slow"), markers=[])

        assert effective.m == OptionValue("slow", "pyproject.toml")

    def test_explicit_empty_m_overrides(self, tmp_path: Path) -> None:
        """An explicit empty ``-m`` replaces the ``addopts -m``."""
        effective = _effective(tmp_path, _addopts("-m slow"), args=["-m", ""])

        assert effective.m == OptionValue("", "extra_args")

    def test_list_addopts(self, tmp_path: Path) -> None:
        """A list ``addopts`` keeps a multi-word ``-m`` value whole."""
        effective = _effective(tmp_path, f'{_INI}addopts = ["-m", "not slow"]\n')

        assert effective.m == OptionValue("not slow", "pyproject.toml")

    def test_env_beats_ini(self, tmp_path: Path) -> None:
        """A ``PYTEST_ADDOPTS`` ``-m`` beats the ini one."""
        effective = _effective(
            tmp_path, _addopts("-m slow"), env_vars={"PYTEST_ADDOPTS": "-m fast"}
        )

        assert effective.m == OptionValue("fast", "PYTEST_ADDOPTS")

    def test_call_beats_env_and_ini(self, tmp_path: Path) -> None:
        """The call's ``-m`` beats both defaults."""
        effective = _effective(
            tmp_path,
            _addopts("-m slow"),
            args=["-m", "unit"],
            env_vars={"PYTEST_ADDOPTS": "-m fast"},
        )

        assert effective.m == OptionValue("unit", "extra_args")

    def test_k_option(self, tmp_path: Path) -> None:
        """``-k`` is found like ``-m``."""
        effective = _effective(tmp_path, _addopts("-k foo"), args=["-k=bar"])

        assert effective.k == OptionValue("bar", "extra_args")

    def test_none(self, tmp_path: Path) -> None:
        """Without ``-m`` or ``-k`` both are None."""
        effective = _effective(tmp_path)

        assert (effective.m, effective.k) == (None, None)


class TestAddoptsOverride:
    """Test ``-o addopts=`` in the call and in ``PYTEST_ADDOPTS``."""

    _SPELLINGS = [
        ["-o", "addopts="],
        ["-oaddopts="],
        ["--override-ini", "addopts="],
        ["--override-ini=addopts="],
    ]

    def test_ini_applied(self, tmp_path: Path) -> None:
        """Without an override the ini ``addopts`` applies."""
        effective = _effective(tmp_path, _addopts("-n auto"))

        assert (effective.ini_source, effective.ini_tokens) == (
            "pyproject.toml",
            ["-n", "auto"],
        )

    @pytest.mark.parametrize("args", _SPELLINGS)
    def test_cleared_in_call(self, tmp_path: Path, args: list[str]) -> None:
        """Every spelling in the call clears the ini ``addopts``."""
        effective = _effective(tmp_path, _addopts("-n auto"), args=args)

        assert effective.ini_tokens == []

    @pytest.mark.parametrize("args", _SPELLINGS)
    def test_cleared_in_env(self, tmp_path: Path, args: list[str]) -> None:
        """Every spelling in ``PYTEST_ADDOPTS`` clears the ini ``addopts``."""
        effective = _effective(
            tmp_path, _addopts("-n auto"), env_vars={"PYTEST_ADDOPTS": " ".join(args)}
        )

        assert effective.ini_tokens == []

    def test_replaced_in_call(self, tmp_path: Path) -> None:
        """``-o addopts=-x`` in the call replaces the ini ``addopts``."""
        effective = _effective(tmp_path, _addopts("-n auto"), args=["-o", "addopts=-x"])

        assert (effective.ini_source, effective.ini_tokens) == ("-o", ["-x"])

    def test_replaced_in_env(self, tmp_path: Path) -> None:
        """``-o addopts=-x`` in ``PYTEST_ADDOPTS`` is attributed to it."""
        effective = _effective(
            tmp_path,
            _addopts("-n auto"),
            env_vars={"PYTEST_ADDOPTS": "-o addopts=-x"},
        )

        assert (effective.ini_source, effective.ini_tokens) == (
            "PYTEST_ADDOPTS",
            ["-x"],
        )

    def test_call_override_beats_env_override(self, tmp_path: Path) -> None:
        """The call's ``-o addopts=`` comes after the env one."""
        effective = _effective(
            tmp_path,
            args=["-o", "addopts=-v"],
            env_vars={"PYTEST_ADDOPTS": "-o addopts=-x"},
        )

        assert (effective.ini_source, effective.ini_tokens) == ("-o", ["-v"])

    def test_unbalanced_quotes_in_call(self, tmp_path: Path) -> None:
        """An override value shlex can't split gives no tokens."""
        effective = _effective(
            tmp_path, _addopts("-n auto"), args=["-o", "addopts=-m 'x"]
        )

        assert effective.ini_tokens == []

    def test_unbalanced_quotes_in_env(self, tmp_path: Path) -> None:
        """The same inside ``PYTEST_ADDOPTS`` does not raise."""
        effective = _effective(
            tmp_path,
            _addopts("-n auto"),
            env_vars={"PYTEST_ADDOPTS": '-o "addopts=-m \'x"'},
        )

        assert effective.ini_tokens == []

    def test_unparsable_env(self, tmp_path: Path) -> None:
        """A ``PYTEST_ADDOPTS`` shlex can't split gives no tokens."""
        effective = _effective(tmp_path, env_vars={"PYTEST_ADDOPTS": "-m 'x"})

        assert effective.env_tokens == []

    def test_override_inside_ini_addopts_ignored(self, tmp_path: Path) -> None:
        """``-o addopts=`` inside ini ``addopts`` has no effect."""
        effective = _effective(tmp_path, _addopts("-x -o addopts="))

        assert effective.ini_tokens == ["-x", "-o", "addopts="]


class TestConfigFileOption:
    """Test ``-c`` / ``--config-file``."""

    _SPELLINGS = [
        ["-c", "f.ini"],
        ["-cf.ini"],
        ["-c=f.ini"],
        ["--config-file", "f.ini"],
        ["--config-file=f.ini"],
    ]

    @pytest.mark.parametrize("args", _SPELLINGS)
    def test_in_call(self, tmp_path: Path, args: list[str]) -> None:
        """Every spelling in the call names the file not read."""
        effective = _effective(tmp_path, _addopts("-x"), args=args)

        assert effective.not_read == "f.ini"
        assert effective.ini_tokens == []

    @pytest.mark.parametrize("args", _SPELLINGS)
    def test_in_env(self, tmp_path: Path, args: list[str]) -> None:
        """Every spelling in ``PYTEST_ADDOPTS`` names the file not read."""
        effective = _effective(
            tmp_path, _addopts("-x"), env_vars={"PYTEST_ADDOPTS": " ".join(args)}
        )

        assert effective.not_read == "f.ini"

    def test_in_ini_addopts_ignored(self, tmp_path: Path) -> None:
        """``-c`` inside ini ``addopts`` has no effect."""
        effective = _effective(tmp_path, _addopts("-c f.ini"))

        assert effective.not_read is None

    def test_dedicated_file(self, tmp_path: Path) -> None:
        """A dedicated pytest file is named."""
        (tmp_path / "pytest.ini").write_text("", encoding="utf-8")

        effective = _effective(tmp_path, _addopts("-x"))

        assert effective.not_read == "pytest.ini"
        assert effective.ini_tokens == []


class TestEnvLookup:
    """Test where ``PYTEST_ADDOPTS`` comes from."""

    def test_inherited(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An inherited value is read."""
        monkeypatch.setenv("PYTEST_ADDOPTS", "-m fast")

        effective = _effective(tmp_path)

        assert effective.env_tokens == ["-m", "fast"]

    def test_env_vars_clear_inherited(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty value in ``env_vars`` clears the inherited one."""
        monkeypatch.setenv("PYTEST_ADDOPTS", "-m fast")

        effective = _effective(tmp_path, env_vars={"PYTEST_ADDOPTS": ""})

        assert (effective.env_tokens, effective.m) == ([], None)

    @pytest.mark.skipif(os.name != "nt", reason="Windows env keys are case-insensitive")
    def test_lower_case_key_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """On Windows a lower-case ``env_vars`` key replaces the value."""
        monkeypatch.setenv("PYTEST_ADDOPTS", "-m fast")

        effective = _effective(tmp_path, env_vars={"pytest_addopts": "-m slow"})

        assert effective.env_tokens == ["-m", "slow"]


class TestStrictMarkers:
    """Test strictness, resolved per key in pytest's order."""

    def test_flag_beats_table_false(self, tmp_path: Path) -> None:
        """``strict_markers=false`` plus ``--strict-markers`` is on."""
        effective = _effective(
            tmp_path, f'{_INI}strict_markers = false\naddopts = "--strict-markers"\n'
        )

        assert (effective.strict_markers, effective.project_strict_markers) == (
            True,
            True,
        )

    def test_strict_does_not_beat_strict_markers(self, tmp_path: Path) -> None:
        """``strict_markers=false`` plus ``--strict`` is off."""
        effective = _effective(
            tmp_path, f'{_INI}strict_markers = false\naddopts = "--strict"\n'
        )

        assert (effective.strict_markers, effective.project_strict_markers) == (
            False,
            False,
        )

    def test_strict_alone(self, tmp_path: Path) -> None:
        """``strict = true`` alone turns strict markers on."""
        effective = _effective(tmp_path, f"{_INI}strict = true\n")

        assert effective.strict_markers is True

    def test_override_beats_strict(self, tmp_path: Path) -> None:
        """``-o strict_markers=false`` beats ``strict = true``."""
        effective = _effective(
            tmp_path, f"{_INI}strict = true\n", args=["-o", "strict_markers=false"]
        )

        assert effective.strict_markers is False

    def test_env_beats_ini_flag(self, tmp_path: Path) -> None:
        """``PYTEST_ADDOPTS`` turns it off; the project config still has it on."""
        effective = _effective(
            tmp_path,
            _addopts("--strict-markers"),
            env_vars={"PYTEST_ADDOPTS": "-o strict_markers=false"},
        )

        assert (effective.strict_markers, effective.project_strict_markers) == (
            False,
            True,
        )

    def test_override_strict_in_call(self, tmp_path: Path) -> None:
        """``-o strict=true`` in the call turns it on."""
        effective = _effective(tmp_path, args=["--override-ini=strict=true"])

        assert (effective.strict_markers, effective.project_strict_markers) == (
            True,
            False,
        )

    def test_table_key_alone(self, tmp_path: Path) -> None:
        """A table ``strict_markers = true`` is the project's own setting."""
        effective = _effective(tmp_path, f"{_INI}strict_markers = true\n")

        assert effective.project_strict_markers is True

    def test_default_off(self, tmp_path: Path) -> None:
        """Nothing set: off."""
        effective = _effective(tmp_path)

        assert (effective.strict_markers, effective.project_strict_markers) == (
            False,
            False,
        )

    def test_config_not_read(self, tmp_path: Path) -> None:
        """An unread config has no project strictness."""
        (tmp_path / "pytest.ini").write_text("", encoding="utf-8")

        effective = _effective(tmp_path, f"{_INI}strict_markers = true\n")

        assert effective.project_strict_markers is False


class TestNumprocesses:
    """Test whether ``-n`` is in effect."""

    @pytest.mark.parametrize(
        ("args", "expected"),
        [
            (["-n", "4"], True),
            (["-n0"], False),
            (["--numprocesses=auto"], True),
            (["-n", "4", "-n0"], False),
            (["-n0", "--numprocesses", "2"], True),
            ([], False),
        ],
    )
    def test_last_wins(self, tmp_path: Path, args: list[str], expected: bool) -> None:
        """The last value counts; ``0`` is off."""
        assert _effective(tmp_path, args=args).numprocesses is expected

    def test_from_ini(self, tmp_path: Path) -> None:
        """An ini ``-n auto`` is in effect."""
        assert _effective(tmp_path, _addopts("-n auto")).numprocesses is True

    def test_call_beats_ini(self, tmp_path: Path) -> None:
        """The call's ``-n 0`` beats the ini ``-n auto``."""
        effective = _effective(tmp_path, _addopts("-n auto"), args=["-n", "0"])

        assert effective.numprocesses is False


class TestAddoptsNotes:
    """Test the rendered ``addopts`` lines."""

    def test_applied(self, tmp_path: Path) -> None:
        """The ini line shows the values and the way out."""
        effective = _effective(tmp_path, _addopts("-n auto -m 'not slow'"))

        assert addopts_notes(effective) == [
            f"addopts (pyproject.toml): -n auto -m 'not slow' — to run without: "
            f"{INI_WAY_OUT}"
        ]

    def test_way_out_text(self) -> None:
        """The way-out strings are copyable call arguments."""
        assert INI_WAY_OUT == 'extra_args=["-o", "addopts="]'
        assert ENV_WAY_OUT == 'env_vars={"PYTEST_ADDOPTS": ""}'

    @pytest.mark.parametrize(
        ("markers", "args", "env", "source"),
        [
            (["fast"], [], "", "markers"),
            (None, ["-m", "fast"], "", "extra_args"),
            (None, [], "-m fast", "PYTEST_ADDOPTS"),
        ],
    )
    def test_replaced(
        self,
        tmp_path: Path,
        markers: list[str] | None,
        args: list[str],
        env: str,
        source: str,
    ) -> None:
        """A replaced ``-m`` is named with its replacing source."""
        effective = _effective(
            tmp_path,
            _addopts("-n auto -m 'not slow'"),
            markers=markers,
            args=args,
            env_vars={"PYTEST_ADDOPTS": env},
        )

        assert addopts_notes(effective)[0] == (
            f"addopts (pyproject.toml): -n auto; its -m 'not slow' was replaced "
            f"by {source} — to run without: {INI_WAY_OUT}"
        )

    def test_replaced_by_explicit_empty(self, tmp_path: Path) -> None:
        """An explicit empty ``-m`` replaces the ``addopts -m`` too."""
        effective = _effective(tmp_path, _addopts("-x -mslow"), args=["-m", ""])

        assert addopts_notes(effective) == [
            f"addopts (pyproject.toml): -x; its -m slow was replaced by extra_args "
            f"— to run without: {INI_WAY_OUT}"
        ]

    def test_whole_addopts_replaced(self, tmp_path: Path) -> None:
        """With nothing left there is no empty ``<label>: ;`` prefix."""
        effective = _effective(tmp_path, _addopts("-m 'not slow'"), markers=["fast"])

        assert addopts_notes(effective) == [
            "addopts (pyproject.toml): -m 'not slow' was replaced by markers — "
            'to run without: extra_args=["-o", "addopts="]'
        ]

    def test_override_line(self, tmp_path: Path) -> None:
        """``-o addopts=X`` from the call needs no way out."""
        effective = _effective(
            tmp_path, _addopts("-n auto"), args=["-o", "addopts=-x -v"]
        )

        assert addopts_notes(effective) == ["addopts (-o): -x -v"]

    def test_override_line_replaced(self, tmp_path: Path) -> None:
        """A later ``-m`` replaces the ``-m`` inside ``-o addopts=X``."""
        effective = _effective(
            tmp_path, args=["-o", "addopts=-x -m slow", "-m", "fast"]
        )

        assert addopts_notes(effective) == [
            "addopts (-o): -x; its -m slow was replaced by extra_args"
        ]

    def test_env_line(self, tmp_path: Path) -> None:
        """``PYTEST_ADDOPTS`` gets its own line and way out."""
        effective = _effective(
            tmp_path, _addopts("-x"), env_vars={"PYTEST_ADDOPTS": "-n 2 -m fast"}
        )

        assert addopts_notes(effective) == [
            f"addopts (pyproject.toml): -x — to run without: {INI_WAY_OUT}",
            f"PYTEST_ADDOPTS: -n 2 -m fast — to run without: {ENV_WAY_OUT}",
        ]

    def test_env_line_replaced(self, tmp_path: Path) -> None:
        """The env ``-m`` replaced by the call is not shown as applied."""
        effective = _effective(
            tmp_path, env_vars={"PYTEST_ADDOPTS": "-m fast"}, markers=["unit"]
        )

        assert addopts_notes(effective) == [
            f"PYTEST_ADDOPTS: -m fast was replaced by markers — to run without: "
            f"{ENV_WAY_OUT}"
        ]

    def test_both_cleared(self, tmp_path: Path) -> None:
        """Both defaults cleared: no line at all."""
        effective = _effective(
            tmp_path,
            _addopts("-n auto"),
            args=["-o", "addopts="],
            env_vars={"PYTEST_ADDOPTS": ""},
        )

        assert addopts_notes(effective) == []

    def test_override_inside_env(self, tmp_path: Path) -> None:
        """``-o addopts=X`` inside ``PYTEST_ADDOPTS`` is part of its line."""
        effective = _effective(
            tmp_path,
            _addopts("-n auto"),
            env_vars={"PYTEST_ADDOPTS": "-o 'addopts=-x -m slow'"},
            args=["-m", "fast"],
        )

        assert addopts_notes(effective) == [
            "PYTEST_ADDOPTS: -o addopts=-x; its -m slow was replaced by extra_args "
            f"— to run without: {ENV_WAY_OUT}"
        ]

    def test_override_inside_env_applied(self, tmp_path: Path) -> None:
        """Not replaced: the ``PYTEST_ADDOPTS`` value is shown as given."""
        effective = _effective(
            tmp_path, env_vars={"PYTEST_ADDOPTS": "-o 'addopts=-x -m slow'"}
        )

        assert addopts_notes(effective) == [
            f"PYTEST_ADDOPTS: -o 'addopts=-x -m slow' — to run without: {ENV_WAY_OUT}"
        ]

    def test_not_read(self, tmp_path: Path) -> None:
        """An unread config gives only the note."""
        effective = _effective(
            tmp_path,
            _addopts("-x"),
            args=["-c", "f.ini"],
            env_vars={"PYTEST_ADDOPTS": "-v"},
        )

        assert addopts_notes(effective) == ["pytest config is in f.ini, not read"]

    def test_config_unreadable(self, tmp_path: Path) -> None:
        """An unreadable config gives no line."""
        effective = _effective(
            tmp_path, "[tool.pytest.ini_options\n", env_vars={"PYTEST_ADDOPTS": "-v"}
        )

        assert effective.config is None
        assert addopts_notes(effective) == []

    def test_nothing_set(self, tmp_path: Path) -> None:
        """No defaults: no line."""
        assert addopts_notes(_effective(tmp_path)) == []
