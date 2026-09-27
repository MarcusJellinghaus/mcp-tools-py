# Implementation review log 2 — issue #233

Second supervised review run. Run 1 (`implementation_review_log_1.md`) ended after
round 3 with a rebase handoff; the branch now contains `origin/main`, so the review
loop restarts here.

## Round 1 — 2026-09-27
**Findings**:
- `code_checker_lint_imports/runners.py:351` — medium — import-linter's on-disk
  grimp cache (`.import_linter_cache` in the project dir) is now written and read
  by two different grimp installs (tool env vs. whatever runs lint-imports outside
  mcp-tools-py, e.g. CI/pre-commit in the project env), with no version guard —
  only file mtime. Two grimp versions can trust each other's stale cache entries.
- `README.md:148` — low — contract types (`contract_types = name: dotted.path`)
  shipped in a distribution installed only in the project env no longer resolve
  once lint-imports runs from the tool env; README documents version drift as the
  only cost, not this.
- `code_checker_lint_imports/runners.py:116` — low — duplicate `--config` in
  `extra_args` is resolved opposite to lint-imports: the bridge takes the first
  occurrence (`break`), Click takes the last.
- `utils/environment_info.py:104` — low — the `locate` probe's 30s timeout is
  additive to the caller's configured lint-imports timeout; undocumented but
  matches the existing cached one-shot probe's behavior elsewhere.
- `tests/test_checker_tools.py` — low — 710 lines, under the 750-line CI cap but
  little headroom left; was already over the 600-line soft check pre-branch.

**Decisions**:
- grimp cache sharing — **accept**. Directly on point for the issue's own
  rationale (avoid silently reading a stale/wrong result); bounded fix.
- contract-types README gap — **accept**. One sentence, same spirit as the
  version-drift sentence already required by the issue.
- duplicate `--config` precedence — **skip**. Needs a user to pass `--config`
  twice, an unusual invocation; speculative per knowledge-base guidance.
- additive probe timeout — **skip**. Matches an existing pattern elsewhere in the
  codebase (the cached one-shot probe); not a regression introduced here.
- test file line count — **skip**. Pre-existing, still under the CI cap.

**Changes**:
- `runners.py` — new `_ensure_no_cache(extra_args)` appends `--no-cache` to the
  constructed lint-imports command unless the caller already controls caching
  (`--no-cache`, `--cache-dir X` or `--cache-dir=X`). `--no-cache` is a real
  import-linter flag; `_combine_caching_arguments` turns it into `cache_dir=None`,
  which `grimp.build_graph` reads as caching disabled. Chosen over scoping
  `--cache-dir` per interpreter: a per-call subprocess gains nothing from cache
  reuse, and a private cache directory would still need managing.
- `test_runners.py` — unit tests for `_ensure_no_cache` (append, empty, no
  duplicate, both `--cache-dir` spellings) plus two on
  `run_lint_imports_check_impl` asserting the default command carries
  `--no-cache` and a caller-supplied `--cache-dir` is left alone; the existing
  exact-command-list test updated.
- `README.md` — one sentence: a `contract_types` entry inside the root package
  still resolves through the bridge, one in a distribution installed only in the
  project env does not.
**Status**: committed (`376a516`); CI passed, branch up to date with `main`

## Round 2 — 2026-09-27
**Findings**:
- `runners.py:383` — medium — round 1's `--no-cache` rests on a wrong premise
  ("a per-call subprocess gains nothing from cache reuse"): grimp's cache is
  on disk in the project directory, so successive MCP calls did reuse it. The
  correctness guard is right, but it costs a real speedup that a tool-env-scoped
  `--cache-dir` would keep. Versus `main` — where lint-imports ran from the
  project env against one coherent grimp — this is a performance regression.
- `runners.py:160` — medium — `_pythonpath_env` prepends the located directory to
  the PYTHONPATH of the *tool env's* interpreter, so a top-level module there
  shadows mcp-tools-py's own dependencies at interpreter startup (probe-verified
  with a stray `grimp.py`). For a flat-layout project the located directory is the
  repo root.
- `tool_context.py:122` — low — the new message says "reinstall and restart the
  server" although `is_tool_available` re-checks the binary every call.
- `README.md:205` — low — the "After installing missing tools" bullet lost its
  console-script half, so nothing states that these tools need no restart.
