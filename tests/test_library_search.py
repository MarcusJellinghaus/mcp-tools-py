"""Tests for the library_search directory-search core and MCP tool."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.library_search import (
    LibrarySearchTools,
    _collect_files,
    _match_glob,
    _search_content,
    search_in_directory,
)
from mcp_tools_py.utils.environment_info import ScopeResolution
from mcp_tools_py.utils.tool_context import ToolContext


def _make_tree(tmp_path: Path) -> Path:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "pkg" / "mod.py").write_text("def foo():\n    pass\n", encoding="utf-8")
    (tmp_path / "pkg" / "types.pyi").write_text("x: int\n", encoding="utf-8")
    (tmp_path / "pkg" / "__pycache__").mkdir()
    (tmp_path / "pkg" / "__pycache__" / "mod.cpython-311.pyc").write_bytes(b"\x00\x01")
    (tmp_path / "some.dist-info").mkdir()
    (tmp_path / "some.dist-info" / "METADATA").write_text(
        "Name: some\n", encoding="utf-8"
    )
    return tmp_path


class TestCollectFiles:
    """_collect_files walks root, excluding __pycache__ and *.dist-info."""

    def test_lists_py_and_pyi_excludes_pycache_and_dist_info(
        self, tmp_path: Path
    ) -> None:
        root = _make_tree(tmp_path)
        files = _collect_files(root)
        assert files == ["pkg/__init__.py", "pkg/mod.py", "pkg/types.pyi"]


class TestMatchGlob:
    """_match_glob uses pathspec/wildmatch semantics (unanchored by depth)."""

    def test_bare_py_glob_matches_at_any_depth(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        files = _collect_files(root)
        matched = _match_glob("*.py", files)
        assert matched == ["pkg/__init__.py", "pkg/mod.py"]


class TestSearchContent:
    """_search_content finds regex matches with context and truncation."""

    def test_basic_match(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        files = _collect_files(root)
        import re

        result = _search_content(files, re.compile("def foo"), root, 0, 50, 200)
        assert result["mode"] == "content_search"
        assert result["total_matches"] == 1
        assert result["details"][0]["file"] == "pkg/mod.py"
        assert result["details"][0]["line"] == 1

    def test_context_lines(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        files = _collect_files(root)
        import re

        result = _search_content(files, re.compile("pass"), root, 1, 50, 200)
        assert result["details"][0]["text"] == "def foo():\n    pass"

    def test_max_results_truncation(self, tmp_path: Path) -> None:
        root = tmp_path
        for i in range(5):
            (root / f"f{i}.py").write_text("needle\n", encoding="utf-8")
        files = _collect_files(root)
        import re

        result = _search_content(files, re.compile("needle"), root, 0, 2, 200)
        assert result["truncated"] is True
        assert len(result["details"]) == 2
        assert result["total_matches"] == 5
        assert "matched_files" in result

    def test_max_result_lines_truncation_respects_char_budget(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path
        line = "needle " + ("x" * 50) + "\n"
        for i in range(5):
            (root / f"f{i}.py").write_text(line, encoding="utf-8")
        files = _collect_files(root)
        import re

        max_result_lines = 1
        char_budget = max_result_lines * 120
        result = _search_content(
            files, re.compile("needle"), root, 0, 50, max_result_lines
        )
        chars_used = sum(len(d["text"]) for d in result["details"])
        assert chars_used <= char_budget
        assert result["truncated"] is True

    def test_binary_file_silently_excluded_not_in_skipped(self, tmp_path: Path) -> None:
        root = tmp_path
        (root / "binary.py").write_bytes(b"\x00\x01\x02needle\xff\xfe")
        (root / "text.py").write_text("needle\n", encoding="utf-8")
        files = _collect_files(root)
        import re

        result = _search_content(files, re.compile("needle"), root, 0, 50, 200)
        matched_files = {d["file"] for d in result["details"]}
        assert "binary.py" not in matched_files
        assert "text.py" in matched_files
        assert result.get("skipped_files", []) == []

    @pytest.mark.skipif(
        os.name == "nt", reason="chmod-based unreadable file not reliable on Windows"
    )
    def test_unreadable_file_in_skipped_files(self, tmp_path: Path) -> None:
        root = tmp_path
        unreadable = root / "secret.py"
        unreadable.write_text("needle\n", encoding="utf-8")
        unreadable.chmod(0o000)
        try:
            files = _collect_files(root)
            import re

            result = _search_content(files, re.compile("needle"), root, 0, 50, 200)
            assert "secret.py" in result.get("skipped_files", [])
        finally:
            unreadable.chmod(0o644)


class TestSearchInDirectory:
    """search_in_directory orchestrates glob, content search and scope_root."""

    def test_file_search_mode_lists_everything_by_default(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        result = search_in_directory(root)
        assert result["mode"] == "file_search"
        assert result["files"] == ["pkg/__init__.py", "pkg/mod.py", "pkg/types.pyi"]
        assert result["total_files"] == 3
        assert result["truncated"] is False

    def test_scope_root_present_and_absolute_in_file_search(
        self, tmp_path: Path
    ) -> None:
        root = _make_tree(tmp_path)
        result = search_in_directory(root)
        assert result["scope_root"] == str(root.resolve())
        assert Path(result["scope_root"]).is_absolute()

    def test_scope_root_present_and_absolute_in_content_search(
        self, tmp_path: Path
    ) -> None:
        root = _make_tree(tmp_path)
        result = search_in_directory(root, pattern="foo")
        assert result["scope_root"] == str(root.resolve())
        assert Path(result["scope_root"]).is_absolute()

    def test_glob_filters_file_search(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        result = search_in_directory(root, glob="*.pyi")
        assert result["files"] == ["pkg/types.pyi"]

    def test_content_search_with_glob(self, tmp_path: Path) -> None:
        root = _make_tree(tmp_path)
        result = search_in_directory(root, glob="*.py", pattern="foo")
        assert result["mode"] == "content_search"
        assert result["total_matches"] == 1
        assert result["details"][0]["file"] == "pkg/mod.py"

    def test_invalid_regex_falls_back_to_literal_and_adds_note(
        self, tmp_path: Path
    ) -> None:
        root = _make_tree(tmp_path)
        (tmp_path / "pkg" / "literal.py").write_text("a(b\n", encoding="utf-8")
        result = search_in_directory(root, pattern="a(b")
        assert result["note"] == (
            "Pattern treated as literal text (invalid regex). "
            "Use Python re syntax for regex search."
        )
        assert result["total_matches"] == 1
        assert result["details"][0]["file"] == "pkg/literal.py"


class TestLibrarySearchTools:
    """LibrarySearchTools wires resolve_scope and search_in_directory together."""

    def test_scope_resolution_error_short_circuits(
        self, tool_context: ToolContext
    ) -> None:
        mcp = MagicMock()
        captured = {}

        def _capture(fn):  # type: ignore[no-untyped-def]
            captured["fn"] = fn
            return fn

        mcp.tool.return_value = _capture
        LibrarySearchTools(tool_context).register(mcp)
        search_library_files = captured["fn"]

        with (
            patch(
                "mcp_tools_py.library_search.resolve_scope",
                return_value=ScopeResolution(error="boom"),
            ),
            patch("mcp_tools_py.library_search.search_in_directory") as mock_search,
        ):
            result = search_library_files("mypy")

            assert result == {"error": "boom"}
            mock_search.assert_not_called()

    def test_wiring_matches_direct_call(
        self, tool_context: ToolContext, tmp_path: Path
    ) -> None:
        root = tmp_path / "scope_root"
        root.mkdir()
        (root / "a.py").write_text("def foo():\n    pass\n", encoding="utf-8")
        (root / "b.py").write_text("def bar():\n    pass\n", encoding="utf-8")

        mcp = MagicMock()
        captured = {}

        def _capture(fn):  # type: ignore[no-untyped-def]
            captured["fn"] = fn
            return fn

        mcp.tool.return_value = _capture
        LibrarySearchTools(tool_context).register(mcp)
        search_library_files = captured["fn"]

        with patch(
            "mcp_tools_py.library_search.resolve_scope",
            return_value=ScopeResolution(directory=str(root)),
        ):
            result = search_library_files(
                "mypy", glob="*.py", pattern="foo", context_lines=0
            )

        expected = search_in_directory(
            root, glob="*.py", pattern="foo", context_lines=0
        )
        assert result == expected

    def test_unparseable_glob_returns_error_dict(
        self, tool_context: ToolContext, tmp_path: Path
    ) -> None:
        mcp = MagicMock()
        captured = {}

        def _capture(fn):  # type: ignore[no-untyped-def]
            captured["fn"] = fn
            return fn

        mcp.tool.return_value = _capture
        LibrarySearchTools(tool_context).register(mcp)
        search_library_files = captured["fn"]

        with patch(
            "mcp_tools_py.library_search.resolve_scope",
            return_value=ScopeResolution(directory=str(tmp_path)),
        ):
            result = search_library_files("mypy", glob="!")

        assert "error" in result

    def test_registers_exactly_one_tool_named_search_library_files(
        self, tool_context: ToolContext
    ) -> None:
        mcp = MagicMock()
        decorator = MagicMock(side_effect=lambda fn: fn)
        mcp.tool.return_value = decorator

        LibrarySearchTools(tool_context).register(mcp)

        assert mcp.tool.call_count == 1
        registered_fn = decorator.call_args.args[0]
        assert registered_fn.__name__ == "search_library_files"
