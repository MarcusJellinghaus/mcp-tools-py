# review-implementation review log 2

Issue #225 — mypy: let `[tool.mypy]` own the flag set

Continues from [implementation_review_log_1.md](./implementation_review_log_1.md), which ended
at round 3 with a rebase handoff rather than a clean round.

## Round 1 — 2026-09-04

**Findings**

- `code_checker_mypy/runners.py:61-69` — medium — `_resolve_cache_dir` ignores `MYPY_CACHE_DIR`, which mypy reads (`main.py:1463-1467`) three lines above the `MYPY_NUM_WORKERS` block this PR deliberately pops, so the timeout report can name a path mypy never wrote and mark it certain.
- `code_checker_mypy/runners.py:61-64` — low — a config `cache_dir` containing `~` or `$VAR` is joined literally, though mypy runs it through `expand_path`.
- `docs/pyproject-configuration.md:183/192/205` — low — three statements about `--cache-dir` that disagree; round 2 of log 1 asked for this fix and only half of it landed.
- `pr_info/steps/step_2.md:38-40,80` — low — the plan's `_resolve_cache_dir` signature and the literal failure prefix no longer match the implementation.
- `tests/test_error_transparency.py:224-238` — low — `test_timeout_reported_as_timeout` passes `project_dir="."`, so it now recursively walks the developer's real `.mypy_cache`.

**Decisions**

- Accept the `MYPY_CACHE_DIR` gap: same ambient-environment class as the hole this PR closed, and it defeats step 2's own rule against confident-but-wrong statements.
- Accept the expansion bug and the docs contradiction: both are one-place corrections inside code and prose this change already owns.
- Accept the test fix: a test's runtime should not depend on state outside it.
- Skip the stale `step_2.md` signature. `pr_info/` is deleted at the end of the process and is background material; tracking implementation drift there is not work.

**Changes**

`_resolve_cache_dir` gained the `MYPY_CACHE_DIR` layer in mypy's precedence position and a `_expand_config_cache_dir` helper. A scratch probe against mypy 2.3.1 established that expansion is *not* uniform by source — argument verbatim, environment `expanduser` only, config `expandvars` + `expanduser` — so the resolver mirrors that asymmetry rather than normalising it. The docs section states the `--cache-dir` effect once. The timeout test runs against a `tmp_path` project, and `TestMypyTimeoutMessage` clears `MYPY_CACHE_DIR` so an ambient value cannot override the configs those tests write. Five new tests cover precedence and the three expansion behaviours.

**Checks**: pylint clean, mypy clean, pytest 675 passed / 1 skipped, ruff clean.

**Status**: committed

## Round 2 — 2026-09-04

**Findings**

- `checker_tools/mypy_tool.py:56-59` — low — the client-visible `cache_dir` docstring gives the fallback as config-then-default, omitting the `MYPY_CACHE_DIR` layer that round 1's own commit established as beating the config; the same variable appears in no user-facing prose anywhere.
- `code_checker_mypy/runners.py:119-124` — suggestion — `rglob` plus `entry.is_file()`/`entry.stat()` costs two syscalls per cache entry and is unbounded; `os.walk` over `os.scandir` entries would halve them.

No critical issues. The reviewer re-probed mypy 2.3.1 and confirmed all four precedence claims and all three expansion asymmetries that round 1's resolver encodes, plus the `certain` flag in every branch.

**Decisions**

- Accept the docstring gap: a client-visible docstring asserting a precedence the code disproves is the exact silent mismatch this issue exists to remove.
- Skip the syscall optimisation. The code is correct and readable, the path has already spent a full timeout, and even a large project's cache walks in well under a second — a micro-optimisation is not reason to change working code.

**Changes**

`mypy_tool.py` states all four precedence levels. `docs/pyproject-configuration.md` gained two paragraphs in "Sharing mypy's cache": `MYPY_CACHE_DIR` beats the config and is passed through untouched, because an ambient value is a deliberate choice that keeps tool runs and shell runs in one cache; `MYPY_NUM_WORKERS` is the one mypy variable the server pops, because it forces the native parser and would split the cache silently. Neither variable had appeared in the docs before, so the section introduces both rather than contrasting with existing text.

**Checks**: pylint clean, mypy clean, pytest 675 passed / 1 skipped.

**Status**: committed

## Round 3 — 2026-09-04

**Findings**

