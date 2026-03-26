# Sample Project — File Contents

Source files for the test plan. All imports use fully-qualified paths from the repo root.

## Structure

```
sample_project/
├── __init__.py
├── models.py
├── utils.py
├── services.py
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_utils.py
    └── test_services.py
```

---

## `__init__.py`

Empty file. Same for `tests/__init__.py`.

---

## `models.py`

Two constants, two classes. No imports from other sample modules — this is the leaf dependency.

```python
"""Domain models for the sample project."""

MAX_NAME_LENGTH: int = 100
DEFAULT_STATUS: str = "active"


class User:
    """A simple user model."""

    def __init__(self, name: str, email: str) -> None:
        self.name = name[:MAX_NAME_LENGTH]
        self.email = email
        self.status = DEFAULT_STATUS

    def deactivate(self) -> None:
        """Mark the user as inactive."""
        self.status = "inactive"

    def __repr__(self) -> str:
        return f"User(name={self.name!r}, status={self.status!r})"


class Order:
    """A simple order model."""

    def __init__(self, order_id: int, user: User) -> None:
        self.order_id = order_id
        self.user = user
        self.items: list[str] = []

    def add_item(self, item: str) -> None:
        """Add an item to the order."""
        self.items.append(item)

    def total_items(self) -> int:
        """Return the number of items."""
        return len(self.items)
```

---

## `utils.py`

Three functions. Imports `User`, `MAX_NAME_LENGTH`, `DEFAULT_STATUS` from `models`.

```python
"""Utility functions that depend on models."""

from tests.mcp_tools_py_manual.sample_project.models import (
    DEFAULT_STATUS,
    MAX_NAME_LENGTH,
    User,
)


def create_user(name: str, email: str) -> User:
    """Create a user with validation."""
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Name exceeds {MAX_NAME_LENGTH} characters")
    return User(name=name, email=email)


def is_active(user: User) -> bool:
    """Check if a user is active."""
    return user.status == DEFAULT_STATUS


def format_user(user: User) -> str:
    """Format user for display."""
    return f"{user.name} <{user.email}>"
```

---

## `services.py`

Two functions. Imports from both `models` and `utils`.

```python
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
```

---

## `tests/test_models.py`

4 tests. Imports `User`, `Order`, `MAX_NAME_LENGTH`, `DEFAULT_STATUS` from `models`.

```python
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
```

---

## `tests/test_utils.py`

4 tests. Imports from `models` and `utils`.

```python
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
```

---

## `tests/test_services.py`

3 tests. Imports from `models` and `services`.

```python
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
```

---

## Dependency Graph

```
test_services.py ──→ services.py ──→ utils.py ──→ models.py
test_utils.py    ──→ utils.py    ──→ models.py
test_models.py   ──→ models.py
```

This chain ensures that renaming a symbol in `models.py` must propagate through `utils.py`, `services.py`, and all three test files.
