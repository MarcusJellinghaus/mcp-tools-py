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

**Justify any native tool.** Before Read, Write, Edit, Glob, Grep, or Bash, say in chat, on two lines:

- *What it does* — one sentence.
- *Why MCP doesn't* — which tool you'd have used, and what stops it.

If you can't name the gap, use the MCP tool. Exempt: the approved commands under Git operations.

**Protected files** (`.mcp*.json`, `.claude/settings*.json`, `.mcp-file-access`): MCP refuses writes to them by design. Stop and ask the user to edit the file — a refusal is not a gap, so never fall back to Edit/Write, Bash or PowerShell.

**No session scratchpad.** MCP tools can't write outside the project. Temporary files go in `.scratch/`.

### Tool mapping

| Task | MCP tool |
|------|----------|
| Read file | `mcp__mcp-workspace__read_file` |
| Edit file | `mcp__mcp-workspace__edit_file` |
| Write file | `mcp__mcp-workspace__save_file` |
| Append to file | `mcp__mcp-workspace__append_file` |
| Delete file | `mcp__mcp-workspace__delete_this_file` |
| Delete directory (`rmdir`; `rm -r` with `recursive=True`) | `mcp__mcp-workspace__delete_directory` |
| Move file | `mcp__mcp-workspace__move_file` |
| List directory | `mcp__mcp-workspace__list_directory` |
| Search files | `mcp__mcp-workspace__search_files` |
| Read reference project | `mcp__mcp-workspace__read_reference_file` |
| List reference dir | `mcp__mcp-workspace__list_reference_directory` |
| Get reference projects | `mcp__mcp-workspace__get_reference_projects` |
| Search reference files | `mcp__mcp-workspace__search_reference_files` |
| Get base branch | `mcp__mcp-workspace__get_base_branch` |
| Check file size | `mcp__mcp-workspace__check_file_size` |
| Check branch status | `mcp__mcp-workspace__check_branch_status` |
| Run pytest | `mcp__mcp-tools-py__run_pytest_check` |
| Run pylint | `mcp__mcp-tools-py__run_pylint_check` |
| Run mypy | `mcp__mcp-tools-py__run_mypy_check` |
| Run vulture | `mcp__mcp-tools-py__run_vulture_check` |
| Run lint-imports | `mcp__mcp-tools-py__run_lint_imports_check` |
| Run ruff check | `mcp__mcp-tools-py__run_ruff_check` |
| Run ruff fix | `mcp__mcp-tools-py__run_ruff_fix` |
| Run bandit | `mcp__mcp-tools-py__run_bandit_check` |
| Run tach | `mcp__mcp-tools-py__run_tach_check` |
| Format code (project's configured formatter) | `mcp__mcp-tools-py__run_format_code` |
| Check a Python semantic before claiming it | scratch probe — see [Scratch probes](#scratch-probes) |
| Get library source of installed deps (never `python -c "__file__"` + cat site-packages) | `mcp__mcp-tools-py__get_library_source` |
| Search installed deps / stdlib source | `mcp__mcp-tools-py__search_library_files` |
| Run deptry | `mcp__mcp-tools-py__run_deptry_check` |
| Refactoring | `mcp__mcp-tools-py__move_symbol`, `move_module`, `rename_symbol`, `list_symbols`, `find_references` |
| Git read-only (status, diff, log, show, fetch, ls_tree, ls_files, ls_remote, rev_parse, branch list) | `mcp__mcp-workspace__git` |
| Git write (switch/create branch, delete branch, commit, push, force-push after rebase) | `mcp__mcp-workspace__git_branch`, `git_branch_delete`, `git_commit`, `git_push`, `git_push_force` |
| View GitHub issue | `mcp__mcp-workspace__github_issue_view` |
| List GitHub issues | `mcp__mcp-workspace__github_issue_list` |
| View GitHub PR | `mcp__mcp-workspace__github_pr_view` |
| Search GitHub issues/PRs | `mcp__mcp-workspace__github_search` |
| Create GitHub issue | `mcp__mcp-workspace__github_issue_create` |
| Edit GitHub issue | `mcp__mcp-workspace__github_issue_edit` |
| Comment on GitHub issue | `mcp__mcp-workspace__github_issue_comment` |
| Set issue workflow status | `mcp__mcp-workspace__github_issue_set_status` |
| Sub-issues (list, link, unlink) | `mcp__mcp-workspace__github_subissue_list`, `github_subissue_add`, `github_subissue_remove` |
| Create GitHub PR | `mcp__mcp-workspace__github_pr_create` |
| Reply to / resolve PR review comment | `mcp__mcp-workspace__github_review_comment_reply`, `github_review_thread_resolve` |
| List GitHub labels | `mcp__mcp-workspace__github_label_list` |

**`git_commit`:** always pass `paths`, never `all=True` — `all` is `git add -A`, which commits every untracked file that isn't gitignored (stray downloads, notes, files other sessions left behind).

Sibling repos are readable in full via the reference tools and `git` with `reference_name` (`get_reference_projects` lists them). Check there before asking about another repo. The GitHub issue/PR read tools and the issue write tools also take `reference_name` for reference projects. That is the only cross-repo route; for repos that aren't reference projects, stop and report.

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
New markers must be registered under `[tool.pytest.ini_options] markers` in `pyproject.toml`, or collection fails (`--strict-markers`).

```python
# Fast unit tests (recommended for regular development)
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])

# All tests (slow)
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])

# Integration tests only
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"], markers=["integration"])
```

When debugging test failures, add `"-v", "-s", "--tb=short"` to extra_args.

## Scratch probes

Don't assert Python behaviour you haven't run. Probe it:

```python
mcp__mcp-workspace__save_file(".scratch/test_probe.py", ...)
mcp__mcp-tools-py__run_pytest_check(extra_args=["-p", "no:cacheprovider", ".scratch/test_probe.py"])
```

A path argument scopes the run, so a probe costs seconds. Delete when done — `delete_directory(".scratch", recursive=True)`; CI still blocks any PR carrying one. `.scratch/` is gitignored; the `read-write /.scratch/` rule in `.mcp-file-access` keeps it writable for the MCP file tools.

Never use `python -c` via Bash. If you reason instead of running, label the conclusion analytical.

## Git operations

**Allowed commands via Bash tool.** These have no MCP equivalent — use Bash directly. Skills that instruct bash commands (e.g. `git rebase`) must also use Bash.

```
git add / rebase / push --force-with-lease
gh run view
mcp-coder check file-size --max-lines 750
```

**Status labels:** `github_issue_create` and `github_issue_edit` reject `status-*` labels; use `mcp__mcp-workspace__github_issue_set_status` to change issue workflow status (`from_status` guards the current status; `reference_name` for reference projects).

**Privileged agents:** `commit-pusher`, `issue-updater` and `issue-approver` each carry a frontmatter `PreToolUse` hook that allows their extra tools without a prompt — `git_commit` and `git_push` for `commit-pusher`, `github_issue_edit` for `issue-updater`, `github_issue_set_status` for `issue-approver`. No `bypassPermissions`. Frontmatter hooks are skipped in untrusted folders and under `-p` → there the tools prompt (interactive) or are denied (`-p`). That is an ergonomics device, not access control — any session can launch them. None of the three has `Bash`. Rationale and limits: `docs/repository-setup/agent-permissions.md` in the mcp-coder repository.

**Compact diff:** use `mcp__mcp-workspace__git` for code review. Has compact diff built-in with exclude pattern support.

**Before every commit:** run `mcp__mcp-tools-py__run_format_code`, then `mcp__mcp-workspace__git_commit`.

**Bash discipline:** no `cd` prefix, no `git -C` — commands already run in the project directory. Don't chain approved with unapproved commands. Run them separately.

**Commit messages:** standard format. See Writing style for length. No attribution footers.

**Pull requests:** no "Generated with Claude Code" footer. Keep descriptions concise.

## Writing style

Before sending, cut any sentence that doesn't tell the reader something new or change what they do next — chat, commits, PRs, docs, comments, skill output alike. No pleasantries, no hedging, no filler opens or closes; hedge only when the uncertainty changes the action. Stay readable: short clauses or arrow chains over dense paragraphs; lead with the outcome.

Don't restate investigation the tool calls already show (file reads, searches, test runs). In chat, give the conclusion and the decision points only — not a narrated walkthrough of how you got there.

## Progress during loops

Repeating the same action across 3+ items (e.g. files, issues, repos) → one short line per item as it completes, not just a final summary.

## Asking questions

Never use the AskUserQuestion tool. Ask questions as plain text in the chat.

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
