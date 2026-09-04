# review-implementation review log 3

Issue #225 — mypy: let `[tool.mypy]` own the flag set

Continues from [implementation_review_log_2.md](./implementation_review_log_2.md), which ended
clean at round 4.

## Round 1 — 2026-09-04

**Findings**

- `pyproject.toml:102-108` — medium — the migration to `strict = true` dropped `warn_unused_configs`, which `--strict` does not imply. Diffing the full option snapshot of (old config + old `STRICT_FLAGS`) against (new config alone) leaves exactly one difference, so the "provably behaviour-neutral" claim was false by one key.
- `docs/pyproject-configuration.md` — low — the `Duplicate module named ...` bullet claimed that is "the usual outcome for a `src/` layout with no `explicit_package_bases`". Probed: a `src/` layout with `__init__.py` returns rc=0 clean, PEP 420 without returns rc=1 `import-not-found`; neither produces `Duplicate module`.
- `checker_tools/mypy_tool.py:47-49` — low — the client-visible docstring warns that `follow_imports` splits the cache but says nothing equivalent for `disable_error_codes`, though both are in `OPTIONS_AFFECTING_CACHE`.
- `checker_tools/mypy_tool.py:31-33` — suggestion — "the server adds only output-formatting flags" is stronger than the code, which also emits `--cache-dir`, `--follow-imports` and `--disable-error-code` on request.
- `code_checker_mypy/runners.py:70-72` — suggestion — `MYPY_CACHE_DIR` is tested for truthiness with `.strip()` but consumed unstripped.

**Decisions**

- Accept the `warn_unused_configs` regression: behaviour-neutrality is the migration's own central claim, and this one had a live symptom.
- Accept the docs and docstring corrections: all three are the issue's own defect class — prose asserting something mypy does not do — and each is a one-place fix inside text this change already owns.
- Accept the `MYPY_CACHE_DIR` item only contingently, on the engineer verifying it against mypy's source first.

**Changes**

`warn_unused_configs = true` is back. Restoring it surfaced `unused section(s): module = ['jedi.*']`; the engineer found `jedi` itself is still matched by `refactoring/jedi_tools.py`, so the override was narrowed to `module = ["jedi"]` rather than deleted, and mypy returns clean with no notes. The `Duplicate module` bullet now names the shape that actually produces it — the same module basename under two roots, neither carrying an `__init__.py`. The `disable_error_codes` entry carries the cache warning its counterpart already had, and the opening line gained "unless you pass one of the parameters below".

The fifth finding was withdrawn on inspection. mypy 2.3.1 `main.py:1463-1467` tests `environ_cache_dir.strip()` and assigns `environ_cache_dir` unstripped — precisely what `_resolve_cache_dir` does, so dropping the `.strip()` would have introduced the divergence it was meant to remove. The comment above the branch now records that the asymmetry is deliberate.

**Checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped.

**Status**: committed

## Round 2 — 2026-09-04

**Findings**

- `docs/pyproject-configuration.md:166-169` — low — round 1's correction to the `Duplicate module named ...` bullet was itself wrong. It gave the condition as "the same module basename under two roots, neither carrying an `__init__.py`", but the reviewer probed `src/pkg/{__init__.py,util.py}` against `tests/pkg/{__init__.py,util.py}` and got rc=2 with `__init__.py` present in both.
- `docs/pyproject-configuration.md:138-140` — low — the bolded "The MCP tool adds only output-formatting flags" is absolute, though `--follow-imports` is an import-resolution flag the server does send on request. Commit `dbae3ab` qualified the same sentence in `mypy_tool.py` and missed this copy.
- `pyproject.toml:106` with `code_checker_mypy/parsers.py:43-48` — suggestion — mypy prints `unused section(s)` as plain text on stdout even under `--output json`, so `parse_mypy_json_output` discards it. `run_mypy_check(target_directories=["src"])` reports "No type errors found" while a config warning goes unreported.

**Decisions**

- Accept both prose corrections. The `Duplicate module` sentence had now been wrong twice, so the instruction was to re-probe before rewriting rather than reason from the issue's table.
- Skip the swallowed-note gap. `main` carries both `warn_unused_configs = true` and the same `pytest.*` override, and the parser behaviour predates this branch, so it is a pre-existing issue rather than a regression this PR introduced. Worth its own issue; out of scope here.

**Changes**

