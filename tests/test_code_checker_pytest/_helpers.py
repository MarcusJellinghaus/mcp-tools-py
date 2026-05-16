"""Project-builder helpers for code_checker_pytest integration tests."""

from pathlib import Path


def _create_focused_project(project_dir: Path) -> None:
    """Create a small focused project with 1 passing test and 1 failing test with prints."""
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)

    # Create conftest.py
    (project_dir / "tests" / "conftest.py").write_text("""
# Basic pytest configuration for focused testing
import pytest

@pytest.fixture
def sample_data():
    return {"value": 42, "name": "test"}
""")

    # Create test_simple.py with print statements
    (project_dir / "tests" / "test_simple.py").write_text("""
def test_passing():
    \"\"\"A simple passing test.\"\"\"
    print("Debug: test_passing started")
    result = 2 + 2
    print(f"Debug: calculation result is {result}")
    assert result == 4
    print("Debug: test_passing completed successfully")

def test_failing_with_prints():
    \"\"\"A failing test that includes print statements for debugging.\"\"\"
    print("Debug: processing value")
    data = {"key": "value"}
    print(f"Debug: data structure is {data}")
    
    # This will fail
    result = len(data)
    print(f"Debug: data length is {result}")
    assert result == 5  # Intentionally wrong
    print("Debug: this line should not be reached")
""")


def _create_large_project(project_dir: Path) -> None:
    """Create a large project with multiple test files and many failures."""
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)

    # Create conftest.py
    (project_dir / "tests" / "conftest.py").write_text("""
import pytest

@pytest.fixture
def common_data():
    return list(range(10))
""")

    # Create test_module_a.py - 5 tests: 3 pass, 2 fail
    (project_dir / "tests" / "test_module_a.py").write_text("""
def test_a1_pass():
    assert 1 == 1

def test_a2_pass():
    assert "hello" == "hello"

def test_a3_pass():
    assert [1, 2, 3] == [1, 2, 3]

def test_a4_fail():
    print("Debug: test_a4_fail executing")
    assert 1 == 2  # Fail

def test_a5_fail():
    print("Debug: test_a5_fail processing data")
    data = [1, 2, 3]
    print(f"Debug: data is {data}")
    assert len(data) == 5  # Fail
""")

    # Create test_module_b.py - 10 tests: 5 pass, 5 fail
    (project_dir / "tests" / "test_module_b.py").write_text("""
def test_b1_pass():
    assert True

def test_b2_pass():
    assert 10 > 5

def test_b3_pass():
    assert "test" in "testing"

def test_b4_pass():
    assert {"a": 1}.get("a") == 1

def test_b5_pass():
    assert not False

def test_b6_fail():
    print("Debug: b6 starting")
    assert False  # Fail

def test_b7_fail():
    print("Debug: b7 calculating")
    result = 5 * 5
    print(f"Result: {result}")
    assert result == 30  # Fail

def test_b8_fail():
    print("Debug: b8 list operations")
    items = [1, 2, 3, 4]
    print(f"Items: {items}")
    assert len(items) == 10  # Fail

def test_b9_fail():
    print("Debug: b9 string operations")
    text = "hello world"
    print(f"Text: {text}")
    assert text.startswith("goodbye")  # Fail

def test_b10_fail():
    print("Debug: b10 dict operations")
    data = {"x": 1, "y": 2}
    print(f"Data: {data}")
    assert data["z"] == 3  # Fail - KeyError
""")

    # Create test_module_c.py - 8 tests: all pass
    (project_dir / "tests" / "test_module_c.py").write_text("""
def test_c1_pass():
    assert 42 == 42

def test_c2_pass():
    assert "python" == "python"

def test_c3_pass():
    assert [1, 2] + [3, 4] == [1, 2, 3, 4]

def test_c4_pass():
    assert max([1, 5, 3]) == 5

def test_c5_pass():
    assert min([1, 5, 3]) == 1

def test_c6_pass():
    assert sum([1, 2, 3]) == 6

def test_c7_pass():
    assert len("hello") == 5

def test_c8_pass():
    assert sorted([3, 1, 2]) == [1, 2, 3]
""")


def _create_edge_case_project(project_dir: Path) -> None:
    """Create project with edge cases: collection errors and all passing tests."""
    (project_dir / "tests").mkdir(parents=True, exist_ok=True)

    # Create test_no_assertions.py with collection errors
    (project_dir / "tests" / "test_no_assertions.py").write_text("""
# This will cause collection errors
import non_existent_module

def test_with_import_error():
    non_existent_module.do_something()
    assert True
    
def test_syntax_error():
    # Intentional syntax error
    if True
        assert True
""")

    # Create test_all_pass.py with only passing tests
    (project_dir / "tests" / "test_all_pass.py").write_text("""
def test_simple_pass():
    print("Debug: simple test passing")
    assert True

def test_math_pass():
    print("Debug: math test")
    assert 2 + 2 == 4

def test_string_pass():
    print("Debug: string test")
    assert "hello".upper() == "HELLO"
""")
