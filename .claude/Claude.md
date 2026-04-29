## About this repo

`mcp-tools-py` is an MCP server exposing Python code-quality tools (pylint, pytest, mypy, ruff, black, isort, vulture, bandit, lint-imports) as structured MCP endpoints.

## Shared libraries

This project depends on `mcp-coder-utils` for subprocess execution, logging, and file I/O.

**Import rule:** never import `mcp_coder_utils` directly. Always use the local shim modules:

| Need | Import from |
|------|-------------|
| Logging (`log_function_call`, `setup_logging`, `OUTPUT`) | `mcp_tools_py.log_utils` |
| Subprocess (`execute_command`, `CommandResult`, etc.) | `mcp_tools_py.utils.subprocess_runner` |
| File I/O (`read_file`) | `mcp_tools_py.utils.file_utils` |

This is enforced by the `mcp_coder_utils_isolation` contract in `.importlinter`.

**Do not reimplement** functionality that exists in `mcp-coder-utils`. Check the `mcp-coder-utils` reference project before writing new utilities.

## MCP Tools — mandatory

Use MCP tools for **all** operations. Never use `Read`, `Write`, `Edit`, `Glob`, `Grep`, or `Bash` for tasks that have an MCP equivalent.

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
| Git (status, log, diff, fetch, etc.) | `mcp__workspace__git` |
| Get base branch | `mcp__workspace__get_base_branch` |
| View GitHub issue | `mcp__workspace__github_issue_view` |
| List GitHub issues | `mcp__workspace__github_issue_list` |
| View GitHub PR | `mcp__workspace__github_pr_view` |
| Search GitHub | `mcp__workspace__github_search` |

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

**MCP tools (use these for read-only git and GitHub queries):**

```
mcp__workspace__git           (status, log, diff, fetch, show, merge_base, ls_files, ls_remote, etc.)
mcp__workspace__github_issue_view
mcp__workspace__github_issue_list
mcp__workspace__github_pr_view
mcp__workspace__github_search
mcp__workspace__check_branch_status
```

**Bash-only (no MCP equivalent):**

```
git commit / git checkout / git rebase / git push
gh run view
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
