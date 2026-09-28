# Implementation review log 3 — issue #233

Third supervised review run. Run 2 (`implementation_review_log_2.md`) converged after
five rounds; this run restarts the loop against the current branch tip.

## Round 1 — 2026-09-28
**Findings**:
- `code_checker_lint_imports/runners.py:394-401` — medium — with a multi-`root_packages`
  config, a root package the project interpreter cannot locate at all is dropped
  silently whenever another package did resolve: `locate_packages` returns `usable`
  as a flat list, and the `elif not usable and not in_cwd` branch only fires when
  nothing resolved. lint-imports then builds that package's graph from whatever copy
  sits in the tool env's site-packages and reports PASSED on stale code — the silent
  stale read this feature exists to prevent.
- `utils/target_scripts/probe.py:102-131` — low — `_site_dirs()` omits
  `site.getusersitepackages()`, so a project package installed with `pip install
  --user` is classified `usable` and a whole site-packages tree is prepended to the
  tool-env subprocess's `PYTHONPATH`, ahead of the tool env's own `grimp` (compiled
  extension) and `click` — the outcome the issue's rationale rules out explicitly.
- `runners.py:391` — low — `locate_packages`' non-timeout reason already begins
  "could not locate \<names\> in \<interpreter\>", so the ERROR line repeats the
  phrase and the name list.
- `docs/architecture/architecture.md:172` — low — the `environment_info.py` bullet
  describes only the cached one-shot probe and omits `locate_packages`, though the
  adjacent `probe.py` bullet was updated for `locate`.
- `utils/environment_info.py:53` — low — narrowing `TOOL_DISTRIBUTIONS` to the
  `python -m` tools removed the only place ruff/bandit/vulture/tach/import-linter
  versions were logged, and nothing logs the tool env's versions that now run.

**Decisions**:
- unresolved root package unreported — **accept**. A functional gap in the feature's
  core guarantee, not speculation; bounded and testable.
- user site-packages — **accept**. Narrow (non-venv installs are unsupported), but
  the consequence is the grimp shadowing the issue rules out by name, and the fix is
  one guarded line.
- duplicated ERROR phrase — **accept**. Trivial, and it is a user-facing message.
- architecture.md bullet — **accept**. One line; the adjacent bullet was updated.
- tool-env version logging — **skip**. The issue's decision table settles this:
  version drift is documented, not detected. Adding version logging is new scope.

**Changes**:
- `environment_info.py` — `locate_packages` returns `(usable, skipped, unresolved)`;
  a requested name with no directory behind it lands in `unresolved` instead of
  vanishing.
- `runners.py` — new `_unresolved_info_line`, emitted unconditionally rather than
  behind "nothing resolved", so the site-skip line and the unresolved line can both
  appear. A package resolving to lint-imports' own cwd still counts as resolved, so
  the flat-layout case keeps `_cwd_info_line` and raises no false warning. The
  non-timeout probe reason became "probe of \<interpreter\> failed: ...", so the
  caller's ERROR line reads once for all three reasons.
- `probe.py` — `_site_dirs()` also appends `site.getusersitepackages()` in its own
  try/except, stdlib-only.
- `docs/architecture/architecture.md` — the `environment_info.py` bullet names
  `locate_packages`, its three-way split and that it is uncached.
- Tests — `locate_packages`-level and report-level cases for both mixed
  resolved/unresolved shapes, a real-subprocess test that the user site directory is
  reported, and the failure test parametrized over timeout/failure/unparsable
  asserting the package name appears exactly once.
**Status**: committed (`7b31243`)

## Round 2 — 2026-09-28
No correctness defects. `lint-imports` was run through the new bridge on this repo and
read the working tree (4 contracts, 106 files), both bridge integration tests pass for
real, and `_CONFIG_CANDIDATES` plus the `.toml`→TOML / else→INI `--config` dispatch were
checked against the installed import-linter and match, `root_packages` winning over
`root_package`. The step-1 lint-imports carve-out is deleted from all three sites.

