# Issue #145 — Fix `run_pytest_check` extra_args path validator

## Problem

`sanitize_extra_args()` in `src/mcp_tools_py/code_checker_pytest/utils.py` treats every non-flag entry in `extra_args` as a path candidate. Flag *values* (e.g. `auto` in `-n auto`, `not integration` in `-m "not integration"`) are not paths, but the loop tries to resolve them under `project_dir` and emits a spurious `"Path 'X' not found relative to project_dir."` note.

The cleaning loop already has a `skip_next` mechanism, but it only fires for `-m` *and only when* `markers=` is also passed. So `-n auto`, `-k <expr>`, `-m <expr>` (no `markers=`), `--maxfail 3`, etc. all leak their values into the path validator.

## Fix — shape-then-existence heuristic

Replace the per-arg "everything non-flag is a path candidate" logic with two-step classification:

1. **Shape match** — treat the arg as a path candidate iff it contains `/`, `\`, `::`, or ends with `.py`.
2. **Filesystem fallback** — if shape didn't match, only treat it as a path if `os.path.exists(project_dir/arg)` is true (preserves the bare-`subdir` test case).
3. **Otherwise** — silent passthrough. No user-facing note. `cleaned` unchanged.

Shape-matched args still go through the existence check; if they don't resolve, the existing `"Path 'X' not found..."` note fires (now a useful typo warning instead of a false positive).

## Architectural / design changes

None. This is a localized bug fix:

- No new modules, no new public API.
- `SanitizedArgs` dataclass unchanged — `has_path_args` semantics preserved.
- `checker_tools.py:237` (the consumer of `has_path_args`) untouched.
- Existing notes (`"Path argument '...' detected..."`, `"Path '...' not found..."`, `"Absolute path '...' ignored..."`) preserved verbatim.
- Cleaning loop (`-v`, `-s`, `tests/`, `-m` + `markers=`) unchanged.
- The change is internal to a single function, ~15 lines.

## KISS simplifications vs. issue spec

The issue's "Decisions" table proposed `logger.debug` calls for every classification branch + a new module logger. **Dropped**: no consumer for those debug logs, the user-facing `notes` already cover observability for the meaningful branches, and adding them would inflate the diff without behavioral benefit. YAGNI — can be added later if a real need surfaces.

No standalone `_looks_like_path()` helper; the four-condition predicate is inlined as one boolean expression for clarity.

## Files modified

- `src/mcp_tools_py/code_checker_pytest/utils.py` — rewrite path-detection loop (~lines 73–93) inside `sanitize_extra_args()`.
- `tests/test_code_checker_pytest/test_extra_args.py` — add 6 new tests in `TestSanitizeExtraArgsPathDetection`.

## Files created

None.

## Folders / modules touched

- `src/mcp_tools_py/code_checker_pytest/` (one file)
- `tests/test_code_checker_pytest/` (one file)

## Steps

- [step_1.md](step_1.md) — Fix `sanitize_extra_args()` path-detection loop and add regression tests.