The bullet now gives the actual condition — any two files under the targeted roots that resolve to the same module name — and says explicitly that `__init__.py` does not prevent it. The engineer probed three shapes first (both roots with `__init__.py`, neither with it, and two top-level modules sharing a basename); all three return rc=2 identically, which is what establishes that the module-name collision is the whole story. The thesis line gained the same qualifying clause `mypy_tool.py` already carried — and a third copy of it turned up at `README.md:86`, also absolute, also corrected.

**Checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped.

**Status**: committed

## Round 3 — 2026-09-04

**Findings**

- `docs/pyproject-configuration.md:135-136` — medium — "It does **not** walk up the directory tree: a config file above the project directory is never read" is false. `_find_config_file` loops upward from cwd and breaks only at a `.git`/`.hg` directory or the filesystem root.
- The "no floor" callout, three copies (`docs/pyproject-configuration.md:144-147`, `README.md:87-89`, `checker_tools/mypy_tool.py:32-34`) — medium — all state that a project with no `[tool.mypy]` is checked at mypy's defaults. Probed false in two shapes: no config file at all, and a `pyproject.toml` carrying only `[project]`; both inherited a parent's `strict = true`.
- `docs/pyproject-configuration.md:134-135` — low — "takes the first one that carries a mypy section" holds only for the shared config names. A `mypy.ini` with no `[mypy]` section halts the search instead of continuing it.
- `code_checker_mypy/runners.py:44-47` — low — `_resolve_cache_dir`'s docstring jumps straight to the user-level fallback, skipping the parent walk.
- `checker_tools/mypy_tool.py:31-33` — suggestion — "unless you pass one of the parameters below" sweeps in `timeout_seconds` and `target_directories`, which send no flags; the docs and README copies name exactly three.
- `docs/pyproject-configuration.md:168-171` — below the bar — `src/util.py` plus `src/util.pyi` resolve to the same module name and return rc=0, so "any two files" has one counterexample.

**Decisions**

- Accept the first five. The no-floor sentence is the one the issue designates as doing the safety work, so a caller being told "almost nothing was verified" when a parent config applied strict checking is the worst version of this PR's own defect class.
- Skip the `.pyi` counterexample, agreeing with the reviewer's own rating. A stub/implementation pair is a normal arrangement nobody consults this bullet about, and the bullet has already been rewritten twice.
- Left `pr_info/steps/step_3.md:34` carrying the same wrong claim, consistent with earlier rounds: `pr_info/` is deleted at the end of the process.

**Changes**

The engineer confirmed every claim against the installed mypy's own sources before writing, and turned up something the review had not: **the upward walk is new in mypy 1.15**, introduced by PR #16965, while this repo declares a floor of `mypy>=1.13.0`. Tags `v1.13.0` and `v1.14.0` still carry the flat `CONFIG_FILES` tuple with no parent loop, so on the floor version the original sentence was correct. All new wording is version-qualified rather than stated flatly.

The discovery paragraph now gives the per-directory filename order, the different meaning of a missing section for the INI names versus the shared names, the upward repeat with its `.git`/`.hg` and root stops, the user-level fallback, and the 1.13/1.14 exception — closing by noting that the old conclusion still holds whenever the project directory is the repository root, which is the common case. All three no-floor copies now say "no `[tool.mypy]` section **of its own**" and name the parent-config alternative. `_resolve_cache_dir`'s docstring names the walk before the user-level fallback. The qualifying clause names the same three flag-sending parameters everywhere.

**Checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped.

**Status**: committed

## Round 4 — 2026-09-04

**Findings**

- `docs/pyproject-configuration.md:140` and `code_checker_mypy/runners.py:48-51` — low — round 3's version gate is too broad. "(Mypy 1.13 and 1.14 look in the working directory only.)" is false: both versions consult `~/.config/mypy/config` and `~/.mypy.ini`, because their `defaults.CONFIG_FILES` includes `USER_CONFIG_FILES`. What 1.15 added is the parent-directory walk alone.
- The no-floor callout, three copies — low — round 3 added "or at a parent directory's config", but the parent config is out of scope in exactly the case the docs call usual: a project directory that *is* the repository root, where the walk breaks immediately. The user-level config applies there, and on every version including the floor. Probed: a repo-root project with only `[project]` plus `~/.mypy.ini` carrying `strict = True` returns rc=1 `no-untyped-def`; the same project with an empty home returns rc=0.

**Decisions**

- Accept both. Each is a defect the previous round's own fix introduced or left half-done, in sentences this round is editing anyway.
- The reviewer disclosed that log 1 round 2 raised the user-level omission and it was dismissed, and offered that skipping again would be defensible. Overruled: round 3 has since accepted the identical defect for the parent-config shape, so leaving the sibling branch unstated would fix the narrower case and not the one that applies at the declared floor.