**Findings** (all low, all wording in `7b31243`):
- `runners.py:231` — `_unresolved_info_line` opens "nothing added to PYTHONPATH", but
  after `7b31243` it fires alongside a successful bridge, so in the mixed case a
  directory *was* added and the line contradicts what happened. The new test asserts
  the prefix, baking it in; sibling `_skipped_info_line` already says "not added".
- `probe.py:104-130` — the rationale given for the new `site.getusersitepackages()`
  entry is unreachable for this caller: `execute_command` classifies the probe as a
  Python command, so `prepare_env` applies `get_python_isolation_env()`, setting
  `PYTHONNOUSERSITE=1`; the child reports `site.ENABLE_USER_SITE == False`, so a
  `--user`-installed package lands in `unresolved`, never `usable`.
- `environment_info.py:105-109` — the guarantee "every requested name appears in
  `skipped` or `unresolved`, or contributed a directory to `usable`" overpromises: two
  names resolving to the same parent directory means the second contributes nothing,
  because of the `directory not in usable` de-dup. Behaviour is correct; the wording
  is absolute where it isn't.
- Nit — `_site_dirs()` de-duplicates by raw string comparison while the `roots` check
  below normalizes via `_normalized`.

**Decisions**:
- unresolved info line wording — **accept**. A user-facing report line that states
  something untrue about what just happened, with a test pinning it.
- probe.py rationale — **accept**. Keep the guard as defence in depth (a caller that
  does not isolate can run the probe), but a comment must not claim a scenario that
  cannot occur. Note this narrows round 1's finding 2: the guard is insurance, not a
  fix for a reachable bug.
- `locate_packages` docstring guarantee — **accept**. One line.
- `_site_dirs()` de-dup spelling — **skip**. No functional effect; the consumer only
  does containment tests.

**Changes**:
- `runners.py` — `_unresolved_info_line` opens "[Info: not added to PYTHONPATH, the
  project interpreter cannot import ...", matching `_skipped_info_line` and true in
  the mixed case. Three test assertions used the old prefix, not the one the review
  named; all three updated, and the longer prefix keeps them distinguishable from the
  site-packages line.
- `probe.py` — the premise was probe-verified first (the child reports
  `site.ENABLE_USER_SITE == False` and no user site directory on `sys.path`). The
  guard stays, its docstring now presenting it as defence in depth for a caller that
  does not isolate the user site.
- `environment_info.py` — the guarantee reads "accounted for", noting that two names
  sharing a parent directory contribute that directory once.
**Status**: committed (`7080c9e`)

## Round 3 — 2026-09-28
No critical issues. The load-bearing pieces of `7b31243`/`7080c9e` were re-verified:
`locate_packages` accounts for every requested name and `skipped`/`unresolved` are
mutually exclusive; `prepare_env` starts from `os.environ.copy()` and applies the
caller's `env` last, so `_pythonpath_env`'s prepend survives; `lint_imports_binary` is
not classified as a Python command, so the isolation env never competes with it; the
new user-site entry cannot misclassify a normal source tree.

**Findings**:
- `runners.py:411-424` (line reached via `_unresolved_info_line`, `:228`) — low — a
  flat-layout project that is not installed in the project env gets "[Info: not added
  to PYTHONPATH, the project interpreter cannot import X — lint-imports may be reading
  an installed copy of X]" on every run. `locate_packages` runs `probe.py` by absolute
  path, so the child's `sys.path[0]` is the probe's directory and the project dir is
  never on `sys.path`; a package present only as a directory there comes back
  `unresolved` (probe-verified). But lint-imports' own `sys.path.insert(0, os.getcwd())`
  resolves it correctly — the case issue #233 explicitly calls covered.
  `_without_cwd`/`_cwd_info_line` handle the resolved-to-cwd variant, not this one.

**Decisions**:
- flat-layout false alarm — **accept**. Evidence-backed, and re-raised legitimately:
  log 1 round 3 saw it but that round was voided by a rebase handoff, so it was never
  triaged on merit. Behaviour is correct and only the report text overstates the risk,
  but a warning that exists to flag a genuine stale read loses its value if it fires
  when there is none. Fix is bounded and testable.

**Changes**:
- Premise probe-verified first: a package existing only as a directory in a project dir
  does come back `unresolved`, because the probe runs by absolute path.
