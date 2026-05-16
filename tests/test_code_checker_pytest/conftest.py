"""Shared fixtures for code_checker_pytest integration tests."""

import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from mcp_tools_py.server import ToolServer


@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test projects."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def server(temp_project_dir: Path) -> ToolServer:
    """Create a ToolServer instance for testing."""
    return ToolServer(project_dir=temp_project_dir)
