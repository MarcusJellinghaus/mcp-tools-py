"""Tests for shim re-export modules."""


def test_file_utils_read_file_is_reexport():
    from mcp_tools_py.utils.file_utils import read_file
    from mcp_coder_utils.fs import read_file as upstream

    assert read_file is upstream


def test_pytest_utils_read_file(tmp_path):
    p = tmp_path / "hello.txt"
    p.write_text("hello", encoding="utf-8")
    from mcp_tools_py.code_checker_pytest.utils import read_file

    assert read_file(str(p)) == "hello"


def test_log_utils_reexports():
    from mcp_tools_py.log_utils import OUTPUT, log_function_call, setup_logging
    from mcp_coder_utils.log_utils import (
        OUTPUT as u_OUTPUT,
        log_function_call as u_lfc,
        setup_logging as u_sl,
    )
    assert OUTPUT is u_OUTPUT
    assert log_function_call is u_lfc
    assert setup_logging is u_sl


def test_subprocess_runner_reexports():
    from mcp_tools_py.utils.subprocess_runner import execute_command, CommandResult
    from mcp_coder_utils.subprocess_runner import (
        execute_command as u_ec,
        CommandResult as u_cr,
    )
    assert execute_command is u_ec
    assert CommandResult is u_cr


def test_importlinter_config_has_isolation_contract():
    """Verify the isolation contract is defined in .importlinter."""
    import pathlib

    config = pathlib.Path(".importlinter").read_text(encoding="utf-8")
    assert "mcp_coder_utils_isolation" in config
