# Step 1: SanitizedArgs dataclass + sanitize_extra_args() with unit tests

> **Context**: Read `pr_info/steps/summary.md` for the full issue overview. This step adds the core deduplication logic that Step 2 will integrate into `server.py`.

## TDD: Tests first, then implementation

---

## Part A: Unit tests for sanitize_extra_args()

### WHERE
- **Create**: `tests/test_code_checker_pytest/test_extra_args.py`

### WHAT
Test function scenarios matching the deduplication table from the issue:

```python
# Test cases to cover:
def test_no_extra_args_returns_defaults()
    # sanitize_extra_args(None, None) -> cleaned_args=[], verbosity=2, notes=[]

def test_passthrough_unrelated_args()
    # sanitize_extra_args(["-x", "--tb=short"], None) -> cleaned_args=["-x", "--tb=short"], verbosity=2

def test_v_flag_extracts_verbosity()
    # sanitize_extra_args(["-v"], None) -> cleaned_args=[], verbosity=1
    # sanitize_extra_args(["-vv"], None) -> cleaned_args=[], verbosity=2
    # sanitize_extra_args(["-vvv"], None) -> cleaned_args=[], verbosity=3

def test_v_flag_mixed_with_other_args()
    # sanitize_extra_args(["-x", "-vvv", "--tb=short"], None) -> cleaned_args=["-x", "--tb=short"], verbosity=3

def test_s_flag_removed_silently()
    # sanitize_extra_args(["-s", "-x"], None) -> cleaned_args=["-x"], verbosity=2, notes=[]

def test_m_flag_removed_when_markers_provided()
    # sanitize_extra_args(["-m", "slow"], ["integration"]) -> cleaned_args=[], verbosity=2
    # notes=["Note: -m flag in extra_args was ignored because the markers parameter was used."]

def test_m_flag_kept_when_no_markers()
    # sanitize_extra_args(["-m", "slow"], None) -> cleaned_args=["-m", "slow"], verbosity=2, notes=[]

def test_tests_path_removed()
    # sanitize_extra_args(["tests"], None) -> cleaned_args=[], verbosity=2
    # sanitize_extra_args(["tests/"], None) -> cleaned_args=[], verbosity=2

def test_combined_deduplication()
    # sanitize_extra_args(["-s", "-vvv", "-m", "slow", "tests", "-x"], ["unit"])
    # -> cleaned_args=["-x"], verbosity=3
    # -> notes contains the -m warning
```

### HOW
```python
import pytest
from mcp_code_checker.code_checker_pytest.utils import sanitize_extra_args
from mcp_code_checker.code_checker_pytest.models import SanitizedArgs
```

### DATA
Each test asserts against `SanitizedArgs` fields: `cleaned_args`, `verbosity`, `notes`.

---

## Part B: SanitizedArgs dataclass

### WHERE
- **Modify**: `src/mcp_code_checker/code_checker_pytest/models.py`

### WHAT
Add at the end of the file (after `PytestReport`):

```python
@dataclass
class SanitizedArgs:
    """Result of sanitizing extra_args for pytest execution."""
    cleaned_args: list[str]
    verbosity: int
    notes: list[str]
```

### HOW
- Uses existing `dataclass` import already at top of file
- No new imports needed

---

## Part C: Export SanitizedArgs

### WHERE
- **Modify**: `src/mcp_code_checker/code_checker_pytest/__init__.py`

### WHAT
- Add `SanitizedArgs` to the import from `models`
- Add `"SanitizedArgs"` to `__all__`

---

## Part D: sanitize_extra_args() function

### WHERE
- **Modify**: `src/mcp_code_checker/code_checker_pytest/utils.py`

### WHAT
```python
def sanitize_extra_args(
    extra_args: list[str] | None,
    markers: list[str] | None,
) -> SanitizedArgs:
```

### ALGORITHM (pseudocode)
```
1. If extra_args is None or empty, return SanitizedArgs([], 2, [])
2. Initialize: cleaned=[], verbosity=2, notes=[], skip_next=False
3. Iterate over extra_args with index:
   a. If skip_next: skip_next=False, continue
   b. If arg is "-v"/"-vv"/"-vvv": set verbosity = count of 'v' chars, skip arg
   c. If arg is "-s": skip arg (always auto-added)
   d. If arg is "tests" or "tests/": skip arg (auto-appended)
   e. If arg is "-m" AND markers is not None: skip arg + next arg, add note
   f. Else: append to cleaned
4. Return SanitizedArgs(cleaned, verbosity, notes)
```

### HOW
```python
from mcp_code_checker.code_checker_pytest.models import ErrorContext, SanitizedArgs
```
- Add import of `SanitizedArgs` to existing import line
- Add `import structlog` and log notes via `structured_logger.info("extra_args sanitized", ...)`

### DATA
- **Input**: `extra_args: list[str] | None`, `markers: list[str] | None`
- **Output**: `SanitizedArgs(cleaned_args=list[str], verbosity=int, notes=list[str])`
- Only handles `-m` as two separate args (`["-m", "slow"]`), not combined form

---

## Verification
After this step:
- `pytest tests/test_code_checker_pytest/test_extra_args.py` passes
- `mypy src/mcp_code_checker/code_checker_pytest/models.py src/mcp_code_checker/code_checker_pytest/utils.py` passes
- No changes to `server.py` or `runners.py` yet