- `tool_context.py:5` — low — module docstring still describes "the target
  environment", singular, now that console-script answers come from
  `tool_environment`.
- `test_bridge_integration.py:130,155` — low — the only unmocked end-to-end tests
  pass `extra_args=["--no-cache"]`, which suppresses `_ensure_no_cache`, so the
  command the server actually constructs is never exercised for real.

**Decisions**:
- grimp cache tradeoff — **accept**. A regression against `main` deserves better
  than a wrong rationale; prefer a `--cache-dir` scoped so a different grimp
  cannot read it, keeping both correctness and reuse. `--no-cache` may stand if
  scoping cannot be made robust, with the rationale corrected either way.
- PYTHONPATH shadowing — **accept**. Skip the prepend when the located directory
  is already the subprocess's cwd (the flat-layout case lint-imports' own
  `sys.path.insert(0, os.getcwd())` covers), which removes the risky entry with
  no loss of bridging.
- "restart the server" wording — **skip**. The issue's decision table specifies
  this wording explicitly, and advising a restart after reinstalling the server's
  own package is sound regardless of the per-call re-check.
- README restart bullet — **skip**. Same reason; the issue's Affected list names
  the `:204` "no restart needed" line for removal, and with the wording above kept
  the README is self-consistent.
- stale module docstring — **accept**. Same class as the attribute docstring fixed
  in run 1 round 2; one line.
- integration tests suppressing `_ensure_no_cache` — **accept**. Trivial, and it
  makes the only real end-to-end test cover the constructed command.

**Changes**:
- `runners.py` — `_ensure_no_cache` replaced by `_cache_scope()` / `_scope_cache()`:
  the command now carries `--cache-dir .import_linter_cache/grimp-<version>-py<X.Y>`,
  so a different grimp build simply misses the cache instead of trusting it, and
  reuse is preserved. `--no-cache` remains only as the fallback when grimp's
  version cannot be read (no key means no safe scope). All three premises were
  verified rather than assumed: `importlib.metadata.version("grimp")` resolves
  without importing grimp, grimp's `FileSystem.write` creates nested cache
  directories, and grimp writes its own `.gitignore` (`*`) inside the cache
  directory, so the new path is ignored even in projects lacking a rule for it.
