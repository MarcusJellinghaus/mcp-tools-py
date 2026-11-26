# Python Guidelines

For repos with the `mcp-tools-py` toolkit. Skills and agents name steps by purpose; here they map to these tools.

## Tools by purpose

- **Checks:** pylint, mypy, ruff (`run_pylint_check`, `run_mypy_check`, `run_ruff_check`).
- **Tests:** pytest (`run_pytest_check`), with the arguments and marker filters CLAUDE.md requires.
- **Format:** `run_format_code`.
- **Dead code and architecture:** vulture (`run_vulture_check`), import-linter (`run_lint_imports_check`), tach (`run_tach_check`). The implementation-review supervisor runs vulture and lint-imports itself before its final status: import-contract violations go to the user (fixes may move code between layers); simple vulture whitelist additions go to `code-engineer`, then re-run until clean.
- **Refactoring:** `move_symbol`, `move_module` (they update imports), `rename_symbol`.

## Conventions

- **f-strings are preferred.**
- **Use type hint syntax appropriate for the project's minimum supported Python version.**
- **Avoid conditional imports.** If a dependency is missing, stop and escalate to the user rather than working around it.
- **Tests for optional resources should skip, not fake.** When a test depends on something that may not be available (an optional SDK, a database, an API, a CLI tool), use `pytest.importorskip` or `pytest.mark.skipif` to skip transparently. Don't mock the resource just to make the test run everywhere — skipping is honest and avoids false confidence.
- **Test layout:** tests for `src/foo/bar.py` go in `tests/foo/test_bar.py`.
- **Config names:** the dependency manifest is `pyproject.toml` (dependencies, extras, `[tool.*]` check config such as mypy overrides); architecture-check config is `.importlinter` and `tach.toml`. Apply requirement changes during planning so implementation starts in the updated Python environment.

## Refactoring

- Allowed edits in a pure move include `try/except ImportError` optional-import blocks and the `__init__.py` / `conftest.py` files the move needs.
- Import cycles: pylint `R0401` counts function-local imports as edges, but not `if TYPE_CHECKING:` imports. A shared runtime value (e.g. a NamedTuple) goes in a dependency-free module such as `types.py`.
- Verifying a pure move: pytest test count and markers, `patch` targets that resolve but patch nothing, fixtures no longer applied.
