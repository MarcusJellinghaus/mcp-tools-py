"""Read the project's pytest config and resolve the options pytest ends up using."""

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from mcp_tools_py.utils.file_utils import read_file
from mcp_tools_py.utils.project_config import read_pyproject_tool_tables

# pytest reads the first of these that exists, even when empty, before pyproject.toml.
DEDICATED_FILES = ("pytest.toml", ".pytest.toml", "pytest.ini", ".pytest.ini")

# Read by pytest only when pyproject.toml has no pytest section: file, section header.
_FALLBACK_FILES = (("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]"))

# pytest's bool spellings for ini values, compared lowercased.
_TRUE_SPELLINGS = frozenset({"y", "yes", "t", "true", "on", "1"})
_FALSE_SPELLINGS = frozenset({"n", "no", "f", "false", "off", "0"})

# The copyable call arguments that clear ini addopts / PYTEST_ADDOPTS.
INI_WAY_OUT = 'extra_args=["-o", "addopts="]'
ENV_WAY_OUT = 'env_vars={"PYTEST_ADDOPTS": ""}'

# Options that take a value, by spelling, mapped to their short form.
_VALUE_OPTIONS = {
    "-m": "-m",
    "-k": "-k",
    "-n": "-n",
    "--numprocesses": "-n",
    "-o": "-o",
    "--override-ini": "-o",
    "-c": "-c",
    "--config-file": "-c",
}
_FLAG_OPTIONS = frozenset({"--strict-markers", "--strict"})


@dataclass(frozen=True)
class PytestConfig:
    """What pyproject.toml says about pytest, or which other file pytest reads instead.

    Attributes:
        addopts: ini ``addopts`` tokens; empty when none.
        markers: Project marker names, in config order.
        strict_markers: Table value of ``strict_markers``; None when unset or
            of a type the table does not accept.
        strict: Table value of ``strict``; None when unset or of a type the
            table does not accept.
        not_read: The file pytest reads instead of pyproject.toml; the fields
            above are then empty.
    """

    addopts: list[str]
    markers: list[str]
    strict_markers: bool | None
    strict: bool | None
    not_read: str | None = None


@dataclass(frozen=True)
class OptionValue:
    """The value of an option and where pytest took it from.

    Attributes:
        value: The option value; ``""`` for an explicit empty value.
        source: ``pyproject.toml``, ``-o``, ``PYTEST_ADDOPTS``, ``markers``
            or ``extra_args``.
    """

    value: str
    source: str


@dataclass(frozen=True)
class EffectiveConfig:
    """The pytest config of one call: ini ``addopts``, ``PYTEST_ADDOPTS``, call.

    Attributes:
        config: The project config; None when it can't be read.
        not_read: The file pytest reads instead of pyproject.toml, from the
            config or ``-c`` / ``--config-file``.
        ini_source: Where the applied ini ``addopts`` come from:
            ``pyproject.toml``, ``-o`` (the call) or ``PYTEST_ADDOPTS``
            (an ``-o addopts=`` inside it).
        ini_tokens: The applied ini ``addopts``; empty when none, cleared or
            not read.
        env_tokens: The ``PYTEST_ADDOPTS`` tokens; empty when unset, empty or
            unparsable.
        m: The effective ``-m``; None when there is none.
        k: The effective ``-k``; None when there is none.
        numprocesses: The last ``-n`` / ``--numprocesses`` value is not ``0``.
        n: The effective ``-n`` / ``--numprocesses`` value and its source;
            None when there is none.
        strict_markers: Strict markers are on, from all sources.
        project_strict_markers: Strict markers are on from the project config
            alone: its ``addopts`` and table keys.
    """

    config: PytestConfig | None
    not_read: str | None
    ini_source: str
    ini_tokens: list[str]
    env_tokens: list[str]
    m: OptionValue | None
    k: OptionValue | None
    numprocesses: bool
    n: OptionValue | None
    strict_markers: bool
    project_strict_markers: bool


def _parse_bool(value: str) -> bool | None:
    """Parse one of pytest's bool spellings, case-insensitively.

    Args:
        value: The ini string value.

    Returns:
        The bool it spells, or None for any other text.
    """
    lowered = value.lower()
    if lowered in _TRUE_SPELLINGS:
        return True
    if lowered in _FALSE_SPELLINGS:
        return False
    return None


def _marker_name(entry: str) -> str:
    """Return the marker name of a ``markers`` entry: the text before ``(`` or ``:``."""
    for separator in "(:":
        entry = entry.split(separator, 1)[0]
    return entry.strip()


