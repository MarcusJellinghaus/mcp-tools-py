"""Integration tests verifying environment variables reach pytest subprocesses."""

import sys
from pathlib import Path

import pytest

from mcp_tools_py.code_checker_pytest.runners import run_tests


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a minimal pytest project that inspects its own environment."""
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    # A test that asserts specific env vars are present
    (tests_dir / "test_env_check.py").write_text(
        "import os\n"
        "\n"
        "\n"
        "def test_custom_env_var():\n"
        '    val = os.environ.get("MY_CUSTOM_VAR")\n'
        '    assert val == "hello_from_runner", (\n'
        '        f"Expected MY_CUSTOM_VAR=hello_from_runner, got {val!r}"\n'
        "    )\n"
        "\n"
        "\n"
        "def test_python_isolation_env():\n"
        '    """Verify Python isolation vars set by prepare_env."""\n'
        '    assert os.environ.get("PYTHONUNBUFFERED") == "1"\n'
        '    assert os.environ.get("PYTHONDONTWRITEBYTECODE") == "1"\n'
        '    assert os.environ.get("PYTHONIOENCODING") == "utf-8"\n'
        "\n"
        "\n"
        "def test_mcp_vars_removed():\n"
        '    """MCP transport vars must be stripped from subprocess env."""\n'
        '    assert os.environ.get("MCP_STDIO_TRANSPORT") is None\n'
        '    assert os.environ.get("MCP_SERVER_NAME") is None\n'
        "\n"
        "\n"
        "def test_path_preserved():\n"
        '    """PATH must still be set so the subprocess can find executables."""\n'
        '    path = os.environ.get("PATH") or os.environ.get("Path") or ""\n'
        "    assert len(path) > 0\n"
    )
    return tmp_path


@pytest.mark.integration
class TestPytestRunnerEnvIntegration:
    """Verify env vars flow correctly through run_tests -> execute_command -> prepare_env."""

    def test_custom_env_vars_visible_in_subprocess(self, temp_project: Path) -> None:
        """Custom env_vars passed to run_tests must be visible inside tests."""
        report = run_tests(
            project_dir=str(temp_project),
            test_folder="tests",
            python_executable=sys.executable,
            extra_args=["-k", "test_custom_env_var"],
            env_vars={"MY_CUSTOM_VAR": "hello_from_runner"},
            timeout_seconds=30,
        )
        assert not report.summary.failed, (
            f"test_custom_env_var failed — env var not received. "
            f"passed={report.summary.passed}, failed={report.summary.failed}"
        )
        assert report.summary.passed == 1

    def test_python_isolation_applied(self, temp_project: Path) -> None:
        """Python isolation env vars from prepare_env must be set."""
        report = run_tests(
            project_dir=str(temp_project),
            test_folder="tests",
            python_executable=sys.executable,
            extra_args=["-k", "test_python_isolation_env"],
            timeout_seconds=30,
        )
        assert not report.summary.failed, (
            f"Python isolation vars missing. "
            f"passed={report.summary.passed}, failed={report.summary.failed}"
        )
        assert report.summary.passed == 1

    def test_mcp_vars_stripped(self, temp_project: Path) -> None:
        """MCP-specific env vars must be removed from subprocess."""
        import os

        original = os.environ.copy()
        try:
            os.environ["MCP_STDIO_TRANSPORT"] = "should_be_removed"
            os.environ["MCP_SERVER_NAME"] = "should_be_removed"

            report = run_tests(
                project_dir=str(temp_project),
                test_folder="tests",
                python_executable=sys.executable,
                extra_args=["-k", "test_mcp_vars_removed"],
                timeout_seconds=30,
            )
            assert not report.summary.failed, (
                f"MCP vars leaked into subprocess. "
                f"passed={report.summary.passed}, failed={report.summary.failed}"
            )
            assert report.summary.passed == 1
        finally:
            os.environ.clear()
            os.environ.update(original)

    def test_path_preserved(self, temp_project: Path) -> None:
        """PATH env var must be present in subprocess."""
        report = run_tests(
            project_dir=str(temp_project),
            test_folder="tests",
            python_executable=sys.executable,
            extra_args=["-k", "test_path_preserved"],
            timeout_seconds=30,
        )
        assert not report.summary.failed, (
            f"PATH not preserved in subprocess. "
            f"passed={report.summary.passed}, failed={report.summary.failed}"
        )
        assert report.summary.passed == 1

    def test_all_env_checks_pass_together(self, temp_project: Path) -> None:
        """Run all env checks in a single pytest invocation."""
        import os

        original = os.environ.copy()
        try:
            os.environ["MCP_STDIO_TRANSPORT"] = "should_be_removed"

            report = run_tests(
                project_dir=str(temp_project),
                test_folder="tests",
                python_executable=sys.executable,
                env_vars={"MY_CUSTOM_VAR": "hello_from_runner"},
                timeout_seconds=30,
            )
            assert not report.summary.failed, (
                f"Some env checks failed. "
                f"passed={report.summary.passed}, failed={report.summary.failed}"
            )
            assert report.summary.passed == 4
        finally:
            os.environ.clear()
            os.environ.update(original)
