# Step 1 — Move the ruff JSON parser into `utils/`

**Prerequisite for step 5.** `formatter/ruff_runner.py` needs `parse_ruff_json_output`,
but `tach.toml` places `formatter` and `code_checker_ruff` in the same
`tool_implementation` layer and `formatter.depends_on` lists only `utils` and
`log_utils`. Importing across would fail `run_tach_check`. Moving the parser down to
`utils/` makes both consumers depend downward only.

**No `tach.toml` edge is added. Do not add one.**

## WHERE

**Create** `src/mcp_tools_py/utils/ruff_parsing.py`

**Delete** (after the move):
- `src/mcp_tools_py/code_checker_ruff/models.py` — sole symbol `RuffMessage`
- `src/mcp_tools_py/code_checker_ruff/parsers.py` — sole symbol `parse_ruff_json_output`

One destination file, not a `models.py` + `parsers.py` pair: each source module holds
exactly one symbol.

**Modify**
- `src/mcp_tools_py/code_checker_ruff/__init__.py`
- `src/mcp_tools_py/code_checker_ruff/reporting.py`
- `src/mcp_tools_py/code_checker_ruff/runners.py`
- `tests/test_code_checker_ruff/test_parsers.py`
- `tests/test_code_checker_ruff/test_reporting.py`

The two test files **stay where they are** — only their imports change. Moving them buys
nothing and loses `git log --follow`.

## WHAT

`utils/ruff_parsing.py` holds both symbols **byte-identically** to their current bodies.
This is a move, not a rewrite:

```python
class RuffMessage(NamedTuple):
    code: str
    message: str
    filename: str
    line: int
    column: int
    end_line: int
    end_column: int
    url: str
    fixable: bool
    noqa_row: int


def parse_ruff_json_output(
    raw_output: str,
    project_dir: str,
) -> tuple[List[RuffMessage], str | None]: ...
```

The `from .models import RuffMessage` relative import inside `parsers.py` disappears —
both symbols now live in one module.

## HOW

Prefer `mcp__mcp-tools-py__move_symbol`, which rewrites importers automatically:

```
move_symbol(
    source_file="src/mcp_tools_py/code_checker_ruff/models.py",
    symbol_names=["RuffMessage"],
    dest_file="src/mcp_tools_py/utils/ruff_parsing.py",
)
move_symbol(
    source_file="src/mcp_tools_py/code_checker_ruff/parsers.py",
    symbol_names=["parse_ruff_json_output"],
    dest_file="src/mcp_tools_py/utils/ruff_parsing.py",
)
```

Then by hand:

1. Check `utils/ruff_parsing.py`. `parse_ruff_json_output` uses the module-level
   `logger` and the `json` and `os` imports from `parsers.py`, so the new module must
   define `logger = logging.getLogger(__name__)` and import `json`, `logging` and `os`.
   It must not import from itself (e.g. a rewritten `from .models import RuffMessage`
   pointing back at `ruff_parsing`). Add whatever `move_symbol` did not carry over.
2. Delete the two emptied source modules (`delete_this_file`). Confirm with
   `list_symbols` that neither still holds `RuffMessage` or `parse_ruff_json_output`.
   A leftover `logger` (and its imports) in `parsers.py` is expected — it goes with the
   file.
3. `code_checker_ruff/__init__.py` — **remove** both symbols from the imports **and**
   from `__all__`. They are not re-exported. Callers import from
   `mcp_tools_py.utils.ruff_parsing`, so there is one home rather than a home plus a
   re-export.
4. Verify with `find_references` that `code_checker_ruff/runners.py` line 81, 132 and 162
   call sites resolve, and that `reporting.py`'s 5 annotation uses type-check.

Do not touch `tach.toml` or `.importlinter`.

## ALGORITHM

None — pure move.

## DATA

Unchanged. `parse_ruff_json_output` still returns
`tuple[list[RuffMessage], str | None]`, where the second element is a parse-error message
or `None`.

## TESTS

No new behaviour, so no new test. The existing suites are the regression:

- `tests/test_code_checker_ruff/test_parsers.py` — 11 call sites, import updated
- `tests/test_code_checker_ruff/test_reporting.py` — constructs `RuffMessage`, import updated
- `tests/test_shim_reexports.py` and `tests/test_packaging.py` — check these pass; they
  assert things about module structure

Add one assertion to `tests/test_code_checker_ruff/test_parsers.py`: importing
`RuffMessage` or `parse_ruff_json_output` from `mcp_tools_py.code_checker_ruff` raises
`ImportError`. That pins the "one home, no re-export" decision so a later convenience
re-export cannot creep back in.

## DONE WHEN

`run_tach_check` and `run_lint_imports_check` pass, plus pylint / pytest / mypy / ruff /
vulture. Run
these **before** moving to step 2 — this step is independently verifiable and its failure
mode is a layering error, not a test failure.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`.
>
> Move `RuffMessage` and `parse_ruff_json_output` into a single new
> `src/mcp_tools_py/utils/ruff_parsing.py`, delete the two emptied source modules, and
> drop both symbols from `code_checker_ruff/__init__.py`'s imports and `__all__` — no
> re-export. Use the `move_symbol` MCP tool so importers are rewritten for you. Add one
> test asserting the old import path now raises `ImportError`.
>
> Do not add a `tach.toml` edge. Do not move the test files. This is a pure move: do not
> rewrite either symbol's body.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check`,
> `run_lint_imports_check`, `run_ruff_check` and `run_vulture_check`. All must pass. Then
> make exactly one commit.
