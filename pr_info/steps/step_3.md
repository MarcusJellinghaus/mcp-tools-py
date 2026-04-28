# Step 3 — Create `.github/workflows/notify-downstream.yml`

**Reference:** `pr_info/steps/summary.md` (issue #182).
**Commit:** one — single new file.

## WHERE
- **File (new):** `.github/workflows/notify-downstream.yml`

## WHAT
Create a GitHub Actions workflow that sends a `repository_dispatch` event to `MarcusJellinghaus/mcp_coder` whenever this repo's `main` branch updates (or via manual trigger). Event type: `upstream-main-updated`. Payload: `{"upstream": "mcp-tools-py", "sha": "<commit sha>"}`.

### Exact file content (verbatim from issue #182)

```yaml
name: Notify downstream of main update

# When this repo's main changes, send a repository_dispatch event to mcp_coder
# so it can re-run mypy against the latest main of this package.
#
# Requires repo secret DOWNSTREAM_PAT — a fine-grained PAT with
#   Contents: Read & write   (on the target repo, mcp_coder)
#   Metadata: Read
# Create at: https://github.com/settings/personal-access-tokens/new
# Add to this repo via: Settings → Secrets and variables → Actions → New repository secret.

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  dispatch-to-mcp-coder:
    name: dispatch-to-mcp_coder
    runs-on: ubuntu-latest
    steps:
      - name: Send upstream-main-updated to mcp_coder
        uses: peter-evans/repository-dispatch@v3
        with:
          token: ${{ secrets.DOWNSTREAM_PAT }}
          repository: MarcusJellinghaus/mcp_coder
          event-type: upstream-main-updated
          client-payload: '{"upstream": "mcp-tools-py", "sha": "${{ github.sha }}"}'
```

## HOW
- New file — created via `mcp__workspace__save_file`.
- The `DOWNSTREAM_PAT` secret is set out-of-band by the user (not part of any commit).
- No path filter or concurrency settings — main-branch pushes are infrequent and dispatch is cheap (per issue decision).
- Note: target repository name is `mcp_coder` (underscore), not `mcp-coder`. Easy typo target — copy verbatim.
- No job-level `permissions:` block (matches sibling `mcp-workspace#168` decision).

## ALGORITHM
N/A — declarative workflow.

## DATA
- **Event sent:** `repository_dispatch` to `MarcusJellinghaus/mcp_coder`
- **Type:** `upstream-main-updated`
- **Payload:** `{"upstream": "mcp-tools-py", "sha": "<github.sha>"}`

## Verification (this step)

1. **YAML sanity** — re-read the file end-to-end with `mcp__workspace__read_file`. Confirm:
   - File parses as YAML (no tabs, no mixed indentation).
   - `repository: MarcusJellinghaus/mcp_coder` (underscore — verify byte-by-byte).
   - `client-payload` JSON string is `'{"upstream": "mcp-tools-py", "sha": "${{ github.sha }}"}'`.
2. Mandatory MCP checks per CLAUDE.md (no-op for non-Python files but required):
   ```
   mcp__tools-py__run_pylint_check
   mcp__tools-py__run_pytest_check    (extra_args=["-n", "auto", "-m", "not integration"])
   mcp__tools-py__run_mypy_check
   ```
3. Real verification (post-merge, by user — listed in acceptance criteria, not part of this step's commit):
   - Push to this repo's `main` triggers a `repository_dispatch` run in `mcp_coder`'s Actions tab.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`. Implement step 3 only.
>
> Create the new file `.github/workflows/notify-downstream.yml` with **exactly** the YAML content shown verbatim in the "Exact file content" section of step_3.md. Do not modify, paraphrase, or reformat any line — including comments, indentation, and the `client-payload` JSON string.
>
> Critical details:
> - Target repository is `MarcusJellinghaus/mcp_coder` (with underscore in `mcp_coder`).
> - No job-level `permissions:` block.
> - No `concurrency:` block, no `paths:` filter on the `push` trigger.
>
> Use `mcp__workspace__save_file`. After saving, re-read the file and verify byte-for-byte against the spec.
>
> Run the three mandatory MCP checks. Commit:
>
> Commit message: `Add notify-downstream workflow to dispatch main updates to mcp_coder (#182)`.
