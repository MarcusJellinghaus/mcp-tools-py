# Step 3: rc 2 detail, footer, file-level errors and `max_issues` docs

**Commit message:** `fix(mypy): always show the blocking error group on rc 2`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_3.md`. Steps 1 and 2 are already committed. Implement this step only, tests first. Run the checks listed in the summary, fix what they report, then make exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/reporting.py`: `_format_message`, `create_mypy_prompt`
- `src/mcp_tools_py/checker_tools/mypy_tool.py`: `max_issues` docstring, which is the tool description
- `README.md` line 97
- `tests/mcp_tools_py_manual/TEST_PLAN.md` lines 225 and 232
- `tests/test_code_checker_mypy/test_reporting.py`

## WHAT

No new public functions or signature changes.

## HOW

The three rc 2 behaviours are gated on `result.return_code == 2`, not on `>= 2`. The negative-line gate must be `msg.line < 0`, because an existing test pins `src/file0.py:0:1`.

## ALGORITHM

```python
# _format_message
location = msg.file if msg.line < 0 else f"{msg.file}:{msg.line}:{msg.column}"
lines = [f"- {location} - {msg.message}"]
```

```python
# create_mypy_prompt: no field identifies a blocker, so use the last error on rc 2
errors = [m for m in issues if m.severity == "error"]
last_error = errors[-1] if result.return_code == 2 and errors else None
last_code = (last_error.code or "other") if last_error else None
# the last-error group does not count against the limit
others = [g for g in groups if g[0] != last_code][:limit]
detailed = [g for g in groups if g[0] == last_code or g in others]
summarised = [g for g in groups if g not in detailed]
```

```python
# each detailed group: replaces the slice and the "... and N more" arithmetic
shown = messages[:MAX_LOCATIONS_PER_CODE]
if last_error in messages and last_error not in shown:
    shown.append(last_error)
# print shown, then "  ... and {len(messages) - len(shown)} more" when any are hidden
```

Footer condition becomes `if issues and result.return_code != 2:`.

## DATA

- File-level error line: `- src\pkg\mod.py - Source file found twice ...`.
- Groups keep their sorted order. The last-error group stays in its sorted position, ahead of the summary lines.

## Docs

- `mypy_tool.py` docstring, `README.md`: add that when mypy exits with code 2, the code holding the last error is also shown in detail without counting against `max_issues`, including with `max_issues=0`.
- `create_mypy_prompt` docstring (`max_issues`, "0 or less shows counts only"): add the same exit code 2 exception.
- `TEST_PLAN.md`:
  - 3e: "No file paths" holds unless mypy exits with code 2, when the code holding the last error is shown in detail.
  - 3f: the same exception for "every other code gets one summary line".

## Tests first

All in `test_reporting.py`:

- Negative line prints `- f.py - msg` with no `:-1:-1`, for an error and for a note. Line 0 still prints `f.py:0:1`.
- rc 2, `max_issues=1`: the last error's group is detailed even though it is not the most frequent, and the top group is also detailed.
- rc 2, `max_issues=0`: the last error's group is detailed, the others are summary lines, and no `Notes:` section appears.
- rc 2, `max_issues=1`, where the last-error group is also the most frequent: it does not use the slot, so it and the next group are detailed. It is not shown twice, and a third group stays a summary line.
- rc 1, `max_issues=0`: unchanged, with no detail.
- rc 2 where the group has 7 messages: the last one is listed, followed by `... and 1 more`.
- rc 2 where the last message is a note or warning: the group is chosen by the last `severity == "error"`.
- Footer is absent on rc 2 and present on rc 1.
