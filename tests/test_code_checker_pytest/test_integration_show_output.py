"""Integration tests verifying captured output of passing tests reaches the report."""

import sys
from pathlib import Path
from typing import List

import pytest

from mcp_tools_py.code_checker_pytest.reporting import create_prompt_for_passing_output
from mcp_tools_py.code_checker_pytest.runners import run_tests


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a minimal pytest project whose passing test prints in every stage."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_prints.py").write_text(
        "import sys\n"
        "\n"
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.fixture\n"
        "def probe():\n"
        '    print("SETUP_PROBE")\n'
        "    yield\n"
        '    print("TEARDOWN_PROBE")\n'
        "\n"
        "\n"
        "def test_prints(probe):\n"
        '    print("HELLO_PROBE")\n'
        '    sys.stderr.write("STDERR_PROBE\\n")\n'
    )
    return tmp_path


@pytest.mark.integration
class TestPassingOutputIntegration:
    """Verify json-report captures passing-test output serially and under xdist."""

    @pytest.mark.parametrize("n_args", [["-n", "0"], ["-n", "2"]])
    def test_captured_output_of_passing_test(
        self, temp_project: Path, n_args: List[str]
    ) -> None:
        """Setup, call, teardown and stderr output all appear in the prompt."""
        report = run_tests(
            project_dir=str(temp_project),
            test_folder="tests",
            python_executable=sys.executable,
            extra_args=n_args,
            timeout_seconds=60,
        )
        assert report.summary.passed == 1

        result = create_prompt_for_passing_output(report)

        for probe in ("SETUP_PROBE", "HELLO_PROBE", "TEARDOWN_PROBE", "STDERR_PROBE"):
            assert probe in result
