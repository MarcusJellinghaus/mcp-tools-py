# Step 8 — Documentation sweep and regenerated dependency graph

Two distinct kinds of edit, easy to conflate:

- **Count edits** — the env move changes "five console-script tools" to **seven** and
  "five `python -m` tools" to **three**.
- **Enumeration edits** — every place that *names* the formatters rather than counting.

Plus three traps that must **not** change.

## ⚠️ Do not change

| Location | Why |
|---|---|
| `docs/architecture/architecture.md` lines 163, 252 and `tests/test_registrars.py` | "five **registrars**" is an unrelated count |
| `docs/architecture/architecture.md:274` | The repo's own workflow list — mcp-tools-py keeps black until step 6 of the migration sequence |
| `docs/architecture/architecture.md:173` | The `utils/target_scripts/probe.py` bullet, immediately above an edited line |
| `docs/pyproject-configuration.md:36` | `ruff-timeout` is already listed; `black-timeout` and `isort-timeout` both stay valid |
| `tach.toml` | No new edge, in either direction |

## Count edits — five → seven console-script, five → three `python -m`

- `src/mcp_tools_py/utils/tool_context.py` — module docstring, `is_tool_available`
  docstring, `unavailable_message` docstring
- `src/mcp_tools_py/utils/environment_info.py::_failed` — "all five module tools"
- `src/mcp_tools_py/server.py:73` — "The five `python -m` tools are left to the lazy probe"
- `README.md:198` — "if those five are not installed" → three
- `README.md:205` — "restart the MCP server after installing one of those five" → three
- `docs/architecture/architecture.md:174` — "used by the five console-script tools" →
  seven. **This line takes a count edit *and* an enumeration edit.**
- `tests/test_server_params.py:798` — docstring "Each of the five names is warned about
  with the handler's message", over a loop on `CONSOLE_SCRIPT_TOOLS` → seven

## Enumeration edits

Everywhere reading *"pytest, pylint, mypy, black and isort run in it"* /
*"ruff, bandit, vulture, tach and lint-imports come from mcp-tools-py's own environment"*,
black and isort move to the second list:

- `src/mcp_tools_py/utils/tool_context.py` — **class** docstring, both `environment` and
  `tool_environment` attribute descriptions
- `src/mcp_tools_py/server.py:39` and `:101` — the `python_executable` parameter docstrings
  on `ToolServer.__init__` and `create_server`
- `README.md:115`, `:149`, `:158`, `:203`
- `docs/architecture/architecture.md:230`, `:233` — the project-env / tool-env split
  explanation, which is precisely what this env move changes
- `docs/architecture/architecture.md:174` — as above, both kinds of edit on one line

Formatter naming:

- `src/mcp_tools_py/formatter/formatter_tools.py:43-50` — the **user-visible MCP tool
  docstring**. "Run code formatters (black, isort) on the project" and
  `Valid values: "isort", "black"`. This is what an agent reads before calling the tool,
  so it must describe all four steps and say the default is resolved from the project's
  configuration.
