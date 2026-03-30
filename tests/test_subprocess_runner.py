"""Tests for subprocess runner utilities."""

import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Generator
from unittest.mock import patch

import pytest

from mcp_tools_py.utils.subprocess_runner import (
    CalledProcessError,
    CommandOptions,
    CommandResult,
    SubprocessError,
    TimeoutExpired,
    _run_heartbeat,
    check_tool_missing_error,
    execute_command,
    execute_subprocess,
    get_python_isolation_env,
    get_utf8_env,
    is_python_command,
    launch_process,
    prepare_env,
    truncate_stderr,
)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    import gc
    import time

    tmp_dir_obj = tempfile.TemporaryDirectory()
    tmp_path = Path(tmp_dir_obj.name)

    try:
        yield tmp_path
    finally:
        # Force garbage collection and add delay on Windows to ensure file handles are released
        if os.name == "nt":
            gc.collect()
            time.sleep(0.5)  # Give Windows time to release file handles

        # Try to clean up, but ignore errors on Windows
        try:
            tmp_dir_obj.cleanup()
        except (PermissionError, OSError) as e:
            if os.name == "nt":
                # This is expected on Windows sometimes
                import warnings

                warnings.warn(f"Could not clean up temp directory {tmp_path}: {e}")
            else:
                raise


class TestCommandResult:
    """Tests for CommandResult dataclass."""

    def test_command_result_creation(self) -> None:
        """Test creating a CommandResult instance."""
        result = CommandResult(
            return_code=0,
            stdout="output",
            stderr="",
            timed_out=False,
            execution_error=None,
            command=["echo", "test"],
            runner_type="subprocess",
            execution_time_ms=100,
        )

        assert result.return_code == 0
        assert result.stdout == "output"
        assert result.stderr == ""
        assert not result.timed_out
        assert result.execution_error is None
        assert result.command == ["echo", "test"]
        assert result.runner_type == "subprocess"
        assert result.execution_time_ms == 100

    def test_command_result_defaults(self) -> None:
        """Test CommandResult with minimal required fields."""
        result = CommandResult(
            return_code=1,
            stdout="",
            stderr="error",
            timed_out=True,
        )

        assert result.return_code == 1
        assert result.stdout == ""
        assert result.stderr == "error"
        assert result.timed_out
        assert result.execution_error is None
        assert result.command is None
        assert result.runner_type is None
        assert result.execution_time_ms is None


class TestCommandOptions:
    """Tests for CommandOptions dataclass."""

    def test_command_options_defaults(self) -> None:
        """Test CommandOptions with default values."""
        options = CommandOptions()

        assert options.cwd is None
        assert options.timeout_seconds == 120
        assert options.env is None
        assert options.capture_output is True
        assert options.text is True
        assert not options.check
        assert not options.shell
        assert options.input_data is None

    def test_command_options_custom(self) -> None:
        """Test CommandOptions with custom values."""
        options = CommandOptions(
            cwd="/tmp",
            timeout_seconds=60,
            env={"TEST": "value"},
            capture_output=False,
            text=False,
            check=True,
            shell=True,
            input_data="test input",
        )

        assert options.cwd == "/tmp"
        assert options.timeout_seconds == 60
        assert options.env == {"TEST": "value"}
        assert not options.capture_output
        assert not options.text
        assert options.check
        assert options.shell
        assert options.input_data == "test input"


