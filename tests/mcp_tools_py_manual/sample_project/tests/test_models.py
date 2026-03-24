"""Tests for models module."""

from tests.mcp_tools_py_manual.sample_project.models import (
    DEFAULT_STATUS,
    MAX_NAME_LENGTH,
    Order,
    User,
)


def test_user_creation() -> None:
    user = User(name="Alice", email="alice@example.com")
    assert user.name == "Alice"
    assert user.status == DEFAULT_STATUS


def test_user_deactivate() -> None:
    user = User(name="Bob", email="bob@example.com")
    user.deactivate()
    assert user.status == "inactive"


def test_user_name_truncation() -> None:
    long_name = "A" * (MAX_NAME_LENGTH + 50)
    user = User(name=long_name, email="x@example.com")
    assert len(user.name) == MAX_NAME_LENGTH


def test_order_add_item() -> None:
    user = User(name="Alice", email="alice@example.com")
    order = Order(order_id=1, user=user)
    order.add_item("Widget")
    assert order.total_items() == 1
