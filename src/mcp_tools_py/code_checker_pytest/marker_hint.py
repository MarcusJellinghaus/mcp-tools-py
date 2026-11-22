"""Name the ``-m`` marker names a failed run can blame, and what the project registers."""

import re

from mcp_tools_py.code_checker_pytest.pytest_config import EffectiveConfig

# pytest's built-in markers; they count as registered.
BUILTIN_MARKERS = frozenset(
    {
        "skip",
        "skipif",
        "xfail",
        "parametrize",
        "usefixtures",
        "filterwarnings",
        "tryfirst",
        "trylast",
    }
)
STRICT_SUGGESTION = (
    "To have pytest reject unknown -m names (pytest 9+), turn on strict markers in "
    "the project config (--strict-markers in addopts, or strict_markers = true); "
    "tests carrying unregistered marks then fail collection."
)
RERUN_TIP = (
    "Under pytest-xdist pytest's own message is lost; to see it, "
    'rerun with extra_args=["-n", "0"].'
)

_KEYWORDS = frozenset({"and", "or", "not"})
# pytest's -m tokens: punctuation, a quoted string or an identifier; any other
# character is a token of its own that makes the expression invalid.
_TOKEN = re.compile(r"""[(),=]|'[^']*'|"[^"]*"|[\w:+\-.\[\]\\/]+|\S""")
_IDENT = re.compile(r"[\w:+\-.\[\]\\/]+")
_UNKNOWN_MARKERS = re.compile(
    r"Unknown marker\(s\) in '-m' expression: (.*)\. Use 'pytest --markers'"
)
_UNKNOWN_PREFIX = "ERROR: Unknown marker(s)"


def _is_ident(token: str) -> bool:
    """Return whether token is an identifier: not a keyword, only ident characters."""
    return token not in _KEYWORDS and _IDENT.fullmatch(token) is not None


def _is_string(token: str) -> bool:
    """Return whether token is a quoted string."""
    return len(token) > 1 and token[0] in "'\"" and token[-1] == token[0]


def _skip_kwargs(tokens: list[str], start: int) -> tuple[int, bool]:
    """Read ``(key=value, …)`` starting at the ``(`` at tokens[start].

    Args:
        tokens: The expression tokens.
        start: Index of the ``(``.

    Returns:
        The index after the closing ``)``, or after the next ``)`` (or the
        end) when the arguments are malformed, and whether they are well formed.
    """
    i = start + 1
    while True:
        key, equal, value = (tokens[i : i + 3] + ["", "", ""])[:3]
        if _is_ident(key) and equal == "=" and (_is_ident(value) or _is_string(value)):
            i += 3
            if tokens[i : i + 1] == [")"]:
                return i + 1, True
            if tokens[i : i + 1] == [","]:
                i += 1
                continue
        rest = tokens[i:]
        return (i + rest.index(")") + 1 if ")" in rest else len(tokens)), False


def scan_expression(expr: str) -> tuple[list[tuple[str, bool]], bool]:
    """Find the names in a ``-m`` expression and whether it parses.

    One pass over pytest's grammar: a stack holds the ``not`` parity per
    parenthesis level, and an operand/operator state checks validity.

    Args:
        expr: The ``-m`` expression.

    Returns:
        ``(name, negated)`` per name in order, negated meaning under an odd
        number of ``not``; and whether pytest's grammar accepts the expression.
        ``name(key=value)`` arguments are not names; ``True`` / ``False`` /
        ``None`` at top level are.
    """
    tokens = _TOKEN.findall(expr)
    stack = [0]
    pending = 0
    operand = True
    valid = True
    names: list[tuple[str, bool]] = []
    i = 0
    while i < len(tokens):
        part = tokens[i]
        i += 1
        if operand:
            if part == "not":
                pending += 1
            elif part == "(":
                stack.append((stack[-1] + pending) % 2)
                pending = 0
            elif _is_ident(part):
                names.append((part, (stack[-1] + pending) % 2 == 1))
                pending = 0
                operand = False
                if tokens[i : i + 1] == ["("]:
                    i, well_formed = _skip_kwargs(tokens, i)
                    valid = valid and well_formed
            else:
                valid = False
        elif part in ("and", "or"):
            operand = True
        elif part == ")" and len(stack) > 1:
            stack.pop()
        else:
            if _is_ident(part):
                names.append((part, False))
            valid = False
    return names, valid and not operand and len(stack) == 1


