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
