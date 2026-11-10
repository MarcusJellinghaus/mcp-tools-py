"""Tests for grouping failed collectors by cause on both reporting paths."""

from typing import List, Optional

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    ErrorContext,
    PytestReport,
    Summary,
)
from mcp_tools_py.code_checker_pytest.reporting import (
    MAX_COLLECTOR_IDS,
    PYTEST_HINT,
    XDIST_MARKER,
    collectors_failed_line,
    create_prompt_for_failed_tests,
    failed_collector_count,
    group_failed_collectors,
)
from mcp_tools_py.code_checker_pytest.verdict import classify_run, format_error_text

IMPORTLIB_FRAME = (
    "importlib\\__init__.py:126: in import_module\n    return _bootstrap()"
)


def _collector(
    nodeid: str, longrepr: Optional[str], outcome: str = "failed"
) -> Collector:
    return Collector(nodeid=nodeid, outcome=outcome, result=[], longrepr=longrepr)


def _report(collectors: List[Collector], exit_code: int = 2) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=exit_code,
        root="/tmp",
        environment={},
        summary=Summary(collected=0, total=0),
        collectors=collectors,
        error_context=ErrorContext(
            exit_code=exit_code,
            exit_code_meaning="",
            error_message="",
            suggestion="",
        ),
    )


def test_identical_e_lines_form_one_group() -> None:
    longrepr_a = "tests/a.py:1: in <module>\nE   ImportError: root cause"
    longrepr_b = "tests/b.py:7: in <module>\nE   ImportError: root cause"
    report = _report(
        [_collector("tests/a.py", longrepr_a), _collector("tests/b.py", longrepr_b)]
    )

    groups = group_failed_collectors(report)

    assert groups == [
        "E   ImportError: root cause\n"
        f"{longrepr_a}\n"
        "same error in 1 more collector: tests/b.py"
    ]


def test_conftests_with_same_first_frame_stay_separate() -> None:
    report = _report(
        [
            _collector(
                "tests/conf_a",
                f"{IMPORTLIB_FRAME}\nE   ModuleNotFoundError: No module named 'a_xyz'",
            ),
            _collector(
                "tests/conf_b",
                f"{IMPORTLIB_FRAME}\nE   ModuleNotFoundError: No module named 'b_xyz'",
            ),
        ]
    )

    groups = group_failed_collectors(report)

    assert len(groups) == 2
    assert "a_xyz" in groups[0]
    assert "b_xyz" in groups[1]


def test_syntax_errors_naming_different_files_stay_separate() -> None:
    report = _report(
        [
            _collector(
                "tests/a.py",
                'E     File "tests/a.py", line 1\nE   SyntaxError: invalid syntax',
            ),
            _collector(
                "tests/b.py",
                'E     File "tests/b.py", line 1\nE   SyntaxError: invalid syntax',
            ),
        ]
    )

    assert len(group_failed_collectors(report)) == 2


def test_repeated_node_id_counts_once_without_same_error_line() -> None:
    longrepr = "E   ImportError: root cause"
    report = _report(
        [_collector("tests/a.py", longrepr), _collector("tests/a.py", longrepr)]
    )

    groups = group_failed_collectors(report)

    assert failed_collector_count(report) == 1
    assert len(groups) == 1
    assert "same error" not in groups[0]
    assert collectors_failed_line(report) == "1 collector failed (1 distinct error)"


def test_group_lists_capped_node_ids() -> None:
    report = _report(
        [_collector(f"tests/t{i}.py", "E   ImportError: x") for i in range(13)]
    )

    groups = group_failed_collectors(report)

    assert len(groups) == 1
    same_error = groups[0].splitlines()[-1]
    listed = [f"tests/t{i}.py" for i in range(1, MAX_COLLECTOR_IDS + 1)]
    assert same_error == (
        f"same error in 12 more collectors: {', '.join(listed)}, … and 2 more"
    )
    assert collectors_failed_line(report) == "13 collectors failed (1 distinct error)"


def test_no_truncation_suffix_when_all_ids_fit() -> None:
    report = _report(
        [
            _collector(f"tests/t{i}.py", "E   ImportError: x")
            for i in range(MAX_COLLECTOR_IDS + 1)
        ]
    )

    assert "… and" not in group_failed_collectors(report)[0]


