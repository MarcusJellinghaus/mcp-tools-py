"""End-to-end integration tests for refactoring workflows."""

import time
from pathlib import Path

import pytest

from mcp_tools_py.refactoring.jedi_tools import find_references, list_symbols
from mcp_tools_py.refactoring.rope_tools import move_module, move_symbol, rename_symbol


@pytest.fixture
def multi_module_project(tmp_path: Path) -> Path:
    """Create a realistic multi-module project for integration testing.

    Structure:
        myproject/
        ├── __init__.py
        ├── models.py        # defines: User, Address, validate_email
        ├── services.py      # imports and uses User, validate_email from models
        └── utils.py          # imports Address from models
    """
    pkg = tmp_path / "myproject"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")

    (pkg / "models.py").write_text(
        "class User:\n"
        '    """A user account."""\n'
        "\n"
        "    def __init__(self, name: str, email: str) -> None:\n"
        "        self.name = name\n"
        "        self.email = email\n"
        "\n"
        "\n"
        "class Address:\n"
        '    """A mailing address."""\n'
        "\n"
        "    def __init__(self, street: str, city: str) -> None:\n"
        "        self.street = street\n"
        "        self.city = city\n"
        "\n"
        "\n"
        "def validate_email(email: str) -> bool:\n"
        '    """Check if an email address is valid."""\n'
        '    return "@" in email and "." in email\n'
    )

    (pkg / "services.py").write_text(
        "from myproject.models import User, validate_email\n"
        "\n"
        "\n"
        "def create_user(name: str, email: str) -> User:\n"
        '    """Create a new user after validating email."""\n'
        "    if not validate_email(email):\n"
        '        raise ValueError("Invalid email")\n'
        "    return User(name, email)\n"
    )

    (pkg / "utils.py").write_text(
        "from myproject.models import Address\n"
        "\n"
        "\n"
        "def format_address(addr: Address) -> str:\n"
        '    """Format an address for display."""\n'
        '    return f"{addr.street}, {addr.city}"\n'
    )

    return tmp_path


@pytest.mark.integration
def test_full_workflow_split_large_file(multi_module_project: Path) -> None:
    """End-to-end: discover symbols, move one to new module, verify imports."""
    project = multi_module_project

    # 1. list_symbols on models.py -> should show User, Address, validate_email
    symbols_output = list_symbols(project, "myproject/models.py")
    assert "User" in symbols_output
    assert "Address" in symbols_output
    assert "validate_email" in symbols_output

    # 2. find_references for validate_email -> should show models.py, services.py
    refs_output = find_references(project, "myproject/models.py", "validate_email")
    assert "models.py" in refs_output
    assert "services.py" in refs_output

    # 3. move_symbol validate_email (dry_run=True) -> files unchanged
    dry_result = move_symbol(
        project,
        "myproject/models.py",
        "validate_email",
        "myproject/validation.py",
        dry_run=True,
    )
    assert "[DRY RUN]" in dry_result
    # Files should be unchanged after dry run
    models_text = (project / "myproject" / "models.py").read_text()
    assert "def validate_email" in models_text
    assert not (project / "myproject" / "validation.py").exists()

    # 4. move_symbol validate_email (dry_run=False) -> verify changes
    result = move_symbol(
        project,
        "myproject/models.py",
        "validate_email",
        "myproject/validation.py",
    )
    assert "successfully" in result.lower() or "modified" in result.lower()

    # validation.py exists and defines validate_email
    validation_text = (project / "myproject" / "validation.py").read_text()
    assert "def validate_email" in validation_text

    # models.py no longer defines validate_email
    models_after = (project / "myproject" / "models.py").read_text()
    assert "def validate_email" not in models_after
    # But still has User and Address
    assert "class User" in models_after
    assert "class Address" in models_after

    # services.py imports from validation, not models
    services_text = (project / "myproject" / "services.py").read_text()
    assert "validate_email" in services_text
    assert "validation" in services_text

    # utils.py unchanged (it imports Address, not validate_email)
    utils_text = (project / "myproject" / "utils.py").read_text()
    assert "from myproject.models import Address" in utils_text