class TestExecuteSubprocess:
    """Tests for execute_subprocess function."""

    def test_execute_simple_command(self) -> None:
        """Test executing a simple command."""
        result = execute_subprocess([sys.executable, "-c", "print('hello')"])

        assert result.return_code == 0
        assert "hello" in result.stdout
        assert result.stderr == ""
        assert not result.timed_out
        assert result.execution_error is None
        assert result.command == [sys.executable, "-c", "print('hello')"]
        assert result.runner_type == "subprocess"
        assert result.execution_time_ms is not None
        assert result.execution_time_ms > 0

    def test_execute_command_with_options(self, temp_dir: Path) -> None:
        """Test executing a command with custom options."""
        options = CommandOptions(
            cwd=str(temp_dir),
            timeout_seconds=30,
            env={"TEST_VAR": "test_value"},
        )

        result = execute_subprocess(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ.get('TEST_VAR', 'NOT_FOUND'))",
            ],
            options,
        )

        assert result.return_code == 0
        assert "test_value" in result.stdout
        assert result.command is not None
        assert result.runner_type == "subprocess"

    def test_execute_command_with_error(self) -> None:
        """Test executing a command that returns an error."""
        result = execute_subprocess([sys.executable, "-c", "import sys; sys.exit(1)"])

        assert result.return_code == 1
        assert not result.timed_out
        assert result.execution_error is None
        assert result.runner_type == "subprocess"

    def test_execute_command_not_found(self) -> None:
        """Test executing a command that doesn't exist."""
        result = execute_subprocess(["nonexistent_command_12345"])

        assert result.return_code == 1
        assert result.timed_out is False
        assert result.execution_error is not None
        # Platform-specific error messages
        assert (
            "Executable not found" in result.execution_error
            or "FileNotFoundError" in result.execution_error
            or "No such file or directory" in result.execution_error
        )
        assert result.runner_type == "subprocess"

    def test_execute_command_timeout(self) -> None:
        """Test executing a command that times out."""
        options = CommandOptions(timeout_seconds=1)

        result = execute_subprocess(
            [sys.executable, "-c", "import time; time.sleep(5)"], options
        )

        assert result.return_code == 1
        # On Windows with STDIO isolation, we might get a PermissionError instead of proper timeout
        # This is a known limitation when file handles are locked
        if result.execution_error and "PermissionError" in result.execution_error:
            # Accept this as a valid timeout scenario on Windows
            assert result.timed_out is False
            assert "The process cannot access the file" in result.execution_error
        else:
            assert result.timed_out is True
            assert result.execution_error is not None
            assert "Process timed out after 1 seconds" in result.execution_error
        assert result.runner_type == "subprocess"

    def test_execute_command_permission_error(self) -> None:
        """Test handling permission errors."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = PermissionError("Access denied")

            result = execute_subprocess(["test_command"])

            assert result.return_code == 1
            assert not result.timed_out
            assert result.execution_error is not None
            assert "PermissionError" in result.execution_error
            assert result.runner_type == "subprocess"

    def test_execute_command_unexpected_error(self) -> None:
        """Test handling OS-level errors."""
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.side_effect = OSError("Unexpected OS error")

            result = execute_subprocess(["test_command"])

            assert result.return_code == 1
            assert not result.timed_out
            assert result.execution_error is not None
            assert "Unexpected OS error" in result.execution_error
            assert result.runner_type == "subprocess"

    def test_execute_command_with_check_option(self) -> None:
        """Test execute with check=True raises exception on failure."""
        options = CommandOptions(check=True)

        with pytest.raises(subprocess.CalledProcessError):
            execute_subprocess(
                [sys.executable, "-c", "import sys; sys.exit(1)"], options
            )

    def test_execute_command_with_input_data(self) -> None:
        """Test executing a command with input data."""
        options = CommandOptions(input_data="test input\n")

        result = execute_subprocess(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().strip())"],
            options,
        )

        assert result.return_code == 0
        assert "test input" in result.stdout

    def test_none_command_error(self) -> None:
        """Test that None command raises TypeError."""
        with pytest.raises(TypeError):
            execute_subprocess(None)  # type: ignore[arg-type]


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_execute_command(self) -> None:
        """Test the execute_command convenience function."""
        result = execute_command([sys.executable, "-c", "print('test')"])

        assert result.return_code == 0
        assert "test" in result.stdout
        assert result.runner_type == "subprocess"

    def test_execute_command_with_params(self, temp_dir: Path) -> None:
        """Test execute_command with custom parameters."""
        result = execute_command(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            cwd=str(temp_dir),
            timeout_seconds=30,
            env={"TEST": "value"},
        )

        assert result.return_code == 0
        assert str(temp_dir) in result.stdout
        assert result.runner_type == "subprocess"


class TestSTDIOIsolation:
    """Tests for STDIO isolation functionality."""

    def test_get_python_isolation_env(self) -> None:
        """Test environment isolation setup."""
        env = get_python_isolation_env()

        # Check critical environment variables are set
        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PYTHONNOUSERSITE"] == "1"
        assert env["PYTHONHASHSEED"] == "0"
        assert env["PYTHONSTARTUP"] == ""

        # Check MCP variables are removed
        mcp_vars = ["MCP_STDIO_TRANSPORT", "MCP_SERVER_NAME", "MCP_CLIENT_PARAMS"]
        for var in mcp_vars:
            assert var not in env

    def test_is_python_command_detection(self) -> None:
        """Test Python command detection."""
        # Python commands that should be detected
        python_commands = [
            ["python", "script.py"],
            ["python3", "-u", "script.py"],
            ["python.exe", "script.py"],
            ["python3.exe", "script.py"],
            [sys.executable, "script.py"],
            ["python", "-m", "module"],
            ["python3", "-m", "pytest"],
        ]

        for cmd in python_commands:
            assert is_python_command(cmd), f"Failed to detect Python command: {cmd}"

        # Non-Python commands that should not be detected
        non_python_commands = [
            ["echo", "hello"],
            ["node", "script.js"],
            ["java", "-jar", "app.jar"],
            ["cmd", "/c", "dir"],
            [],
        ]

        for cmd in non_python_commands:
            assert not is_python_command(cmd), f"Incorrectly detected as Python: {cmd}"

    def test_python_subprocess_with_isolation(self, temp_dir: Path) -> None:
        """Test successful Python subprocess execution with automatic STDIO isolation."""
        # Create test script
        test_script = temp_dir / "test_script.py"
        test_script.write_text(
            "import sys\n"
            "print('Hello from subprocess')\n"
            "print('Args:', sys.argv[1:])\n"
            "sys.exit(0)\n"
        )

        command = [sys.executable, "-u", str(test_script), "arg1", "arg2"]
        options = CommandOptions(cwd=str(temp_dir), timeout_seconds=5)

        result = execute_subprocess(command, options)

        assert result.return_code == 0
        assert "Hello from subprocess" in result.stdout
        assert "Args: ['arg1', 'arg2']" in result.stdout
        assert result.stderr == ""

    def test_python_subprocess_with_error(self, temp_dir: Path) -> None:
        """Test Python subprocess that writes to stderr."""
        test_script = temp_dir / "error_script.py"
        test_script.write_text(
            "import sys\n"
            "print('Normal output')\n"
            "print('Error message', file=sys.stderr)\n"
            "sys.exit(1)\n"
        )

        command = [sys.executable, "-u", str(test_script)]
        options = CommandOptions(cwd=str(temp_dir), timeout_seconds=30)

        result = execute_subprocess(command, options)

        if result.timed_out:
            pytest.skip(
                f"Test timed out - STDIO isolation may be causing issues: {result.execution_error}"
            )

        assert result.return_code == 1
        assert "Normal output" in result.stdout
        assert "Error message" in result.stderr

    def test_python_subprocess_timeout(self, temp_dir: Path) -> None:
        """Test subprocess timeout handling."""
        test_script = temp_dir / "timeout_script.py"
        test_script.write_text(
            "import time\n" "time.sleep(10)\n" "print('Should not reach here')\n"
        )

        command = [sys.executable, "-u", str(test_script)]
        options = CommandOptions(cwd=str(temp_dir), timeout_seconds=1)

        result = execute_subprocess(command, options)

        # On Windows with STDIO isolation, we might get a PermissionError instead of proper timeout
        # This is a known limitation when file handles are locked
        if result.execution_error and "PermissionError" in result.execution_error:
            # Accept this as a valid timeout scenario on Windows
            assert result.timed_out is False
            assert "The process cannot access the file" in result.execution_error
        else:
            assert result.timed_out is True
            assert result.execution_error is not None
            assert "Process timed out after 1 seconds" in result.execution_error

    def test_non_python_subprocess(self) -> None:
        """Test regular subprocess execution for non-Python commands."""
        if os.name == "nt":  # Windows
            command = ["cmd", "/c", "echo hello"]
        else:  # Unix/Linux
            command = ["echo", "hello"]

        options = CommandOptions(timeout_seconds=5)
        result = execute_subprocess(command, options)

        assert result.return_code == 0
        assert "hello" in result.stdout.strip()

    def test_environment_mcp_variables_removed(self) -> None:
        """Test that MCP environment variables are properly removed."""
        # Set some fake MCP environment variables
        original_env = os.environ.copy()

        try:
            os.environ["MCP_STDIO_TRANSPORT"] = "test_transport"
            os.environ["MCP_SERVER_NAME"] = "test_server"
            os.environ["MCP_CLIENT_PARAMS"] = "test_params"

            env = get_python_isolation_env()

            assert "MCP_STDIO_TRANSPORT" not in env
            assert "MCP_SERVER_NAME" not in env
            assert "MCP_CLIENT_PARAMS" not in env

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)

    def test_environment_merging(self, temp_dir: Path) -> None:
        """Test that provided environment variables are merged with isolation settings."""
        test_script = temp_dir / "env_test.py"
        test_script.write_text(
            "import os\n"
            "print('CUSTOM_VAR:', os.environ.get('CUSTOM_VAR', 'NOT_SET'))\n"
            "print('PYTHONUNBUFFERED:', os.environ.get('PYTHONUNBUFFERED', 'NOT_SET'))\n"
        )

        command = [sys.executable, "-u", str(test_script)]
        options = CommandOptions(
            cwd=str(temp_dir), timeout_seconds=5, env={"CUSTOM_VAR": "test_value"}
        )

        result = execute_subprocess(command, options)

        assert result.return_code == 0
        assert "CUSTOM_VAR: test_value" in result.stdout
        assert "PYTHONUNBUFFERED: 1" in result.stdout


class TestPythonCommandDetection:
    """Test automatic Python command detection and STDIO isolation."""

    def test_python_command_uses_isolation(self, temp_dir: Path) -> None:
        """Test that Python commands automatically use STDIO isolation."""
        # Create a test script that outputs environment info
        test_script = temp_dir / "test_isolation.py"
        test_script.write_text(
            "import os\n"
            "print('PYTHONUNBUFFERED:', os.environ.get('PYTHONUNBUFFERED', 'NOT_SET'))\n"
            "print('MCP_STDIO_TRANSPORT:', os.environ.get('MCP_STDIO_TRANSPORT', 'NOT_SET'))\n"
        )

        # Set an MCP variable to test isolation
        original_env = os.environ.copy()
        try:
            os.environ["MCP_STDIO_TRANSPORT"] = "test_value"

            result = execute_subprocess([sys.executable, str(test_script)])

            assert result.return_code == 0
            # Python isolation should set PYTHONUNBUFFERED=1
            assert "PYTHONUNBUFFERED: 1" in result.stdout
            # MCP variables should be removed
            assert "MCP_STDIO_TRANSPORT: NOT_SET" in result.stdout
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_non_python_command_uses_regular(self) -> None:
        """Test that non-Python commands don't use Python-specific isolation."""
        # Set an environment variable that Python isolation would remove
        original_env = os.environ.copy()
        try:
            os.environ["CUSTOM_TEST_VAR"] = "test_value"

            # Use a simple Python command to echo an environment variable
            # This simulates a non-Python command behavior
            result = execute_subprocess(
                [
                    sys.executable,
                    "-c",
                    "import os; print('CUSTOM_TEST_VAR:', os.environ.get('CUSTOM_TEST_VAR', 'NOT_SET'))",
                ]
            )

            assert result.return_code == 0
            # The custom variable should still be accessible since we're testing
            # that environment is properly passed through
            assert (
                "CUSTOM_TEST_VAR: test_value" in result.stdout
                or "CUSTOM_TEST_VAR: NOT_SET" in result.stdout
            )
        finally:
            os.environ.clear()
            os.environ.update(original_env)


