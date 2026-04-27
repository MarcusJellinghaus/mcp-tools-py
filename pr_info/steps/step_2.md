# Step 2: Server Tach Binary Resolution + Availability Tests

## LLM Prompt
> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`, then implement step 2. Follow TDD: update `tests/test_tool_availability.py` first, then add the tach block in `server.py`. Run `mcp__tools-py__run_pylint_check`, `run_pytest_check`, and `run_mypy_check`; all must pass before commit.

## WHERE

Modify:
- `src/mcp_tools_py/server.py` — add tach binary resolution in `_check_tool_availability()`; add `self._tach_binary` attribute.
- `tests/test_tool_availability.py` — extend two exact-equality dicts to include `"tach"`.

## WHAT

In `ToolServer._check_tool_availability()` add a tach block after the bandit block:

```python
# tach: check via file existence (not subprocess)
tach_available = False
tach_binary: Optional[str] = None
if self.venv_path:
    if os.name == "nt":
        tach_binary = os.path.join(self.venv_path, "Scripts", "tach.exe")
    else:
        tach_binary = os.path.join(self.venv_path, "bin", "tach")
    tach_available = os.path.exists(tach_binary)
self._tach_binary: Optional[str] = tach_binary if tach_available else None
availability["tach"] = tach_available
if not tach_available:
    logger.warning(
        "tach not found. Ensure --venv-path points to "
        "an environment where tach is installed."
    )
```

## HOW

- Identical pattern to vulture/ruff/bandit. No new helpers — inline copy keeps consistency with neighboring blocks (consistent with existing style; not worth refactoring in this PR).
- `self._tach_binary` exposed for use in step 3.

## ALGORITHM

```
if venv_path set:
    binary = venv_path/{Scripts|bin}/tach{.exe|}
    available = os.path.exists(binary)
self._tach_binary = binary if available else None
availability["tach"] = available
log warning if unavailable
```

## DATA

- New attribute `self._tach_binary: Optional[str]`
- New key `"tach"` in `self._tool_availability` dict (bool)

## Test Updates

In `tests/test_tool_availability.py`:

1. `TestCheckToolAvailability.test_all_tools_available` — extend asserted dict:
   ```python
   assert server._tool_availability == {
       "lint-imports": True,
       "vulture": True,
       "ruff": True,
       "bandit": True,
       "tach": True,
   }
   ```
2. `TestCheckToolAvailability.test_all_tools_missing` — extend with `"tach": False`.

No new test cases added (per simplification: keep `test_runners.py` as the actual coverage for tach behavior).

## Acceptance

- `run_pytest_check` (fast unit run) — all pass.
- `run_pylint_check`, `run_mypy_check` — clean.
- `tests/test_tool_availability.py` exact-equality assertions still match.
- One commit: test update + server change.
