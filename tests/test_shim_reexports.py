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