- `src/mcp_tools_py/formatter/runner.py` — module docstring line 3 ("sequences formatter
  runners (isort, black)") and the `steps` argument docstring ("Defaults to
  `["isort", "black"]`")
- `src/mcp_tools_py/formatter/__init__.py:1` — "Formatter package for code formatting
  tools (black, isort)"
- `README.md:44` — the auto-detect list
- `README.md:460` — "`run_format_code` | Runs isort then black"
- `docs/architecture/architecture.md:11` — "code formatting (black, isort)"
- `docs/architecture/architecture.md:19` — "Formatting: black and isort behind a single
  `run_format_code` tool"
- `docs/architecture/architecture.md:58` — "Black + isort via the `run_format_code` MCP
  tool before commits"
- `docs/architecture/architecture.md:69-70` — the ASCII block diagram, which places
  `black` / `isort` in the project-env column
- `docs/architecture/architecture.md:165` — the `formatter/` bullet naming
  `black_runner.py` and `isort_runner.py`; add `ruff_runner.py` and `common.py`

## Timeout documentation

`docs/pyproject-configuration.md:45` — the `run_format_code` row. Worst case is no longer
`black-timeout + isort-timeout`; on a ruff repo it is **3 × `ruff-timeout`**, because
`ruff_imports` is two invocations in write mode and `ruff_format` is one. Record both
shapes. Line 46 already records 2 × `ruff-timeout` for `run_ruff_fix` — match its wording.

## The new configuration key

`[tool.mcp-tools-py] formatter` is the **first non-timeout key** in that section, and
`docs/pyproject-configuration.md` currently reads as a timeout-key list end to end. Add a
short "Formatter selection" section covering:

- accepted values `"ruff"` and `"black"`
- the detection fallback: `[tool.ruff.format]` versus `[tool.black]`
- both present, or neither present, is an error naming the key
- the migration note: **a migrating repo adds `[tool.ruff.format]` even if empty** — that
  empty table is the signal, and detection is deliberately unchanged from it

*Open question for Marcus: confirm a new subsection there is the right home.*

## Release note

**The first `run_format_code` after this upgrade will reformat** if the tool-env formatter
version differs from what the project env had. This is a real, user-visible effect of the
env move and needs recording somewhere durable. The repo has no `CHANGELOG`.

*Open question for Marcus: where does this go?* Put it in the PR description at minimum,
and mention that each step now reports its formatter version so any future drift is
visible rather than mysterious.

## Regenerated graph

`docs/architecture/dependencies/pydeps_graph.dot` and `.svg` carry
`formatter.black_runner` / `formatter.isort_runner` nodes and now need
`formatter.ruff_runner` and `formatter.common`. Regenerate via `tools/pydeps_graph.*` —
read the script first, and check `docs/architecture/dependencies/readme.md` for the
documented procedure. Do not hand-edit the generated files.

Two lines of justification in chat before running it, per the repo's Bash discipline.

## TESTS

Only one code change here: `tests/test_server_params.py:798` is a docstring. Everything
else is documentation.

Before committing, grep for stragglers:

```
search_files(pattern="black and isort|isort, black|isort then black|black, isort")
search_files(pattern="five console-script|five `python -m`|those five|five names")
```

Re-read every hit against the "do not change" table above. Two of the "five" hits are
supposed to survive.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass, the greps return only the three
deliberate survivors, and `check_file_size` is clean.

Finally: `delete_directory(".scratch", recursive=True)` if any earlier step left one. CI
blocks a PR carrying one.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_8.md`.
>
> Sweep the documentation for the env move. Two distinct kinds of edit: **counts** ("five
> console-script tools" → seven, "five `python -m` tools" → three) and **enumerations**
> (every place naming black and isort as project-env tools, or naming the formatters as
> "black, isort"). The step file lists every location.
>
> Three things must **not** change: "five registrars" in `architecture.md` lines 163 and
> 252 and in `tests/test_registrars.py`; `architecture.md:274`, which is this repo's own
> workflow list and keeps black; and `architecture.md:173`, the probe bullet sitting next
> to an edited line. Do not touch `tach.toml`.
>
> Update `formatter_tools.py`'s MCP tool docstring — it is user-visible to agents and must
> describe all four steps and say the default comes from the project's configuration.
>
> In `docs/pyproject-configuration.md`, update the `run_format_code` timeout row (3 ×
> `ruff-timeout` on a ruff repo, since `ruff_imports` is two invocations) and add a
> "Formatter selection" section for the new `[tool.mcp-tools-py] formatter` key, including
> the note that a migrating repo adds `[tool.ruff.format]` even when empty.
>
> Regenerate `docs/architecture/dependencies/pydeps_graph.dot` and `.svg` via
> `tools/pydeps_graph.*` — read the script and `dependencies/readme.md` first, justify the
> Bash call in chat, and do not hand-edit the output.
>
> Before committing, grep for stragglers with the two patterns in the step file and check
> each hit against the do-not-change table.
>
> Put the release note — the first `run_format_code` after upgrade may reformat, because
> the formatter now comes from the tool env — in the PR description, and flag to Marcus
> that it may want a more durable home.
>
> Delete `.scratch/` if any earlier step left one.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
