"""Tests for utils module."""

import pytest

from tests.mcp_tools_py_manual.sample_project.models import MAX_NAME_LENGTH, User
from tests.mcp_tools_py_manual.sample_project.utils import (
    create_user,
    format_user,
    is_active,
)


def test_create_user() -> None:
    user = create_user("Alice", "alice@example.com")
    assert isinstance(user, User)


def test_create_user_too_long() -> None:
    with pytest.raises(ValueError):
        create_user("A" * (MAX_NAME_LENGTH + 1), "x@example.com")


def test_is_active() -> None:
    user = create_user("Alice", "alice@example.com")
    assert is_active(user) is True
    user.deactivate()
    assert is_active(user) is False


def test_format_user() -> None:
    user = create_user("Alice", "alice@example.com")
    assert format_user(user) == "Alice <alice@example.com>"
