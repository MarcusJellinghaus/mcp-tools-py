# Step 1 — Drop Forced `-s`, Add Conditional xdist Strip

## LLM Prompt

> Read `pr_info/steps/summary.md` for issue context and `pr_info/steps/step_1.md` (this file) for the specific work to do. Implement Step 1 only: fix the forced `-s` append and add a conditional xdist-aware strip in `sanitize_extra_args`. Follow TDD — update/add tests first (they should fail), then apply the code change so they pass. Run `mcp__tools-py__run_pylint_check`, `mcp__tools-py__run_pytest_check` (with the fast-unit-test marker exclusion from `.claude/CLAUDE.md`), and `mcp__tools-py__run_mypy_check`. All three must pass before the commit. Do not touch `runners.py` — that is Step 2.

## Goal

Move `-s` from "auto-added by the tool" to "user opt-in via `extra_args=["-s"]`", and protect against the xdist worker crash by stripping `-s` when xdist is active.

## WHERE

**Source files (modify):**

- `src/mcp_tools_py/checker_tools/pytest_tool.py` — remove `+ ["-s"]` append.
- `src/mcp_tools_py/code_checker_pytest/utils.py` — remove unconditional `-s` strip; add conditional xdist-aware strip.

**Test files (modify / extend):**

- `tests/test_code_checker_pytest/test_extra_args.py` — update existing tests, add new ones.
- `tests/test_server_params.py` — update expected `extra_args` and inline comment.

## WHAT

### `src/mcp_tools_py/checker_tools/pytest_tool.py`

At lines 93-94, change:

```python
# Always add -s for print statement capture
final_extra_args = sanitized.cleaned_args + ["-s"]
```

to:

```python
final_extra_args = sanitized.cleaned_args
```

(or drop the local variable entirely and pass `sanitized.cleaned_args` to `check_code_with_pytest`.)

### `src/mcp_tools_py/code_checker_pytest/utils.py`

**Function signature unchanged:**

```python
def sanitize_extra_args(
    extra_args: Optional[List[str]],
    markers: Optional[List[str]],
    project_dir: str = "",
) -> SanitizedArgs
```

**Remove** lines 56-58 (the unconditional `-s` skip).

**Add** after the main `for arg in extra_args` loop (before the path-detection block) a small post-pass that detects the `["-n", VALUE]` pair in `cleaned` and conditionally strips `-s`.

**Extend** the "Limitations" docstring section to document that only the two-arg `["-n", VALUE]` form triggers the strip; `--numprocesses` long form passes through.

## HOW

- No new imports.
- No new return-type fields — reuse the existing `notes: List[str]` channel on `SanitizedArgs` (same pattern as the `-m` / `markers` conflict).
- Note string (verbatim from issue):
  > `Note: -s flag in extra_args was stripped because -n <value> (xdist) is incompatible with -s and causes worker crashes. Use -n 0 (no xdist) or omit -n if you need -s.`
- Pylint/mypy: no new public surface to annotate.

## ALGORITHM

Post-loop, inside `sanitize_extra_args`, before the path-detection block:

```
find first index i where cleaned[i] == "-n" and i+1 < len(cleaned)
if found:
    value = cleaned[i+1]
    if value != "0" and "-s" in cleaned:
        cleaned = [a for a in cleaned if a != "-s"]
        notes.append(<xdist strip note>)
```

## DATA

- Return type unchanged: `SanitizedArgs(cleaned_args, verbosity, notes, has_path_args)`.
- New behavioral contract:
  - `["-s"]` → `cleaned_args == ["-s"]`, no note.
  - `["-s", "-n", "auto"]` → `cleaned_args == ["-n", "auto"]`, one xdist note.
  - `["-s", "-n", "0"]` → `cleaned_args == ["-s", "-n", "0"]`, no note.
  - `["-s", "--numprocesses", "auto"]` → `cleaned_args == ["-s", "--numprocesses", "auto"]`, no note (documented limitation).

## Test Changes (TDD — Write These First)

### `tests/test_code_checker_pytest/test_extra_args.py`

1. **Update `test_s_flag_removed_silently`** — rename to `test_lone_s_flag_passes_through`; assert `sanitize_extra_args(["-s", "-x"], None).cleaned_args == ["-s", "-x"]` and `notes == []`.
2. **Update `test_combined_deduplication`** — input `["-s", "-vvv", "-m", "slow", "tests", "-x"]` with `markers=["unit"]` has no `-n`, so expected `cleaned_args == ["-s", "-x"]`.
3. **Add `test_s_stripped_when_xdist_active`** — input `["-s", "-n", "auto"]`, assert `cleaned_args == ["-n", "auto"]` and `len(notes) == 1` with `"xdist"` in the note.
4. **Add `test_s_preserved_with_n_zero`** — input `["-s", "-n", "0"]`, assert `cleaned_args == ["-s", "-n", "0"]` and `notes == []`.
5. **Add `test_numprocesses_long_form_does_not_trigger_strip`** — input `["-s", "--numprocesses", "auto"]`, assert `-s` passes through (documents limitation).

### `tests/test_server_params.py` (lines 73-82)

- Update expected `extra_args=["--no-header", "-s"]` → `extra_args=["--no-header"]`.
- Remove or replace the `verbosity comes from sanitize_extra_args (default 2), -s is always appended` comment.

## Quality Gates

Run all three after the implementation, with no remaining issues:

```python
mcp__tools-py__run_pylint_check()
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"])
mcp__tools-py__run_mypy_check()
```

## Commit Message Suggestion

```
Drop forced -s, strip -s when xdist active (fixes #192 part 1)

- pytest_tool.py: stop appending -s to every pytest invocation
- utils.py: remove unconditional -s strip; strip -s only when
  ["-n", VALUE] with VALUE != "0" is also present, with a note
- Tests updated for the new opt-in surface and xdist-conflict behavior
```
