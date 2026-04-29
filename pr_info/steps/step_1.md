# Step 1 — Shape-then-existence path detection in `sanitize_extra_args()`

## LLM prompt

> Read `pr_info/steps/summary.md` for full context, then implement the change described in this file (`pr_info/steps/step_1.md`). Follow TDD: write the new tests first, then update `sanitize_extra_args()` so they pass alongside all existing tests. Keep the diff minimal — only the path-detection loop changes. Do not introduce a module logger or helper functions. Run pylint, pytest, and mypy via the MCP tools after the change; all three must pass.

---

## WHERE

- **Source**: `src/mcp_tools_py/code_checker_pytest/utils.py`
  - Function: `sanitize_extra_args()`
  - Region: the path-detection loop, currently lines ~73–93 (the `if project_dir:` block)
- **Tests**: `tests/test_code_checker_pytest/test_extra_args.py`
  - Class: `TestSanitizeExtraArgsPathDetection` (already exists, append 6 methods)

## WHAT

Signature is unchanged:

```python
def sanitize_extra_args(
    extra_args: Optional[List[str]],
    markers: Optional[List[str]],
    project_dir: str = "",
) -> SanitizedArgs: ...
```

Only the body of the path-detection loop changes. No new public symbols, no helper functions, no logger.

## HOW

- No new imports.
- No changes to the cleaning loop above the path-detection block.
- No changes to `SanitizedArgs` or to `checker_tools.py`.
- `has_path_args` semantics preserved exactly: `True` iff at least one arg in `cleaned` resolves to an existing file/dir under `project_dir`.

## ALGORITHM

```
for arg in cleaned:
    if arg starts with "-": continue
    if isabs(arg): note "Absolute path ... ignored"; continue
    looks_like_path = "/" in arg or "\" in arg or "::" in arg or arg.endswith(".py")
    file_part = arg.split("::", 1)[0] if "::" in arg else arg
    exists = os.path.exists(join(project_dir, file_part))
    if looks_like_path:
        if exists: has_path_args=True; note "Path argument '...' detected..."
        else:      note "Path '...' not found relative to project_dir."
    elif exists:
        has_path_args=True; note "Path argument '...' detected..."
    # else: silent passthrough (no note)
```

## DATA

Return value: `SanitizedArgs(cleaned_args, verbosity, notes, has_path_args)` — same shape as today. The only change in observable behavior:

- Flag values like `auto`, `not integration`, `test_foo or test_bar`, `3` no longer produce `"Path '...' not found..."` notes.
- Bare directory tokens that *do* exist under `project_dir` (e.g. `subdir`) still set `has_path_args=True` via the fs-fallback branch — preserves `test_existing_directory_sets_has_path_args`.
- Bare tokens that *don't* exist and don't look like paths now pass silently (was: emitted false-positive note).

## Tests to add (in `TestSanitizeExtraArgsPathDetection`)

Each uses a real `tempfile.TemporaryDirectory()` as `project_dir`. All assert `not any("not found" in n for n in result.notes)`.

1. `test_xdist_worker_count_no_false_positive` — `extra_args=["-n", "auto"]`. Assert `has_path_args is False`, `cleaned_args == ["-n", "auto"]`.
2. `test_marker_expression_without_markers_param_no_false_positive` — `extra_args=["-m", "not integration"]`, `markers=None`. Assert `has_path_args is False`, `cleaned_args == ["-m", "not integration"]`.
3. `test_keyword_expression_no_false_positive` — `extra_args=["-k", "test_foo or test_bar"]`. Assert `has_path_args is False`, `cleaned_args == ["-k", "test_foo or test_bar"]`.
4. `test_maxfail_numeric_value_no_false_positive` — `extra_args=["--maxfail", "3"]`. Assert `has_path_args is False`, `cleaned_args == ["--maxfail", "3"]`.
5. `test_combined_xdist_and_marker_no_false_positives` — `extra_args=["-n", "auto", "-m", "not integration"]`. Assert `has_path_args is False`, `cleaned_args == ["-n", "auto", "-m", "not integration"]`.
6. `test_flag_value_coexists_with_real_path` — Create `tests/test_file.py` under `tmpdir`. `extra_args=["-n", "auto", "tests/test_file.py"]`. Assert `has_path_args is True`, `cleaned_args == ["-n", "auto", "tests/test_file.py"]`, and `not any("'auto'" in n for n in result.notes)`.

## Existing tests that must keep passing

- `test_existing_file_sets_has_path_args` — `.py` shape match + exists.
- `test_existing_directory_sets_has_path_args` — bare `subdir` (no shape) + exists → fs-fallback branch.
- `test_node_id_with_existing_file_sets_has_path_args` — `::` shape match + exists.
- `test_nonexistent_path_keeps_has_path_args_false` — `"no_such_file.py"` shape-matches via `.py` → still emits "not found" note.
- `test_absolute_path_keeps_has_path_args_false` — abs-path branch unchanged.
- `test_mixed_args_detects_paths`, `test_empty_project_dir_keeps_has_path_args_false`, `test_existing_tests_unchanged_with_defaults` — unchanged.

## Verification

Run, in order:

```
mcp__tools-py__run_pylint_check
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"])
mcp__tools-py__run_mypy_check
```

All three must pass with no new issues. Then format and commit:

```
./tools/format_all.sh
git add src/mcp_tools_py/code_checker_pytest/utils.py tests/test_code_checker_pytest/test_extra_args.py
git commit -m "Fix sanitize_extra_args misclassifying flag values as paths (#145)"
```

## Commit boundary

This step produces **exactly one commit** containing the code change, the 6 new tests, and any formatter-only adjustments from `format_all.sh`.
