# Step 9 — Wire the workers note into the toolkit `_run_test`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_9.md`).
First add tests to `tests/test_toolkit_test.py`, then change `_run_test` in `src/mcp_tools_py/toolkit.py`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; then check that `toolkit.py` has ≤ 750 lines (`check_file_size`). All must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/toolkit.py` (`_run_test`)
- `tests/test_toolkit_test.py` (add tests; it is at 713 lines, so if it would pass 750, put the new tests in a new `tests/test_toolkit_workers.py`)

## WHAT / HOW
- Combine both notes into the single note `_with_note` takes. Replace
  `note: str | None = result.get("test_paths_note")` with
  ```python
  note = "\n".join(filter(None, [result.get("workers_note"), result.get("test_paths_note")])) or None
  ```
  The workers note comes first. Every existing `_with_note(..., note)` return then carries it.
- Parse `-n` once at `full`: declare `effective: EffectiveConfig | None = None` before the `try` and pass `effective=effective` to `check_code_with_pytest`. The `full` branch already assigns `effective`. Add `EffectiveConfig` to the existing `pytest_config` import.
- `_with_note` stays unchanged.

## ALGORITHM
```
effective = None
if depth == "full": effective = effective_config(...)   # existing line
result = check_code_with_pytest(..., effective=effective)
note = "\n".join(filter(None, [workers_note, test_paths_note])) or None
```

## DATA
`ActionResult.summary` = `"workers: ...\n<test paths note>\n\n<summary>"` when both are present.

## Tests (write first)
Patch `mcp_tools_py.toolkit.check_code_with_pytest`, as the existing tests do:
- Passing run with `workers_note="workers: 4 (config.toml)"` → `summary` starts with it.
- Both `workers_note` and `test_paths_note` → `summary` starts with `"workers: 4 (config.toml)\n<test paths note>\n\n"`.
- ERROR and "No Tests Found" (`skipped`) returns also carry the note.
- At `full` depth, `check_code_with_pytest` was called with a non-None `effective`; at `quick`/`standard`, with `effective=None`.

## Precondition
If `toolkit.py` exceeds 750 lines, move `_registered_markers` to `toolkit_checks.py` as described in step 4's precondition. If it is still over 750, write one line to `pr_info/.blocked.txt` and stop.