- `runners.py` — new `_provided_by_cwd(names, project_dir)` splits `unresolved` into
  names findable nowhere and names the project directory itself provides
  (`<project_dir>/<parts…>/<last>` as a directory, or `<last>.py` as a file), walking a
  dotted name along its components to match `probe.py`'s `_importable_from`. The
  cwd-provided names reuse the existing `in_cwd`/`_cwd_info_line` mechanism —
  `project_dir` is appended to `in_cwd` only when `_without_cwd` did not already
  contribute it — so the report carries one "already lint-imports' working directory"
  line instead of a false "cannot import" warning. No new info line, no parallel
  mechanism.
- `test_pythonpath_bridge.py` — four tests: flat-layout package in the project dir, the
  dotted `ns.pkg` variant, a single-module `pkg.py` variant, and a name absent
  everywhere still getting the unresolved line and no cwd line.
**Status**: committed (`c786722`)

## Round 4 — 2026-09-28
No critical issues. `c786722` was scrutinised on every axis and found sound: the dotted
walk `*parents, last = name.split(".")` is the correct inverse of `probe.py`'s
`_importable_from` (which strips `name.count(".") + 1` components); `if cwd_names and
not in_cwd` cannot double-count, since `_without_cwd` only puts a directory in `in_cwd`
when it resolves to `project_dir`; and the cwd claim is true — `importlinter.cli`'s
`sys.path.insert(0, os.getcwd())` entry was probe-confirmed to win over a `PYTHONPATH`
copy of the same package.

**Findings**:
- `runners.py:222-240` (`_skipped_info_line`) — low — the false alarm `c786722` fixed
  for `unresolved` survives for `skipped`. A flat-layout project installed
  **non-editably** into the project env resolves its root package to that env's
  `site-packages`, so the name lands in `skipped` and the report says lint-imports may
  be reading an installed copy — but `<project_dir>/pkg` is on `sys.path[0]` and wins,
  by the same probe-verified premise that justified `c786722`. The editable variant
  resolves to the project root and `_without_cwd` already covers it, which is why the
  gap shows only in the non-editable case.
- `runners.py:203-213` (`_cwd_info_line`) — nit — the `Args` still say "Located
  directories equal to the project directory", but `run_lint_imports_check_impl` now
  also passes `project_dir` itself, which was never located.

**Decisions**:
- `skipped` false alarm — **accept**. This is the symmetric half of the round 3 fix;
  leaving the warning accurate for one resolution path and false for the other is worse
  than either state, and the fix reuses `_provided_by_cwd` unchanged.
- `_cwd_info_line` docstring — **accept**. One line, in code the previous commit
  touched.

**Changes**:
- Premise re-verified by probe first: a subprocess doing `sys.path.insert(0, os.getcwd())`
  imports the working-tree copy over a rival on `PYTHONPATH`, and since `PYTHONPATH`
  precedes site-packages, beating it beats a site-packages copy too.
  `importlinter.cli.lint_imports` does that insert as its first statement.
- `runners.py` — `run_lint_imports_check_impl` runs `skipped`'s names through
  `_provided_by_cwd` as well, keeping only names the project directory does not provide
  in `skipped` and folding the rest into `cwd_names`. A name genuinely only in
  site-packages keeps its warning. No new info line; `_provided_by_cwd` is unchanged
  apart from its docstring, whose first return element is renamed `unresolved` →
  `elsewhere` now that it serves both callers.
- `runners.py` — `_cwd_info_line`'s summary and `Args` describe what the directories
  actually are: those lint-imports imports from without a bridge, including the project
  directory itself when it provides a name that was not located there.
- `test_pythonpath_bridge.py` — the non-editable flat-layout case, and a mixed
  two-package config where only the site-packages-only name is warned about.
**Status**: committed (`36e6b9a`)

## Round 5 — 2026-09-28
No critical issues. The report logic was verified coherent as a whole now that three
paths can feed `cwd_names`: no name is dropped (every one lands in `skipped`, in
`unresolved`, or is covered by a `usable` directory, and each half ends in an info line
or a bridged entry); none is double-warned (`skipped` and `unresolved` are mutually
exclusive by the `continue` in `locate_packages`, and a name legitimately in both
`skipped` and `usable` is a multi-portion namespace package, where one portion is
bridged and the other warned about — both statements true); no duplicate cwd entry; and
every info line's text holds in each combination enumerated.

