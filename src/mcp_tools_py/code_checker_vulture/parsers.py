"""Parser for vulture's text output."""

import re
from typing import NamedTuple

_LINE_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+): (?P<msg>.+?) "
    r"\((?P<conf>\d+)% confidence(?:, \d+ lines?)?\)$"
)
_NAMED_RE = re.compile(r"^(?P<kind>unused [a-z ]+?) '(?P<name>[^']+)'$")


class VultureMessage(NamedTuple):
    """One vulture finding.

    `kind` is e.g. "unused function", or the full message for kinds that name
    no symbol ("unreachable code after 'return'", "unsatisfiable 'if'
    condition"), whose `name` is None.
    """

    file: str
    line: int
    kind: str
    name: str | None
    message: str
    confidence: int


def parse_vulture_output(text: str) -> tuple[list[VultureMessage], list[str]]:
    """Parse vulture's output lines; file paths use "/" separators.

    Returns:
        The parsed messages and the non-blank lines that did not parse.
    """
    messages: list[VultureMessage] = []
    unparsed: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        match = _LINE_RE.match(line)
        if match is None:
            unparsed.append(line)
            continue
        msg = match["msg"]
        named = _NAMED_RE.match(msg)
        messages.append(
            VultureMessage(
                file=match["file"].replace("\\", "/"),
                line=int(match["line"]),
                kind=named["kind"] if named else msg,
                name=named["name"] if named else None,
                message=msg,
                confidence=int(match["conf"]),
            )
        )
    return messages, unparsed