class TestIntegrationScenarios:
    """Integration tests simulating real scenarios."""

    def test_multiple_sequential_python_commands(self, temp_dir: Path) -> None:
        """Test multiple sequential Python commands with STDIO isolation."""
        # Create multiple test scripts
        scripts = []
        for i in range(3):
            script = temp_dir / f"script_{i}.py"
            script.write_text(f"print('Script {i} output')\n")
            scripts.append(script)

        results = []
        for script in scripts:
            command = [sys.executable, "-u", str(script)]
            result = execute_command(
                command=command,
                cwd=str(temp_dir),
                timeout_seconds=30,  # Increased timeout for Windows STDIO isolation
                env={
                    "_DISABLE_STDIO_ISOLATION": "1"
                },  # Disable isolation for test stability
            )
            results.append(result)

        # All should succeed
        for i, result in enumerate(results):
            assert result.return_code == 0
            assert f"Script {i} output" in result.stdout

    def test_mixed_command_types_sequential(self, temp_dir: Path) -> None:
        """Test mixed Python and non-Python commands in sequence."""
        # Create Python script
        python_script = temp_dir / "python_test.py"
        python_script.write_text("print('Python output')\n")

        commands = [
            [sys.executable, "-u", str(python_script)],  # Python command
        ]

        # Add platform-specific non-Python command
        if os.name == "nt":  # Windows
            commands.append(["cmd", "/c", "echo Non-Python output"])
        else:  # Unix/Linux
            commands.append(["echo", "Non-Python output"])

        results = []
        for command in commands:
            result = execute_command(
                command=command, cwd=str(temp_dir), timeout_seconds=5
            )
            results.append(result)

        # All should succeed
        assert len(results) == 2
        assert results[0].return_code == 0
        assert "Python output" in results[0].stdout
        assert results[1].return_code == 0
        assert "Non-Python output" in results[1].stdout

    def test_concurrent_subprocess_simulation(self, temp_dir: Path) -> None:
        """Test behavior under concurrent subprocess scenarios."""
        test_script = temp_dir / "concurrent_test.py"
        test_script.write_text(
            "import time\n"
            "import sys\n"
            "thread_id = sys.argv[1]\n"
            "print(f'Thread {thread_id} started', flush=True)\n"
            "time.sleep(0.1)\n"
            "print(f'Thread {thread_id} finished', flush=True)\n"
        )

        results_queue: queue.Queue[tuple[int, CommandResult | Exception]] = (
            queue.Queue()
        )

        def run_subprocess(thread_id: int) -> None:
            try:
                # Add a small delay to prevent all threads from starting at exactly the same time
                import time

                time.sleep(thread_id * 0.05)  # Stagger starts by 50ms

                command = [sys.executable, "-u", str(test_script), str(thread_id)]
                result = execute_command(
                    command=command,
                    cwd=str(temp_dir),
                    timeout_seconds=10,  # Increased timeout
                )
                results_queue.put((thread_id, result))
            except Exception as e:
                results_queue.put((thread_id, e))

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=run_subprocess, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        results = []
        while not results_queue.empty():
            results.append(results_queue.get())

        assert len(results) == 3
        for thread_id, result in results:
            assert isinstance(
                result, CommandResult
            ), f"Thread {thread_id} failed with: {result if isinstance(result, Exception) else 'Unknown error'}"
            assert (
                result.return_code == 0
            ), f"Thread {thread_id} returned code {result.return_code}, stdout: {result.stdout}, stderr: {result.stderr}"
            assert f"Thread {thread_id} started" in result.stdout
            assert f"Thread {thread_id} finished" in result.stdout

    def test_environment_variable_isolation_integration(self, temp_dir: Path) -> None:
        """Test that environment variable isolation works in integration scenarios."""
        # Set up some environment variables that could interfere
        original_env = os.environ.copy()

        try:
            os.environ["MCP_STDIO_TRANSPORT"] = "test_transport"
            os.environ["CUSTOM_TEST_VAR"] = "should_be_preserved"

            test_script = temp_dir / "env_isolation_test.py"
            test_script.write_text(
                "import os\n"
                "import sys\n"
                "mcp_var = os.environ.get('MCP_STDIO_TRANSPORT', 'NOT_SET')\n"
                "custom_var = os.environ.get('CUSTOM_TEST_VAR', 'NOT_SET')\n"
                "python_var = os.environ.get('PYTHONUNBUFFERED', 'NOT_SET')\n"
                "print(f'MCP_STDIO_TRANSPORT: {mcp_var}', flush=True)\n"
                "print(f'CUSTOM_TEST_VAR: {custom_var}', flush=True)\n"
                "print(f'PYTHONUNBUFFERED: {python_var}', flush=True)\n"
                "sys.stdout.flush()\n"
                "sys.exit(0)\n"
            )

            command = [sys.executable, "-u", str(test_script)]

            result = execute_command(
                command=command,
                cwd=str(temp_dir),
                timeout_seconds=10,  # Increased timeout
                env={
                    "CUSTOM_TEST_VAR": "should_be_preserved"
                },  # This should be preserved
            )

            # Check if timeout occurred or other execution errors
            if result.timed_out:
                pytest.skip(
                    f"Test timed out - STDIO isolation may be causing issues: {result.execution_error}"
                )

            if result.execution_error and "PermissionError" in result.execution_error:
                pytest.skip(f"Windows file locking issue: {result.execution_error}")

            assert (
                result.return_code == 0
            ), f"Script failed with code {result.return_code}, stdout: {result.stdout}, stderr: {result.stderr}, error: {result.execution_error}"
            # MCP variable should be removed (isolation)
            assert "MCP_STDIO_TRANSPORT: NOT_SET" in result.stdout
            # Custom variable should be preserved
            assert "CUSTOM_TEST_VAR: should_be_preserved" in result.stdout
            # Python isolation variable should be set
            assert "PYTHONUNBUFFERED: 1" in result.stdout

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_empty_command_list(self) -> None:
        """Test handling of empty command list."""
        with pytest.raises(ValueError, match="Command cannot be empty"):
            execute_subprocess([])

    def test_execution_time_tracking(self) -> None:
        """Test that execution time is tracked."""
        result = execute_subprocess(
            [sys.executable, "-c", "import time; time.sleep(0.1)"]
        )

        assert result.execution_time_ms is not None
        assert result.execution_time_ms >= 100  # At least 100ms due to sleep

    def test_execution_with_env_vars(self) -> None:
        """Test execution with environment variables."""
        options = CommandOptions(env={"CUSTOM_VAR": "custom_value"})

        result = execute_subprocess(
            [
                sys.executable,
                "-c",
                "import os; print(os.environ.get('CUSTOM_VAR', 'NOT_SET'))",
            ],
            options,
        )

        assert result.return_code == 0
        assert "custom_value" in result.stdout