**Findings**:
- `runners.py:209` — low — `_provided_by_cwd`'s `(base / last).is_dir()` accepts a
  directory with no `__init__.py`, but such a directory is only a namespace *portion*:
  probe-verified, with `sys.path = [cwd, site]`, `cwd/pkg/` without `__init__.py` plus
  `site/pkg/__init__.py` imports the **site** copy, because the finder records the
  portion and keeps scanning until a regular package wins. So for that shape the
  warning is suppressed while lint-imports really does read the installed copy — a
  silent stale read. Narrow (it needs a project-dir directory colliding with a root
  package name), but it fails towards false silence rather than a false warning. The new
  `test_skipped_package_present_in_the_project_dir_is_not_warned_about` fixture uses
  exactly that shape, so it pins the suppression where suppression is wrong.
- `_cwd_info_line` — nit — says "the package" singular and names only directories, so
  with several root packages a reader cannot tell which package the line covers.

**Decisions**:
- namespace-portion suppression — **accept**. The failure direction is what decides it:
  every other inaccuracy this run was a false warning, which a reader can discount,
  whereas this is silence about the exact stale read the feature exists to prevent. The
  two callers need opposite treatment — a name from `skipped` has an installed regular
  package that beats a bare portion, so its warning must stay; a name from `unresolved`
  has no copy in that env to lose to, so suppression stays correct.
- `_cwd_info_line` singular wording — **skip**. Naming the packages means threading them
  into a helper that deliberately takes directories; cosmetic, and the reviewer agreed
  it is not worth a commit.

**Changes**:
- Premise re-probed first: with `sys.path = [cwd, site]`, a bare `cwd/pkg/` plus
  `site/pkg/__init__.py` imports the site copy; `cwd/pkg/__init__.py` or `cwd/pkg.py`
  wins; a bare `cwd/pkg/` alone resolves as a namespace package.
- `runners.py` — `_provided_by_cwd` returns `(elsewhere, provided, portion)`: `provided`
  requires `__init__.py` or a `.py` module, a directory without `__init__.py` lands in
  `portion`. The two callers now differ: for `unresolved`, portions still count as
  project-dir-provided (nothing installed can outrank them); for `skipped`, portions stay
  in the warning set, since the installed regular package is what lint-imports reads.
  Filtering `skipped` by a set of warned names keeps its original key order.
- `test_pythonpath_bridge.py` — two `skipped`-case fixtures gained the `__init__.py` their
  docstrings mean, plus
  `test_skipped_package_shadowed_only_by_a_bare_directory_is_warned_about`. The two
  `unresolved` tests using a bare directory stay as they are and now cover the
  unresolved-portion branch, where suppression is correct.
**Status**: committed (`99f6e74`)

## Round 6 — 2026-09-28
No critical issues. `99f6e74`'s mechanics were re-probed end to end in all four shapes
(bare cwd dir loses to a regular package later on the path; a bare dir alone resolves as
a namespace; `cwd/pkg/__init__.py` wins; bare `cwd/a/` plus `cwd/a/b/__init__.py` raises
`ImportError` when a regular `a` sits later). The `skipped` filter is a pure subtraction
of `skipped_in_cwd` and preserves key order; `installed` and `skipped_portions` cannot
overlap.

**Findings**:
- `runners.py:467-476` — low, comment accuracy only — both comments added by `99f6e74`
  reason about the wrong `sys.path`. lint-imports runs the **tool env's** binary with
  `PYTHONPATH` = `usable` only, so the project interpreter's site-packages — the source
  of every `skipped` entry — is never on the subprocess's path, and the tool env's
  site-packages was never probed. So "nothing installed can outrank a namespace portion
  when the project interpreter found the name nowhere" does not follow (a regular package
  of that name in the tool env would outrank it, making the suppression unverified rather
  than provably safe), and a `skipped` name's installed copy is not what lint-imports
  reads unless the two envs coincide — the kept warning is hedged, so the direction is
  still the safe one, but not for the stated reason.