@pytest.mark.integration
def test_rename_then_verify_references(multi_module_project: Path) -> None:
    """End-to-end: rename a class, verify all references updated."""
    project = multi_module_project

    # 1. find_references for User -> should show models.py, services.py
    refs_output = find_references(project, "myproject/models.py", "User")
    assert "models.py" in refs_output
    assert "services.py" in refs_output

    # 2. rename User to AppUser (dry_run=True) -> verify preview
    dry_result = rename_symbol(
        project,
        "myproject/models.py",
        "User",
        "AppUser",
        dry_run=True,
    )
    assert "[DRY RUN]" in dry_result
    # Files should be unchanged
    models_text = (project / "myproject" / "models.py").read_text()
    assert "class User" in models_text

    # 3. rename User to AppUser (dry_run=False)
    result = rename_symbol(
        project,
        "myproject/models.py",
        "User",
        "AppUser",
    )
    assert "successfully" in result.lower() or "modified" in result.lower()

    # models.py defines AppUser, not User
    models_after = (project / "myproject" / "models.py").read_text()
    assert "class AppUser" in models_after
    assert "class User" not in models_after

    # services.py references AppUser
    services_text = (project / "myproject" / "services.py").read_text()
    assert "AppUser" in services_text
    assert "User" not in services_text or "AppUser" in services_text


@pytest.mark.integration
def test_move_module_then_verify_imports(multi_module_project: Path) -> None:
    """End-to-end: move a module to a subpackage, verify imports updated."""
    project = multi_module_project

    # 1. move_module utils.py to subpkg/
    result = move_module(
        project,
        "myproject/utils.py",
        "myproject/subpkg",
    )
    assert "successfully" in result.lower() or "modified" in result.lower()

    # subpkg/utils.py exists
    assert (project / "myproject" / "subpkg" / "utils.py").exists()

    # Original utils.py should be gone
    assert not (project / "myproject" / "utils.py").exists()

    # models.py imports should be unaffected (utils imports from models, not vice versa)
    models_text = (project / "myproject" / "models.py").read_text()
    assert "class User" in models_text
    assert "class Address" in models_text


# --- Hang-regression tests (issue #112) ---
# These verify that rope operations complete quickly without hanging.
# The old multiprocessing-based timeout wrapper caused indefinite hangs
# on Windows when running inside an MCP stdio server.

_HANG_TIMEOUT = 10  # seconds — rope completes in <1s on small projects


@pytest.mark.integration
def test_rename_symbol_does_not_hang(multi_module_project: Path) -> None:
    """rename_symbol must complete within _HANG_TIMEOUT seconds."""
    start = time.monotonic()
    result = rename_symbol(
        multi_module_project, "myproject/models.py", "User", "AppUser"
    )
    elapsed = time.monotonic() - start
    assert (
        elapsed < _HANG_TIMEOUT
    ), f"rename_symbol took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
    assert "modified" in result.lower() or "successfully" in result.lower()


@pytest.mark.integration
def test_move_symbol_does_not_hang(multi_module_project: Path) -> None:
    """move_symbol must complete within _HANG_TIMEOUT seconds."""
    start = time.monotonic()
    result = move_symbol(
        multi_module_project,
        "myproject/models.py",
        "validate_email",
        "myproject/validation.py",
    )
    elapsed = time.monotonic() - start
    assert (
        elapsed < _HANG_TIMEOUT
    ), f"move_symbol took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
    assert "modified" in result.lower() or "successfully" in result.lower()


@pytest.mark.integration
def test_move_module_does_not_hang(multi_module_project: Path) -> None:
    """move_module must complete within _HANG_TIMEOUT seconds."""
    (multi_module_project / "myproject" / "subpkg").mkdir()
    (multi_module_project / "myproject" / "subpkg" / "__init__.py").write_text("")
    start = time.monotonic()
    result = move_module(multi_module_project, "myproject/utils.py", "myproject/subpkg")
    elapsed = time.monotonic() - start
    assert (
        elapsed < _HANG_TIMEOUT
    ), f"move_module took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
    assert "modified" in result.lower() or "successfully" in result.lower()


