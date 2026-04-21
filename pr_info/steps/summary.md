# Summary: Complete mcp-coder-utils adoption and add shared libraries docs

**Issue:** #176

## Goal

Fully adopt `mcp-coder-utils` as the single shared library, enforce import isolation via shims, and document the pattern in CLAUDE.md.

## Architectural / Design Changes

### Before

- `mcp-coder-utils` is a dependency, and two shim files exist (`log_utils.py`, `utils/subprocess_runner.py`), but **no code actually uses them** — all ~18 source files import `mcp_coder_utils.*` directly.
- `utils/file_utils.py` has a hand-written `read_file` implementation.
- `code_checker_pytest/utils.py` has its own copy of `read_file`.
- No import-linter contract enforces isolation.

### After

- **All production code** imports `mcp_coder_utils` functionality exclusively through local shim modules:
  - `mcp_tools_py.log_utils` → re-exports `mcp_coder_utils.log_utils`
  - `mcp_tools_py.utils.subprocess_runner` → re-exports `mcp_coder_utils.subprocess_runner`
  - `mcp_tools_py.utils.file_utils` → re-exports `mcp_coder_utils.fs`
- **Only the 3 shim files** are allowed to import from `mcp_coder_utils` directly.
- A new `forbidden` contract in `.importlinter` enforces this at CI time.
- CLAUDE.md documents the shared library pattern so future contributors (human or LLM) don't reintroduce direct imports.

### Why shims?

Shims decouple the codebase from the upstream package's module layout. If `mcp_coder_utils` renames a module, only one shim file changes — not 18 consumers.

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/utils/file_utils.py` | Rewrite as re-export shim from `mcp_coder_utils.fs` |
| `src/mcp_tools_py/utils/__init__.py` | May need minor update if re-exported names change |
| `src/mcp_tools_py/code_checker_pytest/utils.py` | Delete local `read_file`, import from `utils.file_utils` |
| `src/mcp_tools_py/main.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/server.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/checker_tools.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/utility_tools.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/inspect_library.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/formatter/formatter_tools.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/formatter/black_runner.py` | `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/formatter/isort_runner.py` | `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/refactoring/__init__.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/refactoring/rope_tools.py` | `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/code_checker_pylint/runners.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/code_checker_pylint/reporting.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/code_checker_pytest/reporting.py` | `log_utils` import prefix swap |
| `src/mcp_tools_py/code_checker_mypy/runners.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/code_checker_ruff/runners.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/code_checker_bandit/runners.py` | `log_utils` + `subprocess_runner` import prefix swap |
| `src/mcp_tools_py/code_checker_vulture/runners.py` | `subprocess_runner` import prefix swap |
| `.importlinter` | Add `mcp_coder_utils_isolation` forbidden contract |
| `.claude/CLAUDE.md` | Add "Shared libraries" section |

## Files NOT Modified

| File | Reason |
|------|--------|
| `tests/test_code_checker_pylint_main.py` | Test-local `read_file` helper — no benefit in swapping |

## Steps Overview

1. **Step 1** — Update `file_utils.py` shim + swap `code_checker_pytest/utils.py` consumer + test
2. **Step 2** — Redirect all `log_utils` direct imports (prefix swap) + test
3. **Step 3** — Redirect all `subprocess_runner` direct imports (prefix swap) + test
4. **Step 4** — Add import-linter isolation contract + verify
5. **Step 5** — Add "Shared libraries" section to CLAUDE.md
