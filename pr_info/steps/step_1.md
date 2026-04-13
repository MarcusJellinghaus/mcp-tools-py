# Step 1: Add `_is_tool_available()` and Shrink `_check_tool_availability()`

> **Context**: See `pr_info/steps/summary.md` for full issue context and architectural overview.

## Goal

Transform `server.py` so that the 5 slow subprocess checks (pytest, pylint, mypy, black, isort) no longer block `__init__`. Add a lazy `_is_tool_available()` method. Update `test_tool_availability.py` to match.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/server.py` | Modify |
| `tests/test_tool_availability.py` | Modify |

## WHAT — `server.py` Changes

### 1a. Shrink `_check_tool_availability()` — remove subprocess block

Remove the `ThreadPoolExecutor` block and the 5-tool subprocess loop. Keep only the 4 file-existence checks (lint-imports, vulture, ruff, bandit) which set binary path attributes.

Remove unused imports: `ThreadPoolExecutor`, `as_completed` from `concurrent.futures`.

**Signature** (unchanged): `def _check_tool_availability(self) -> dict[str, bool]`

**After**: Returns dict with only 4 keys: `lint-imports`, `vulture`, `ruff`, `bandit`.

### 1b. Add `_is_tool_available()` method

```python
def _is_tool_available(self, tool_name: str) -> bool
```

**Algorithm** (pseudocode):
```
if tool_name in self._tool_availability:
    return self._tool_availability[tool_name]
result = execute_command([self._resolved_python, "-m", tool_name, "--version"], timeout_seconds=10)
available = result.return_code == 0 and not result.execution_error
if available:
    logger.info("%s version: %s", tool_name, result.stdout.strip())
else:
    logger.warning("%s not found in %s. ...", tool_name, self._resolved_python, tool_name)
self._tool_availability[tool_name] = available
return available
```

**DATA**: Returns `bool`. Side-effect: populates `self._tool_availability[tool_name]`.

### 1c. Remove startup debug log

Remove the `logger.debug("Tool environment resolved", ...)` block at the end of `__init__` that dumps `tool_availability`.

## WHAT — `test_tool_availability.py` Changes

### Tests to update in `TestCheckToolAvailability`:

- `test_all_tools_available`: Expected dict shrinks to 4 eager keys (lint-imports, vulture, ruff, bandit). The 5 subprocess tools are no longer in the dict after init.
  Expected dict: `{"lint-imports": True, "vulture": True, "ruff": True, "bandit": True}`
- `test_one_tool_missing`: Delete — this test's concept (one subprocess tool fails at init time) no longer applies. The scenario is covered by `test_unavailable_tool_logs_warning` in the new `TestIsToolAvailable` class.
- `test_all_tools_missing`: Expected dict shrinks to 4 eager keys (all False).
  Expected dict: `{"lint-imports": False, "vulture": False, "ruff": False, "bandit": False}`
- `test_timed_out_tool_marked_unavailable`: Expected dict shrinks to 4 eager keys.
  Expected dict: `{"lint-imports": True, "vulture": True, "ruff": True, "bandit": True}` (timeout only applied to subprocess tools which are gone; eager file-checks aren't affected by subprocess timeouts)
- `test_black_available`, `test_isort_available`: Remove (these tested subprocess-based checks at init time; now covered by lazy tests).
- `test_parallel_execution_maps_results_correctly`: Remove (ThreadPoolExecutor is gone).

### New test class: `TestIsToolAvailable`

- `test_first_call_runs_subprocess_and_caches`: Call `_is_tool_available("pytest")` → verify `execute_command` called once, result cached in `_tool_availability["pytest"]`.
- `test_second_call_returns_cached_no_subprocess`: Pre-populate `_tool_availability["pytest"] = True` → call `_is_tool_available("pytest")` → verify `execute_command` NOT called.
- `test_eager_tool_returned_from_cache`: Pre-populate `_tool_availability["ruff"] = True` at init → call `_is_tool_available("ruff")` → verify no subprocess, returns True.
- `test_unavailable_tool_logs_warning`: Call `_is_tool_available("pytest")` with failing execute_command → verify result is False and cached.
- `test_available_tool_logs_version`: Call `_is_tool_available("pytest")` with successful execute_command returning "pytest 8.0.0" → verify result is True.

### Tests to update in `TestToolHandlerShortCircuit`:

These tests set `server._tool_availability` as a dict, then call tool handlers. After this step, the tool handlers still use the old `.get()` API (changed in step 2), so these tests remain unchanged in step 1.

## HOW — Integration Points

- `_is_tool_available()` uses the existing `execute_command` from `mcp_coder_utils.subprocess_runner` (already imported in `server.py`).
- No new imports needed.
- `_check_tool_availability()` no longer needs `ThreadPoolExecutor` / `as_completed` — remove those imports.

## LLM Prompt

```
Implement Step 1 of issue #158 (defer tool availability checks).
See pr_info/steps/summary.md for context and pr_info/steps/step_1.md for detailed spec.

In server.py:
1. Remove the ThreadPoolExecutor subprocess block from _check_tool_availability() — keep only the 4 file-existence checks (lint-imports, vulture, ruff, bandit).
2. Remove the concurrent.futures imports (ThreadPoolExecutor, as_completed).
3. Add _is_tool_available(self, tool_name: str) -> bool that checks the cache dict first, runs subprocess on miss, logs version or warning, caches and returns.
4. Remove the logger.debug("Tool environment resolved", ...) block at end of __init__.

In test_tool_availability.py:
1. Update TestCheckToolAvailability tests — expected dicts now have 4 eager keys only.
2. Remove test_black_available, test_isort_available, test_parallel_execution_maps_results_correctly.
3. Add TestIsToolAvailable class with tests for: first-call subprocess+cache, second-call cache-hit, eager-tool cache-hit, unavailable-tool caching, version logging.

Run all three quality checks after changes. All must pass.
```
