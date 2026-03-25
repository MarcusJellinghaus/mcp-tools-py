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

# Real project dir — same as what the MCP server uses
_REAL_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent


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


# --- Real project dir tests (issue #112) ---
# These run against the actual project root, exactly like the MCP server does.
# TODO: Consider reverting to tmp_path-based tests — testing from tmp is more
# isolated and reproducible. These were added to diagnose a hang that only
# reproduced with the real project dir.


@pytest.mark.integration
def test_rename_symbol_real_project_does_not_hang() -> None:
    """rename_symbol on real project dir must not hang (dry_run)."""
    start = time.monotonic()
    result = rename_symbol(
        _REAL_PROJECT_DIR,
        "tests/mcp_tools_py_manual/sample_project/models.py",
        "MAX_NAME_LENGTH",
        "NAME_MAX_CHARS",
        dry_run=True,
    )
    elapsed = time.monotonic() - start
    assert (
        elapsed < _HANG_TIMEOUT
    ), f"rename_symbol took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
    assert "[DRY RUN]" in result


@pytest.mark.integration
def test_move_symbol_real_project_does_not_hang() -> None:
    """move_symbol on real project dir must not hang (dry_run)."""
    start = time.monotonic()
    result = move_symbol(
        _REAL_PROJECT_DIR,
        "tests/mcp_tools_py_manual/sample_project/utils.py",
        "format_user",
        "tests/mcp_tools_py_manual/sample_project/services.py",
        dry_run=True,
    )
    elapsed = time.monotonic() - start
    assert (
        elapsed < _HANG_TIMEOUT
    ), f"move_symbol took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
    assert "[DRY RUN]" in result


@pytest.mark.integration
def test_move_module_real_project_does_not_hang(tmp_path: Path) -> None:
    """move_module on real project dir must not hang (dry_run)."""
    # move_module dry_run requires dest package to exist
    # Use a temp subdir inside the sample_project for the dest
    dest_pkg = (
        _REAL_PROJECT_DIR
        / "tests"
        / "mcp_tools_py_manual"
        / "sample_project"
        / "_tmp_helpers"
    )
    dest_pkg.mkdir(exist_ok=True)
    (dest_pkg / "__init__.py").write_text("")
    try:
        start = time.monotonic()
        result = move_module(
            _REAL_PROJECT_DIR,
            "tests/mcp_tools_py_manual/sample_project/utils.py",
            "tests/mcp_tools_py_manual/sample_project/_tmp_helpers",
            dry_run=True,
        )
        elapsed = time.monotonic() - start
        assert (
            elapsed < _HANG_TIMEOUT
        ), f"move_module took {elapsed:.1f}s (limit {_HANG_TIMEOUT}s)"
        assert "[DRY RUN]" in result
    finally:
        # Clean up temp dest package
        (dest_pkg / "__init__.py").unlink(missing_ok=True)
        dest_pkg.rmdir()
