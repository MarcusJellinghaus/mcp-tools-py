"""Service layer that depends on models and utils."""

from tests.mcp_tools_py_manual.sample_project.models import Order, User
from tests.mcp_tools_py_manual.sample_project.utils import create_user, is_active


def register_user(name: str, email: str) -> User:
    """Register a new user."""
    user = create_user(name, email)
    return user


def place_order(user: User, items: list[str]) -> Order | None:
    """Place an order for an active user."""
    if not is_active(user):
        return None
    order = Order(order_id=1, user=user)
    for item in items:
        order.add_item(item)
    return order
