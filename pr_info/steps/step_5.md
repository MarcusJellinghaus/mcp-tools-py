# Step 5: Result output with review reminders

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

Enhance the result output from `_move_symbol_impl()` to include structured summary
and review reminders as specified in the issue.

## WHERE

| File | Function/Section |
|------|-----------------|
| `src/mcp_tools_py/refactoring/rope_tools.py` | `_move_symbol_impl()` — result string building |
| `tests/test_refactoring/test_rope_tools.py` | New test for result output content |

## WHAT

### Result string format (non-dry-run)

```
move_symbol completed successfully.
  Moved: my_func, MyClass, MY_VAR (from src/foo.py → src/baz.py)
  Created: src/baz.py
  Modified: src/foo.py
  Modified: src/bar.py
  Self-referencing import removed from src/baz.py: import src.baz
Note: Imports are absolute — review and convert to relative where applicable.
Note: Review symbol order and imports in all affected files.
```

### Result string format (dry-run)

```
[DRY RUN] move_symbol preview:
  Symbols: my_func, MyClass, MY_VAR
  [DRY RUN] Would create: src/baz.py
  [DRY RUN] Would modify: src/foo.py
  [DRY RUN] Would modify: src/bar.py
Note: Imports are absolute — review and convert to relative where applicable.
Note: Review symbol order and imports in all affected files.
```

### New test

```python
def test_move_symbol_result_includes_review_notes(sample_project: Path) -> None:
    """Result output includes import style note and review reminder."""
```

## ALGORITHM

```python
# Build result lines list throughout _move_symbol_impl
lines = []
lines.append("move_symbol completed successfully.")
lines.append(f"  Moved: {', '.join(symbol_names)} (from {source_file} → {dest_file})")
# ... file change lines from _format_changes ...
# ... self-import removal lines from step 4 ...
lines.append("Note: Imports are absolute — review and convert to relative where applicable.")
lines.append("Note: Review symbol order and imports in all affected files.")
return "\n".join(lines)
```

## DATA

Return value is still `str`. Content is enriched with:
- Symbol list summary
- Self-import removal notes (from Step 4)
- Two standard review notes (always appended)

## LLM PROMPT

```
Implement Step 5 from pr_info/steps/step_5.md (see pr_info/steps/summary.md for context).

Update _move_symbol_impl() result output to include:
1. Summary of moved symbols and source/dest
2. File change details (created/modified)
3. Self-import removal notes (if any, from step 4)
4. Two review reminder notes (always):
   - "Imports are absolute — review and convert to relative where applicable."
   - "Review symbol order and imports in all affected files."

Apply same pattern to dry-run output. Add test verifying the notes appear.

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "feat(move_symbol): structured result output with review reminders"
```