def test_no_e_line_falls_back_to_last_non_empty_line() -> None:
    report = _report(
        [
            _collector("tests/a.py", "frame a\nImportError: x\n\n"),
            _collector("tests/b.py", "frame b\nImportError: x"),
            _collector("tests/c.py", "frame a\nImportError: y"),
        ]
    )

    groups = group_failed_collectors(report)

    assert len(groups) == 2
    assert groups[0].startswith("frame a\nImportError: x")
    assert groups[0].endswith("same error in 1 more collector: tests/b.py")
    assert groups[1] == "frame a\nImportError: y"


def test_xdist_marker_texts_with_different_workers_form_one_group() -> None:
    report = _report(
        [
            _collector("gw1", f"{XDIST_MARKER} between gw0 and gw1"),
            _collector("gw2", f"{XDIST_MARKER} between gw0 and gw2"),
        ]
    )

    groups = group_failed_collectors(report)

    assert len(groups) == 1
    assert "gw0 and gw1" in groups[0]
    assert "same error in 1 more collector: gw2" in groups[0]


def test_collector_without_longrepr_is_counted_but_forms_no_group() -> None:
    report = _report(
        [
            _collector("tests/a.py", "E   ImportError: x"),
            _collector("tests/b.py", None),
        ]
    )

    assert failed_collector_count(report) == 2
    assert len(group_failed_collectors(report)) == 1
    assert collectors_failed_line(report) == "2 collectors failed (1 distinct error)"


def test_collectors_without_longrepr_show_no_distinct_errors() -> None:
    report = _report([_collector("tests/a.py", None), _collector("tests/b.py", None)])

    assert collectors_failed_line(report) == "2 collectors failed"


def test_error_path_without_longrepr_shows_count_above_output_tail() -> None:
    report = _report([_collector("tests/a.py", None), _collector("tests/b.py", None)])
    assert report.error_context is not None
    report.error_context.error_message = "collection output tail"

    text = format_error_text(report, classify_run(report))

    assert "Problems:\n2 collectors failed\n\ncollection output tail" in text
    assert "distinct" not in text


def test_passed_collectors_are_ignored() -> None:
    report = _report([_collector("tests", "E   ignored", outcome="passed")])

    assert failed_collector_count(report) == 0
    assert not group_failed_collectors(report)
    assert collectors_failed_line(report) == ""


def test_count_line_pluralizes_distinct_errors() -> None:
    report = _report(
        [
            _collector("tests/a.py", "E   ImportError: x"),
            _collector("tests/b.py", "E   ImportError: y"),
        ]
    )

    assert collectors_failed_line(report) == "2 collectors failed (2 distinct errors)"


def test_error_path_has_count_line_right_after_problems() -> None:
    report = _report([_collector("tests/a.py", "E   ImportError: x")])

    text = format_error_text(report, classify_run(report))

    assert (
        "Problems:\n1 collector failed (1 distinct error)\n\nE   ImportError: x" in text
    )


def test_failed_path_has_count_line() -> None:
    report = _report(
        [
            _collector("tests/a.py", "E   ImportError: x"),
            _collector("tests/b.py", "E   ImportError: x"),
        ],
        exit_code=1,
    )

    prompt = create_prompt_for_failed_tests(report)

    assert prompt is not None
    assert prompt.startswith(
        "2 collectors failed (1 distinct error)\n\nE   ImportError: x\n"
    )
    assert "same error in 1 more collector: tests/b.py\n\n" in prompt


def test_failed_path_bounds_collector_part() -> None:
    report = _report(
        [_collector(f"tests/t{i}.py", f"E   ImportError: {i}") for i in range(20)],
        exit_code=1,
    )

    prompt = create_prompt_for_failed_tests(report, max_lines=30)

    assert prompt is not None
    assert "lines /" in prompt and "omitted" in prompt
    assert "ImportError: 10" not in prompt
    assert len(prompt.splitlines()) <= 30
    assert prompt.endswith(PYTEST_HINT)
