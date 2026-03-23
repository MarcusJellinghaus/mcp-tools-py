# Refactoring Principles

## Key Rules

- **Move, don't change.** Functions and classes should be relocated as-is. Logic changes belong in a separate PR.
- **Only adjust imports.** The only code changes during a refactor should be import statements and `__init__.py` re-exports.
- **Clean deletion, no legacy artifacts.** Delete old files entirely — no stubs, no deprecation warnings, no backward-compatible re-exports. Update all consumers immediately.
- **Small steps.** One module per PR when possible. Keep diffs under 25,000 tokens. Move related functions together.
- **Tests mirror source structure.** When moving source code, move corresponding tests to match.

## Process

1. Plan the target structure before moving anything
2. Move source code (copy-paste, no modifications)
3. Move tests to mirror new structure
4. Run all checks (pytest, pylint, mypy, import linter, tach)

## Full Guide

For detailed process, checklists, and conflict resolution strategies, see [Safe Refactoring Guide](../../docs/processes-prompts/refactoring-guide.md).
