# Step 2 — Bump action versions in existing workflows (`ci.yml`, `publish.yml`)

**Reference:** `pr_info/steps/summary.md` (issue #182).
**Commit:** one — both files together (single logical change: "uniform action toolchain").

## WHERE
- **Files:**
  - `.github/workflows/ci.yml`
  - `.github/workflows/publish.yml`

## WHAT

### `.github/workflows/ci.yml` — 6 edits across 2 jobs (`test`, `architecture`)

For **each** of the two jobs (`test` job and `architecture` job):
1. `uses: astral-sh/setup-uv@v5` → `uses: astral-sh/setup-uv@v8`
2. `uses: actions/setup-python@v5` → `uses: actions/setup-python@v6`
3. `python-version: 3.11` → `python-version: "3.11"`  *(quoted — avoids YAML float footgun)*

`actions/checkout@v6` is already current — leave as-is.

### `.github/workflows/publish.yml` — 1 edit

In the `build` job:
- `uses: actions/setup-python@v5` → `uses: actions/setup-python@v6`

`python-version: "3.11"` is already quoted in `publish.yml` — leave as-is. `actions/checkout@v6`, `actions/upload-artifact@v7`, `actions/download-artifact@v8`, and `pypa/gh-action-pypi-publish@release/v1` are all current — leave as-is.

Other workflows (`approve-command.yml`, `label-new-issues.yml`) already use current versions — do **not** touch.

## HOW
- Mechanical text replacements. No content/logic changes.
- Use `mcp__workspace__edit_file` with unique-context anchors so each replacement targets the right occurrence (since `setup-uv@v5` and `setup-python@v5` each appear twice in `ci.yml`).

## ALGORITHM
N/A — version bumps.

## DATA
N/A.

## Verification (this step)

1. **Visual diff** — confirm only action versions and `python-version` quoting changed; no whitespace or content drift.
2. **YAML sanity** — re-read each modified file end-to-end with `mcp__workspace__read_file` and confirm structure is intact.
3. Mandatory MCP checks per CLAUDE.md (no Python files were touched, so these should be no-ops, but run them anyway for compliance):
   ```
   mcp__tools-py__run_pylint_check
   mcp__tools-py__run_pytest_check    (with fast-unit-test marker exclusion)
   mcp__tools-py__run_mypy_check
   ```

The actual CI-side validation (workflow parses, action versions resolve) only happens once the commit is pushed and CI runs. That's expected.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`. Implement step 2 only.
>
> In `.github/workflows/ci.yml`, in **both** the `test` job and the `architecture` job, make these three replacements (so 6 total edits):
> - `astral-sh/setup-uv@v5` → `astral-sh/setup-uv@v8`
> - `actions/setup-python@v5` → `actions/setup-python@v6`
> - `python-version: 3.11` → `python-version: "3.11"`
>
> In `.github/workflows/publish.yml`, in the `build` job, replace:
> - `actions/setup-python@v5` → `actions/setup-python@v6`
>
> Do not touch `approve-command.yml`, `label-new-issues.yml`, or any non-listed lines. Do not change `actions/checkout@v6` (already current). Do not change `python-version: "3.11"` in `publish.yml` (already quoted).
>
> Use `mcp__workspace__edit_file` with enough surrounding context to disambiguate the duplicate occurrences in `ci.yml`. Re-read each file after editing to confirm correctness.
>
> Run the three mandatory MCP checks. Commit:
>
> Commit message: `CI: bump setup-uv to v8 and setup-python to v6, quote python-version (#182)`.
