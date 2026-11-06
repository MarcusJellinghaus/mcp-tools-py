"""Tests for run_pytest_check(use_last_coverage_run=True)."""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utils.tool_context import ToolContext
from tests._coverage_project import _run_pytest_check, _write_project

NO_RUN = "No saved coverage run. Run with coverage=True first."


@pytest.fixture
def mock_pytest_run() -> Iterator[MagicMock]:
    """Stand in for the pytest run, which reuse must never start."""
    with patch(
        "mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest"
    ) as mock_run:
        yield mock_run


class TestArguments:
    """Test which arguments reuse accepts, without a real project."""

    @pytest.mark.parametrize(
        ("name", "value"),
        [
            ("markers", ["unit"]),
            ("extra_args", ["-x"]),
            ("env_vars", {"A": "1"}),
            ("timeout_seconds", 5),
            ("coverage", True),
        ],
    )
    def test_conflicting_argument_is_refused_by_name(
        self, tmp_path: Path, mock_pytest_run: MagicMock, name: str, value: Any
    ) -> None:
        """The error names the argument and pytest doesn't run."""
        result = _run_pytest_check(tmp_path)(
            use_last_coverage_run=True, **{name: value}
        )

        assert result == (
            f"Error: use_last_coverage_run=True cannot be used with: {name}."
        )
        mock_pytest_run.assert_not_called()

    def test_all_conflicts_are_named(
        self, tmp_path: Path, mock_pytest_run: MagicMock
    ) -> None:
        """Several conflicting arguments are listed together."""
        result = _run_pytest_check(tmp_path)(
            use_last_coverage_run=True, markers=["unit"], coverage=True
        )

        assert result.endswith("cannot be used with: markers, coverage.")
        mock_pytest_run.assert_not_called()

    def test_empty_values_count_as_not_passed(
        self, tmp_path: Path, mock_pytest_run: MagicMock
    ) -> None:
        """Empty collections and a None timeout are no conflict."""
        result = _run_pytest_check(tmp_path)(
            use_last_coverage_run=True,
            markers=[],
            extra_args=[],
            env_vars={},
            timeout_seconds=None,
            coverage=False,
        )

        assert result == NO_RUN
        mock_pytest_run.assert_not_called()

    def test_zero_timeout_counts_as_passed(
        self, tmp_path: Path, mock_pytest_run: MagicMock
    ) -> None:
        """Only None means no timeout was given."""
        result = _run_pytest_check(tmp_path)(
            use_last_coverage_run=True, timeout_seconds=0
        )

        assert "timeout_seconds" in result
        mock_pytest_run.assert_not_called()

    def test_works_with_pytest_unavailable(
        self,
        tmp_path: Path,
        mock_pytest_run: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Reuse runs before the availability gates, as it needs no pytest."""
        tool = _run_pytest_check(tmp_path)
        monkeypatch.setattr(ToolContext, "is_tool_available", lambda *_: False)

        assert tool(use_last_coverage_run=True) == NO_RUN
        mock_pytest_run.assert_not_called()


@pytest.fixture
def covered_project(tmp_path: Path) -> Path:
    """A real project with one saved coverage run."""
    _write_project(tmp_path)
    _run_pytest_check(tmp_path)(coverage=True)
    return tmp_path


@pytest.mark.integration
@pytest.mark.skipif(
    importlib.util.find_spec("pytest_cov") is None,
    reason="pytest-cov is not installed",
)
class TestRealProject:
    """Test reuse after a real coverage run."""

    def test_returns_the_digest_without_running_pytest(
        self, covered_project: Path, mock_pytest_run: MagicMock
    ) -> None:
        """The saved numbers and qualifiers come back; pytest doesn't run."""
        result = _run_pytest_check(covered_project)(use_last_coverage_run=True)

        assert "stmts" in result
        assert "selection: full suite" in result
        assert "fail_under=99 is configured; not applied to this run" in result
        assert "uncovered  6-7" in result
        mock_pytest_run.assert_not_called()

    def test_no_saved_run_names_coverage_true(self, tmp_path: Path) -> None:
        """A project that never ran with coverage has nothing to reuse."""
        _write_project(tmp_path)

        result = _run_pytest_check(tmp_path)(use_last_coverage_run=True)

        assert "coverage=True" in result
        assert "stmts" not in result

    @pytest.mark.parametrize(
        "change",
        [
            pytest.param(("edit", "src/pkg/mod.py"), id="edit-source"),
            pytest.param(("add", "src/pkg/new.py"), id="add-source"),
            pytest.param(("delete", "src/pkg/mod.py"), id="delete-source"),
            pytest.param(("edit", "tests/test_mod.py"), id="edit-test"),
            pytest.param(("add", "tests/test_new.py"), id="add-test"),
            pytest.param(("delete", "tests/test_mod.py"), id="delete-test"),
        ],
    )
    def test_changed_file_is_stale_with_no_numbers(
        self, covered_project: Path, change: tuple[str, str]
    ) -> None:
        """Any edited, new or deleted Python file in scope makes the data stale."""
        kind, relative = change
        path = covered_project / relative
        if kind == "delete":
            path.unlink()
        else:
            with path.open("a", encoding="utf-8") as file:
                file.write("# changed\n")

        result = _run_pytest_check(covered_project)(use_last_coverage_run=True)

        assert result.startswith("stale — rerun: 1 file changed")
        assert "stmts" not in result

    def test_max_modules_zero_applies(self, covered_project: Path) -> None:
        """The overview stays and the ranking goes."""
        result = _run_pytest_check(covered_project)(
            use_last_coverage_run=True, max_modules=0
        )

        assert "stmts" in result
        assert "uncovered  6-7" not in result

    def test_narrowing_to_a_measured_directory(self, covered_project: Path) -> None:
        """A directory under the measured source gives a digest."""
        result = _run_pytest_check(covered_project)(
            use_last_coverage_run=True, coverage_source=["src/pkg"]
        )

        assert "stmts" in result

    def test_out_of_scope_coverage_source_is_refused(
        self, covered_project: Path
    ) -> None:
        """Tests were not measured, so narrowing to them gives no numbers."""
        result = _run_pytest_check(covered_project)(
            use_last_coverage_run=True, coverage_source=["tests"]
        )

        assert "'tests'" in result
        assert "stmts" not in result