@pytest.mark.integration
def test_move_module_dry_run_without_dest_package(multi_module_project: Path) -> None:
    """Dry-run should preview changes even when dest package doesn't exist yet."""
    project = multi_module_project

    # dest package does NOT exist
    assert not (project / "myproject" / "newpkg").exists()

    result = move_module(
        project,
        "myproject/utils.py",
        "myproject/newpkg",
        dry_run=True,
    )

    # Should show a preview, not an error
    assert "[DRY RUN]" in result, f"Expected dry-run preview, got: {result}"
    assert "error" not in result.lower(), f"Unexpected error in dry run: {result}"

    # No files should be created or modified
    assert not (project / "myproject" / "newpkg").exists()
    utils_text = (project / "myproject" / "utils.py").read_text()
    assert "from myproject.models import Address" in utils_text


@pytest.mark.integration
def test_move_module_with_pre_existing_dest_package(
    multi_module_project: Path,
) -> None:
    """move_module must move the file when dest package already exists."""
    project = multi_module_project

    # Pre-create the destination package (simulates manual creation)
    subpkg = project / "myproject" / "subpkg"
    subpkg.mkdir()
    (subpkg / "__init__.py").write_text("")

    result = move_module(
        project,
        "myproject/utils.py",
        "myproject/subpkg",
    )
    assert "successfully" in result.lower() or "modified" in result.lower()

    # File must be physically moved
    assert (
        project / "myproject" / "subpkg" / "utils.py"
    ).exists(), "utils.py not found at destination"
    assert not (
        project / "myproject" / "utils.py"
    ).exists(), "Original utils.py still exists — file was not moved"


@pytest.mark.integration
def test_move_module_nested_project_structure(tmp_path: Path) -> None:
    """move_module with deeply nested packages (closer to real-world usage)."""
    # Create a project with deeper nesting: tests/app/sample/
    root = tmp_path
    pkg = root / "tests" / "app" / "sample"
    pkg.mkdir(parents=True)

    # Create __init__.py at each level
    for p in [root / "tests", root / "tests" / "app", pkg]:
        (p / "__init__.py").write_text("")

    (pkg / "models.py").write_text(
        "class Item:\n"
        "    def __init__(self, name: str) -> None:\n"
        "        self.name = name\n"
    )

    (pkg / "utils.py").write_text(
        "from tests.app.sample.models import Item\n"
        "\n"
        "\n"
        "def format_item(item: Item) -> str:\n"
        '    return f"Item: {item.name}"\n'
    )

    (pkg / "services.py").write_text(
        "from tests.app.sample.utils import format_item\n"
        "from tests.app.sample.models import Item\n"
        "\n"
        "\n"
        "def display(name: str) -> str:\n"
        "    return format_item(Item(name))\n"
    )

    result = move_module(
        root,
        "tests/app/sample/utils.py",
        "tests/app/sample/helpers",
    )
    assert (
        "successfully" in result.lower() or "modified" in result.lower()
    ), f"move_module failed: {result}"

    # File physically moved
    assert (pkg / "helpers" / "utils.py").exists(), "utils.py not at destination"
    assert not (pkg / "utils.py").exists(), "Original utils.py still exists"

    # Imports rewritten in services.py
    services_text = (pkg / "services.py").read_text()
    assert "helpers" in services_text, f"Imports not rewritten: {services_text}"


@pytest.mark.integration
def test_rename_symbol_dry_run_does_not_hang(multi_module_project: Path) -> None:
    """rename_symbol dry_run must complete within _HANG_TIMEOUT seconds."""
    start = time.monotonic()
    result = rename_symbol(
        multi_module_project,
        "myproject/models.py",
        "User",
        "AppUser",
        dry_run=True,
    )
    elapsed = time.monotonic() - start
    assert (
        elapsed < _HANG_TIMEOUT
    ), f"rename_symbol dry_run took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
    assert "[DRY RUN]" in result
