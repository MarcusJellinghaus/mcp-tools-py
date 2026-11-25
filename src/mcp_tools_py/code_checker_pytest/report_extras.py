"""Report-level reply output selected by pytest's own flags: -rs, -rw, --durations."""

from dataclasses import dataclass

from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.pytest_config import EffectiveConfig
from mcp_tools_py.code_checker_pytest.report_data import (
    durations,
    folded_skips,
    skip_lines,
    stage_seconds,
    warning_groups,
    warning_line,
)
from mcp_tools_py.code_checker_pytest.reporting import Sections

# Deviation from pytest: a fixed default, independent of the -v the tool passes.
DEFAULT_DURATIONS_MIN = 0.005
# Sum of test stage durations above which the hint suggests --durations.
SLOW_RUN_SECONDS = 10.0
SNAPSHOT_NOTE = (
    "--snapshot-update was passed: baselines may have been rewritten; check git status."
)
DURATIONS_MIN_NOTE = "--durations-min has no effect without --durations."
_NO_EFFECT_TAIL = (
    "has no effect here; supported: -rs, -rw"
    " (failures are always shown; -s shows passing-test output)"
)

_SECTION_LETTERS = frozenset({"s", "w"})
# Letters this tool handles: sections, aliases, always-shown failures, resets.
_HANDLED_LETTERS = frozenset("sSwfFEaAN")
_RESETS = "aAN"
_CALL_SOURCE = "extra_args"


@dataclass(frozen=True)
class ReportFlags:
    """The report flags in effect for one call.

    Attributes:
        letters: Supported section letters (``s``, ``w``) of the effective
            ``-r`` after resolution.
        r_label: The call spelling of ``-r`` when it comes from extra_args,
            else None.
        no_effect: Unsupported or unknown letters for the note, only for a
            call ``-r``; ``""`` when none.
        durations: The effective ``--durations``; None when not in effect.
        durations_min: The effective ``--durations-min``, else
            ``DEFAULT_DURATIONS_MIN``.
        durations_min_in_call: ``--durations-min`` comes from extra_args.
        show_capture: The effective ``--show-capture`` value, if any.
        snapshot_update: ``--snapshot-update`` is in effect.
        disable_warnings: ``--disable-warnings`` (or its alias) is in effect.
    """

    letters: frozenset[str]
    r_label: str | None
    no_effect: str
    durations: int | None
    durations_min: float
    durations_min_in_call: bool
    show_capture: str | None
    snapshot_update: bool
    disable_warnings: bool


def resolve_report_chars(value: str) -> tuple[frozenset[str], str]:
    """Resolve an ``-r`` value like pytest's getreportopt, with this tool's deviations.

    ``S``/``F`` are aliases of ``s``/``f``; ``a`` is ``sxXEfw`` and ``A`` is
    ``PpsxXEfw`` (both include ``w`` here); ``N`` resets the list.

    Args:
        value: The effective ``-r`` value.

    Returns:
        The supported section letters in effect, and the letters without
        effect: unsupported or unknown letters after the last ``a``/``A``/``N``,
        in first-seen order.
    """
    opts = ""
    for char in value:
        char = char.lower() if char in "FS" else char
        if char == "a":
            opts = "sxXEfw"
        elif char == "A":
            opts = "PpsxXEfw"
        elif char == "N":
            opts = ""
        elif char not in opts:
            opts += char
    last_reset = max(value.rfind(char) for char in _RESETS)
    no_effect = ""
    for char in value[last_reset + 1 :]:
        if (
            char not in _HANDLED_LETTERS
            and not char.isspace()
            and char not in no_effect
        ):
            no_effect += char
    return frozenset(opts) & _SECTION_LETTERS, no_effect


def _count(value: str) -> int | None:
    """Read a ``--durations`` count.

    Returns:
        The count, or None when it is not a non-negative int.
    """
    try:
        count = int(value)
    except ValueError:
        return None
    return count if count >= 0 else None


def _seconds(value: str) -> float:
    """Read a ``--durations-min``.

    Returns:
        The seconds, or DEFAULT_DURATIONS_MIN when it is not a number.
    """
    try:
        return float(value)
    except ValueError:
        return DEFAULT_DURATIONS_MIN


def report_flags(effective: EffectiveConfig) -> ReportFlags:
    """Resolve the report flags of one call from its effective config.

    Args:
        effective: The effective config of the call.

    Returns:
        The flags in effect; label and "no effect" letters only for a call ``-r``.
    """
    options = effective.options
    r_option = options.get("-r")
    letters: frozenset[str] = frozenset()
    r_label = None
    no_effect = ""
    if r_option is not None:
        letters, no_effect = resolve_report_chars(r_option.value)
        if r_option.source == _CALL_SOURCE:
            r_label = r_option.label or f"-r{r_option.value}"
        else:
            no_effect = ""
    durations_option = options.get("--durations")
    min_option = options.get("--durations-min")
    show_capture = options.get("--show-capture")
    return ReportFlags(
        letters=letters,
        r_label=r_label,
        no_effect=no_effect,
        durations=_count(durations_option.value) if durations_option else None,
        durations_min=_seconds(min_option.value)
        if min_option
        else DEFAULT_DURATIONS_MIN,
        durations_min_in_call=min_option is not None
        and min_option.source == _CALL_SOURCE,
        show_capture=show_capture.value if show_capture else None,
        snapshot_update="--snapshot-update" in options,
        disable_warnings="--disable-warnings" in options,
    )


