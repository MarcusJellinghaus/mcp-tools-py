# Summary — #77: Add `--strict-markers` to pytest addopts; check toolkit marker handling on pytest 8

## Goal

Make this repo's pytest config reject unregistered markers, prove it with a
permanent integration test, document the rule, and fix two comments in
`src/mcp_tools_py/toolkit.py`. The pytest 8.3.5 check (issue step 4) was done
during analysis; the issue's table is the record and is not re-run.

## Architectural / design changes

There are no runtime or behaviour changes in `src/`. The changes are:

- **Test configuration:** `[tool.pytest.ini_options] addopts` gains the
  `--strict-markers` flag. Use the flag, not the `strict_markers = true` ini
  key: the ini key only exists from pytest 9, and the dependency floor is
  `pytest>=8.3.5`.
  - A marker typo on a test now fails collection instead of only warning.
  - An unknown name in `-m` now fails with a hint (exit 4) instead of
    selecting nothing (exit 5).
- **This repo consumes its own toolkit's override:** mcp-coder's unattended
  runs pass `-o strict_markers=false` (`_STRICT_MARKERS_OFF`) to deselect
  marker names this repo does not register. That override must stay in
  `_run_test` and in `check_instructions.unattended`; it is not touched.
- **New regression test:** an integration test runs pytest in a subprocess
  with this repo's `pyproject.toml` (`-c`) on a temp test file that carries an
  unregistered marker. It asserts a nonzero exit and the
  `'<name>' not found in \`markers\` configuration option` message.
  It follows the subprocess pattern of `tests/test_subprocess_tracing.py`,
  including its autouse `_no_outer_tracing` fixture.
- **Comments only in `toolkit.py`:**
  - The comment above `_STRICT_MARKERS_OFF` gets a pytest 8 note: there the
    override has no effect, so a test carrying an unregistered mark still
    fails collection under `--strict-markers`.
  - The comment above `UNATTENDED_EXCLUDED_MARKERS` loses its stale
    cross-reference to mcp-coder's removed `AUTOMATED_EXCLUDED_MARKERS`.
- **Not changed:** `verify()`; `test_unattended_in_strict_marker_project_is_ok`
  (no skipif); the single `integration` marker (no new markers).

## Files

| File | Action | Step |
|---|---|---|
| `tests/test_repo_pytest_config.py` | create | 1 |
| `pyproject.toml` | modify (`addopts`) | 1 |
| `vulture_whitelist.py` | modify (comment on `_no_outer_tracing`) | 1 |
| `.claude/CLAUDE.md` | modify (one sentence after "Available marker") | 1 |
| `src/mcp_tools_py/toolkit.py` | modify (two comments) | 2 |

No new folders or modules besides the one test module.

## Steps

1. `--strict-markers` in `addopts`, with its regression test, the vulture
   comment and the CLAUDE.md sentence. All of these describe or prove the same
   config change.
2. The two comments in `toolkit.py`.

## Out of scope

- `--tb=short` in `addopts`.
- A unit-test time budget.
- A `verify()` item about `--strict-markers`.
- Finer markers.
