# Step 1: Parallelize tool availability checks

> **Commit message:** `perf: parallelize tool availability checks at startup (#154)`
>
> **Reference:** See `pr_info/steps/summary.md` for full context.

## Test (TDD — write first)

### WHERE
`tests/test_tool_availability.py` — add one test to `TestCheckToolAvailability`

### WHAT
```python
def test_parallel_execution_maps_results_correctly(self) -> None:
```

### HOW
Uses the same `_create_server` helper and mock patterns as existing tests. Each of the 5 tools gets a distinct `side_effect` response (mix of available/unavailable), verifying results are correctly mapped to tool names regardless of execution order. Additionally patches `concurrent.futures.ThreadPoolExecutor` to wrap and verify that `submit()` was called 5 times, confirming parallel execution.

### ALGORITHM
```
1. Define side_effect that returns success for pytest/mypy/isort, failure for pylint/black
2. Patch FastMCP + execute_command with that side_effect
3. Create server via _create_server()
4. Assert _tool_availability["pytest"] is True
5. Assert _tool_availability["pylint"] is False
6. Assert _tool_availability["black"] is False
7. Assert _tool_availability["mypy"] is True
8. Assert _tool_availability["isort"] is True
9. Assert ThreadPoolExecutor.submit was called 5 times
```

### DATA
Asserts against `server._tool_availability` dict — same structure as existing tests.

---

## Implementation

### WHERE
`src/mcp_tools_py/server.py`

### WHAT — New import (module-level)
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
```

### WHAT — Modified method
```python
def _check_tool_availability(self) -> dict[str, bool]:
```
Signature unchanged. Internal implementation changes only.

### ALGORITHM
```
1. Define _check_one(tool) that calls execute_command and returns (tool, available)
   where: available = result.return_code == 0 and not result.execution_error
2. Open ThreadPoolExecutor context manager
3. Submit _check_one for each tool in ["pytest", "pylint", "mypy", "black", "isort"]
4. Iterate as_completed(futures), extract (tool, available), log warning if not available
5. After executor block: lint-imports and vulture checks stay exactly as-is (sequential os.path.exists)
6. Return availability dict
```

### HOW — Integration
- `_check_one` is a local closure inside `_check_tool_availability` (not a method) — it captures `self._resolved_python` from the enclosing scope.
- `Mock.side_effect` is thread-safe for reads, so existing tests won't break under threaded execution.
- The `ThreadPoolExecutor` is used as a context manager (`with` statement) so cleanup is automatic.
- `futures` is a dict mapping `Future -> tool_name` for result extraction in `as_completed`.

### DATA
Return type unchanged: `dict[str, bool]` with keys `["pytest", "pylint", "mypy", "black", "isort", "lint-imports", "vulture"]`.

---

## Verification Checklist
- [ ] New test passes
- [ ] All existing tests in `test_tool_availability.py` still pass (mocks are order-independent)
- [ ] `mcp__tools-py__run_pylint_check` — no issues
- [ ] `mcp__tools-py__run_mypy_check` — no issues
- [ ] `mcp__tools-py__run_pytest_check` — all pass

---

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.

Implement step 1: parallelize the 5 tool availability checks in
_check_tool_availability() using ThreadPoolExecutor + as_completed.

1. First, add the new test test_parallel_execution_maps_results_correctly
   to TestCheckToolAvailability in tests/test_tool_availability.py.
2. Then modify _check_tool_availability() in src/mcp_tools_py/server.py:
   - Add module-level import: ThreadPoolExecutor, as_completed
   - Replace the sequential for-loop with ThreadPoolExecutor.submit() + as_completed()
   - Keep lint-imports and vulture checks sequential (unchanged)
3. Run all three code quality checks and fix any issues.

Verify that the test asserts ThreadPoolExecutor.submit was called 5 times.
```
