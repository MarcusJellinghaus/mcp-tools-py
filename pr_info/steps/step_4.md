# Step 4 — Create `.github/workflows/upstream-mypy-check.yml`

**Reference:** `pr_info/steps/summary.md` (issue #182).
**Commit:** one — single new file.

## WHERE
- **File (new):** `.github/workflows/upstream-mypy-check.yml`

## WHAT
Create a GitHub Actions workflow that:
- Listens for `repository_dispatch` events of type `upstream-main-updated` (sent by `mcp-coder-utils` after #28 ships).
- Also accepts manual triggering via `workflow_dispatch` (with an optional `upstream` input for the dynamic job name).
- Installs `mcp-coder-utils` from `git+main`, then this repo with the `[typecheck]` extra (introduced in step 1), then runs `mypy --strict src tests`.

### Exact file content (verbatim from issue #182)

```yaml
name: Upstream mypy check

# Triggered by repository_dispatch when mcp-coder-utils' main branch changes.
# Runs mypy --strict against this repo with the latest mcp-coder-utils from main.
# On failure: standard GitHub Actions email + red icon in the Actions tab.

on:
  repository_dispatch:
    types: [upstream-main-updated]
  workflow_dispatch:
    inputs:
      upstream:
        description: 'Upstream that triggered this run (shown in the job name)'
        required: false
        default: 'manual'

permissions:
  contents: read

jobs:
  mypy-against-upstream-main:
    name: mypy-against-upstream-${{ github.event.client_payload.upstream || github.event.inputs.upstream }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v8
      - uses: actions/setup-python@v6
        with:
          python-version: "3.11"

      # Order matters: install upstream from git BEFORE `.[typecheck]`
      # so uv's resolver doesn't replace it with a PyPI version. The base
      # pyproject.toml has no version pin on mcp-coder-utils, so any
      # already-installed version satisfies the constraint.
      - name: Install mcp-coder-utils from main
        run: uv pip install --system "mcp-coder-utils @ git+https://github.com/MarcusJellinghaus/mcp-coder-utils.git"

      - name: Install mcp-tools-py with typecheck extra
        run: uv pip install --system ".[typecheck]"

      - name: Run mypy --strict
        run: mypy --strict src tests
```

## HOW
- New file — created via `mcp__workspace__save_file`.
- **Depends on step 1** (the `[typecheck]` extra must exist for `uv pip install --system ".[typecheck]"` to succeed). Steps 1, 2, 3 should land before step 4 if a dispatch happens to fire mid-rollout, though within a single PR ordering is moot.
- The install-order comment is **load-bearing** (acceptance criteria explicitly requires it). Do not abbreviate.
- The mypy invocation `mypy --strict src tests` is intentionally identical to the `ci.yml` matrix entry — only the `mcp-coder-utils` version varies between runs. Do not drift.
- Workflow-level `permissions: contents: read` is least-privilege hygiene.

## ALGORITHM
N/A — declarative workflow. The "logic" is the install-order constraint: git-install upstream first → install this repo's `[typecheck]` extra second → run mypy.

## DATA
- **Trigger event:** `repository_dispatch` (type `upstream-main-updated`) or `workflow_dispatch`
- **Payload field used:** `client_payload.upstream` (for job-name display)
- **Side effect:** mypy exit code → GitHub Actions success/failure status

## Verification (this step)

1. **YAML sanity** — re-read the file end-to-end with `mcp__workspace__read_file`. Confirm:
   - File parses as YAML, no tabs, consistent indentation.
   - The install-order comment is present, complete, and immediately precedes the `Install mcp-coder-utils from main` step.
   - All action versions: `checkout@v6`, `setup-uv@v8`, `setup-python@v6`.
   - `python-version: "3.11"` is quoted.
   - mypy command is exactly `mypy --strict src tests`.
2. Mandatory MCP checks per CLAUDE.md:
   ```
   mcp__tools-py__run_pylint_check
   mcp__tools-py__run_pytest_check    (extra_args=["-n", "auto", "-m", "not integration"])
   mcp__tools-py__run_mypy_check
   ```
3. Real verification (post-merge, by user — listed in acceptance criteria, not part of this step's commit):
   - Manually trigger `Upstream mypy check` via `workflow_dispatch` and confirm mypy runs to completion (success or expected failure).
   - After `mcp-coder-utils#28` ships and a push to its `main` lands, an `Upstream mypy check` run appears in this repo's Actions tab.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`. Implement step 4 only.
>
> Create the new file `.github/workflows/upstream-mypy-check.yml` with **exactly** the YAML content shown verbatim in the "Exact file content" section of step_4.md. Do not modify, paraphrase, or reformat any line — including the install-order comment block (which is required by the issue's acceptance criteria) and the dynamic `name:` expression.
>
> Critical details:
> - Action versions exactly: `actions/checkout@v6`, `astral-sh/setup-uv@v8`, `actions/setup-python@v6`.
> - `python-version: "3.11"` (quoted).
> - The install order is load-bearing: `mcp-coder-utils` from git **before** `.[typecheck]`. Do not reorder. Keep the multi-line comment that explains why.
> - mypy invocation is exactly `mypy --strict src tests` (matches `ci.yml`'s mypy matrix entry).
> - `permissions: contents: read` at workflow level.
>
> Use `mcp__workspace__save_file`. After saving, re-read the file and verify byte-for-byte against the spec.
>
> Run the three mandatory MCP checks. Commit:
>
> Commit message: `Add upstream-mypy-check workflow listening to mcp-coder-utils (#182)`.
