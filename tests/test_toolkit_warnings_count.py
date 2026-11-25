"""The toolkit's test action never shows the run_pytest_check warnings count."""

from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary
from mcp_tools_py.code_checker_pytest.models import Warning as ReportWarning
from mcp_tools_py.code_checker_pytest.reporting import get_test_summary
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.toolkit import PythonToolkit
from tests._pytest_results import make_pytest_results


def _warned_report() -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=0.0,
        exitcode=0,
        root="",
        environment={},
        summary=Summary(collected=3, total=3, passed=3),
        warnings=[ReportWarning(message="w1"), ReportWarning(message="w2")],
    )


@pytest.mark.parametrize("status", [RunStatus.PASSED, RunStatus.ERROR])
def test_toolkit_summary_has_no_warnings_count(
    tmp_path: Path, status: RunStatus
) -> None:
    """A warning-bearing report reaches _run_test; its summary has no count."""
    report = _warned_report()
    results = make_pytest_results(
        status,
        ["worker crashed"] if status is RunStatus.ERROR else None,
        test_results=report,
        summary_text=get_test_summary(report),
    )
    request = ActionRequest(
        action="test", depth="standard", project_dir=tmp_path, params={}
    )
    with patch("mcp_tools_py.toolkit.check_code_with_pytest", return_value=results):
        result = PythonToolkit().run(request)
    assert "Passed: 3" in result.summary
    assert "⚠️ Warnings" not in result.summary
