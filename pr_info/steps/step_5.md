# Step 5 — Dry run shows rope's unified diff per symbol

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_5.md` only. Use TDD: write the test first, then the change. Run pylint, pytest (`-n auto`) and mypy through the MCP tools and make them pass. Run `run_format_code`, then make one commit.

## Precondition

`rope.base.change.ChangeSet` has a `get_description()` method. Check with `get_library_source`. If it doesn't, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/refactoring/rope_tools.py`: the dry-run branch of `_move_symbol_impl`
- `tests/test_refactoring/test_rope_tools.py`

## WHAT

There are no new functions. In the per-symbol loop, the dry run also collects the diffs:

```python
if dry_run:
    all_change_lines.append(_format_changes(changes, dry_run=True))
    diffs.append(f"Diff for {name}:\n{changes.get_description()}")
```

## HOW

Add the following to `dry_lines` after the file list and before the existing notes:

```
Diffs (each computed against the unmodified source; diffs touching the same file can overlap):
<diff blocks, in the order computed>
Note: Self-referencing imports of the destination module shown in a diff are removed in the real run.
```

Print the diffs in full: no cap and no summary. The real run doesn't change.

## DATA

Each block is `Diff for <name>:` followed by rope's description, which contains `--- a/<path>` and `+++ b/<path>` unified-diff headers.

## Tests

`test_move_symbol_dry_run_shows_diff`: run a dry run of `my_func` from `src/foo.py` into `src/baz.py`. The result contains:
- `Diff for my_func:`
- `--- a/src/foo.py`
- `+++ b/src/baz.py`
- `-def my_func():`
- `Self-referencing imports`

`src/baz.py` doesn't exist afterwards.