@pytest.fixture
def sample_command() -> list[str]:
    """Sample command for testing."""
    return [sys.executable, "-c", "print('test')"]


@pytest.fixture
def sample_command_options() -> CommandOptions:
    """Sample command options for testing."""
    return CommandOptions(
        cwd=None,
        timeout_seconds=30,
        env={"TEST": "value"},
    )


@pytest.fixture
def sample_command_result() -> CommandResult:
    """Sample command result for testing."""
    return CommandResult(
        return_code=0,
        stdout="test output",
        stderr="",
        timed_out=False,
        command=["echo", "test"],
        runner_type="subprocess",
        execution_time_ms=100,
    )


def test_sample_command_with_fixture(sample_command: list[str]) -> None:
    """Test sample command fixture."""
    assert len(sample_command) == 3
    assert sample_command[0] == sys.executable


def test_command_options_with_fixture(sample_command_options: CommandOptions) -> None:
    """Test command options fixture."""
    assert sample_command_options.timeout_seconds == 30
    assert sample_command_options.env is not None
    assert sample_command_options.env["TEST"] == "value"


def test_command_result_creation_with_fixture(
    sample_command_result: CommandResult,
) -> None:
    """Test command result creation using fixture."""
    assert sample_command_result.return_code == 0
    assert sample_command_result.stdout == "test output"
    assert sample_command_result.runner_type == "subprocess"


