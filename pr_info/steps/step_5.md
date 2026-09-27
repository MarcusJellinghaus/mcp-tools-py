# Step 5 — Documentation

Read [summary.md](./summary.md) first.

Scope: prose only. No source, test or configuration changes.

## WHERE

- `README.md` — `:115` (parameter table), `:145-197` (Environment Configuration),
  `:203-204` (Troubleshooting)
- `docs/architecture/architecture.md` — §5 Module Overview (`probe.py`,
  `utils/tool_context.py`), §7 Deployment View

## WHAT

**`README.md:115`** — `--python-executable` is the project interpreter. Drop "and
the checker tools"; add that ruff, bandit, vulture, tach and lint-imports come from
mcp-tools-py's own environment and need not be installed there.

**Environment Configuration** — replace the "there is **one** configurable
environment" framing with the split:

- **project env** — `--python-executable`. Holds the project's dependencies, and
  pytest, pylint, mypy, black and isort, which must import them. Library and symbol
  resolution (`get_library_source`, `list_symbols`, `find_references`) follows it too.
- **tool env** — where `mcp_tools_py` is installed. Supplies ruff, bandit, vulture,
  tach and lint-imports, which are its own dependencies. Not configurable.

One sentence on version drift: these five run at the tool env's versions, which may
differ from what the project pins, so a project that cares about CI parity should
keep compatible ranges in both places. One sentence on lint-imports: it runs from
the tool env but finds the project's root package, read from the import-linter
config and located through the project interpreter.

The "Incorrect Configuration" section keeps its point — a system interpreter still
breaks pytest/pylint/mypy and resolves library lookups against the wrong packages —
but must stop claiming it breaks the five console scripts.

**Troubleshooting** — rewrite the last two bullets:

- `"ruff is not available"` (or bandit/vulture/tach/lint-imports) no longer points at
  `--python-executable`. It means mcp-tools-py's own install is incomplete: the
  message names the tool env directory searched; reinstall mcp-tools-py (with its
  dependencies) and restart the server.
- The "no restart needed" bullet loses the console-script half. What remains: the
  `python -m` tools are answered by a cached probe of the configured interpreter, so
  restart after installing one of those five.

**`architecture.md` §7** — the deployment bullet currently says there is one
configurable environment "because the checkers must import the project's
dependencies". Narrow that to the checkers that actually do, and say the
console-script tools resolve in the tool env.

**`architecture.md` §5** — the `probe.py` bullet gains the `locate` subcommand
alongside `info` and `source`; the `utils/tool_context.py` bullet mentions that the
context carries both environments and which tools use which.

## ALGORITHM / DATA

None.

## VERIFY

No code changed, so the check suite is a formality — run
`run_pytest_check(["-n","auto"])` once to confirm nothing was touched by accident.
Re-read the edited README sections against the behaviour built in steps 1-3; the
parameter table, Environment Configuration and Troubleshooting must not contradict
each other.

Commit: `docs: describe the project/tool environment split (#233)`

## LLM PROMPT

> Implement step 5 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_5.md` first. Edit only `README.md` and
> `docs/architecture/architecture.md`. Keep the existing tone and be brief — no new
> sections, no duplicated explanations between the parameter table, Environment
> Configuration and Troubleshooting. Verify no source file changed, then one commit.
