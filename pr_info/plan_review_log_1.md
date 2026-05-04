# Plan Review Log 1 — 2026-05-04

Issue: #171
Branch: 171-run-lint-imports-check-hides-failures-return-code-dropped-output-unstructured



## Round 1 — 2026-05-04

**Findings:**
- summary.md §1: deviates from issue's "mirror bandit four-file split" wording; chooses single-file like tach/vulture. Principled but unstated. (minor)
- step_1.md: `MAX_OUTPUT_LINES = 300` redeclared locally instead of imported from pytest. Justified — pytest's OutputBuilder is record-coupled. (minor / acceptable)
- step_1.md: Step 1 commit produces unused package (importlinter wiring lands in step 2). Acceptable TDD-in-isolation but relationship not made explicit. (minor)
- step_2.md `re` import removal: plan said "verify with a search"; verification already done — `re` referenced only by deleted regexes on lines 35-36. (nit)
- step_1.md Tests: Decision #3 fixture taxonomy (clean/broken/warnings/mixed/malformed) not mapped to test classes for reviewer parity. (minor)
- step_2.md Done When: only optional smoke check for `run_lint_imports_check`; original symptom (LLM-visible output) deserves required end-to-end verification. (major)
- step_2.md Done When: missing `run_tach_check` and `run_lint_imports_check` exit checks even though step 2 modifies both `tach.toml` and `.importlinter`. (major)
- step_2.md: missing one-line update to `docs/architecture/architecture.md` to list the new `code_checker_lint_imports` package. (minor — Boy Scout)
- Out-of-scope discipline: plan correctly flags 3 items as out-of-scope. (none)

**Decisions:**
- All 5 recommended changes accepted as straightforward improvements. No design/scope question required user input — deviations from issue wording (single-file split, local MAX_OUTPUT_LINES, raw-body output) are principled and consistent with knowledge base (KISS/YAGNI, planning principles).

**User decisions:** None this round. All changes auto-accepted by supervisor.

**Changes applied** (via `/plan_update`):
- `step_2.md` — `WHERE — files to modify`: added `docs/architecture/architecture.md` Boy-Scout bullet.
- `step_2.md` — `WHAT — checker_tools.py` §3: replaced "verify with a search" with explicit "Verified: re referenced only by deleted regexes on lines 35-36".
- `step_2.md` — `HOW — verification order` step 5 + `Done When`: promoted optional smoke check to required `run_tach_check` and `run_lint_imports_check` (latter must show `=== PASSED ===` first non-empty line).
- `step_1.md` — `Tests`: appended fixture-taxonomy → test-class mapping (clean / broken / warnings / mixed / malformed).
- `summary.md` — Architectural / Design Changes §1: added sentence explaining why single-file matches tach/vulture better than bandit's four-file split.

**Status:** Pending commit (plan files + log committed together).


## Round 2 — 2026-05-04

**Findings:**
- step_1.md `_parse_warnings` regex `r"No matches for ignored import\s+\S.*?\."` with DOTALL: non-greedy `.*?\.` stops at the first period; mis-parses dotted module names like `mcp_coder.mcp_workspace_git -> mcp_workspace.git_operations.` from the issue's reproduction case. (major — parser correctness)
- step_2.md Boy-Scout `docs/architecture/architecture.md` bullet: instruction "list the new package alongside existing entries" too vague — implementer must guess subsection. (minor)
- step_1.md ALGORITHM step 3 combined-output construction: awkward conditional concat of stderr, drops empty-stdout fallback that the original wrapper had. (minor)
- step_2.md `_register_lint_imports` shim docstring/logging changes: acceptable, internal log only. (nit)
- step_2.md smoke check phrasing depends on no flags being passed: holds for the smoke run. (nit)
- All Round 1 fixes verified in place: tach + lint-imports exit checks, re-import verification explicit, fixture taxonomy mapping, single-file deviation rationale.

**Decisions:**
- All 3 recommended changes accepted as straightforward improvements (parser bug fix is a spec correction, not a scope change). No design/scope question for user.

**User decisions:** None this round.

**Changes applied** (via `/plan_update`):
- `step_1.md` `_parse_warnings`: replaced DOTALL pattern with line-anchored `re.MULTILINE` pattern `^No matches for ignored import\s+(?P<src>\S[^\n]*?)\s*->\s*(?P<dst>\S[^\n]*?\.)\s*$`, plus rationale and two-step fallback note.
- `step_1.md` `TestParseWarnings`: fixture spec now mandates a realistic dotted-module example to exercise the regex fix.
- `step_1.md` ALGORITHM step 3: replaced conditional concat with `"\n".join(s for s in (result.stdout, result.stderr) if s)`.
- `step_2.md` Boy-Scout bullet: disambiguated — read file first, prefer existing `code_checker_*` enumeration, else single bullet under §1 Key Features.