def _read_addopts(value: object, is_ini: bool) -> list[str]:
    """Return the ``addopts`` tokens of a string (ini_options only) or a list."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if is_ini and isinstance(value, str):
        try:
            return shlex.split(value)
        except ValueError:
            return []
    return []


def _read_markers(value: object, is_ini: bool) -> list[str]:
    """Return the marker names of a list or a multi-line string (ini only)."""
    if isinstance(value, list):
        entries = [str(v) for v in value]
    elif is_ini and isinstance(value, str):
        entries = value.splitlines()
    else:
        return []
    names = [_marker_name(entry) for entry in entries]
    return [name for name in names if name]


def _read_strict(value: object, is_ini: bool) -> bool | None:
    """Return a strict key's bool, or its bool spelling (ini_options only)."""
    if isinstance(value, bool):
        return value
    if is_ini and isinstance(value, str):
        return _parse_bool(value)
    return None


def _fallback_file(root: Path) -> str | None:
    """Find the ``tox.ini`` / ``setup.cfg`` that has a pytest section.

    Args:
        root: The project root.

    Returns:
        The file name, or None when neither has one.  An ``OSError`` from
        reading an existing file propagates.
    """
    for name, header in _FALLBACK_FILES:
        path = root / name
        if os.path.isfile(path) and any(
            line.strip() == header for line in read_file(path).splitlines()
        ):
            return name
    return None


def read_pytest_config(project_dir: str) -> PytestConfig | None:
    """Read the project's pytest config. Never raises; None when it can't be read.

    The dedicated pytest files win over pyproject.toml; ``tox.ini [pytest]`` and
    ``setup.cfg [tool:pytest]`` only when pyproject.toml has no pytest section
    (an ``ini_options`` table, even empty, or a non-empty ``[tool.pytest]``).

    Args:
        project_dir: Path to the project root.

    Returns:
        The config read from ``[tool.pytest.ini_options]`` or ``[tool.pytest]``,
        or one naming the file pytest reads instead in ``not_read``.  None when
        a file can't be read, pyproject.toml is not valid TOML, or both pytest
        tables are non-empty (pytest rejects that).
    """
    root = Path(project_dir)
    for name in DEDICATED_FILES:
        if os.path.isfile(root / name):
            return PytestConfig([], [], None, None, name)
    try:
        tool = read_pyproject_tool_tables(root)
        pytest_table = tool.get("pytest")
        if not isinstance(pytest_table, dict):
            pytest_table = {}
        ini = pytest_table.get("ini_options")
        if not isinstance(ini, dict):
            ini = None
        native = {k: v for k, v in pytest_table.items() if k != "ini_options"}
        if ini and native:
            return None
        if ini is None and not native:
            return PytestConfig([], [], None, None, _fallback_file(root))
    except (ValueError, OSError):
        return None

    # A non-empty [tool.pytest] wins over an empty ini_options.
    is_ini = not native
    table = native or ini or {}
    return PytestConfig(
        addopts=_read_addopts(table.get("addopts"), is_ini),
        markers=_read_markers(table.get("markers"), is_ini),
        strict_markers=_read_strict(table.get("strict_markers"), is_ini),
        strict=_read_strict(table.get("strict"), is_ini),
    )


def _option_spans(tokens: list[str]) -> list[tuple[int, int, str, str]]:
    """Find the tracked options in every spelling: ``-X v``, ``-Xv``, ``-X=v``.

    Long options are read as ``--long v`` and ``--long=v``; the flags
    ``--strict-markers`` and ``--strict`` have the value ``""``.

    Args:
        tokens: Command-line tokens.

    Returns:
        ``(start, end, short option, value)`` per occurrence, in token order;
        ``tokens[start:end]`` is the occurrence.
    """
    spans = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        name, has_value, rest = token.partition("=")
        if token in _FLAG_OPTIONS:
            spans.append((i, i + 1, token, ""))
        elif token in _VALUE_OPTIONS:
            if i + 1 < len(tokens):
                spans.append((i, i + 2, _VALUE_OPTIONS[token], tokens[i + 1]))
            i += 1
        elif token.startswith("--") and has_value and name in _VALUE_OPTIONS:
            spans.append((i, i + 1, _VALUE_OPTIONS[name], rest))
        elif token[:2] in _VALUE_OPTIONS:
            spans.append((i, i + 1, token[:2], token[2:].removeprefix("=")))
        i += 1
    return spans


def _option_events(tokens: list[str]) -> list[tuple[str, str]]:
    """Return ``(short option, value)`` for each tracked option, in token order."""
    return [(option, value) for _, _, option, value in _option_spans(tokens)]


