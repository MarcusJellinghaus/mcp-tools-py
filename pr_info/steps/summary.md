# Summary — #225 mypy: let `[tool.mypy]` own the flag set

## Problem

`run_mypy_check` hands mypy a flag set that no plain `mypy` invocation reproduces:
`STRICT_FLAGS`, `--namespace-packages`, `--explicit-package-bases`, a constructed
`MYPYPATH`, and an unconditional `--follow-imports normal`. The strictness flags and
`follow_imports` are in mypy's `OPTIONS_AFFECTING_CACHE`, so the server can never share
a cache with a shell run. On a large project a cold cache exceeds the timeout, the run is
killed, and there is no way to warm the cache from outside — every call fails identically
and the error message says nothing that would let a caller recover.

## Goals

1. `[tool.mypy]` becomes the single source of truth for the flag set, unconditionally.
2. A timeout reports enough to diagnose and retry: cache state, the exact command, cwd,
   interpreter, and the limit that was actually used.
3. This repo migrates its own config in the same commit that removes the flags.

## Architectural / design changes

**Configuration ownership moves from the server to the checked project.** This is the
same position the project already shipped for pylint — `code_checker_pylint/runners.py`
builds `[python, "-m", "pylint", "--output-format=json"]` plus caller args plus targets,
with no hardcoded rule or severity flags. Mypy becomes consistent with that decision
rather than taking a new one.

The resulting split is what makes cache sharing work: the flags the server passes on
**every** call are exactly the ones **outside** `OPTIONS_AFFECTING_CACHE`, and the ones
that affect the cache belong to the project's config — or, for the two per-call overrides
in the table below, to a caller who explicitly asks for them. `follow_imports` and
`disable_error_code` are both in `OPTIONS_AFFECTING_CACHE`, so supplying either still
splits the cache; that is why neither is sent by default.

| Concern | Owner after this change |
|---------|------------------------|
| Strictness, import resolution, per-module overrides, `follow_imports` default | The checked project's `[tool.mypy]` |
| Output format (`--output json`, `--no-color-output`, `--show-column-numbers`, `--show-error-codes`) | The server |
| Per-call overrides (`--cache-dir`, `--follow-imports`, `--disable-error-code`, targets) | The caller, when explicitly supplied |

**No floor, and no detection.** A project with no `[tool.mypy]` is checked at mypy's
defaults and reports "passed". This is documented plainly in the client-visible tool
docstring and in `docs/pyproject-configuration.md`, rather than papered over with a
fallback or a config probe.

**`--follow-imports` becomes conditional.** It is cache-affecting, so passing it on every
call would override the project's config and re-split the cache — the exact trap this
change exists to close. Two internal defaults change to make that work
(`runners.run_mypy_check(follow_imports: str | None = None)` and dropping the
`follow_imports or "normal"` coercion in `reporting.py`). The MCP surface is unchanged;
it already declares `follow_imports: str | None = None`.

**Breaking change (wire-visible).** `strict` is a published MCP tool parameter, so it
appears in the schema of every connected client. It is removed cleanly, with no
deprecation window: accepting and ignoring it would report a strictness setting the
server does not honour, which is the same silent mismatch this issue exists to remove.
There is no CHANGELOG in this repo, so **the PR description must carry this note**.

**`MYPY_NUM_WORKERS` is popped from the subprocess environment.** mypy reads it as of 2.1
and it forces `native_parser`, which is cache-affecting — so an ambient value in the
user's shell would silently split the cache with nothing on our command line naming the
cause. The exposure is pre-existing (`os.environ.copy()` already passes it through);
it is closed in the same pass that drops the `MYPYPATH` assignment.

**No new modules.** Steps 2 and 3 of the issue collapse into a single `if
result.timed_out:` branch plus one private helper in `runners.py`, because that function
already holds the command, cwd, interpreter, cache dir and resolved timeout.

## Files created / modified

No new source modules or packages. No new dependencies.

