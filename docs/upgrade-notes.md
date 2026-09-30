# Upgrade Notes

Behaviour changes to check when upgrading. Newest first.

---

## `run_format_code`: ruff support, formatters from the tool env (#235)

### The first `run_format_code` after upgrading may reformat

black and isort now run from mcp-tools-py's own environment (the tool env), like
ruff, bandit, vulture, tach and lint-imports, instead of from the environment
`--python-executable` names. If the tool env's black or isort version differs from
the one your project env had, the first run reformats code that was already
formatted. Commit that diff on its own.

Each formatter step now starts its output with the formatter version it ran, so
later drift is visible rather than mysterious.

### Breaking changes

| Change | Remedy |
|--------|--------|
| `run_format_code` without `steps` errors when `pyproject.toml` has neither `[tool.black]` nor `[tool.ruff.format]` — common for repos running black at its defaults | Add `[tool.black]` (even empty), or set `[tool.mcp-tools-py] formatter = "black"` |
| `steps=[]` is an error; it used to mean the defaults | Omit `steps` for the default, or name the steps |
| `DEFAULT_STEPS` is no longer exported from `mcp_tools_py.formatter` | Call `resolve_steps(project_root)` |

See [formatter selection](pyproject-configuration.md#toolmcp-tools-py-formatter--formatter-selection)
for the new `ruff` steps and how the formatter is chosen.

### Known limitation: console scripts are found only next to the tool-env interpreter

A console script is looked up only in the tool-env interpreter's own script
directory, with no `PATH` fallback. That already applied to ruff, bandit, vulture,
tach and lint-imports; it now applies to black and isort. Setups whose scripts live
elsewhere (`pip install --user`, some conda layouts) report black or isort as not
available where `python -m` used to work.

### Keep CI's black and isort compatible

A project whose CI runs its own pinned black or isort (e.g. `black --check`) should
keep version ranges compatible with mcp-tools-py's. Otherwise agent formatting and
CI disagree on every commit.