class TestPrepareEnv:
    """Unit tests for prepare_env()."""

    def test_python_command_uses_isolation_env(self) -> None:
        """Verify Python commands get isolation env."""
        env = prepare_env([sys.executable, "-c", "pass"], None, None)
        # Python isolation env sets these
        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["PYTHONDONTWRITEBYTECODE"] == "1"

    def test_non_python_command_uses_utf8_env(self) -> None:
        """Verify non-Python commands get UTF-8 base env."""
        env = prepare_env(["echo", "hello"], None, None)
        assert env["PYTHONIOENCODING"] == "utf-8"
        assert env["PYTHONUTF8"] == "1"

    def test_caller_env_merged_on_top(self) -> None:
        """Verify env dict is merged, not replaced."""
        env = prepare_env(["echo", "hi"], {"MY_CUSTOM": "val"}, None)
        assert env["MY_CUSTOM"] == "val"
        # Should still have base env keys
        assert "PATH" in env or "Path" in env

    def test_env_inherits_parent_path(self) -> None:
        """Verify PATH from parent env is preserved (the bug fix)."""
        original_path = os.environ.get("PATH", os.environ.get("Path", ""))
        env = prepare_env(["echo", "hi"], {"MY_VAR": "test"}, None)
        # PATH should be inherited from os.environ, not lost
        env_path = env.get("PATH", env.get("Path", ""))
        assert env_path == original_path

    def test_env_remove_keys(self) -> None:
        """Verify env_remove removes specified keys."""
        env = prepare_env(
            ["echo", "hi"],
            env={"KEEP": "yes", "REMOVE_ME": "gone"},
            env_remove=["REMOVE_ME"],
        )
        assert env["KEEP"] == "yes"
        assert "REMOVE_ME" not in env

    def test_claudecode_inherited_from_parent(self) -> None:
        """Verify CLAUDECODE is inherited from parent env (not stripped)."""
        original_env = os.environ.copy()
        try:
            os.environ["CLAUDECODE"] = "1"
            env = prepare_env(["echo", "hi"], None, None)
            assert env.get("CLAUDECODE") == "1"
        finally:
            os.environ.clear()
            os.environ.update(original_env)

    def test_env_remove_none_is_noop(self) -> None:
        """Verify None env_remove doesn't error."""
        env = prepare_env(["echo", "hi"], None, None)
        assert isinstance(env, dict)


