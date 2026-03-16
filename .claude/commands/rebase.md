---
allowed-tools: Bash(git status:*), Bash(git log:*), Bash(git branch:*), Bash(git ls-files:*), Bash(git fetch:*), Bash(git rebase:*), Bash(git add:*), Bash(git rm:*), Bash(git commit:*), Bash(git checkout --ours:*), Bash(git remote get-url:*), Bash(git checkout --theirs:*), Bash(git restore:*), Bash(git stash:*), Bash(git push --force-with-lease:*), Bash(git diff:*), Bash(git rev-parse:*), Bash(gh run view:*), Bash(./tools/format_all.sh:*), Bash(tools/format_all.bat:*), Bash(gh issue view:*), mcp__mcp-tools-py__run_pylint_check, mcp__mcp-tools-py__run_pytest_check, mcp__mcp-tools-py__run_mypy_check, mcp__filesystem__list_directory, mcp__filesystem__read_file, mcp__filesystem__save_file, mcp__filesystem__append_file, mcp__filesystem__delete_this_file, mcp__filesystem__move_file, mcp__filesystem__edit_file
workflow-stage: utility
suggested-next: (context-dependent)
---

# Rebase Branch onto Main

Rebase the current feature branch onto `origin/main` and resolve conflicts.

## Pre-flight Checks (Abort if any fail)

1. Working directory is clean (`git status` shows no uncommitted changes)
2. Not already in rebase/merge state
3. Not on main/master branch
4. Remote origin exists

## Workflow

1. `git fetch origin`
2. `git rebase origin/main`
3. For each conflict:
   - Apply resolution strategy (see below)
   - Verify no conflict markers remain
   - `git add <file>` or `git rm <file>`
   - `git rebase --continue`
4. Run code checks: `mcp__mcp-tools-py__run_pytest_check`, `mcp__mcp-tools-py__run_pylint_check`, `mcp__mcp-tools-py__run_mypy_check`
5. Fix any issues from merge
6. Report summary and ask for user confirmation
7. `git push --force-with-lease`

## Conflict Resolution Strategies

| File Type | Strategy |
|-----------|----------|
| Code files (`.py`, `.js`, etc.) | Keep both sides, merge imports |
| Test files | Keep all tests from both sides |
| Config files | Merge additively, prefer HEAD for same keys |
| Lockfiles (`*-lock.json`, `*.lock`) | Accept theirs (`--theirs`), notify user to regenerate after rebase |

## Abort Rules (in priority order)

1. Any unexpected error - abort, report full error
2. Binary file conflict - abort, cannot auto-resolve
3. Unknown file type - abort, no safe strategy
4. Conflict markers remain after resolution - abort
5. Same file conflicts 3+ times - abort
6. Code quality fails after 2 fix attempts - abort
7. Any other unexpected situation - abort, suggest manual intervention

On abort: run `git rebase --abort`, report which rule triggered, suggest next steps.