def _head_rows(header: str, rows: list[str], max_lines: int, max_chars: int) -> str:
    """Render a header and the first rows that fit; rows are sorted, so the head matters.

    Args:
        header: The section's first line.
        rows: The section's rows, most relevant first.
        max_lines: Line budget of the section.
        max_chars: Character budget of the section.

    Returns:
        The header and every row when they fit; else the header, the first
        rows and an omitted-count line; ``""`` when not even the header, one
        row and that line fit.
    """
    full = "\n".join([header, *rows])
    if len(full.splitlines()) <= max_lines and len(full) <= max_chars:
        return full
    best = ""
    used_lines = len(header.splitlines())
    used_chars = len(header)
    for kept, row in enumerate(rows, start=1):
        used_lines += len(row.splitlines())
        used_chars += len(row) + 1
        omitted = f"({len(rows) - kept} more rows not shown, budget used up.)"
        if used_lines + 1 > max_lines or used_chars + len(omitted) + 1 > max_chars:
            break
        best = "\n".join([header, *rows[:kept], omitted])
    return best


def _durations_section(
    report: PytestReport, flags: ReportFlags
) -> tuple[str, list[str]] | None:
    """Header and rows of the --durations section; None when there is no entry.

    Args:
        report: The parsed pytest report.
        flags: The report flags; ``durations`` is not None.

    Returns:
        The header and the rows at or above the minimum, then a hidden-count
        line when entries within the cut are below it.
    """
    count = flags.durations or 0
    entries = durations(report)
    cut = entries[:count] if count else entries
    if not cut:
        return None
    header = f"Slowest {count} durations:" if count else "Slowest durations:"
    rows = [
        f"{entry.seconds:.2f}s {entry.when} {entry.nodeid}"
        for entry in cut
        if entry.seconds >= flags.durations_min
    ]
    hidden = len(cut) - len(rows)
    if hidden:
        rows.append(
            f"({hidden} durations < {flags.durations_min:g}s hidden;"
            " pass --durations-min=0 to show them.)"
        )
    return header, rows


def report_sections(
    report: PytestReport, flags: ReportFlags, max_lines: int, max_chars: int
) -> str:
    """Render the -rs, -rw and --durations sections and the empty-result line.

    Each present section gets an even share of the budget left and is cut to
    its first rows; one whose first row does not fit is named in the dropped
    notice. The empty-result line is only for a call ``-r``.

    Args:
        report: The parsed pytest report.
        flags: The report flags in effect.
        max_lines: Line budget of the whole text.
        max_chars: Character budget of the whole text.

    Returns:
        The rendered sections, or ``""`` when there is nothing to show.
    """
    out = Sections(max_lines, max_chars)
    sections = flags.letters - ({"w"} if flags.disable_warnings else set())
    folded = folded_skips(report) if "s" in sections else []
    groups = warning_groups(report) if "w" in sections else []
    present: list[tuple[str, str, list[str]]] = []
    if folded:
        present.append(("skip reasons (-rs)", "Skip reasons:", skip_lines(folded)))
    if groups:
        rows = [warning_line(group) for group in groups]
        present.append(("warnings (-rw)", "Warnings:", rows))
    if flags.durations is not None:
        section = _durations_section(report, flags)
        if section is not None:
            present.append(("durations", *section))
    for index, (label, header, rows) in enumerate(present):
        share = len(present) - index
        text = _head_rows(header, rows, out.lines // share, out.chars // share - 1)
        if not (text and out.add(text)):
            out.dropped.append(label)
    if flags.r_label:
        empties = []
        if "s" in sections and not folded:
            empties.append("no skipped tests")
        if "w" in sections and not groups:
            empties.append("no warnings")
        if empties:
            out.add(f"{flags.r_label}: {', '.join(empties)}.")
    return out.text()


def hint_line(report: PytestReport, flags: ReportFlags) -> str | None:
    """The one hint line naming the flags that would expand this reply.

    The ``-r`` part is one combined value: every applicable letter plus the
    supported letters already in effect, so following it drops nothing.
    ``--durations=5`` joins when an ``-r`` part is offered or the test stages
    sum to more than ``SLOW_RUN_SECONDS``, unless ``--durations`` is in effect.

    Args:
        report: The parsed pytest report.
        flags: The report flags in effect.

    Returns:
        ``For details: extra_args=[...] (...)``, or None when nothing remains.
    """
    allowed = {"s", "w"} - ({"w"} if flags.disable_warnings else set())
    in_effect = flags.letters & allowed
    applicable: set[str] = set()
    if folded_skips(report):
        applicable.add("s")
    if report.warnings and not flags.disable_warnings:
        applicable.add("w")
    parts: list[str] = []
    why: list[str] = []
    if applicable - in_effect:
        letters = "".join(c for c in "sw" if c in applicable | in_effect)
        parts.append(f'"-r{letters}"')
        if "s" in letters:
            why.append("skip reasons")
        if "w" in letters:
            why.append("warnings — counted only by default")
    if flags.durations is None and (parts or stage_seconds(report) > SLOW_RUN_SECONDS):
        parts.append('"--durations=5"')
        why.append("slowest tests")
    if not parts:
        return None
    return f"For details: extra_args=[{', '.join(parts)}] ({', '.join(why)})"


def flag_notes(flags: ReportFlags) -> list[str]:
    """Notes for report flags with no or a surprising effect.

    Args:
        flags: The report flags in effect.

    Returns:
        In order: the "no effect" note for a call ``-r``, the
        ``--durations-min`` note when it is passed without ``--durations``,
        and the snapshot note for ``--snapshot-update`` from any source.
    """
    notes = []
    if flags.no_effect:
        notes.append(f"-r{flags.no_effect} {_NO_EFFECT_TAIL}")
    if flags.durations_min_in_call and flags.durations is None:
        notes.append(DURATIONS_MIN_NOTE)
    if flags.snapshot_update:
        notes.append(SNAPSHOT_NOTE)
    return notes
