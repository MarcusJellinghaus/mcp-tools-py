"""Shared fixtures for the refactoring tests."""

from typing import Iterator

import pytest

from mcp_tools_py.refactoring.jedi_tools import _get_project


@pytest.fixture(autouse=True)
def _clear_project_cache() -> Iterator[None]:
    """Drop cached jedi projects so their child processes are released."""
    _get_project.cache_clear()
    yield
    _get_project.cache_clear()
