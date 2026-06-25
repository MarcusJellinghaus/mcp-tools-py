# Step 2 — move_module / move_symbol: AttributeError hint hardening

**Goal:** Item 3 in `summary.md`. When rope raises an `AttributeError` (e.g.
`'NoneType' object has no attribute 'is_folder'`) because it cannot analyze the
source, append an actionable hint to the existing error message. Scope is
**message hardening only** — do not touch rope internals.

**One commit:** tests + implementation + all checks passing.

---

## WHERE
- Production:
  - `src/mcp_tools_py/refactoring/rope_tools.py`
    - `_move_module_impl` (broad `except Exception` near line 789)
    - `_move_symbol_impl` (broad `except Exception` near line 407)
- Tests:
  - `tests/test_refactoring/test_rope_tools.py`

## WHAT
No signature changes. Modify only the existing broad handlers.

## HOW (KISS — single handler, no duplicated cleanup)
Keep the existing `except Exception as exc:` (it already runs the correct dry-run
cleanup and preserves the original text). Append the hint only when the caught
exception **is an `AttributeError`** — triggered by type via `isinstance`, never
by a string match.

`_move_module_impl`:
```python
except Exception as exc:  # pylint: disable=broad-exception-caught
    if created_pkg_for_dry_run:
        _cleanup_package(abs_dest_pkg, project_dir)
    msg = f"Error moving module '{source_module}': {exc}"
    if isinstance(exc, AttributeError):
        msg += (
            "\nHint: rope could not analyze the source module. "
            "Try move_symbol, or move the file manually."
        )
    return msg
```

`_move_symbol_impl` (mirror — same cleanup it already does):
```python
except Exception as exc:  # pylint: disable=broad-exception-caught
    if dry_run:
        _cleanup_created_files(abs_dest, created_for_dry_run, project_dir)
    else:
        _cleanup_created_files(abs_dest, created_dest, project_dir)
    msg = f"Error moving symbol: {exc}"
    if isinstance(exc, AttributeError):
        msg += (
            "\nHint: rope could not analyze the source module. "
            "Try moving the symbols individually, or move the file manually."
        )
    return msg
```

## ALGORITHM
```
on exception in move impl:
    run the existing dry-run cleanup (unchanged)
    msg = original "Error moving ..." text   # preserved for debugging
    if isinstance(exc, AttributeError):
        msg += actionable hint
    return msg
```

## DATA
- Returns the same error string as today, with one extra `\nHint: ...` line on
  `AttributeError`. No new types.

## TESTS (TDD — write first)
The public `move_module` / `move_symbol` run rope in a **subprocess**, so patch
the `_impl` functions **directly** (in-process) where mocking rope works. Reuse
the `sample_project` fixture in `test_rope_tools.py`.

- `test_move_module_attribute_error_hint`:
  - `from mcp_tools_py.refactoring.rope_tools import _move_module_impl`
  - `patch("rope.refactor.move.create_move", side_effect=AttributeError("'NoneType' object has no attribute 'is_folder'"))`
  - call `_move_module_impl(sample_project, "src/foo.py", "src/pkg", dry_run=True)`
  - assert original text present (`"is_folder"`) **and** `"Hint:"` /
    `"move the file manually"` present.
  - assert the temp dest package was cleaned up:
    `not (sample_project / "src" / "pkg").exists()`.
- `test_move_symbol_attribute_error_hint`:
  - `from ... import _move_symbol_impl`
  - `patch("rope.refactor.move.create_move", side_effect=AttributeError(...))`
  - call `_move_symbol_impl(sample_project, "src/foo.py", ["my_func"], "src/baz.py", dry_run=True)`
  - assert original `"Error moving symbol:"` text + `"Hint:"` present, and the
    dry-run dest stub is cleaned up (`not (sample_project/"src"/"baz.py").exists()`).

> Note: `create_move` is called inside the `try` after `get_resource`, so the
> source file must exist (the fixture provides `src/foo.py`). dry_run skips the
> git-tracked pre-check, so no git setup is needed.

## VERIFY
1. `run_pylint_check`
2. `run_pytest_check` extra_args `["-n","auto","-m","not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"]`
3. `run_mypy_check`
4. `./tools/format_all.sh`, then commit.

## LLM PROMPT
> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`. Implement Step 2
> only (Item 3, move hardening). Use TDD: first add two tests to
> `tests/test_refactoring/test_rope_tools.py` that import `_move_module_impl` and
> `_move_symbol_impl` directly, patch `rope.refactor.move.create_move` to raise
> `AttributeError("'NoneType' object has no attribute 'is_folder'")`, run each in
> `dry_run=True` against the `sample_project` fixture, and assert the original
> error text **and** an appended `Hint:` line are present and the temporary
> dest dir/file was cleaned up. Then, in
> `src/mcp_tools_py/refactoring/rope_tools.py`, keep the existing broad
> `except Exception` in both `_move_module_impl` and `_move_symbol_impl` (with
> their current cleanup) and append the hint only when
> `isinstance(exc, AttributeError)`. Do not add a second `except` branch, do not
> touch rope internals, and do not change any signatures. Run pylint, pytest
> (`-n auto` with the integration-exclusion `-m`), and mypy until all pass, then
> format and commit.
