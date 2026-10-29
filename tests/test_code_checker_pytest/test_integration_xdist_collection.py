"""Integration test verifying an xdist collection mismatch is reported as an error."""

import sys
from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.verdict import RunStatus


@pytest.mark.integration
def test_xdist_collection_mismatch_is_error(tmp_path: Path) -> None:
    """Workers collecting different parametrize ids abort the run as ERROR."""
    pytest.importorskip("xdist")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_now.py").write_text(
        "from datetime import datetime\n"
        "\n"
        "import pytest\n"
        "\n"
        "\n"
        '@pytest.mark.parametrize("value", [str(datetime.now())])\n'
        "def test_now(value):\n"
        "    assert value\n"
    )

    result = check_code_with_pytest(
        str(tmp_path),
        python_executable=sys.executable,
        extra_args=["-n", "2"],
        timeout_seconds=120,
    )

    assert result["verdict"].status is RunStatus.ERROR
    assert any(
        "Different tests were collected" in p for p in result["verdict"].problems
    )
