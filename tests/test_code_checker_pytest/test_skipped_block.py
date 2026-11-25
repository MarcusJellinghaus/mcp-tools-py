"""Tests for report_extras.skipped_block: the exit-5 skip count and reasons."""

from pathlib import Path

from mcp_tools_py.code_checker_pytest.models import Collector, PytestReport, Summary
from mcp_tools_py.code_checker_pytest.report_extras import skipped_block
from mcp_tools_py.code_checker_pytest.reporting import DROPPED_NOTICE

BIG_LINES = 500
BIG_CHARS = 50_000


def _module_skip(root: Path, name: str, reason: str = "no db") -> Collector:
    """A collector skipped at module level in tests/<name>:3."""
    longrepr = str((str(root / "tests" / name), 3, f"Skipped: {reason}"))
    return Collector(
        nodeid=f"tests/{name}", outcome="skipped", result=[], longrepr=longrepr
    )


def _exit5_report(root: Path, collectors: list[Collector]) -> PytestReport:
    """An exit-5 report: no tests, the given collectors."""
    return PytestReport(
        created=0.0,
        duration=0.5,
        exitcode=5,
        root=str(root),
        environment={},
        summary=Summary(collected=0, total=0),
        collectors=collectors,
        tests=None,
    )


class TestSkippedBlock:
    """skipped_block: the count and folded skip lines of an exit-5 run."""

    def test_two_module_skips(self, tmp_path: Path) -> None:
        """The count, then one skip line per collector."""
        report = _exit5_report(
            tmp_path,
            [_module_skip(tmp_path, "test_a.py"), _module_skip(tmp_path, "test_b.py")],
        )
        assert skipped_block(report, BIG_LINES, BIG_CHARS) == (
            "⏭️ Skipped: 2\n"
            "SKIPPED [1] tests/test_a.py:3: no db\n"
            "SKIPPED [1] tests/test_b.py:3: no db"
        )

    def test_nothing_skipped(self, tmp_path: Path) -> None:
        """No skipped collector or test gives an empty block."""
        collector = Collector(nodeid="tests/test_a.py", outcome="passed", result=[])
        report = _exit5_report(tmp_path, [collector])
        assert skipped_block(report, BIG_LINES, BIG_CHARS) == ""

    def test_reasons_over_budget(self, tmp_path: Path) -> None:
        """Reasons that do not fit are named in the dropped notice; the count stays."""
        collectors = [
            _module_skip(tmp_path, f"test_{i}.py", f"reason {i}") for i in range(50)
        ]
        block = skipped_block(_exit5_report(tmp_path, collectors), 10, 2000)
        lines = block.splitlines()
        assert lines[0] == "⏭️ Skipped: 50"
        assert lines[-1] == f"{DROPPED_NOTICE} skip reasons"
        assert len(lines) <= 10
        assert len(block) <= 2000

    def test_unparsable_reasons(self, tmp_path: Path) -> None:
        """A skip without a readable reason still gives the count, no notice."""
        collector = Collector(
            nodeid="tests/test_a.py", outcome="skipped", result=[], longrepr=None
        )
        report = _exit5_report(tmp_path, [collector])
        assert skipped_block(report, BIG_LINES, BIG_CHARS) == "⏭️ Skipped: 1"