- `README.md:80` — low — the `cache_dir` row still gives the default as config-then-default, the exact wording round 2 corrected in `mypy_tool.py` and `docs/pyproject-configuration.md`; this third user-facing copy was missed.
- `docs/pyproject-configuration.md:215-217` — optional — "an ambient `MYPY_NUM_WORKERS` would split the cache" is untrue of the value `0`, since mypy sets `native_parser` only when `num_workers` is truthy.

No critical issues. The reviewer checked every claim added in rounds 1-2 against mypy 2.3.1's own sources — the four-level precedence (`main.py:1463-1476`), the expansion asymmetry (`config_parser.expand_path` plus the second `expanduser`), `native_parser` membership in `OPTIONS_AFFECTING_CACHE` (`options.py:73`), and the config discovery order (`defaults.py:19-20`). All hold.

**Decisions**

- Accept the README row: leaving one of three user-facing copies stating a precedence the code disproves is the inconsistency this issue exists to remove.
- Accept the `MYPY_NUM_WORKERS` nit despite the reviewer rating it below the bar for its own change. The file was being edited anyway, and a confidently-wrong sentence is the specific failure mode this issue targets.

**Changes**

The README row now reads "None (no flag sent; `MYPY_CACHE_DIR` decides, else `[tool.mypy] cache_dir`, else `.mypy_cache`)", agreeing with the other two copies. The docs paragraph now says "A non-zero value forces mypy's native parser". The engineer confirmed both mypy sites (`main.py:1469-1475` and `:100-102`) by reading the source, having found that a runtime probe of `process_options` alone is misleading because the derivation happens later in `main()`.

**Checks**: pylint clean, mypy clean, pytest 675 passed / 1 skipped.

**Status**: committed

## Round 4 — 2026-09-04

**Findings**: none. The reviewer re-walked the whole diff and verified `7ba6f56`'s two edits against the resolver; all three user-facing copies of the cache precedence now agree with each other and with `_resolve_cache_dir`.

**Decisions**: nothing to act on. One observation was left below the bar by the reviewer and I agree: the internal comment at `runners.py:233-234` states the `MYPY_NUM_WORKERS` effect unqualified where round 3 narrowed the user-facing prose, but it justifies an unconditional pop that is correct for any value.

**Changes**: none.

**Status**: no changes needed — the review loop ends here.

## Final Status

Four rounds. Rounds 1-3 produced seven accepted fixes across three commits; round 4 came back clean, which is what ended the loop.

**Commits**

| Commit | Content |
|---|---|
| `8747d6b` | `MYPY_CACHE_DIR` precedence layer, `_expand_config_cache_dir`, hermetic timeout test, five precedence/expansion tests |
| `cb2a600` | Four-level precedence in the client-visible docstring; `MYPY_CACHE_DIR` and `MYPY_NUM_WORKERS` introduced in the docs |
| `7ba6f56` | README `cache_dir` row; `MYPY_NUM_WORKERS` claim narrowed to a non-zero value |

**Theme.** Every accepted finding was one defect class: the code stated something about mypy's behaviour that mypy does not do. The original `_resolve_cache_dir` reported a cache path with certainty while ignoring the environment variable that overrides it, and each subsequent round found another copy of the same claim — in the docstring, then the docs, then the README — that the fix had not reached. That is the same failure the issue exists to remove, reappearing inside the fix for it.

Worth recording: mypy's cache-path expansion is **not** uniform by source. A `--cache-dir` argument is taken verbatim, `MYPY_CACHE_DIR` gets `expanduser` only, and a config `cache_dir` gets `expandvars` + `expanduser`. The resolver mirrors that asymmetry rather than normalising it, and the docstring says why, because a later "cleanup" would otherwise re-break it. Both engineers established this by reading mypy 2.3.1's own sources after finding that a runtime probe of `process_options` alone is misleading — the `native_parser` derivation happens later, in `main()`.

**Skipped, with reasons**: the argv-quoting/`list2cmdline` item and the `skipped`-entry under-reporting (log 1); the `rglob`→`os.walk` syscall optimisation (correct, readable code on a path that has already spent a full timeout); stale `pr_info/steps/*.md` plan signatures (`pr_info/` is deleted at the end of the process); the unqualified internal comment at `runners.py:233-234`.

**Final checks**: pylint clean, mypy clean, pytest 675 passed / 1 skipped, ruff clean, vulture clean (after whitelisting the autouse fixture, which CI enforces at `--min-confidence 60`), lint-imports 3 contracts kept / 0 broken.

**Noted but not acted on** — pre-existing, unrelated to this issue: `tools/vulture_check.sh` and `.bat` run vulture *without* the `vulture_whitelist.py` argument that `ci.yml:154` passes, so the local scripts and CI disagree.
