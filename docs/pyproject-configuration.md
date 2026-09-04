# Project Configuration via `pyproject.toml`

The checked project's `pyproject.toml` drives several parts of this server: the
`[tool.mcp-tools-py]` section it owns itself, the sections the checkers read for
themselves (`[tool.pylint]`, `[tool.mypy]`), and the keys it reads to auto-detect
target directories.

---

## `[tool.mcp-tools-py]` — subprocess timeouts

```toml
[tool.mcp-tools-py]
check-timeout = 300
mypy-timeout = 600
pytest-timeout = 900
```

Configuration is opt-in. Without it, every program gets the built-in default:
120 seconds, or 300 for pytest.

### Precedence

```
tool argument  →  <tool>-timeout  →  check-timeout  →  --check-timeout  →  built-in
```

`check-timeout` applies to every program; a `<tool>-timeout` key overrides it for
that one program. The `--check-timeout` CLI option is server-wide — there are no
per-tool CLI flags, so a per-project value always wins over it.

### Per-tool keys

`mypy-timeout`, `pylint-timeout`, `pytest-timeout`, `ruff-timeout`,
`bandit-timeout`, `vulture-timeout`, `tach-timeout`, `lint-imports-timeout`,
`black-timeout`, `isort-timeout`. Unknown keys in the section are ignored.

### Keys name programs, not MCP tools

A key bounds **one run of one program**, so a single tool call can spend more than
one budget:

| Tool call | Worst case |
|-----------|------------|
| `run_format_code` | `black-timeout` + `isort-timeout` |
| `run_ruff_fix` | 2 × `ruff-timeout` (a pre-check run, then the apply run) |
| `run_pytest_check` | 2 × `pytest-timeout` + 60s, when the pytest-json-report plugin is missing and the run is retried |

### Values

Positive integers only. `0` and negative values are rejected with a clear error.
`0 = disabled` is deliberately unsupported: an unbounded subprocess in an MCP
server is an unrecoverable hang — nothing else will reap it and the tool call
simply never returns. Use a large value to approximate "never".

A malformed `pyproject.toml` now fails every tool call, including
`run_tach_check` and `run_lint_imports_check`, which read no project
configuration before this setting existed.

### Per-call overrides

`run_mypy_check` and `run_pytest_check` accept a `timeout_seconds` argument that
outranks everything above. The other tools do not.

### Caveats

**Name collision.** `pytest-timeout` is also the name of a well-known PyPI plugin.
There is no TOML clash — that plugin reads `[tool.pytest.ini_options] timeout` —
but the similarity is worth knowing.

**Not a guarantee.** The effective limit is `min(server timeout, harness timeout)`:
a calling agent's watchdog can cut a tool call short regardless of this setting.

---

## How pylint reads `pyproject.toml`

When the MCP tool invokes pylint (via `python -m pylint`), pylint automatically
reads `pyproject.toml` from the project directory. This means your
`[tool.pylint.messages_control]` settings take effect without any extra
configuration in the MCP tool itself.

**The MCP tool passes pylint output through cleanly** — it applies no
post-filtering and adds no hidden `--disable` flags. `pyproject.toml` is the
single source of truth for which messages pylint reports.

---

## Replicating the old ERROR / FATAL default

Previous versions of this tool suppressed all warnings, conventions, and
refactoring messages automatically. To replicate that behaviour in your own
project, add this section to `pyproject.toml`:

```toml
[tool.pylint.messages_control]
disable = ["W", "C", "R"]
```

This disables all messages in the Warning (`W`), Convention (`C`), and
Refactor (`R`) categories, leaving only Error (`E`) and Fatal (`F`) messages
visible — the same set the old default produced.

---

## Finer-grained code control

If you want to disable specific codes rather than entire categories, list them
explicitly. The following codes were previously suppressed by the tool's
hardcoded defaults:

```toml
[tool.pylint.messages_control]
disable = [
    "C0114",  # missing-module-docstring
    "C0116",  # missing-function-docstring
    "C0301",  # line-too-long
    "C0303",  # trailing-whitespace
    "C0305",  # trailing-newlines
    "W0311",  # bad-indentation
    "W0611",  # unused-import
    "W1514",  # unspecified-encoding
]
```

Mix and match to suit your project's standards.

---

## How mypy reads `pyproject.toml`

When the MCP tool invokes mypy (via `python -m mypy`), the project directory is
mypy's working directory, so mypy finds `pyproject.toml` by itself. It looks for
`mypy.ini`, `.mypy.ini`, `pyproject.toml` and `setup.cfg`, in that order, and
takes the first one that carries a mypy section. It does **not** walk up the
directory tree: a config file above the project directory is never read.

