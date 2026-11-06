# Step 1: Raise the `import-linter` floor and verify it

## LLM prompt

Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`), then implement this step for issue #271. Make only the change described here. Follow the verification steps exactly, and never run them against the project's `.venv`. This step produces exactly one commit.

## WHERE

- `pyproject.toml`, line 36, in `[project] dependencies`

## WHAT

No functions or signatures change. Apply this diff:

```diff
-    "import-linter>=2.0",
+    # >=2.12: first version allowing overlapping modules, which target-scripts-stdlib-only needs.
+    "import-linter>=2.12",
```

## HOW

No integration points change: there are no new imports, decorators or registrations. `uv pip install` picks up the new minimum from `pyproject.toml`.

## ALGORITHM

There is no new logic. The verification sequence is below, run from the repo root. These commands have no MCP equivalent, because the MCP checkers run against the project's environment. `<venv>` is a new directory outside the repo, such as one under the system temp directory.

```
uv venv <venv> --python 3.11
uv pip install -e ".[dev]" "import-linter==2.12" --python <venv>/Scripts/python.exe
<venv>/Scripts/lint-imports.exe --no-cache
<venv>/Scripts/python.exe -m pytest tests/test_target_scripts_contract.py
delete <venv>
```

Don't add a marker filter to the pytest command: all three tests are marked `integration`.

## DATA

Expected results:

| Command | Expected result |
|---|---|
| `uv pip install` | Succeeds, with `import-linter` at 2.12 |
| `lint-imports --no-cache` | Exit 0, 4 contracts kept |
| `pytest tests/test_target_scripts_contract.py` | 3 passed, 0 skipped |

## Tests

No new test, as explained under "Testing approach" in the summary. The existing `tests/test_target_scripts_contract.py` is the check for this step.

## Preconditions and failures

If any of these happens, write one line to `pr_info/.blocked.txt` and stop:

- `uv` is missing, or a Python 3.11 venv can't be created.
- The `uv pip install` command fails.
- `lint-imports` doesn't keep all 4 contracts.
- `tests/test_target_scripts_contract.py` doesn't give 3 passed and 0 skipped.

## Checks and commit

1. Run these in the project environment. All must pass:
   - `mcp__mcp-tools-py__run_pylint_check`
   - `mcp__mcp-tools-py__run_mypy_check`
   - `mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`
2. Run `mcp__mcp-tools-py__run_format_code`.
3. Check with `mcp__mcp-workspace__git` (`status`) that `pyproject.toml` is the only tracked file modified.
4. Stage only `pyproject.toml` and commit:

   ```
   fix(deps): raise import-linter minimum to 2.12 (#271)
   ```
