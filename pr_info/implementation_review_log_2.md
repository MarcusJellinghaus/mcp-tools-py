# review-implementation review log 2

Issue #224 — docs: architecture.md and README document 8 and 3 MCP tools respectively; 17 exist

Continues from `implementation_review_log_1.md`, which ran 3 rounds and stopped at a
rebase handoff rather than a code-review conclusion.

## Round 1 — 2026-09-01

**Findings**:
- `README.md:114` — medium — `--log-file` row documents the default backwards ("logs only to console"); `main.py:126-135` writes `project_dir/logs/mcp_tools_py_<timestamp>.log` unless `--console-only` is passed. Raised and dismissed in log 1 round 3; re-raised with new evidence that the row now contradicts `README.md:310` and `architecture.md:235` inside the files this PR audits.
- `docs/architecture/architecture.md:248` — low — forbidden-imports contract described too narrowly as keeping `utils` free of checker and `server` imports; `.importlinter:32-46` also forbids `refactoring`, `utility_tools`, `inspect_library` and `formatter`. Same narrowing at `:138`.
- `docs/architecture/architecture.md:55` — low — "All three checks (pylint, pytest, mypy) must pass" is a residual three-of-N claim.
- Not re-raised, correctly held as deferred: `pyproject.toml:7`, `tests/mcp_tools_py_manual/TEST_PLAN.md:5`, CI "Always" list.

**Decisions**:
- Accept `README.md:114` — a factual error inside the accuracy pass this PR performs, and self-contradicting against two lines the PR itself relies on. Bounded to one table row.
- Accept `architecture.md:248` / `:138` — the narrowed wording was introduced by this PR; an inaccurate new claim in a doc-accuracy change.
- Skip `architecture.md:55` — describes the local dev loop (mirroring `.claude/CLAUDE.md`), not a tool inventory, so it is not the drift this issue targets. Sits with the CI drift the plan deferred to its own issue.

**Changes**:
- `README.md:114-115` — `--log-file` row corrected to the timestamped default; `--console-only` row adjusted so the pair reads coherently.
- `docs/architecture/architecture.md:138, :248` — both statements of the forbidden-imports rule now list the full set from `.importlinter`.
- Checks: pylint clean, mypy clean, pytest 540 passed / 1 skipped.

**Status**: committed

## Round 2 — 2026-09-01

**Findings**:
- `docs/architecture/architecture.md:205` — medium — "All checker tools ... with the shared result formatters on `CheckerTools`" is wrong for 6 of the 9. `CheckerTools` defines three formatters, called only by `pylint_tool.py`, `pytest_tool.py`, `mypy_tool.py`; the rest format via their own package's reporting. Claim newly introduced by this PR when it generalised the accurate "All three tools (pylint, pytest, mypy)".
- `README.md:319` — low — structured-log example shows `"disable_codes": ["C0114", "C0116"]`; `run_pylint_check` accepts no such parameter, and `tests/test_server_params.py:121` asserts it must not.
- Commit `9183fab` — low — commit message is a bare code fence.
- `pr_info/implementation_review_log_2.md` — low — untracked.
- Noted, not raised: `README.md:369, :399` use `python -m src.main` rather than `mcp_tools_py.main`.
- Round 1's two fixes (`d8da8cc`) re-verified as correct and consistent with their surroundings.

**Decisions**:
- Accept `architecture.md:205` — an inaccurate claim this PR introduced, in a section it rewrote. Same over-generalisation that produced the drift the issue targets.
- Accept `README.md:319` — the same stale-parameter drift the PR removed from the pytest table, left standing two sections later. One line.
- Skip commit `9183fab` — the knowledge base says not to clean up commit messages for minor issues.
- Skip the untracked log — committed at the end of this run by design.
- Skip `README.md:369, :399` — pre-existing, in a section this PR did not touch, and not tool-inventory drift; same class as the `CONTRIBUTING.md` exclusion already recorded in the plan.

**Changes**:
- `docs/architecture/architecture.md:205` — shared-formatter claim restricted to pylint, pytest and mypy; the other six noted as formatting via their own package's reporting.
- `README.md:319` — example field replaced with `"max_issues": 1`, a parameter the tool actually accepts.
- Checks: pylint clean, mypy clean, pytest 540 passed / 1 skipped.

**Status**: committed

## Round 3 — 2026-09-01

**Findings**:
- No critical issues.
- `docs/architecture/architecture.md:205` — low — the clause added by `89d142b` ("the other six format through their own package's reporting") is true for only three of the six: `code_checker_vulture`, `code_checker_tach` and `code_checker_lint_imports` have no `reporting.py`. Contradicts `architecture.md:144-145` in the same document. The trailing "the other checkers parse stdout directly" is loose for the same three.
- Everything else in the branch re-verified against source, including both edits in `89d142b`.

**Decisions**:
- Accept — newly introduced by this PR, one clause, and self-contradicting inside a document whose purpose is accuracy. Fixed with wording that refers to the distinction already drawn at `:144-145` rather than re-enumerating packages, so it cannot drift again.

**Changes**:
- `docs/architecture/architecture.md:205` — the six non-shared checkers are now described as returning a string their own package produced, from `reporting.py` or straight from `runners.py` where there is none; trailing clause changed to "work from the command's stdout" (accurate for vulture and tach, which do not parse).
- Checks: pylint clean, mypy clean, pytest 540 passed / 1 skipped.

**Status**: committed

## Round 4 — 2026-09-01

**Findings**: None. Every claim at `architecture.md:205` re-verified against source, including that it now defers to the `:144-145` distinction rather than contradicting it. Searches for residual `8 tools`, `3 tools`, `CodeCheckerServer`, `checker_tools.py`, `planned`, `disable_codes`, `verbosity` and `format_all` across both files return zero hits.

**Decisions**: Nothing to accept.

**Changes**: None.

**Status**: no changes needed — review converged.

## Final Status

Review complete after 4 rounds in this run (7 across both logs). Three commits produced:

| Commit | Change |
|---|---|
| `d8da8cc` | `--log-file` default corrected; forbidden-imports scope widened to match `.importlinter` |
| `89d142b` | shared-formatter claim restricted to pylint/pytest/mypy; non-existent `disable_codes` removed from a README log example |
| `0ea9bcb` | per-checker formatting claim in the runtime view corrected |

Architecture checks run at close: `run_vulture_check` produced no output; `run_lint_imports_check` PASSED, 3 contracts kept, 0 broken.

Scope held throughout: documentation only, `README.md` and `docs/architecture/architecture.md`. No source, test or config file was touched in any round.

Deferred to their own issues, unchanged: `pyproject.toml:7` package description, `tests/mcp_tools_py_manual/TEST_PLAN.md:5`, the CI "Always" job list, `CONTRIBUTING.md`'s missing `tools/*.bat` scripts, and `README.md:369, :399` (`python -m src.main`).

Outstanding: the branch is behind `origin/main` and needs a rebase before a PR is opened.
