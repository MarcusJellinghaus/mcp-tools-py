# Implementation Review Log — Issue #182 (Run 1)

**Branch:** `182-add-cross-repo-ci-listen-to-mcp-coder-utils-notify-mcp-coder-add-typecheck-extra`
**Scope:** CI / packaging metadata only — `pyproject.toml` + `.github/workflows/`. No source code or test changes.
**Started:** 2026-04-28

## Round 1 — 2026-04-28

**Findings:**
- **Critical**: `.github/workflows/upstream-mypy-check.yml` pins `astral-sh/setup-uv@v8`, which does not exist in the GitHub Actions marketplace. Commit `af6fc17` already rolled `ci.yml` back to `@v7` for the same reason; the new workflow was missed.
- **Critical (engineer-flagged)**: `pr_info/` is committed and `ci.yml`'s `check-forbidden-folders` job blocks PRs with that folder.
- **Boy Scout**: `pr_info/steps/summary.md`, `step_2.md`, `step_4.md` and the issue body still reference `setup-uv@v8`.
- **Confirmed-correct (no action)**: Intentional `[typecheck]` mypy duplication, mypy staying in `[dependencies]`, quoted `python-version: "3.11"`, no `types-requests`, install-order in `upstream-mypy-check.yml`, `notify-downstream.yml` payload/target, `permissions: contents: read`, `publish.yml` setup-python bump.
- **Local checks (engineer)**: pylint clean, mypy clean, pytest 479 passed / 1 skipped.

**Decisions:**
- Accept fix #1 → change `setup-uv@v8` to `@v7` in `upstream-mypy-check.yml`. Real CI bug; mirrors the established rollback.
- Skip #2 (`pr_info/` blocking PR): pr_info/ is removed during PR finalization (knowledge_base: "deleted later during the process"). Out of scope for code review.
- Skip Boy Scout doc drift in `pr_info/`: those files are about to be deleted; not worth churn.

**Changes:**
- `.github/workflows/upstream-mypy-check.yml`: `astral-sh/setup-uv@v8` → `@v7` (one-line edit).

**Status:** committed as `9ce5070` (`ci: pin astral-sh/setup-uv to v7 in upstream-mypy-check (#182)`).

## Round 2 — 2026-04-28

**Findings:**
- Round 1 fix confirmed: `astral-sh/setup-uv@v7` now in `upstream-mypy-check.yml`. All 3 `setup-uv` refs uniform at `@v7`; all 4 `setup-python` refs uniform at `@v6`.
- All acceptance-criteria items satisfied: mypy floor + `[typecheck]` extra, both new workflows parse with correct payload/target/install-order/permissions, both modified workflows bumped uniformly with quoted `python-version`.
- No new critical or accept items.

**Decisions:** No changes needed.

**Changes:** None.

**Status:** No code changes — loop terminates.

## Final Status

- **Rounds run:** 2
- **Code commits this review:** 1 (`9ce5070`)
- **Outstanding issues:** None blocking merge. The `pr_info/` folder will be removed during PR finalization (`/implementation_finalise` or equivalent) — out of scope for code review.
- **Acceptance criteria:** All in-PR items satisfied. Out-of-band items (DOWNSTREAM_PAT secret, post-merge dispatch observation) are user actions, unaffected by review.
