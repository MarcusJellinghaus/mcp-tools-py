"""Unit tests for pylint utils module."""

import os

from mcp_tools_py.code_checker_pylint.utils import normalize_path


class TestNormalizePath:
    """Test cases for normalize_path function."""

    def test_normalize_path_with_base_dir_prefix(self) -> None:
        """Test normalizing a path that starts with the base directory."""
        base_dir = os.path.join("home", "user", "project")
        path = os.path.join("home", "user", "project", "src", "module.py")
        result = normalize_path(path, base_dir)
        assert result == os.path.join("src", "module.py")

    def test_normalize_path_without_base_dir_prefix(self) -> None:
        """Test normalizing a path that doesn't start with the base directory."""
        base_dir = os.path.join("home", "user", "project")
        path = os.path.join("other", "path", "module.py")
        result = normalize_path(path, base_dir)
        assert result == os.path.join("other", "path", "module.py")

    def test_normalize_path_with_backslashes(self) -> None:
        """Test normalizing a path with backslashes."""
        base_dir = "home/user/project"
        path = "home\\user\\project\\src\\module.py"
        result = normalize_path(path, base_dir)
        expected = os.path.join("src", "module.py")
        assert result == expected

    def test_normalize_path_with_forward_slashes(self) -> None:
        """Test normalizing a path with forward slashes."""
        base_dir = "home\\user\\project"
        path = "home/user/project/src/module.py"
        result = normalize_path(path, base_dir)
        expected = os.path.join("src", "module.py")
        assert result == expected

    def test_normalize_path_base_dir_without_trailing_sep(self) -> None:
        """Test normalizing when base_dir doesn't have trailing separator."""
        base_dir = os.path.join("home", "user", "project")
        path = os.path.join("home", "user", "project", "src", "module.py")
        result = normalize_path(path, base_dir)
        assert result == os.path.join("src", "module.py")

    def test_normalize_path_base_dir_with_trailing_sep(self) -> None:
        """Test normalizing when base_dir has trailing separator."""
        base_dir = os.path.join("home", "user", "project") + os.path.sep
        path = os.path.join("home", "user", "project", "src", "module.py")
        result = normalize_path(path, base_dir)
        assert result == os.path.join("src", "module.py")