**Changes**

The engineer confirmed `defaults.py` at tags `v1.13.0`, `v1.14.0` and `v1.15.0` before writing. The version gate now ends at the filesystem root, notes that 1.13 and 1.14 skip the upward walk, and states the user-level fallback as unconditional across versions, naming both files; `runners.py` carries the same split. One neighbouring sentence changed from "never reads a config above it" to "never reads a parent directory's config", which would otherwise have contradicted the unconditional fallback two lines below. All three no-floor copies now name the user-level config beside the parent config as a single clause.

**Checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped.

**Status**: committed

## Round 5 — 2026-09-04

**Findings**

- The no-floor callout, three copies (`docs/pyproject-configuration.md:155`, `README.md:89-90`, `checker_tools/mypy_tool.py:36`) — medium — round 4's clause attached "reports passed" to both branches. The inherited-config branch does not pass: a project containing only `[project]`, nested under this repo, inherits `strict = true` and returns rc=1 `no-untyped-def`. The two hazards are opposites, and the text collapsed them.
- Same three copies — low — all name `~/.mypy.ini` alone, but `USER_CONFIG_FILES` is `["~/.config/mypy/config", "~/.mypy.ini"]` and the first wins. A reader debugging inherited strictness would inspect the lower-precedence path.
- `docs/pyproject-configuration.md:143-144` — low — "a project nested inside a larger repository does" is stated flatly two sentences after the walk was gated to 1.15+, and is false at the declared floor.

**Decisions**

- Accept all three. The first is the sentence the issue designates as doing the safety work, now mis-stating the very failure mode round 4 added it to describe.
- Change of approach. Five consecutive rounds had each found that patching one clause introduced or exposed a defect in its neighbour, so the instruction this time was to rewrite the callout as a coherent passage and then re-read the entire `## How mypy reads pyproject.toml` section as a unit, rather than to edit the reported lines.

**Changes**

The callout now names the two failure modes separately — nothing in scope gives a silent pass at mypy's defaults, which do not check the body of an unannotated function at all; a parent or user-level config in scope gives errors the project never asked for — and closes on what is true of both, that neither names the config it used. The `README.md` and `mypy_tool.py` copies state the same pair more briefly, the docstring included, since it is what an agent reads before calling the tool. The user-level configs are named in precedence order, and the nested-repository sentence is gated to 1.15+.

The whole-section pass earned its keep: it found two contradictions nobody had reported. A section-less `mypy.ini` ends discovery *including* the user-level fallback, which the neighbouring "every version then falls back" sentence contradicted — probed both ways to confirm — so the paragraph now branches explicitly. And "Unlike the missing strictness above" in the import-resolution section became wrong the moment the callout named a branch that does produce loud errors; it now reads "Unlike the silent pass above".

**Checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped.

**Status**: committed

## Round 6 — 2026-09-04

**Findings**

The reviewer's verdict on the previous round's change of approach: the wholesale rewrite worked. Reading the whole section together with all three copies turned up no contradiction between them and none inside the section. Two items remained, both in the discovery paragraph.

- `docs/pyproject-configuration.md:134-138` — low — the paragraph lists four config filenames and then assigns a rule to three of them, leaving `.mypy.ini` unassigned. Singling out `mypy.ini` invites the wrong inference: both are in `defaults.CONFIG_NAMES`, and only `SHARED_CONFIG_NAMES` gets the skip. Probed identical behaviour.
- `docs/pyproject-configuration.md:141-142` and the two shorter copies — suggestion — the user-level fallback is given as an ordered pair, but `USER_CONFIG_FILES` inserts `$XDG_CONFIG_HOME/mypy/config` at index 0 when the variable is set, on every version including the floor.

**Decisions**

- Accept the `.mypy.ini` omission: this is the paragraph a reader consults precisely when a config they expected to apply did not.
- Accept the XDG clause, but **only in the docs discovery paragraph**. The reviewer rated it marginal and would not have held the PR for it. The `README.md` and `mypy_tool.py` copies say less rather than saying something false, and after five rounds of edits rippling between copies, narrowing the blast radius was worth more than uniformity.

**Changes**

The no-section rule now names both INI filenames, and the fallback reads `$XDG_CONFIG_HOME/mypy/config` when set, then `~/.config/mypy/config`, then `~/.mypy.ini`. The engineer confirmed the XDG entry leads at the declared floor too, reading `defaults.py` at tag `v1.13.0`, and verified the section-less `.mypy.ini` halt with a control run proving the strict user config really was in reach and discovery really did end.

