# Step 1: Add `format_command()` Function with Tests (TDD)

> **Context**: See `pr_info/steps/summary.md` for issue overview.

## Goal

Add the `format_command()` public function to `subprocess_runner.py` with full
test coverage. This step does NOT modify any log sites — that happens in Step 2.

## WHERE

- **Modify**: `src/mcp_tools_py/utils/subprocess_runner.py`
- **Modify**: `tests/test_subprocess_runner.py`

## WHAT

### New function in `subprocess_runner.py`

```python
def format_command(command: list[str]) -> str:
    """Format a command list as a platform-aware shell string.

    Uses shlex.join() on Unix, subprocess.list2cmdline() on Windows.
    Truncates at 200 characters with '...' suffix.
    """
```

### New test class in `tests/test_subprocess_runner.py`

```python
class TestFormatCommand:
    @pytest.mark.parametrize("command,expected_truncated", [...])
    def test_truncation_boundary(self, command, expected_truncated) -> None: ...
    def test_single_element_command(self) -> None: ...
    def test_empty_command(self) -> None: ...
    def test_unix_uses_shlex_join(self) -> None: ...
    def test_windows_uses_list2cmdline(self) -> None: ...
```

## HOW

- Add `import shlex` at top of `subprocess_runner.py`
- Add `"format_command"` to the `__all__` list
- Add `format_command` import in test file's import block
- Place function after `truncate_stderr()` (utility functions section)

## ALGORITHM

```
def format_command(command):
    if os.name == "nt":
        full = subprocess.list2cmdline(command)
    else:
        full = shlex.join(command)
    if len(full) > 200:
        return full[:200] + "..."
    return full
```

## DATA

- **Input**: `list[str]` — command and arguments
- **Output**: `str` — shell-formatted string, max 203 chars (200 + "...")

## Commit

One commit: `Add format_command() helper for full command logging (#96)`

---

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.

Implement Step 1 of issue #96: Add the format_command() function to
subprocess_runner.py with tests.

1. Write tests FIRST in tests/test_subprocess_runner.py (TestFormatCommand class)
2. Implement format_command() in src/mcp_tools_py/utils/subprocess_runner.py
3. Add import shlex and export in __all__
4. Run all three quality checks (pylint, pytest, mypy)
5. Commit when all checks pass

Do NOT modify any log sites yet — that is Step 2.
```