def _env_addopts(env_vars: dict[str, str] | None) -> str:
    """Return the run's ``PYTEST_ADDOPTS``: ``os.environ`` overlaid with env_vars.

    Args:
        env_vars: The caller's env vars, if any; keys match case-insensitively
            on Windows.

    Returns:
        The value; ``""`` when unset.
    """
    value = os.environ.get("PYTEST_ADDOPTS", "")
    for key, env_value in (env_vars or {}).items():
        if key == "PYTEST_ADDOPTS" or (
            os.name == "nt" and key.upper() == "PYTEST_ADDOPTS"
        ):
            value = env_value
    return value


def _split(value: str) -> list[str]:
    """Split like a shell command line.

    Args:
        value: The command-line text.

    Returns:
        The tokens; ``[]`` when the quoting is unbalanced.
    """
    try:
        return shlex.split(value)
    except ValueError:
        return []


def _strict_markers_on(tokens: list[str], table: PytestConfig | None) -> bool:
    """Resolve strict markers per key, as pytest does: the last override wins.

    Args:
        tokens: The applied tokens, in pytest's order.
        table: The config whose table keys are the starting values, if any.

    Returns:
        ``strict_markers`` when set, else ``strict``.
    """
    strict_markers = table.strict_markers if table else None
    strict = table.strict if table else None
    for option, value in _option_events(tokens):
        key, _, setting = value.partition("=")
        if option == "--strict-markers":
            strict_markers = True
        elif option == "--strict":
            strict = True
        elif option == "-o" and key == "strict_markers":
            strict_markers = _parse_bool(setting)
        elif option == "-o" and key == "strict":
            strict = _parse_bool(setting)
    return strict_markers if strict_markers is not None else bool(strict)


def _scan_overrides(
    env_tokens: list[str], call_tokens: list[str]
) -> tuple[str | None, OptionValue | None]:
    """Find the last ``-c`` and ``-o addopts=`` in PYTEST_ADDOPTS, then the call.

    pytest picks the config file and its ``addopts`` before expanding them,
    so the same options inside ini ``addopts`` have no effect.

    Args:
        env_tokens: The ``PYTEST_ADDOPTS`` tokens.
        call_tokens: The markers ``-m`` and the sanitized extra_args.

    Returns:
        The ``-c`` file, if any, and the ``addopts`` override value with its
        source (``PYTEST_ADDOPTS`` or ``-o``), if any.
    """
    config_file = None
    override = None
    for source, tokens in (("PYTEST_ADDOPTS", env_tokens), ("-o", call_tokens)):
        for option, value in _option_events(tokens):
            if option == "-c":
                config_file = value
            elif option == "-o" and value.startswith("addopts="):
                override = OptionValue(value.removeprefix("addopts="), source)
    return config_file, override


def effective_config(
    project_dir: str,
    markers: list[str] | None,
    cleaned_args: list[str],
    env_vars: dict[str, str] | None,
) -> EffectiveConfig:
    """Combine ini ``addopts``, ``PYTEST_ADDOPTS`` and the call, in pytest's order.

    Never raises: an unreadable config gives ``config=None`` and no ini tokens.

    Args:
        project_dir: Path to the project root.
        markers: The ``markers`` parameter of run_pytest_check.
        cleaned_args: The sanitized extra_args.
        env_vars: The caller's env vars, if any.

    Returns:
        The effective config of the call.
    """
    config = read_pytest_config(project_dir)
    env_tokens = _split(_env_addopts(env_vars))
    marker_tokens = ["-m", " and ".join(markers)] if markers else []
    config_file, override = _scan_overrides(env_tokens, marker_tokens + cleaned_args)
    not_read = config_file or (config.not_read if config else None)

    project = None if not_read else config
    ini_source = override.source if override else "pyproject.toml"
    ini_tokens: list[str] = []
    if project is not None:
        ini_tokens = _split(override.value) if override else project.addopts

    sources = (
        (ini_source, ini_tokens),
        ("PYTEST_ADDOPTS", env_tokens),
        ("markers", marker_tokens),
        ("extra_args", cleaned_args),
    )
    last: dict[str, OptionValue] = {}
    for source, tokens in sources:
        for option, value in _option_events(tokens):
            last[option] = OptionValue(value, source)
    numprocesses = last.get("-n")
    return EffectiveConfig(
        config=config,
        not_read=not_read,
        ini_source=ini_source,
        ini_tokens=ini_tokens,
        env_tokens=env_tokens,
        m=last.get("-m"),
        k=last.get("-k"),
        numprocesses=numprocesses is not None and numprocesses.value != "0",
        n=numprocesses,
        strict_markers=_strict_markers_on(
            [token for _, tokens in sources for token in tokens], project
        ),
        project_strict_markers=project is not None
        and _strict_markers_on(project.addopts, project),
    )