| Step | File | Change |
|------|------|--------|
| 1 | `pyproject.toml` | Add `strict = true`, `warn_unreachable = true` to `[tool.mypy]` |
| 1 | `src/mcp_tools_py/code_checker_mypy/runners.py` | Remove `STRICT_FLAGS`, `strict`, `config_file`, package flags, `MYPYPATH`; conditional `--follow-imports`; pop `MYPY_NUM_WORKERS` |
| 1 | `src/mcp_tools_py/code_checker_mypy/reporting.py` | Remove `strict` and the `follow_imports` coercion |
| 1 | `src/mcp_tools_py/checker_tools/mypy_tool.py` | Remove `strict` param, log field and docstring block; state config ownership and the no-floor behaviour |
| 1 | `tests/test_code_checker_mypy/test_runners.py` | Drop `strict=`; add command-line/env assertion test |
| 1 | `tests/test_code_checker_mypy/test_integration.py` | Drop `strict=`; replace `test_mypy_strict_vs_non_strict` with a config-driven test |
| 1 | `tools/mypy.bat`, `tools/checks2clipboard.bat` | Collapse to `mypy src tests` |
| 1 | `.github/workflows/ci.yml`, `.github/workflows/upstream-mypy-check.yml` | Collapse to `mypy src tests` (plus job `name:` and header comment) |
| 1 | `CONTRIBUTING.md` | `:217` command; `:121` wording |
| 1 | `README.md` | Delete `strict` row `:77`; fix the `follow_imports` default `:80`; fix `:427` |
| 1 | `tests/mcp_tools_py_manual/TEST_PLAN.md` | Tests 3a/3b (`:185-197`) reference the removed `strict` parameter |
| 1 | `docs/architecture/architecture.md` | `:253` CI matrix |
| 2 | `src/mcp_tools_py/code_checker_mypy/runners.py` | Timeout branch + `_describe_cache` helper |
| 2 | `tests/test_code_checker_mypy/test_runners.py` | Timeout message tests |
| 2 | `tests/test_error_transparency.py` | `TestMypyTimeout` already covers the branch — keep it passing, don't duplicate it |
| 3 | `docs/pyproject-configuration.md` | New `## How mypy reads pyproject.toml` |
| 3 | `README.md` | New `### Mypy Configuration` pointer |
| 3 | `docs/README.md` | `:18` index entry stops being pylint-only |

## Steps

| Step | Commit | Depends on |
|------|--------|-----------|
| [step_1.md](step_1.md) | Config owns the flag set — atomic, no intermediate state | — |
| [step_2.md](step_2.md) | Honest timeout message with retry guidance | step 1 |
| [step_3.md](step_3.md) | Documentation | steps 1, 2 |

Step 1 is deliberately large: the config change and the flag removal **must** be one
commit. Either order of a split leaves a window where this repo's type checking is
silently lax or the config is written but not obeyed.

## Out of scope

- `-n` / parallel checking — rejected, see the issue's *Why `-n` is out of scope*.
- A `warm_mypy_cache` tool, auto-warm at startup, `dmypy`, `--follow-imports=skip`.
- `_format_mypy_result` prefixes a timeout with "Mypy found type issues that need
  attention". Fixing it honestly means changing `get_mypy_prompt`'s return contract; the
  message itself opens with `Mypy execution failed:`, which reads unambiguously.

## Measurements (issue step zero)

- **Measurement 1** — whether a call longer than 120s returns at all, or the calling
  harness caps it. Not reproducible from a session scoped to this repo; it needs a
  server pointed at a large project, so it stays deferred rather than running as step
  zero.
  - *Owner:* whoever implements step 1, from an `mcp-coder` session (729 files, where
    the problem was measured).
  - *Trigger:* before opening the PR for step 1 — the result belongs in its description.
  - *Acceptance criterion:* one `run_mypy_check(timeout_seconds=400)` call on a cold
    cache either returns a result (the harness does not cap us — our own 120s default
    was the whole problem, and the *Fallback* section stays unneeded) or is killed at
    some limit below 400s (the harness caps us — record the observed limit, since the
    step 2 retry hint is then bounded by it).
  - It blocks no step: step 1 stands on cache sharing regardless of the outcome.
- **Measurement 2** — whether killed runs converge. Needs no code: after step 2 ships,
  call the tool three times on a cold cache and read the size/mtime line.