The whole-section check came back clean, with one deliberate residue recorded: the no-floor callout and the two shorter copies still give the user-level configs as a two-file list. None of them claims the list is exhaustive, so they are simplifications rather than contradictions.

**Checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped.

**Status**: committed

## Round 7 — 2026-09-04

**Findings**: none. The reviewer verified both clauses of `927bbe6` against mypy 2.3.1's `defaults.py` and against the same file at tag `v1.13.0`, confirming the four-name discovery order, the three-item user-level precedence and the XDG insert at index 0 all hold at the declared floor as well as at the installed version. Behavioural probes covered both INI names halting discovery including the user-level fallback, and XDG genuinely winning over `~/.config/mypy/config`.

The reviewer also probed the one neighbouring claim no previous round had tested — that `pyproject.toml` and `setup.cfg` are skipped rather than halting — across four shapes, confirming the asymmetry the paragraph draws is real in both directions.

**Decisions**: nothing to act on.

**Changes**: none.

**Status**: no changes needed — the review loop ends here.

## Final Status

Seven rounds. Rounds 1-6 produced fourteen accepted fixes across six commits; round 7 came back clean, which is what ended the loop.

**Commits**

| Commit | Content |
|---|---|
| `dbae3ab` | `warn_unused_configs` restored, `jedi.*` override narrowed, `disable_error_codes` cache warning, flag claim qualified |
| `1fbabea` | `Duplicate module` condition corrected, flag claim qualified in the docs and README copies |
| `3d8f78a` | Config discovery described correctly — the parent-directory walk, version-gated to mypy 1.15+ |
| `9d7daa2` | Version gate narrowed to the walk alone; user-level config named beside the parent config |
| `5bd72be` | No-floor callout rewritten as a unit, split into its two opposite failure modes |
| `927bbe6` | `.mypy.ini` named in the no-section rule; `$XDG_CONFIG_HOME/mypy/config` added |

**Theme.** Every accepted finding in this run was documentation asserting something mypy does not do — the same defect class logs 1 and 2 recorded, now concentrated entirely in prose. The migration itself was sound; what kept failing was describing it.

Two things are worth carrying forward. First, `--strict` does not imply `warn_unused_configs`, so the "provably behaviour-neutral" claim was false by exactly one key until round 1 caught it — a full option-snapshot diff, not a reading of the flag list, is what found it. Second, and more instructive: **per-clause patching failed five rounds running.** Rounds 1 through 5 each fixed the reported sentence and left, or introduced, a defect in its neighbour — the version gate that swallowed the user-level fallback, the "reports passed" clause attached to the branch that reports errors, the cross-reference that stopped matching the bullet it pointed at. Round 5 changed the instruction from "edit these lines" to "rewrite the passage and then re-read the whole section as a unit", and that pass immediately found two contradictions nobody had reported. Rounds 6 and 7 were near-clean and clean. For prose describing a tool's behaviour, the unit of correctness is the section, not the sentence.

Also recorded: mypy's config discovery is version-dependent in one specific way. The upward walk through parent directories arrived in 1.15 (PR #16965); at this repo's declared floor of 1.13 it does not exist, while the user-level fallback is unconditional at every version. Conflating the two produced two separate wrong statements in two separate rounds.

**Skipped, with reasons**: the `warn_unused_configs` note being swallowed by `parse_mypy_json_output` — real, but `main` carries both the config key and the parser behaviour, so it is pre-existing and belongs in its own issue; the `src/util.py` + `src/util.pyi` counterexample to the `Duplicate module` bullet, a normal arrangement nobody consults that bullet about; and the `$XDG_CONFIG_HOME` entry in the two shorter no-floor copies, deliberately left as a simplification to stop edits rippling between copies again.

**Final checks**: pylint clean, mypy clean, ruff clean, pytest 657 passed / 1 skipped, vulture clean, lint-imports 3 contracts kept / 0 broken. CI green on every pushed commit.

**Outstanding, not review work**: the branch is one commit behind `origin/main` (`60e1cc3 fix(server): detect tools next to the resolved interpreter (#229)`) and no PR has been opened. `60e1cc3` touches `checker_tools/mypy_tool.py`, `tests/test_checker_tools.py`, `README.md` and `docs/architecture/architecture.md`, all of which this branch also changed, so the rebase carries real conflict risk — `mypy_tool.py` most of all, since #229 reworked tool resolution in the same module this branch reworked flag handling in.