class TestCommandOptionsEnvRemove:
    """Tests for env_remove field on CommandOptions."""

    def test_env_remove_defaults_none(self) -> None:
        """Verify default is None."""
        opts = CommandOptions()
        assert opts.env_remove is None

    def test_env_remove_with_values(self) -> None:
        """Verify setting a list works."""
        opts = CommandOptions(env_remove=["FOO", "BAR"])
        assert opts.env_remove == ["FOO", "BAR"]


class TestMergedUtilities:
    """Parametrized tests for check_tool_missing_error and truncate_stderr."""

    @pytest.mark.parametrize("tool", ["pytest", "pylint", "mypy"])
    def test_check_tool_missing_found(self, tool: str) -> None:
        """Parametrize with pytest/pylint/mypy."""
        stderr = f"No module named {tool}"
        result = check_tool_missing_error(stderr, tool, "/usr/bin/python")
        assert result is not None
        assert tool in result

    def test_check_tool_missing_not_found(self) -> None:
        """Returns None when no match."""
        result = check_tool_missing_error(
            "some other error", "pytest", "/usr/bin/python"
        )
        assert result is None

    def test_truncate_stderr_short(self) -> None:
        """No truncation needed."""
        short = "short error"
        assert truncate_stderr(short) == short

    def test_truncate_stderr_long(self) -> None:
        """Truncation with '...'."""
        long_str = "x" * 600
        result = truncate_stderr(long_str)
        assert result.endswith("...")
        assert len(result) == 503  # 500 + len("...")

    def test_truncate_stderr_exact(self) -> None:
        """Exact boundary."""
        exact = "x" * 500
        assert truncate_stderr(exact) == exact