- `runners.py` — new `_without_cwd()` drops a located directory whose resolved
  path equals the resolved project dir (lint-imports inserts its own cwd on
  `sys.path`), with `_cwd_info_line()` reporting it so the reader still sees why
  nothing was prepended; the "cannot import X" line is now guarded by
  `not usable and not in_cwd` so a cwd-resolved package is not reported as
  unimportable. Premise verified in code (`execute_command(..., cwd=project_dir)`
  and `lint_imports`' `sys.path.insert(0, os.getcwd())`) plus a probe.
- `tool_context.py` — module docstring describes both environments and which
  tools each answers for.
- `test_runners.py`, `test_pythonpath_bridge.py` — tests for the cache scoping and
  the cwd skip, including a src-layout case where the repo root and a `src` tree
  are located together and only `src` reaches PYTHONPATH.
- `test_bridge_integration.py` — explicit `--no-cache` dropped, so the end-to-end
  tests run the command the server actually constructs.
- `README.md` — one sentence on the versioned cache directory, since it is a new
  directory appearing in the user's project.
**Status**: committed (`2e279c7`)

## Round 3 — 2026-09-27
**Findings**:
- `runners.py:77` (also `:431`, `README.md:148`, commit `2e279c7`'s message) —
  medium — the premise rounds 1 and 2 built on is inaccurate: grimp *does*
  version-guard its cache. `Cache._read_data_map_file` catches
  `rust.CacheVersionMismatch` and rebuilds, the data file carries
  `"version": 2`, and a meta-file (mtime) hit without a data-file hit raises
  `CacheMiss`. A cross-version read therefore cannot produce a wrong verdict
  unless two grimp *releases* share one cache format version — far narrower than
  "validated by file mtime only, with no version guard".
- `runners.py:64` — low — `importlib.metadata.version("grimp")` reads an
  undeclared transitive dependency (`pyproject.toml` declares only
  `import-linter>=2.0`), and the `None` path degrades silently to `--no-cache`
  with nothing logged and no info line.
- `runners.py:69` — low — per-version cache directories accumulate in the user's
  project; after a grimp or Python upgrade the previous full import graph is never
  read or pruned.
- `runners.py:50` — low — `_cache_scope`'s summary claims a directory "only this
  grimp build can read"; the name is a label, not an enforcement.
- `test_runners.py:96,100,473,486` — low — the expected value is `_cache_scope()`
  itself, so four assertions are tautological; only
  `test_names_grimp_and_python_version_under_the_conventional_root` constrains
  the shape.
- `test_server_params.py:819` — low — `test_lint_imports_warning_reads_the_tool_env`
  asserts only the absence of warnings, so deleting `_warn_missing_console_scripts`
  entirely would still pass it; it also asserts about `tach`, which its name does
  not cover.

**Decisions**:
- grimp cache premise — **escalated to the user, who chose to revert.** The
  mechanism added in rounds 1 and 2 rested on an overstated risk. grimp already
  version-guards its own cache, so the residual exposure is only two grimp
  releases sharing one cache format version and differing in import parsing —
  accepted deliberately, rather than paying for it with per-version cache
  directories accumulating full import graphs in the user's project and a read of
  an undeclared transitive dependency. Reverting to import-linter's default cache
  behaviour also resolves findings 2–5, which all concerned that mechanism.
- `test_server_params.py:819` — **accept**. A test that would pass with the
  function under test deleted is not carrying its weight; strengthen it so the
  call is proven to have run, and align its name with what it asserts.

**Changes** (4 files, +21 / −171 — a net deletion):
- `runners.py` — `_cache_scope()`, `_scope_cache()`, the `_CACHE_FLAGS`/`_CACHE_ROOT`
  constants and the `importlib.metadata`/`sys` imports deleted. The command is
  `[lint_imports_binary] + cleaned_args` again, so no cache flag is injected and a
  caller's `--cache-dir`/`--no-cache` passes straight through. The docstring now
  states accurately that caching is import-linter's default and that grimp guards
  its own cache through the data file's format version.
- `README.md` — round 2's versioned-cache-directory sentence dropped; round 1's
  `contract_types` sentence untouched.
- `test_runners.py` — `TestCacheScope`, `TestScopeCache` (including the four
  tautological assertions) and the two `run_lint_imports_check_impl` cache tests
  removed; `test_command_construction_uses_cleaned_args` remains as the
  pass-through assertion.
- `test_server_params.py` — `test_lint_imports_warning_reads_the_tool_env` →
  `test_warnings_read_the_tool_env_not_the_project_env`. Decision 5's asymmetry is
  preserved, but the tool env now holds *only* `lint-imports`, so tach's warning
  is a positive control proving the loop ran, which is what makes the silence
  about lint-imports meaningful. Deleting `_warn_missing_console_scripts` now
  fails the test, and the `tach` assertion matches the name.
- Cache leakage checked: the integration tests' default `.import_linter_cache`
  lands under pytest's `tmp_path` and dies with it; the repo's own is gitignored.
**Status**: committed (`79ac3df`)

## Round 4 — 2026-09-27
The revert commit `79ac3df` was checked for dangling remains and none were found:
no references to the removed helpers or constants anywhere outside the `pr_info/`
logs, the dropped imports are genuinely unused, command construction is still
covered by `test_command_construction_uses_cleaned_args`, and the strengthened
startup-warning test's asymmetry is real.

**Findings**:
- `probe.py:47` (`_parents`) — low — for a dotted root package whose parent is a
  PEP 420 namespace (`ns.pkg`, which grimp's `ImportLibPackageFinder` permits),
  `os.path.dirname` of the submodule search location yields `…/ns` rather than the
  directory containing `ns`. The bridged PYTHONPATH entry then cannot import the
  package, and because that directory is not a site dir it lands in `usable`, so
  no info line is emitted and lint-imports may silently answer from an installed
  copy.
- `runners.py:365-369` — low — the docstring spends five lines describing
  behaviour the function no longer has; the rationale already lives in `79ac3df`'s
  commit message.

**Decisions**:
- dotted root package in `_parents` — **accept**. This is a functional gap, not
  speculation: for a legal config the bridge produces a path that cannot import
  the package, and it fails silently into exactly the stale-copy PASSED the
  feature exists to prevent. The fix is bounded (strip one path component per dot,
  plus one) and testable.
- over-long docstring — **accept**. The repo's own writing rule says to delete
  what isn't load-bearing; keep at most the sentence that a caller's
  `--cache-dir`/`--no-cache` passes through.

**Changes**:
- Premise verified three ways before coding: import-linter never validates
  dotted-ness (`_build_from_config` passes the value through, `_normalize_user_options`
  only wraps it), grimp's `_has_a_non_namespace_parent` returns False when the
  parent spec has no location so `NotATopLevelModule` fires only for a
  non-namespace parent, and a scratch probe confirmed end to end that
  `PYTHONPATH=<root>/ns` raises `ModuleNotFoundError` while `PYTHONPATH=<root>`
  resolves `ns.pkg`.
- `probe.py` — new `_importable_from(path, name)` strips one path component per
  dot plus one; `_parents` uses it for both branches. The same arithmetic is
  correct for a module, whose file is the extra component. (Round 5 corrected this
  entry: a degenerate over-strip returns `""` only for a relative path; an
  absolute one bottoms out at the filesystem root, which is truthy and would pass
  `_locate`'s `if parent` filter. The case is unreachable — a filesystem-based
  `ModuleSpec`'s path always has at least `name.count(".") + 1` components below
  its `sys.path` entry — so the code is correct and only this rationale was off.)
- `tests/test_environment_info.py` — `test_real_child_locates_a_dotted_name_from_its_root`
  builds a namespace tree, runs the real `probe.py locate ns.pkg`, and asserts the
  reported directory is the root rather than `…/ns`. It fails against the old
  `dirname`.
- `runners.py` — cache paragraph trimmed to its one load-bearing sentence.
**Status**: committed (`5fe8b82`)

## Round 5 — 2026-09-27
**Findings**: no defects. The new path arithmetic was probed against all five cases
(top-level package, dotted package, plain module, dotted module, deeper dotted) and
is correct in each; multi-location namespace packages are correct too, since the
strip count depends only on `spec.name`, and using `spec.name` rather than the
requested name is the more robust choice for an aliased name such as `os.path`.
Two optional notes: the log's "degenerate over-strip returns `\"\"`" rationale holds
only for relative paths (corrected above; the case is unreachable and the code is
correct), and the `spec.origin`-with-a-dot branch has no test of its own.

**Decisions**: both notes **skipped**. The first is a record inaccuracy, not a code
defect, and is fixed in this log rather than in code. The second is a corner of a
shared helper whose arithmetic is already pinned by a real-subprocess test —
"cover the contract, not every corner" — and is not worth restarting the review
loop for. The reviewer's own judgment agreed that neither warranted a fix round.
**Changes**: none (log correction only)
**Status**: no changes needed — loop converged

## Final Status

Five rounds run. Rounds 1–4 produced fixes (four commits); round 5 found no
defects, ending the loop.

**Commits produced by this run**

| Commit | Round | Subject |
|--------|-------|---------|
| `376a516` | 1 | `fix(lint-imports): disable grimp's cache on the tool-env subprocess` |
| `2e279c7` | 2 | `fix(lint-imports): scope grimp's cache per version, keep the repo root off PYTHONPATH` |
| `79ac3df` | 3 | `revert(lint-imports): stop injecting cache flags, grimp guards its own cache` |
| `5fe8b82` | 4 | `fix(probe): locate a dotted root package from its importable root` |

Rounds 1–3 are one arc: a cache concern was raised, acted on twice, then found to
rest on an overstated premise and reverted by the user's decision. The net effect
of the three on the shipped code is nil — `79ac3df` restores import-linter's
default cache behaviour — but the arc is left in history rather than squashed,
because the accepted residual risk is a real decision worth being able to find.
Round 4's dotted-root-package fix and round 2's PYTHONPATH cwd fix are the two
substantive improvements that survive.

**Final checks (supervisor-run)**

- `run_vulture_check` — no output.
- `run_lint_imports_check` — PASSED, 4 contracts kept, 0 broken (Layered
  Architecture; Forbidden external imports; mcp_coder_utils imports only via
  shims; target_scripts import nothing from the project). No architectural
  violations, so nothing to escalate.

**Open items**: none. No finding was left unresolved; every skipped item is
recorded above with its reason.

