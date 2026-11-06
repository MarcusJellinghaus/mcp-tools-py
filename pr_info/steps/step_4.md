# Step 4: `_merge` keeps each result's `fix_text`

**Commit message:** `fix(toolkit): keep each check's fix_text when merging`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_4.md`. Steps 1 to 3 are already committed. Implement this step only, tests first. Run the checks listed in the summary, fix what they report, then make exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit_checks.py`: `_merge`
- `tests/test_toolkit.py`: `TestMerge`

## WHAT

`_merge(results: list[ActionResult]) -> ActionResult` keeps its signature. Update its docstring: `fix_text` is each result's own, or is rebuilt from that result's findings when not set.

## HOW

This is a general change, with no mypy special case. Vulture, lint-imports and tach set `fix_text` directly, so their text now comes through without the `- ` prefix. The issue accepts this. Output from other checkers must not otherwise change.

## ALGORITHM

```python
parts = [
    result.fix_text or "\n".join(_finding_line(finding) for finding in result.findings)
    for result in results
]
fix_text = "\n".join(part for part in parts if part)
```

Skipping empty parts matters: a naive join adds a blank line for an `ok` result, which changes output at standard depth.

## DATA

`fix_text`: `str`, empty when no result has findings or `fix_text`.

## Tests first

All in `TestMerge`:

- A result with a custom `fix_text` keeps it exactly, with no `- ` prefix.
- A result with findings and no `fix_text` is rebuilt. Assert the exact text, so `test_ok_and_findings_is_findings_with_concatenated_findings` keeps meaning the same.
- `ok` plus findings has no leading or blank line.
- Custom text plus a rebuilt result are joined with one `\n`, in result order.
- All `ok`: `fix_text == ""`.