- `_provided_by_cwd` checks `__init__.py` only on the last component, so `a.b` with a
  bare `a/` is classified as provided. Probed: that shape raises `ImportError` when
  something else supplies `a` — loud, not silent.

**Decisions**:
- comment accuracy — **accept**, comments only, no behaviour change. The reviewer judged
  it optional, but a comment asserting a safety proof that does not hold is worse than no
  comment, and the repo's writing rule is to delete what is not load-bearing. Exposure in
  either direction needs a root-package name matching a bare project-dir directory *and*
  a copy of that name in the tool env, which is vanishingly rare.
- `a.b` with a bare `a/` — **skip**. The failure is an `ImportError`, i.e. loud; per the
  knowledge base, cover the contract, not every corner.

**Changes**:
- `runners.py` — the two comments now say that the tool env lint-imports imports from is
  never probed, so neither branch is provable; an unresolved portion is taken as read
  from the working tree to avoid warning about every flat-layout namespace directory,
  while a `skipped` portion keeps its hedged warning because something is known to be
  installed under that name. The residual exposure is noted once rather than per branch.
  No code or test touched.
**Status**: committed (`6d0f101`)

Note: this commit carries no `Co-Authored-By`/`Claude-Session` trailers — the commit agent
applied CLAUDE.md's "No attribution footers" rule, which overrides the session default.
Rounds 1–5's commits (`7b31243`, `7080c9e`, `c786722`, `36e6b9a`, `99f6e74`) do carry
them, from supervisor instructions that should have followed the same rule. Left as is
rather than rewriting pushed history; Marcus's call.

## Round 7 — 2026-09-28
**Findings**: no defects. `6d0f101` was confirmed comment-only (no statement, expression,
signature or docstring changed), and all four claims in the new comment text were checked
against the code they sit on and hold. Both comments are load-bearing: the asymmetry
between the two adjacent branches is otherwise unexplained, and the previous wording was
factually wrong. Whole-branch pass: 767 tests, mypy, ruff, vulture and lint-imports all
clean; no scratch directory, no debug code, no new TODO/FIXME; README and
`docs/architecture/architecture.md` consistent with the two-environment split.
**Decisions**: none needed.
**Changes**: none
**Status**: no changes needed — loop converged

## Final Status

Seven rounds run. Rounds 1–6 each produced one fix, each narrower than the last; round 7
found no defects, ending the loop.

**Commits produced by this run**

| Commit | Round | Subject |
|--------|-------|---------|
| `7b31243` | 1 | `fix(lint-imports): report a root package the project interpreter cannot locate` |
| `7080c9e` | 2 | `docs(lint-imports): correct three wording claims from 7b31243` |
| `c786722` | 3 | `fix(lint-imports): don't warn about a root package the project dir provides` |
| `36e6b9a` | 4 | `fix(lint-imports): don't warn about a non-editable install of the project dir` |
| `99f6e74` | 5 | `fix(lint-imports): keep the warning when a bare directory shadows an install` |
| `6d0f101` | 6 | `docs(lint-imports): fix the sys.path reasoning in two portion comments` |

Rounds 1 and 5 are the substantive ones: round 1 closed the last case where a root package
could go unreported and let lint-imports answer from a stale installed copy, and round 5
closed the same failure re-introduced by rounds 3–4's warning suppression, where a bare
directory counts only as a namespace portion. Rounds 3 and 4 removed false warnings (the
flat-layout and non-editable-install cases the issue itself calls covered); rounds 2 and 6
corrected claims the code made about itself. The arc is one theme throughout: the report's
info lines must be true in every resolution path, because a false silence there is exactly
the stale read this feature exists to prevent.

**Final checks (supervisor-run)**

- `run_vulture_check` — no output.
- `run_lint_imports_check` — PASSED, 4 contracts kept, 0 broken (Layered Architecture;
  Forbidden external imports; mcp_coder_utils imports only via shims; target_scripts
  import nothing from the project). 106 files, 353 dependencies. No architectural
  violations, so nothing to escalate.

**Open items**: none. Every skipped finding is recorded above with its reason.
