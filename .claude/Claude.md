## About this repo

`mcp-tools-py` is an MCP server exposing Python code-quality tools (pylint, pytest, mypy, ruff, black, isort, vulture, bandit, lint-imports) as structured MCP endpoints.

## MCP Tools — mandatory

Use MCP tools for **all** operations. Never use `Read`, `Write`, `Edit`, or `Bash` for tasks that have an MCP equivalent.

### Tool mapping

| Task | MCP tool |
|------|----------|
| Read file | `mcp__workspace__read_file` |
| Edit file | `mcp__workspace__edit_file` |
| Write file | `mcp__workspace__save_file` |
| Append to file | `mcp__workspace__append_file` |
| Delete file | `mcp__workspace__delete_this_file` |
| Move file | `mcp__workspace__move_file` |
| List directory | `mcp__workspace__list_directory` |
| Search files | `mcp__workspace__search_files` |
| Read reference project | `mcp__workspace__read_reference_file` |
| List reference dir | `mcp__workspace__list_reference_directory` |
| Get reference projects | `mcp__workspace__get_reference_projects` |
| Run pytest | `mcp__tools-py__run_pytest_check` |
| Run pylint | `mcp__tools-py__run_pylint_check` |
| Run mypy | `mcp__tools-py__run_mypy_check` |
| Run vulture | `mcp__tools-py__run_vulture_check` |
| Run lint-imports | `mcp__tools-py__run_lint_imports_check` |
| Run ruff check | `mcp__tools-py__run_ruff_check` |
| Run ruff fix | `mcp__tools-py__run_ruff_fix` |
| Run bandit | `mcp__tools-py__run_bandit_check` |
| Format code (black+isort) | `mcp__tools-py__run_format_code` |
| Refactoring | `mcp__tools-py__move_symbol`, `list_symbols`, `find_references` |

## Code quality checks

After making code changes, run:

```
mcp__tools-py__run_pylint_check
mcp__tools-py__run_pytest_check
mcp__tools-py__run_mypy_check
```

All checks must pass before proceeding.

**Pytest:** always use `extra_args: ["-n", "auto"]` for parallel execution.

Available marker: `integration` (requires external resources).

```python
# Fast unit tests (recommended for regular development)
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])

# All tests (slow)
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto"])

# Integration tests only
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto"], markers=["integration"])
```

When debugging test failures, add `"-v", "-s", "--tb=short"` to extra_args.

## Git operations

**Allowed commands via Bash tool.** These have no MCP equivalent — use Bash directly. Skills that instruct bash commands (e.g. `gh issue view`) must also use Bash.

```
git status / diff / commit / log / fetch / ls-tree
gh issue view / gh pr view / gh run view
mcp-coder check branch-status
mcp-coder check file-size --max-lines 750
```

**Before every commit:** run `mcp__tools-py__run_format_code`, then stage and commit.

**Bash discipline:** no `cd` prefix, no `git -C`. Don't chain approved with unapproved commands. Run them separately.

**Commit messages:** standard format, clear and descriptive. No attribution footers.

**Pull requests:** no "Generated with Claude Code" footer. Keep descriptions concise.

## Writing style

Be concise. If one line works, don't use three.

## MCP server issues

Alert immediately if MCP tools are not accessible — this blocks all work.