**Status:** Pending commit (plan files + log committed together).

## Round 3 — 2026-05-04

**Findings:**
- step_1.md `_parse_warnings`: Round 2's MULTILINE regex still requires `->` and destination on same line, but issue #171 reproduction shows lint-imports wraps the warning across two lines EVEN WITHOUT `--verbose` (`mcp_coder.mcp_workspace_git -> \nmcp_workspace.git_operations.`). Round-2 fix was incomplete. (major — parser correctness regression)
- step_1.md DATA section claims "(no output)" body for empty subprocess output, but `_format_report` rules don't implement that substitution. (minor — spec inconsistency)
- step_1.md HOW imports list omits `import re` and `import logging` despite both being used in the new module. (nit — completeness)
- `_BROKEN_LINE_RE` could in theory match progress chatter containing the word BROKEN; lower priority since `--verbose` is stripped. (nit, no action)

**Decisions:**
- All 3 recommended changes accepted as straightforward improvements. The regex wrap-aware preprocessing is a spec correctness fix, not a scope change. No design/scope question for user.

**User decisions:** None this round.

**Changes applied** (via `/plan_update`):
- `step_1.md` `_WARNING_RE`: replaced conditional fallback with wrap-aware preprocessing as primary spec — line joiner glues `No matches for ignored import ...` lines that don't end with `.` to the next non-blank line, then line-anchored MULTILINE regex matches. Added issue-#171 rationale.
- `step_1.md` `TestParseWarnings`: now mandates both the wrapped fixture (verbatim from issue reproduction) and a single-line variant, both producing `src="mcp_coder.mcp_workspace_git"` / `dst="mcp_workspace.git_operations."`.
- `step_1.md` `_format_report` rules: added empty-/whitespace-only `raw_body` → `(no output)` substitution. Added PASSED-state empty-body fixture to `TestFormatReport`.
- `step_1.md` HOW imports list: added `import re` and `import logging`.

**Status:** Pending commit (plan file + log committed together).


## Round 4 — 2026-05-04

**Findings:**
- All Round 1–3 fixes verified in place across `summary.md`, `step_1.md`, `step_2.md`.
- Wrap-aware `_parse_warnings` joiner spec is consistent: regex rationale, ALGORITHM, and `TestParseWarnings` fixtures (wrapped + single-line) all align and exercise the verbatim issue #171 reproduction.
- `(no output)` substitution flows coherently: rule in `_format_report`, asserted in DATA section, fixture in `TestFormatReport`, end-to-end coverage in `TestRunLintImportsCheckImpl`.
- HOW imports list complete (`import re`, `import logging`).
- Combined-output idiom consistent across spec.
- Step 2 exit checks (`run_tach_check` + `run_lint_imports_check` with `=== PASSED ===` first-line assertion) present.
- Step granularity: 2 steps, each one commit, each tangible. Step 2's atomic bundle (wiring + deletion + `.importlinter` + `tach.toml` + architecture doc) is correctly bundled — splitting would break contracts mid-stream.
- All 13 issue Decisions traceable in the plan.

**Decisions:** No changes needed — plan is internally consistent and addresses all issue requirements.

**User decisions:** None this round.

**Changes applied:** None.

**Status:** No changes — plan stable.

## Final Status

**Rounds run:** 4
**Commits produced:**
- `6c66774` — `docs(plan): tighten lint-imports plan after review round 1`
- `7538ff9` — `docs(plan): fix warning regex spec, polish round 2`
- `f7a64cd` — `docs(plan): handle wrapped warning lines, fix empty-body rule`
- (this commit — Final Status log update)

**Plan ready for approval: YES.**

**Summary of evolution:**
- Round 1 tightened exit checks, added Boy-Scout doc update, mapped fixture taxonomy, made `re`-import verification explicit.
- Round 2 fixed a parser-correctness bug in `_parse_warnings` (DOTALL → MULTILINE), polished doc-update instruction, simplified combined-output idiom.
- Round 3 caught that Round 2's fix didn't handle line-wrapped warnings (issue's actual reproduction shape) — made wrap-aware preprocessing the primary spec; added `(no output)` empty-body substitution; completed imports list.
- Round 4 found no defects — plan stable.

**No design / scope / requirements questions were escalated to the user** — all changes were straightforward improvements applied autonomously per skill guidance.
