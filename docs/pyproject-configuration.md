# Pylint Configuration via `pyproject.toml`

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

## Reference

Full list of pylint message codes and categories:
[pylint messages overview](https://pylint.readthedocs.io/en/stable/messages/messages_overview.html)
