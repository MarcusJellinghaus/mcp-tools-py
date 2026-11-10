"""Tests for code_checker_vulture.parsers module."""

import pytest

from mcp_tools_py.code_checker_vulture.parsers import (
    VultureMessage,
    parse_vulture_output,
)


@pytest.mark.parametrize(
    "kind",
    [
        "unused import",
        "unused function",
        "unused class",
        "unused method",
        "unused variable",
        "unused attribute",
        "unused property",
    ],
)
def test_parses_named_kinds(kind: str) -> None:
    messages, unparsed = parse_vulture_output(
        f"src/a.py:12: {kind} 'foo' (60% confidence)"
    )

    assert unparsed == []
    assert messages == [
        VultureMessage(
            file="src/a.py",
            line=12,
            kind=kind,
            name="foo",
            message=f"{kind} 'foo'",
            confidence=60,
        )
    ]


@pytest.mark.parametrize(
    "message",
    [
        "unreachable code after 'return'",
        "unsatisfiable 'if' condition",
        "unsatisfiable 'while' condition",
        "unsatisfiable 'ternary' condition",
    ],
)
def test_parses_unnamed_kinds(message: str) -> None:
    messages, unparsed = parse_vulture_output(
        f"src/a.py:7: {message} (100% confidence)"
    )

    assert unparsed == []
    assert len(messages) == 1
    assert messages[0].kind == message
    assert messages[0].name is None
    assert messages[0].message == message
    assert messages[0].confidence == 100


@pytest.mark.parametrize("suffix", [", 3 lines", ", 1 line"])
def test_size_suffix_is_accepted(suffix: str) -> None:
    messages, unparsed = parse_vulture_output(
        f"src/a.py:7: unused function 'foo' (60% confidence{suffix})"
    )

    assert unparsed == []
    assert messages[0].name == "foo"
    assert messages[0].confidence == 60


def test_windows_path_is_normalised() -> None:
    messages, _ = parse_vulture_output(
        "C:\\x\\a.py:12: unused variable 'bar' (60% confidence)"
    )

    assert messages[0].file == "C:/x/a.py"
    assert messages[0].line == 12
    assert messages[0].name == "bar"


def test_stderr_lines_go_to_unparsed() -> None:
    text = (
        "src/a.py:1: unused import 'os' (90% confidence)\n"
        "\n"
        "Warning: something odd\n"
        "src/b.py:2: unused class 'C' (60% confidence)\n"
    )

    messages, unparsed = parse_vulture_output(text)

    assert [m.file for m in messages] == ["src/a.py", "src/b.py"]
    assert unparsed == ["Warning: something odd"]


def test_empty_output() -> None:
    assert parse_vulture_output("") == ([], [])
