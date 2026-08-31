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

**Do NOT use native Claude Code file tools** (`Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash`) for any operation that has an MCP equivalent. Always use the `mcp__mcp-workspace__*` tools instead. This applies to all file reading, writing, editing, searching, listing, and git operations. If no MCP equivalent exists, use Bash. Check the tool mapping table below first.

### Tool mapping

| Task | MCP tool |
|------|----------|
| Read file | `mcp__mcp-workspace__read_file` |
| Edit file | `mcp__mcp-workspace__edit_file` |
| Write file | `mcp__mcp-workspace__save_file` |
| Append to file | `mcp__mcp-workspace__append_file` |
| Delete file | `mcp__mcp-workspace__delete_this_file` |
| Move file | `mcp__mcp-workspace__move_file` |
| List directory | `mcp__mcp-workspace__list_directory` |
| Search files | `mcp__mcp-workspace__search_files` |
| Read reference project | `mcp__mcp-workspace__read_reference_file` |
| List reference dir | `mcp__mcp-workspace__list_reference_directory` |
| Get reference projects | `mcp__mcp-workspace__get_reference_projects` |
| Search reference files | `mcp__mcp-workspace__search_reference_files` |
| Check file size | `mcp__mcp-workspace__check_file_size` |
| Check branch status | `mcp__mcp-workspace__check_branch_status` |
| Get base branch | `mcp__mcp-workspace__get_base_branch` |
| Run pytest | `mcp__mcp-tools-py__run_pytest_check` |
| Run pylint | `mcp__mcp-tools-py__run_pylint_check` |
| Run mypy | `mcp__mcp-tools-py__run_mypy_check` |
| Run vulture | `mcp__mcp-tools-py__run_vulture_check` |
| Run lint-imports | `mcp__mcp-tools-py__run_lint_imports_check` |
| Run ruff check | `mcp__mcp-tools-py__run_ruff_check` |
| Run ruff fix | `mcp__mcp-tools-py__run_ruff_fix` |
| Run bandit | `mcp__mcp-tools-py__run_bandit_check` |
| Format code (black+isort) | `mcp__mcp-tools-py__run_format_code` |
| Get library source | `mcp__mcp-tools-py__get_library_source` |
| Refactoring | `mcp__mcp-tools-py__move_symbol`, `move_module`, `rename_symbol`, `list_symbols`, `find_references` |
| Git (status, log, diff, fetch, etc.) | `mcp__mcp-workspace__git` |
| `gh issue view` | `mcp__mcp-workspace__github_issue_view` |
| `gh issue list` | `mcp__mcp-workspace__github_issue_list` |
| `gh pr view` | `mcp__mcp-workspace__github_pr_view` |
| `gh search` | `mcp__mcp-workspace__github_search` |

## Code quality checks

After making code changes, run:

```
mcp__mcp-tools-py__run_pylint_check
mcp__mcp-tools-py__run_pytest_check
mcp__mcp-tools-py__run_mypy_check
```

All checks must pass before proceeding.

**Ruff:** use `mcp__mcp-tools-py__run_ruff_check`. Do not call `ruff` directly.

**Pytest:** always use `extra_args: ["-n", "auto"]` for parallel execution.

Available marker: `integration` (requires external resources).

```python
# Fast unit tests (recommended for regular development)
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])

# All tests (slow)
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])

# Integration tests only
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"], markers=["integration"])
```

When debugging test failures, add `"-v", "-s", "--tb=short"` to extra_args.

## Git operations

**MCP tools (use these for read-only git and GitHub queries):**

```
mcp__mcp-workspace__git           (status, log, diff, fetch, show, merge_base, ls_files, ls_remote, etc.)
mcp__mcp-workspace__github_issue_view
mcp__mcp-workspace__github_issue_list
mcp__mcp-workspace__github_pr_view
mcp__mcp-workspace__github_search
mcp__mcp-workspace__check_branch_status
```

**Bash-only (no MCP equivalent):**

```
git commit / git checkout / git rebase / git push
gh run view
mcp-coder check file-size --max-lines 750
```

**Before every commit:** run `mcp__mcp-tools-py__run_format_code`, then stage and commit.

**Bash discipline:** no `cd` prefix, no `git -C`. Don't chain approved with unapproved commands. Run them separately.

**Commit messages:** standard format, clear and descriptive. No attribution footers.

**Pull requests:** no "Generated with Claude Code" footer. Keep descriptions concise.

## Writing style

Be concise. If one line works, don't use three.

## Obsidian knowledge base

Shared knowledge base across my repos (`obsidian-dev-wiki`), via the `obsidian-wiki` MCP server.

**Read at the start of non-trivial work:** `Home.md` (index), the `Repos/<current repo>.md` note, and any `Processes/` note matching the task. If a process note covers the task, follow it rather than improvising.

**Write only what passes all three tests:**

- *durable* — still true in 6 months (not status, versions, or task state)
- *general* — applies beyond the one issue that produced it
- *homeless* — no better place already exists

Existing homes, check before writing: code and docstrings; the repo's `docs/`; CLAUDE.md for how-I-work rules; the GitHub issue for a single defect's root cause; git history for what changed when.

**Always write to `Field Notes/`**, for Marcus to promote. Only edit `Repos/`, `Processes/`, or `Plans/` when Marcus explicitly asks for it. If an existing note already covers the topic, name it in the Field Note (`Promote into [[Note Name]]`) instead of editing that note. Follow `Conventions.md` for frontmatter and naming.

## MCP server issues

Alert immediately if MCP tools are not accessible — this blocks all work.
