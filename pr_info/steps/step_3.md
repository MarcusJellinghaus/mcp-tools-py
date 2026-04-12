# Step 3: Delete local tests + update config files

**Ref:** [summary.md](summary.md) | **Issue:** #152 | **Commit:** `adopt: remove local tests and update config for mcp-coder-utils`

## Goal

Delete local test files for both migrated modules. Update `.importlinter` and `pyproject.toml` to reflect the new dependency structure.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`.
> Implement step 3: delete `tests/test_subprocess_runner.py` and `tests/test_log_utils.py`. Remove the `mcp_tools_py.log_utils` layer from `.importlinter`. Remove the `[[tool.mypy.overrides]]` for `mcp_tools_py.utils.subprocess_runner` from `pyproject.toml`.
> Run all quality checks (pylint, pytest -n auto excluding integration markers, mypy) and fix any issues.

## WHERE — Files to delete

1. `tests/test_subprocess_runner.py` — shared library has its own tests
2. `tests/test_log_utils.py` — shared library has its own tests

## WHERE — Files to modify

### `.importlinter`

**Remove `mcp_tools_py.log_utils` from the layers contract.** It is now an external dependency and can't be an import-linter layer.

Before:
```ini
layers =
    mcp_tools_py.main
    mcp_tools_py.server
    mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.utility_tools | mcp_tools_py.inspect_library | mcp_tools_py.formatter
    mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy | mcp_tools_py.code_checker_ruff | mcp_tools_py.code_checker_bandit
    mcp_tools_py.utils
    mcp_tools_py.log_utils
```

After:
```ini
layers =
    mcp_tools_py.main
    mcp_tools_py.server
    mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.utility_tools | mcp_tools_py.inspect_library | mcp_tools_py.formatter
    mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy | mcp_tools_py.code_checker_ruff | mcp_tools_py.code_checker_bandit
    mcp_tools_py.utils
```

**Keep** `mcp_tools_py.utils` — it still contains `file_utils.py` and `project_config.py`.

### `pyproject.toml`

**Remove** this mypy override block:
```toml
[[tool.mypy.overrides]]
module = ["mcp_tools_py.utils.subprocess_runner"]
# Disable unused ignore warnings for platform-specific Unix attributes
warn_unused_ignores = false
```

**Reason:** After migration, the local `subprocess_runner.py` is a 10-line shim with no `type: ignore` comments. mypy doesn't type-check the installed `mcp_coder_utils` package. The override is dead config.

## WHAT — No new code

This step only deletes files and removes config lines.

## Verification

- [ ] `tests/test_subprocess_runner.py` deleted
- [ ] `tests/test_log_utils.py` deleted
- [ ] `.importlinter` no longer lists `mcp_tools_py.log_utils`
- [ ] `pyproject.toml` no longer has mypy override for `subprocess_runner`
- [ ] pylint passes
- [ ] pytest passes (unit tests, excluding integration markers)
- [ ] mypy passes