def call_replaced_addopts_m(effective: EffectiveConfig) -> bool:
    """Return whether the call's ``-m`` replaced an ``-m`` of the defaults.

    Args:
        effective: The effective config of the call.

    Returns:
        True when the effective ``-m`` comes from ``markers`` or extra_args
        and the applied ini ``addopts`` or ``PYTEST_ADDOPTS`` hold an ``-m``.
    """
    if effective.m is None or effective.m.source not in ("markers", "extra_args"):
        return False
    return any(
        option == "-m"
        for tokens in (effective.ini_tokens, effective.env_tokens)
        for option, _ in _option_events(tokens)
    )


def _drop_m(tokens: list[str]) -> tuple[list[str], list[str]]:
    """Take the ``-m`` options, in all spellings, out of tokens.

    Args:
        tokens: Command-line tokens.

    Returns:
        The tokens without ``-m`` options, and the ``-m`` values.
    """
    m_spans = [span for span in _option_spans(tokens) if span[2] == "-m"]
    dropped = {i for start, end, _, _ in m_spans for i in range(start, end)}
    kept = [token for i, token in enumerate(tokens) if i not in dropped]
    return kept, [value for _, _, _, value in m_spans]


def _render_line(
    label: str, tokens: list[str], replaced_by: str | None, way_out: str | None
) -> str:
    """Render one ``addopts`` line, its replaced ``-m`` marked.

    Args:
        label: The line's label, e.g. ``addopts (pyproject.toml)``.
        tokens: The line's values.
        replaced_by: The source of the effective ``-m`` when it is not this
            line's; its ``-m`` values are then shown as replaced.
        way_out: The call argument that clears the line, if any.

    Returns:
        The line.
    """
    kept, replaced = _drop_m(tokens) if replaced_by else (tokens, [])
    line = f"{label}: {shlex.join(kept)}"
    if replaced:
        m_text = " ".join(f"-m {shlex.quote(value)}" for value in replaced)
        replacement = f"{m_text} was replaced by {replaced_by}"
        line = f"{line}; its {replacement}" if kept else f"{label}: {replacement}"
    if way_out:
        line += f" — to run without: {way_out}"
    return line


def _inline_override(env_tokens: list[str], ini_tokens: list[str]) -> list[str]:
    """Move the ``-m`` of the last ``-o addopts=X`` in env_tokens out of X.

    Args:
        env_tokens: The ``PYTEST_ADDOPTS`` tokens; they hold an ``-o addopts=``.
        ini_tokens: The tokens of its X.

    Returns:
        env_tokens with that override rewritten as ``-o addopts=<X without -m>``
        followed by X's ``-m`` options, so ``_render_line`` can mark them.
    """
    start, end = [
        (start, end)
        for start, end, option, value in _option_spans(env_tokens)
        if option == "-o" and value.startswith("addopts=")
    ][-1]
    kept, m_values = _drop_m(ini_tokens)
    m_tokens = [token for value in m_values for token in ("-m", value)]
    override = ["-o", f"addopts={shlex.join(kept)}"]
    return env_tokens[:start] + override + m_tokens + env_tokens[end:]


def addopts_notes(effective: EffectiveConfig) -> list[str]:
    """Render the applied defaults: ini ``addopts`` and ``PYTEST_ADDOPTS``.

    Args:
        effective: The effective config of the call.

    Returns:
        One line per applied source, or only the "not read" note; ``[]`` when
        nothing applied or the config can't be read.
    """
    if effective.not_read:
        return [f"pytest config is in {effective.not_read}, not read"]
    if effective.config is None:
        return []
    m_source = effective.m.source if effective.m else None
    notes = []
    if effective.ini_tokens and effective.ini_source != "PYTEST_ADDOPTS":
        notes.append(
            _render_line(
                f"addopts ({effective.ini_source})",
                effective.ini_tokens,
                m_source if m_source != effective.ini_source else None,
                INI_WAY_OUT if effective.ini_source == "pyproject.toml" else None,
            )
        )
    if effective.env_tokens:
        replaced_by = m_source if m_source != "PYTEST_ADDOPTS" else None
        tokens = effective.env_tokens
        if replaced_by and effective.ini_source == "PYTEST_ADDOPTS":
            tokens = _inline_override(tokens, effective.ini_tokens)
        notes.append(_render_line("PYTEST_ADDOPTS", tokens, replaced_by, ENV_WAY_OUT))
    return notes
