# Summary: Raise import-linter minimum to 2.12 (#271)

## Problem

`pyproject.toml:36` requires `import-linter>=2.0`, but `lint-imports` stops on this repo's `.importlinter` with version 2.11 (`Modules have shared descendants.`). `uv pip install -e ".[dev]"` keeps any installed version that meets the minimum, so an existing environment stays broken after a reinstall. CI doesn't show this, because it resolves the latest version.

## Cause

`grimp` raises the error when asked for import chains between overlapping modules. In the `target-scripts-stdlib-only` contract, the source module sits inside its forbidden wildcards. `import-linter` 2.12 skips such pairs before calling `grimp`, so 2.12 is the right floor.

## Architectural / design changes

None. Source code, the module layout, `.importlinter`, `tach.toml` and the architecture docs stay as they are. `docs/architecture/architecture.md:48` lists dependency names without versions, so it needs no update.

The only change is the declared minimum version of one dependency. Environments older than 2.12 now upgrade on the next install.

## Files

| Path | Action | Change |
|---|---|---|
| `pyproject.toml` | Modify | Raise the `import-linter` floor to `>=2.12` and add a comment giving the reason |

No files, folders or modules are created. The `import-linter 2.0` strings in `tests/test_environment_info.py` and `tests/test_code_checker_lint_imports/_fixtures.py` are sample data and stay unchanged.

## Testing approach

No new test: the existing `tests/test_target_scripts_contract.py` already fails on an environment below the floor. The new floor is verified by running that file and `lint-imports` once in a throwaway venv with exactly `import-linter==2.12`.

## Constraints

- A raised floor is not a pin, so this fits the no-pinning decision in #204.
- No direct `grimp` requirement: `import-linter` declares its own `grimp` floor.
- No CI job testing floors and no CI install changes (#204).
- Never run the floor verification against the project's `.venv`: it would downgrade that environment.

## Steps

1. [Raise the `import-linter` floor and verify it](./step_1.md)
