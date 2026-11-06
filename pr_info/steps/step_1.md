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

There is no new logic. Bash is disabled in the implement workflow, so run the verification as a scratch probe. After applying the diff, save `.scratch/test_probe.py` with one test that runs this sequence via `subprocess`, with the repo root as the working directory and `<venv>` as a directory under `tmp_path`, and asserts the results under DATA:

```
uv venv <venv> --python 3.11
uv pip install -e ".[dev]" "import-linter==2.12" --python <venv>/Scripts/python.exe
<venv>/Scripts/lint-imports.exe --no-cache
<venv>/Scripts/python.exe -m pytest tests/test_target_scripts_contract.py
```

Pass the probe's subprocesses an environment without `PYTEST_*` variables, so the outer pytest run doesn't leak into the nested one. Don't add a marker filter to the nested pytest command: all three tests are marked `integration`.

Run the probe, with the timeout raised because the install resolves git dependencies:

```
mcp__mcp-tools-py__run_pytest_check(extra_args=["-p", "no:cacheprovider", ".scratch/test_probe.py"], timeout_seconds=900)
```

Then delete it, whether it passed or failed: `mcp__mcp-workspace__delete_directory(".scratch", recursive=True)`.

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
2. After `.scratch/` is deleted, check with `mcp__mcp-workspace__git` (`status`) that the only tracked files modified are `pyproject.toml` and `pr_info/TASK_TRACKER.md`.
3. Write this commit message to `pr_info/.commit_message.txt` and don't commit. The implement workflow formats, commits and pushes:

   ```
   fix(deps): raise import-linter minimum to 2.12 (#271)
   ```
