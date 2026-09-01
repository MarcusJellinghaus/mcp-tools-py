# Project Configuration via `pyproject.toml`

The checked project's `pyproject.toml` drives several parts of this server: the
`[tool.mcp-tools-py]` section it owns itself, plus sections owned by other tools
that it reads (pylint messages, target directories).

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

## One-off overrides with `extra_args`

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