def unknown_marker_names(error_line: str) -> list[str]:
    """Read the names from pytest's ``Unknown marker(s) in '-m' expression`` line.

    Args:
        error_line: pytest's ``ERROR:`` line.

    Returns:
        The names in pytest's order; ``[]`` when the line is not that message.
    """
    match = _UNKNOWN_MARKERS.search(error_line)
    if match is None:
        return []
    return [name for name in match.group(1).split(", ") if name]


def _counted_names(
    effective: EffectiveConfig, exit_code: int | None, marker_error: str | None
) -> list[str]:
    """Return the unregistered names the hint names, deduplicated, order kept.

    Args:
        effective: The effective config of the call; it has a non-empty ``-m``.
        exit_code: pytest's exit code, if known.
        marker_error: pytest's ``ERROR:`` line for a ``-m`` problem, if any.

    Returns:
        pytest's names on an ``Unknown marker(s)`` error, else the unregistered
        names of the expression that can explain the exit code; ``[]`` when
        the config is not read.
    """
    config = effective.config
    if config is None or effective.not_read is not None or effective.m is None:
        return []
    if marker_error and marker_error.startswith(_UNKNOWN_PREFIX):
        names = unknown_marker_names(marker_error)
    elif (
        exit_code == 5
        or (exit_code == 4 and marker_error)
        or (exit_code == 3 and effective.strict_markers)
    ):
        scanned, valid = scan_expression(effective.m.value)
        registered = BUILTIN_MARKERS | set(config.markers)
        names = [
            name
            for name, negated in scanned
            if name not in registered
            and (not negated or effective.strict_markers or not valid)
        ]
    else:
        return []
    return list(dict.fromkeys(names))


def _hint(names: list[str], registered: list[str]) -> str:
    """Render the marker hint for names.

    Args:
        names: The counted names.
        registered: The project's marker names, in config order.

    Returns:
        The hint, listing the project's markers or saying it registers none.
    """
    listed = ", ".join(f"`{name}`" for name in names)
    verb = "is" if len(names) == 1 else "are"
    if registered:
        tail = f"Registered: {', '.join(registered)}"
    else:
        tail = "The project config registers none."
    return f"{listed} {verb} not registered in the project config. {tail}"


def marker_notes(
    effective: EffectiveConfig, exit_code: int | None, marker_error: str | None
) -> list[str]:
    """Render pytest's ``-m`` ERROR line, the marker hint and its tips.

    Args:
        effective: The effective config of the call.
        exit_code: pytest's exit code, if known.
        marker_error: pytest's ``ERROR:`` line for a ``-m`` problem, if any.

    Returns:
        pytest's ``ERROR:`` line on exit 4; then, for a run with a non-empty
        ``-m``, the hint naming the counted names, the ``--strict-markers``
        suggestion when the project config doesn't turn strict markers on,
        and the ``-n 0`` rerun tip on exit 3 with ``-n`` in effect.
    """
    notes = [marker_error] if exit_code == 4 and marker_error else []
    if effective.m is None or not effective.m.value.strip():
        return notes
    counted = _counted_names(effective, exit_code, marker_error)
    if counted and effective.config is not None:
        notes.append(_hint(counted, effective.config.markers))
        if not effective.project_strict_markers:
            notes.append(STRICT_SUGGESTION)
    if exit_code == 3 and effective.numprocesses:
        notes.append(RERUN_TIP)
    return notes
