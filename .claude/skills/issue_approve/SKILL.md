---
description: Approve issue to transition to next workflow status
disable-model-invocation: true
argument-hint: "<issue-number> [--repo owner/repo]"
allowed-tools:
  - mcp__mcp-workspace__github_issue_view
  - "Bash(gh issue view *)"
  - "Bash(MSYS_NO_PATHCONV=1 gh issue comment *)"
  - mcp__mcp-workspace__read_file
---

# Approve Issue

Approve the current issue to transition it to the next status in the workflow.

## Resolve Issue Number

The user may provide an issue number as the argument (available as `$ARGUMENTS`).
If no issue number is provided:
1. Check if the issue number is known from prior `/issue_analyse` or `/issue_create` in this conversation
2. Read `.vscodeclaude_status.txt` and extract the issue number from the `Issue #NNN` line
3. If still unknown, ask the user

## Cross-Repo Issues

If a `--repo owner/repo` flag was given, append it to every `gh` command below, and fetch the
issue with `gh issue view <issue_number> --repo owner/repo` via Bash —
`mcp__mcp-workspace__github_issue_view` only reaches the current repository.

## Instructions

1. Fetch the issue to confirm it exists:
   Call `mcp__mcp-workspace__github_issue_view` with the issue number (or `gh issue view` for cross-repo).

2. Validate that the issue is ready for approval:
   - Issue has been analyzed/discussed
   - Requirements are clear
   - No blocking questions remain

3. Comment `/approve` on the issue (use MSYS_NO_PATHCONV to prevent Windows Git Bash path conversion):

```bash
MSYS_NO_PATHCONV=1 gh issue comment <issue_number> --body "/approve"
```

This triggers the GitHub Action to promote the issue status (e.g., `status-01:created` → `status-02:awaiting-planning`).

**Note:** This skill has `disable-model-invocation` — it can only be run by the user typing `/issue_approve`. If you need this skill as a follow-up, tell the user: "Please run `/issue_approve` to proceed."
