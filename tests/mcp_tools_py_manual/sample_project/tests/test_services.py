"""Tests for services module."""

from tests.mcp_tools_py_manual.sample_project.models import User
from tests.mcp_tools_py_manual.sample_project.services import (
    place_order,
    register_user,
)


def test_register_user() -> None:
    user = register_user("Alice", "alice@example.com")
    assert isinstance(user, User)
    assert user.name == "Alice"


def test_place_order_active() -> None:
    user = register_user("Alice", "alice@example.com")
    order = place_order(user, ["Widget", "Gadget"])
    assert order is not None
    assert order.total_items() == 2


def test_place_order_inactive() -> None:
    user = register_user("Alice", "alice@example.com")
    user.deactivate()
    order = place_order(user, ["Widget"])
    assert order is None