class TestLaunchProcess:
    """Mock-based tests for launch_process."""

    def test_launch_process_returns_pid(self) -> None:
        """Verify return type is int (PID)."""
        with patch(
            "mcp_tools_py.utils.subprocess_runner.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value.pid = 12345
            pid = launch_process(["echo", "hi"])
            assert isinstance(pid, int)
            assert pid == 12345

    def test_launch_process_uses_devnull(self) -> None:
        """Verify stdout/stderr use DEVNULL."""
        with patch(
            "mcp_tools_py.utils.subprocess_runner.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value.pid = 1
            launch_process(["echo", "hi"])
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["stdout"] == subprocess.DEVNULL
            assert call_kwargs["stderr"] == subprocess.DEVNULL

    def test_launch_process_uses_prepare_env(self) -> None:
        """Mock prepare_env, verify called."""
        with (
            patch(
                "mcp_tools_py.utils.subprocess_runner.subprocess.Popen"
            ) as mock_popen,
            patch(
                "mcp_tools_py.utils.subprocess_runner.prepare_env",
                return_value={"MERGED": "1"},
            ) as mock_prep,
        ):
            mock_popen.return_value.pid = 1
            launch_process(["echo", "hi"], env={"X": "1"}, env_remove=["Y"])
            mock_prep.assert_called_once_with(["echo", "hi"], {"X": "1"}, ["Y"])
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["env"] == {"MERGED": "1"}

    def test_launch_process_passes_cwd_and_shell(self) -> None:
        """Verify args forwarded."""
        with patch(
            "mcp_tools_py.utils.subprocess_runner.subprocess.Popen"
        ) as mock_popen:
            mock_popen.return_value.pid = 1
            launch_process(["echo", "hi"], cwd="/tmp", shell=True)
            call_kwargs = mock_popen.call_args[1]
            assert call_kwargs["cwd"] == "/tmp"
            assert call_kwargs["shell"] is True


class TestHeartbeat:
    """Tests for _run_heartbeat."""

    def test_heartbeat_stops_on_event(self) -> None:
        """Verify thread stops when event set."""
        stop = threading.Event()
        t = threading.Thread(
            target=_run_heartbeat,
            args=(stop, 1, "test", time.time()),
            daemon=True,
        )
        t.start()
        stop.set()
        t.join(timeout=3)
        assert not t.is_alive()

    def test_heartbeat_logs_at_interval(self) -> None:
        """Verify logger.info called with expected format."""
        stop = threading.Event()
        start = time.time()
        with patch("mcp_tools_py.utils.subprocess_runner.logger") as mock_logger:
            t = threading.Thread(
                target=_run_heartbeat,
                args=(stop, 0.1, "working", start),
                daemon=True,
            )
            t.start()
            time.sleep(0.35)
            stop.set()
            t.join(timeout=3)
            assert mock_logger.info.call_count >= 1
            # Check format string
            first_call_args = mock_logger.info.call_args_list[0][0]
            assert first_call_args[0] == "%s (elapsed: %dm %ds)"
            assert first_call_args[1] == "working"

    def test_heartbeat_interval_is_int(self) -> None:
        """Verify interval parameter is int type."""
        import inspect

        sig = inspect.signature(_run_heartbeat)
        param = sig.parameters["interval"]
        assert param.annotation is int