**The MCP tool adds only output-formatting flags** — no strictness, no import
resolution, no per-module settings of its own. `[tool.mypy]` is the single source
of truth for the flag set mypy runs with.

> **There is no floor.** A project with no `[tool.mypy]` section is checked at
> mypy's defaults: bodies of unannotated functions are not checked at all. The run
> reports "passed" and nothing warns you that almost nothing was verified. If you
> want strict checking, you have to ask for it.

### Replicating the old strict default

Earlier versions of this tool passed a hardcoded strictness set on every run. To
get that checking back, put it in your `pyproject.toml`:

```toml
[tool.mypy]
strict = true
warn_unreachable = true
```

### Import resolution is yours too — and it fails loudly

`mypy_path`, `namespace_packages` and `explicit_package_bases` are no longer
supplied either. Unlike the missing strictness above, you will notice, in one of
two quite different ways:

- **`import-not-found` / `import-untyped` errors.** Mypy runs and checks your
  code, but reports every import it could not resolve.
- **`Duplicate module named ...`, exit code 2.** The build fails before checking
  anything, so the run reports an error rather than a type result. This is the
  usual outcome for a `src/` layout with no `explicit_package_bases`.

A `src/` layout typically needs:

```toml
[tool.mypy]
mypy_path = "src"
namespace_packages = true
explicit_package_bases = true
```

### Sharing mypy's cache

Mypy discards its incremental cache whenever a cache-affecting option changes, so
a run with a different flag set pays for a full cold rebuild. The flags this
server sends on **every** call leave the cache alone; the three optional ones do
not:

| Flag | Sent | Effect on the cache |
|------|------|---------------------|
| `--output json` | every call | None |
| `--no-color-output` | every call | None |
| `--show-column-numbers` | every call | None |
| `--show-error-codes` | every call (already mypy's default; kept for explicitness) | None |
| `--cache-dir` | when `cache_dir` is passed | Sends the run to a different cache directory |
| `--follow-imports` | when `follow_imports` is passed | Invalidates the cache |
| `--disable-error-code` | when `disable_error_codes` is passed | Invalidates the cache |

So by default — no `cache_dir`, no `follow_imports`, no `disable_error_codes` —
a tool run and a plain `mypy` run in your shell share one cache.

**Passing `follow_imports` or `disable_error_codes` invalidates it.** Both are in
mypy's set of cache-affecting options, so a call that supplies either invalidates
the cache against every run that does not supply the same value — alternating
between the two costs a cold rebuild each way. Use them for one-off narrowing,
not routinely; put the lasting choice in `[tool.mypy]` instead.

**Passing `cache_dir` bypasses it.** The option is not in mypy's cache-affecting
set, so nothing is invalidated — but the run reads and writes a cache of its own,
so it neither benefits from nor warms the one your shell runs use.

The mypy version, the installed plugins and the interpreter are part of the cache
key too. Warming the cache from a different virtualenv fails just as silently as
warming it with the wrong flags.

### Local scripts and CI

Any flag on the command line beats the config file, so a script or CI job still
passing `--strict` re-splits the cache against every other run — including the one
the MCP tool makes. Collapse them to plain `mypy src tests` and let `[tool.mypy]`
decide.

---

## One-off pylint overrides with `extra_args`

To suppress a specific code for a single run without changing `pyproject.toml`,
pass `extra_args` to the MCP tool:

```python
run_pylint_check(extra_args=["--disable=W0611"])
```

Multiple flags are supported:

```python
run_pylint_check(extra_args=["--disable=W0611,C0114", "--max-line-length=120"])
```

`extra_args` values are appended directly to the pylint CLI command, so any
valid pylint option works here.

---

## Target directory auto-detection

When `target_directories` is omitted (or `None`), the checker tools (pylint, mypy,
vulture) auto-detect which directories to analyze from `pyproject.toml`:

| Setting | `pyproject.toml` key | Fallback |
|---------|---------------------|----------|
| Source dirs | `[tool.setuptools.packages.find] where` | `["src"]` |
| Test dirs | `[tool.pytest.ini_options] testpaths` | `["tests"]` |

Example `pyproject.toml` that would auto-detect `["src"]` and `["tests"]`:

```toml
[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Only directories that actually exist on disk are included. If none of the resolved
directories exist, an error is returned.

Pass an explicit `target_directories` list to override auto-detection.

---

## Pylint reference

Full list of pylint message codes and categories:
[pylint messages overview](https://pylint.readthedocs.io/en/stable/messages/messages_overview.html)
