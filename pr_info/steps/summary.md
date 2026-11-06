# Adopt the new Toolkit signatures (#274)

## Goal

Make `mypy src tests` pass again. mcp-coder-utils 8d9baff changed the `Toolkit` base class, and `PythonToolkit` still has the old signatures, which gives 2 `[override]` errors.

| Method | `Toolkit` (new) | `PythonToolkit` (today) |
|---|---|---|
| `describe` | `describe(self)` | `describe(self, config: Mapping[str, Any])` |
| `verify` | `verify(self, project_dir: Path, action: str \| None = None)` | `verify(self, project_dir: Path)` |

## Architectural / design changes

No architectural change: no new modules, classes, dependencies or runtime behaviour.

- **Config:** `describe` no longer receives config. It didn't use it, and the base class constructor stores config as `self.config`. `PythonToolkit` has no `__init__`, so it inherits this.
- **`verify`:** accepts `action` and ignores it, so every action still checks everything. This deviates from the base contract until #272, which is acceptable because nothing calls `verify` with an action yet.

## Files

Created: none. No folders or modules are added.

Modified:

| File | Change |
|---|---|
| `src/mcp_tools_py/toolkit.py` | New `describe` and `verify` signatures, `verify` docstring, remove `Mapping` and `Any` imports |
| `tests/test_toolkit.py` | `TestDescribe` calls `describe()` |

## Decisions

- **One step.** Both signatures fail the same mypy check, so a commit fixing only one would not pass.
- **No `Args:` section on `verify`.** A plain docstring sentence says `action` is ignored. No other method in the class has `Args:`, and this avoids ruff's D417.
- **No test for `action`.** Mypy covers the signature, and a test pinning "ignored" would flip in #272.
- **`describe` docstring stays as it is.** Its stale "`run` only handles `test` so far" is outside this issue.

## Out of scope

Everything else stays in #272, including `verify` filtering by action, the `error` item for an undeclared action, and deptry in `verify`.

## Steps

1. [step_1.md](./step_1.md): adopt both signatures and update `TestDescribe`.
