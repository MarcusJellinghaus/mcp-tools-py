# Step 2 — Fix the two marker comments in `toolkit.py`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`
> exactly as written.
> - Edit comments only. Change no code and no tests.
> - Run the checks below.
>
> Make one commit.

## WHERE

`src/mcp_tools_py/toolkit.py`, the comment block above
`UNATTENDED_EXCLUDED_MARKERS` and `_STRICT_MARKERS_OFF` (around lines 81–92).

## WHAT

There is no TDD here: comment-only changes have no testable behaviour. The
existing tests keep asserting that `_STRICT_MARKERS_OFF` is used:

- `tests/test_toolkit.py::TestPromptFragments::test_unattended_instructions`
- `tests/test_toolkit_test.py::TestRunTestUnattended::test_unattended_passes_markers_and_strict_markers_off`

### Comment above `UNATTENDED_EXCLUDED_MARKERS`

Current:

```python
# Same list as mcp-coder's workflows/rebase_automated.py::AUTOMATED_EXCLUDED_MARKERS;
# this is the single home of the list.
```

New: drop the stale cross-reference and keep the rest.

```python
# This is the single home of the list.
```

### Comment above `_STRICT_MARKERS_OFF`

Current:

```python
# Stops --strict-markers projects rejecting marker names they don't register.
```

New: keep that line and add one sentence.

```python
# Stops --strict-markers projects rejecting marker names they don't register.
# On pytest 8 it has no effect: a test carrying an unregistered mark still fails
# collection under --strict-markers.
```

## HOW

- Do not change `_STRICT_MARKERS_OFF`, `UNATTENDED_EXCLUDED_MARKERS`,
  `_run_test`, `prompt_fragments()` or `verify()`.
- Do not add a skipif to `test_unattended_in_strict_marker_project_is_ok`.

## ALGORITHM

None (comments only).

## DATA

No changes.

## Checks (all must pass)

1. `mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`
2. `mcp__mcp-tools-py__run_pylint_check`, `mcp__mcp-tools-py__run_mypy_check`,
   `mcp__mcp-tools-py__run_ruff_check`
3. `mcp__mcp-tools-py__run_format_code`, then commit with
   `mcp__mcp-workspace__git_commit`, passing
   `paths=["src/mcp_tools_py/toolkit.py"]`.

## Preconditions

If the comment above `UNATTENDED_EXCLUDED_MARKERS` no longer mentions
`AUTOMATED_EXCLUDED_MARKERS`, or `_STRICT_MARKERS_OFF` is missing, write one
line to `pr_info/.blocked.txt` and stop.

## Commit message

```
docs(toolkit): note pytest 8 limit of strict_markers override (#77)
```
