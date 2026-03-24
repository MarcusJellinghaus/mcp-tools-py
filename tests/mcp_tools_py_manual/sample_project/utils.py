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
