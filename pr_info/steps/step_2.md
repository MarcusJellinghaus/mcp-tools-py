# Step 2 — Per-call `timeout_seconds` on the `move_symbol` tool

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md` only. Use TDD: write the test first, then the change. Run pylint, pytest (`-n auto`) and mypy through the MCP tools and make them pass. Run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/refactoring/__init__.py`: the nested `move_symbol` in `_register_rope_tools`
- `tests/test_refactoring/test_refactoring_tools.py`

## WHAT

```python
def move_symbol(
    source_file: str,
    symbol_names: list[str],
    dest_file: str,
    dry_run: bool = False,
    timeout_seconds: int | None = None,
) -> str
```

## HOW

- Resolve `resolved = timeout_seconds if timeout_seconds is not None else timeout`, where `timeout` is the existing closure variable holding `self._timeout`. Pass it as `timeout=resolved` to `rope_move_symbol`.
- Add this to the docstring's Args: `timeout_seconds: Maximum seconds to wait for rope. Overrides the server default for this call. MCP clients may time out earlier than the server.`
- `rope_tools.move_symbol` and `_run_rope_subprocess` already accept `timeout`, and the timed-out message already uses it, so `rope_tools.py` doesn't change.
- Don't add extra validation.

## Tests

`test_move_symbol_timeout_seconds_is_plumbed`:
- Monkeypatch `mcp_tools_py.refactoring.rope_move_symbol` with a fake that records its `timeout` keyword argument and returns `"ok"`.
- Build `RefactoringTools(_context(tmp_path), timeout=60)` and register it on `mock_mcp`. Pick the function whose `__name__ == "move_symbol"`.
- Calling it with `timeout_seconds=7` records `7`. Calling it without `timeout_seconds` records `60`.
