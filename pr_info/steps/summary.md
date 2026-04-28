# Summary — Cross-repo CI: listen to mcp-coder-utils, notify mcp_coder, add typecheck extra

**Issue:** #182
**Scope:** CI / packaging metadata only — no source code or test changes.

## Goal

Wire `mcp-tools-py` into the 4-repo cross-repo CI graph as a "middle" node:

- **Listen** to `mcp-coder-utils` `main` updates and re-run mypy --strict against the latest upstream.
- **Notify** `mcp_coder` when this repo's `main` updates so it can do the same.
- Add a uniform `[typecheck]` extra and bump the mypy floor in lockstep with sibling repos (`mcp-coder-utils`, `mcp-workspace`, `mcp_coder`).
- Bump existing GitHub Actions to the same versions used by the new workflows for toolchain uniformity.

## Architectural / design notes

- **No application code change.** All edits are in `pyproject.toml` and `.github/workflows/`. Source layout, module structure, dependency graph (in code), and the architecture in `docs/architecture/architecture.md` are unaffected.
- **`[typecheck]` extra is intentionally redundant with the runtime mypy pin.** The duplication is accepted to keep the `upstream-mypy-check.yml` step shape (`uv pip install --system ".[typecheck]"`) identical across the 4-repo family. Drift risk is small.
- **`mypy` stays in the main `[dependencies]` block** (pre-existing quirk). Bumping in place is chosen over moving it to `[dev]`/`[typecheck]` to keep the change minimal.
- **No `types-requests` in `[typecheck]`.** `requests` is not used in `src/` or `tests/` (verified by issue author; will re-verify before editing).
- **Cross-repo wiring is event-driven via `repository_dispatch`.** Outbound (`notify-downstream.yml`) sends `upstream-main-updated` to `mcp_coder`. Inbound (`upstream-mypy-check.yml`) receives the same event type from `mcp-coder-utils`.
- **Auto-firing of `upstream-mypy-check.yml` is gated on the upstream prerequisite** (`mcp-coder-utils#28`). Until that ships, only `workflow_dispatch` exercises the workflow. Acceptable per the issue.
- **Install order in `upstream-mypy-check.yml` is load-bearing.** Step 1 installs `mcp-coder-utils` from `git+main`; step 2 installs `.[typecheck]`. The repo's bare `mcp-coder-utils` entry (no version pin) is satisfied by the already-installed git version. Reordering would silently replace upstream-main with PyPI. A YAML comment guards against future reordering.
- **Identical mypy invocation across `upstream-mypy-check.yml` and `ci.yml`'s mypy matrix entry** — both run `mypy --strict src tests`. Only the upstream version varies, giving a clean cross-repo signal.
- **Out-of-band setup (user action, not in PR):** create `DOWNSTREAM_PAT` repo secret. The PAT is reused from `mcp-coder-utils#28` without scope changes.

## Files created or modified

### Created (2)
- `.github/workflows/notify-downstream.yml`
- `.github/workflows/upstream-mypy-check.yml`

### Modified (3)
- `pyproject.toml` — bump mypy floor; add `[typecheck]` extra
- `.github/workflows/ci.yml` — bump `setup-uv@v5→v8` and `setup-python@v5→v6`; quote `python-version: "3.11"` (in both `test` and `architecture` jobs)
- `.github/workflows/publish.yml` — bump `setup-python@v5→v6` (in `build` job only)

### Untouched
- `src/`, `tests/` — no code changes
- `.github/workflows/approve-command.yml`, `.github/workflows/label-new-issues.yml` — already on current action versions
- `docs/architecture/architecture.md` — architecture unchanged
- `tach.toml`, `.importlinter`, `vulture_whitelist.py` — no module structure change

## Implementation steps overview

| # | Step | Commit scope |
|---|------|---|
| 1 | `pyproject.toml` — mypy floor + `[typecheck]` extra | One file, two edits |
| 2 | Bump action versions in existing workflows (`ci.yml`, `publish.yml`) | Mechanical version bumps |
| 3 | Create `.github/workflows/notify-downstream.yml` | New file |
| 4 | Create `.github/workflows/upstream-mypy-check.yml` | New file |

Each step is independently committable, atomic, and reviewable. Steps 1 and 2 can be verified locally (mypy run + YAML parse). Steps 3 and 4 are verified by YAML parse + post-merge `workflow_dispatch` smoke test (issue acceptance criteria, executed by user).

## Verification model

This work has no application logic, so TDD does not apply in the traditional sense. Per-step verification uses:

- **Static checks**: YAML parses (CI loads workflows); `pyproject.toml` is valid TOML.
- **Local checks** (after step 1): mandatory MCP tooling — `run_pylint_check`, `run_pytest_check`, `run_mypy_check` — to confirm the mypy floor bump doesn't surface new strict-mode regressions.
- **Post-merge manual checks** (acceptance criteria, by the user): trigger `Upstream mypy check` via `workflow_dispatch`; observe `mcp_coder` Actions tab after a push.

## Acceptance criteria (from the issue, recap)

- [ ] `pyproject.toml` line 29 bumped to `mypy>=1.13.0`
- [ ] `[typecheck] = ["mypy>=1.13.0"]` extra exists
- [ ] `notify-downstream.yml` exists and parses
- [ ] `upstream-mypy-check.yml` exists and parses, includes the install-order comment, uses `setup-uv@v8` / `setup-python@v6` / `checkout@v6`
- [ ] `ci.yml` bumped to `setup-uv@v8` / `setup-python@v6` (both jobs); `python-version` quoted as `"3.11"` (both spots)
- [ ] `publish.yml` bumped to `setup-python@v6` in `build` job
- [ ] `DOWNSTREAM_PAT` secret set (user action)
- [ ] Manual `workflow_dispatch` of `Upstream mypy check` runs to completion (user action)
- [ ] Post-merge: `Upstream mypy check` run appears after upstream `mcp-coder-utils#28` ships and pushes (user observation)
- [ ] Post-merge: push to this repo's `main` triggers a `repository_dispatch` run in `mcp_coder` (user observation)
