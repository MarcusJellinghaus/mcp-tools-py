# Step 3 — Documentation

One commit, docs only. Steps 1 and 3 already fixed every statement the change made
*false*; this step adds the guidance a migrating project needs. Substance lives in one
place, `docs/pyproject-configuration.md`; everything else points at it.

## WHERE

| File | Change |
|------|--------|
| `docs/pyproject-configuration.md` | New `## How mypy reads pyproject.toml` |
| `README.md` | New `### Mypy Configuration` |
| `docs/README.md` | `:18` index entry |

## WHAT

### `docs/pyproject-configuration.md`

The file has zero mypy content today beyond one incidental mention under `## Target
directory auto-detection` — which is why the flag-set trap was invisible.

**Placement:** directly after `## Finer-grained code control`, so the mypy section sits
adjacent to the pylint pair (`## How pylint reads pyproject.toml` + `## Replicating the
old ERROR / FATAL default`) without interleaving between them.

**Wording to mirror**, from the pylint section: *"The MCP tool passes pylint output
through cleanly — it applies no post-filtering and adds no hidden `--disable` flags.
`pyproject.toml` is the single source of truth for which messages pylint reports."*

Content:

1. mypy reads `[tool.mypy]` automatically because the tool runs with the project
   directory as cwd; the discovery order, and that mypy does **not** walk up the tree.
2. `[tool.mypy]` is the single source of truth for the flag set.
3. **There is no floor.** A project with no `[tool.mypy]` is checked at mypy's defaults
   and still reports "passed". Prominent — its own callout, not a footnote.
4. The migration recipe — `strict = true` and `warn_unreachable = true` — presented like
   the existing `## Replicating the old ERROR / FATAL default`, which is the same shape
   of change.
5. **Import resolution, as its own callout.** `mypy_path`, `namespace_packages` and
   `explicit_package_bases` also stop being supplied. This fails *loudly* — as
   `import-not-found`, or as a hard rc=2 `Duplicate module named` build failure that
   checks nothing at all — so it looks nothing like the silent laxness of item 3. Both
   failure modes must be described, and described as different.
6. The cache table: which flags the server still passes, and why a mismatched flag set
   silently discards the cache. The flags passed on **every** call — `--output json`,
   `--no-color-output`, `--show-column-numbers`, `--show-error-codes`, `--cache-dir` —
   are cache-neutral: none of them is in `OPTIONS_AFFECTING_CACHE`. The two
   caller-supplied ones are **not**: `follow_imports` and `disable_error_code` are both
   in `OPTIONS_AFFECTING_CACHE` (verified against the installed mypy, 50 entries), so
   passing `follow_imports` or `disable_error_codes` splits the cache against every run
   that does not pass the same value. Warn about that explicitly — it is the one
   remaining way a caller can re-open the trap this change closes. Also state that the
   mypy version, installed plugins and interpreter are part of the cache key, so warming
   from a different venv fails as silently as warming with the wrong flags. Do **not**
   imply `--show-error-codes` does any work; it is already mypy's default and is kept
   only as tidying. `--namespace-packages` is removed in step 1 — it must not appear in
   this table at all.
7. Why local scripts and CI must drop `--strict` too: any `--strict` on any command line
   beats the config and re-splits the cache.

### `README.md` — `### Mypy Configuration`

Next to `### Pylint Configuration` (`:34-39`), matching its four-line pointer shape:
mypy reads the project's `pyproject.toml` automatically; `[tool.mypy]` controls the flag
set; a project with no config is checked at mypy's defaults; link to
`docs/pyproject-configuration.md`.

### `docs/README.md:18`

Currently `**[Pylint Configuration](pyproject-configuration.md)** — How pylint reads
pyproject.toml, migration from old defaults, extra_args overrides`. Already stale before
this change, and under config ownership it must stop being pylint-only. Retitle to cover
pylint, mypy and the `[tool.mcp-tools-py]` timeouts the file also documents.

## HOW / ALGORITHM / DATA

None — no code, no signatures, no data structures.

## TESTS

None. TDD does not apply to prose; the claims here were verified by probing mypy 2.3.1
during issue analysis, and step 1's tests assert the behaviour this text describes.

## VERIFICATION

```
mcp__mcp-tools-py__run_pytest_check   extra_args: ["-n", "auto"]
```

Confirm every relative link resolves and that no remaining `--strict` reference in the
repo describes current behaviour:

```
mcp__mcp-workspace__search_files   pattern: "--strict|strict mode|mypy \\(strict\\)"
```

Expected survivors after step 1: none describing this tool's behaviour. Anything left is
either a `[tool.mypy] strict = true` config reference or a bug.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`, then implement step 3 on
> top of steps 1 and 2.
>
> Documentation only — do not change code. Write the substance once, in
> `docs/pyproject-configuration.md`; `README.md` and `docs/README.md` are short pointers.
>
> Two things must be prominent, not footnotes, and must be described as the *different*
> failure modes they are: a project with no `[tool.mypy]` is checked at mypy's defaults
> and silently reports "passed", while missing `mypy_path` / `namespace_packages` /
> `explicit_package_bases` fails loudly with import errors or a hard rc=2 build failure.
>
> Mirror the existing pylint section's wording and placement. Keep it concise — follow
> the repo's writing style.
>
> Run the search in the Verification section and confirm no stale `--strict` reference
> describes current behaviour. Use MCP tools for all file and git operations.
