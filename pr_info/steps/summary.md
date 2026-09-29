# Issue #235 — `run_format_code`: ruff format support, formatters from the tool env

## Goal

A repo that has migrated to `ruff format` must stop having black re-applied by every
agent session. Today `run_format_code` defaults to `["isort", "black"]` unconditionally,
so on a migrated repo each pre-commit run silently reverts the migration.

Four changes deliver that:

1. Two new steps, `ruff_imports` and `ruff_format`.
2. One resolution rule deciding which steps run when `steps is None`, shared by the
   runner layer and the MCP layer.
3. black and isort move from the project env to mcp-tools-py's own tool env, joining
   ruff, bandit, vulture, tach and lint-imports.
4. `python_executable` becomes accepted-and-ignored on the runner layer, so mcp_coder
   keeps working unchanged across the release.

---

## Architectural / design changes

### Environment model — black and isort change sides

`utils/tool_context.py` states the rule: a tool that must **import the project's
dependencies** runs in the project env; a tool that only **reads source text** runs from
mcp-tools-py's own env. Formatters only read source text, so black and isort are on the
wrong side of that rule today, and mcp-tools-py already declares both as its own
dependencies.

After this issue:

| | Before | After |
|---|---|---|
| project env (`--python-executable`) | pytest, pylint, mypy, black, isort | pytest, pylint, mypy |
| tool env (mcp-tools-py's own) | ruff, bandit, vulture, tach, lint-imports | + black, isort |

Counts change accordingly: **five console-script tools → seven**, **five `python -m`
tools → three**. Everything downstream of `TOOL_MODULES` (`CONSOLE_SCRIPT_TOOLS`,
`PROBED_MODULES`, `TOOL_DISTRIBUTIONS`, and the tests parametrized over them) follows
from setting two dict values to `None`.

> ⚠️ "five **registrars**" in `docs/architecture/architecture.md` lines 163 and 252 and
> in `tests/test_registrars.py` is an unrelated count and must not be touched.

**Release risk:** the first `run_format_code` after upgrade reformats if the tool-env
formatter version differs from what the project env had. This needs a release note, and
is why each step reports the version it ran.

### One defaulting rule, two entry points

`formatter/runner.py::run_format_code` (importable, used by mcp_coder) and the
MCP-registered `formatter/formatter_tools.py::run_format_code` each have their own
`steps or DEFAULT_STEPS` site today. Both are replaced by a call to a single
`resolve_steps(project_root)`, so a direct runner caller and an MCP caller get the same
answer.

Resolution order:

1. `[tool.mcp-tools-py] formatter = "ruff" | "black"` wins when present.
2. Otherwise detect from `pyproject.toml`: `[tool.ruff.format]` present and `[tool.black]`
   absent → ruff; `[tool.black]` present and `[tool.ruff.format]` absent → black;
   **both → error**; **neither → error**.

Both error messages name the key *and* the file, so the fix is obvious from the message.
Never guess between two formatters.

### Step names are no longer tool names

`isort` and `black` happen to be both a step name and a tool name, which is why
`formatter_tools.py` can pass a step straight to `is_tool_available()`,
`resolve_timeout()` and `check_line_length_conflicts()`. `ruff_format` and `ruff_imports`
both map to tool `ruff`, so a `_STEP_TOOLS` mapping becomes load-bearing.

### `parse_ruff_json_output` moves to `utils/`

Two unrelated tool implementations now need it. `tach.toml` puts `formatter` and
`code_checker_ruff` in the same `tool_implementation` layer and `formatter.depends_on`
lists only `utils` and `log_utils`, so importing it across would fail `run_tach_check`.
Moving it down to `utils/` means both consumers depend downward only.
**No same-layer `tach.toml` edge is added.**

`code_checker_ruff/__init__.py` **drops** both symbols from its imports and `__all__` —
one home, not a home plus a re-export.

### `steps=[]` is a caller error

Both defaulting sites are `steps or DEFAULT_STEPS` today, so `[]` silently means "the
defaults". Switching to a `steps is None` check would turn it into a silent zero-step
run. `validate_steps` therefore rejects an empty list at both entry points.

### Simplifications applied

These reduce complexity relative to a literal reading of the issue, without changing any
acceptance criterion:

- **`resolve_steps` lives in `runner.py`**, not a new module. The issue asks for a
  *standalone function* in `formatter/`; `runner.py` already owns `validate_steps` and
  the step tables, and `formatter_tools.py` already imports from it.
- **`DEFAULT_STEPS` is deleted**, not deprecated. Verified: its only consumers are the
  two defaulting sites this issue replaces. mcp_coder imports `FormatterResult`,
  `run_black` and `run_isort` — never `DEFAULT_STEPS`.
- **One `utils/ruff_parsing.py`**, not a `models.py` + `parsers.py` pair. Each source
  module holds exactly one symbol; mirroring the split preserves structure that existed
  only by convention. Both source modules are deleted.
- **Versions read from the environment the binary came from**, not from a `--version`
  subprocess per step. The environment is threaded from the caller — `formatter_binary(name,
  environment)`, with the MCP layer passing `self.context.tool_environment`, which is
  injectable and is what `tests/conftest.py:78` replaces. `None` falls back to the cached
  `tool_environment()` accessor in `utils/python_environment.py`, which is also
  `ToolContext.tool_environment`'s `default_factory`. `formatter_version(distribution,
  environment)` takes that **same** environment: `None` or the running interpreter is
  answered by `importlib.metadata.version()`, since the running process then *is* that
  environment; any other environment is answered from the cached
  `get_environment_info(interpreter).distributions` probe. So the banner always names the
  distribution whose console script was invoked, even under an injected environment. This
  removes four subprocesses per run and four timeout interactions.
  *Deviation from the issue text, which specifies `--version` subprocesses. The
  acceptance criterion ("Each step's `output` names the formatter version it ran") is met
  identically. Revert path if the lookup ever stops matching the invoked binary: swap
  `formatter_version()` for a `--version` subprocess inside the step's timeout budget —
  one function, one call site per runner.*
  The banner **does** change `FormatterResult.output` text for `black` and `isort`. The
  "existing explicit `["isort", "black"]` behaviour unchanged" criterion covers the steps
  that run and their `success`, `files_changed` and `unparsable_files`, not `output`
  content.
- **Shared runner boilerplate** in `formatter/common.py`, created in step 2 for
  `formatter_binary` and extended in steps 3 and 4. It cannot live in `runner.py`, which already
  imports both runner modules — that would be a circular import. `black_runner.py` and
  `isort_runner.py` each carry an identical `_truncate_output` and an identical
  timed-out / execution-error / combine-stdout-and-stderr preamble; two more runners
  would make four copies. Two small functions, no base class.
- **`per-file-ignores` matching stays literal.** The notice is advisory, not a gate;
  implementing glob semantics would be the largest complexity in the issue for the
  smallest payoff. A leading-literal-segment prefix match satisfies the acceptance
  criterion, and a false negative just means no notice — the status quo.

### Behaviour that is deliberately asymmetric between the two ruff steps

| | `ruff_format` | `ruff_imports` |
|---|---|---|
| command | `ruff format [--check] <dirs>` | `ruff check --select I [--fix] <dirs>` |
| write mode | one invocation | **two** — JSON pre-check, then `--fix` |
| `files_changed` | empty in write mode; parsed in `--check` only | from the pre-check `fixable` messages |
| parse errors | exit 2 + `error: Failed to parse` on stderr, plus the `invalid-syntax:` marker paths in `--check` mode | JSON syntax-error diagnostics |

Both runners report `files_changed` and `unparsable_files` as **project-relative paths with
forward slashes**, via one `relative_path` helper in `formatter/common.py` that
relativizes **only absolute** paths — ruff prints relative to its `cwd=project_dir` and
`parse_ruff_json_output` has already relativized `filename`, so an unconditional
`os.path.relpath` would re-anchor them against the process's cwd.
`ruff_imports` check-mode `success` is keyed on *any* `I` diagnostic, not only the fixable
subset, so an unfixable unsorted import still fails the check.

`ruff format` does **not** sort imports, so `ruff_imports` is load-bearing, not
belt-and-braces. `ruff format` write mode prints only `N files reformatted` and never
names files. A `--check` parser must key on the **marker line**
(`unformatted:` / `invalid-syntax:`), never on `-->`, or unparsable files are silently
recorded as "would be reformatted". The `invalid-syntax:` path is **recorded in
`unparsable_files`**, not discarded, or `--check` mode fails while naming nothing. `ruff check --select I --fix` exits 1 for both a
parse error and an ordinary unfixed violation and writes nothing to stderr, so its exit
code cannot discriminate — hence the JSON route.

---

## Files created

| Path | Purpose |
|---|---|
| `src/mcp_tools_py/utils/ruff_parsing.py` | `RuffMessage` + `parse_ruff_json_output`, moved down a layer |
| `src/mcp_tools_py/formatter/common.py` | `formatter_binary` (step 2); `truncate_output`, `combine_output`, `formatter_version`, `version_line` (step 3); `relative_path` (step 4) |
| `src/mcp_tools_py/formatter/ruff_runner.py` | `run_ruff_format`, `run_ruff_imports` |
| `tests/test_formatter_common.py` | Step 3 |
| `tests/test_ruff_format_runner.py` | Step 4 |
| `tests/test_ruff_imports_runner.py` | Step 5 |
| `tests/test_formatter_resolution.py` | Step 6 |
| `tests/test_formatter_integration.py` | Step 7 |
| `docs/upgrade-notes.md` | Step 8 — the reformat-on-first-run release note |

## Files deleted

| Path | Reason |
|---|---|
| `src/mcp_tools_py/code_checker_ruff/models.py` | Sole symbol `RuffMessage` moved to `utils/ruff_parsing.py` |
| `src/mcp_tools_py/code_checker_ruff/parsers.py` | Sole symbol `parse_ruff_json_output` moved likewise |

## Files modified

**Source**

- `src/mcp_tools_py/code_checker_ruff/__init__.py` — drops both symbols from imports and `__all__`
- `src/mcp_tools_py/code_checker_ruff/reporting.py` — `RuffMessage` import (5 annotation uses)
- `src/mcp_tools_py/code_checker_ruff/runners.py` — `parse_ruff_json_output` import; calls at lines 81, 132, 162
- `src/mcp_tools_py/utils/environment_info.py` — `TOOL_MODULES`; `_failed` docstring count
- `src/mcp_tools_py/utils/python_environment.py` — cached `tool_environment()` accessor, the default when no environment is passed in
- `src/mcp_tools_py/utils/tool_context.py` — `tool_environment` `default_factory`; module docstring, class docstring, `is_tool_available`, `unavailable_message`
- `src/mcp_tools_py/utils/project_config.py` — new public `read_pyproject_tool_tables(Path)`, the single `pyproject.toml` reader `per_file_ignores_notice`, `resolve_steps` and `_read_mcp_tools_section` share. Added in **step 5**, its first consumer; step 6 reuses it and adds no second reader
- `src/mcp_tools_py/formatter/__init__.py` — exports `resolve_steps`, drops `DEFAULT_STEPS`; module docstring
- `src/mcp_tools_py/formatter/runner.py` — `resolve_steps`, `_STEP_TOOLS`, `_BLACK_STEPS`/`_RUFF_STEPS`, `validate_steps`, deprecated `python_executable`, keyword-only `environment` passed through to the runners
- `src/mcp_tools_py/formatter/formatter_tools.py` — `environment=self.context.tool_environment`, resolution call, step→tool mapping, timeout dict, MCP docstring, `_unparsable_block` wording (the isort-only "Windows, piped stdout" explanation is wrong for a ruff syntax error)
- `src/mcp_tools_py/formatter/black_runner.py` — tool-env console script; deprecated param; shared helpers
- `src/mcp_tools_py/formatter/isort_runner.py` — same
- `src/mcp_tools_py/server.py` — docstrings at lines 39, 101; count at line 73

**Tests**

- `tests/conftest.py` — no edit expected; `CONSOLE_SCRIPT_TOOLS` is derived
- `tests/test_code_checker_ruff/test_parsers.py` — import only (11 call sites), file stays put
- `tests/test_code_checker_ruff/test_reporting.py` — `RuffMessage` import
- `tests/test_black_runner.py`, `tests/test_isort_runner.py` — command shape, version line
- `tests/test_project_config.py` — `read_pyproject_tool_tables` (step 5)
- `tests/test_formatter_runner.py` — `resolve_steps`, empty-list rejection, ignored `python_executable`
- `tests/test_formatter_tools.py` — formatter declaration fixture; black-unavailable via `tool_environment.binary`
- `tests/test_server_params.py` — docstring count at line 798
- `tests/test_tool_context.py` — follows `CONSOLE_SCRIPT_TOOLS`; verify

**Docs**

- `README.md` — lines 44, 115, 149, 158, 198, 203, 205, 460
- `docs/architecture/architecture.md` — lines 11, 19, 58, 69-70, 165, 174, 230, 233
- `docs/pyproject-configuration.md` — line 45, plus a new "Formatter selection" section (the key list at line 36 needs no edit)
- `docs/README.md` — one line linking `upgrade-notes.md` under Configuration
- `docs/architecture/dependencies/pydeps_graph.dot` and `.svg` — regenerated

**Unchanged on purpose**

- `docs/architecture/architecture.md:274` — this repo's own workflow list; mcp-tools-py
  keeps black until step 6 of the migration sequence
- `docs/architecture/architecture.md:173` — the `probe.py` bullet, adjacent to an edited line
- `docs/architecture/architecture.md` lines 163, 252 and `tests/test_registrars.py` — "five registrars"
- `tach.toml` — no new edge
- `utils/tool_context.py::resolve_timeout` and `utils/project_config.py::ToolName` — already generic / already include `ruff`

---

## Step sequence

Ordered so each commit is independently verifiable, and so an availability regression
surfaces before any new-feature code is in the tree.

| Step | Commit |
|---|---|
| 1 | Move `RuffMessage` + `parse_ruff_json_output` into `utils/ruff_parsing.py` |
| 2 | black and isort resolve from the tool env |
| 3 | `formatter/common.py`: shared output helpers + version reporting |
| 4 | `run_ruff_format` |
| 5 | `run_ruff_imports`, plus the shared `read_pyproject_tool_tables` reader |
| 6 | `resolve_steps`, step→tool mapping, both entry points wired |
| 7 | End-to-end acceptance tests |
| 8 | Documentation sweep + regenerated dependency graph |

## Definition of done for every step

```
mcp__mcp-tools-py__run_format_code
mcp__mcp-tools-py__run_pylint_check
mcp__mcp-tools-py__run_pytest_check   extra_args=["-n", "auto"]
mcp__mcp-tools-py__run_mypy_check
mcp__mcp-tools-py__run_tach_check
mcp__mcp-tools-py__run_lint_imports_check
```

All must pass. One commit per step. No `.scratch/` directory left behind — CI blocks any
PR carrying one.

## Decisions taken during planning

1. **The release note goes in a new `docs/upgrade-notes.md`**, linked from
   `docs/README.md` under Configuration, and is repeated in the PR description. The repo
   has no `CHANGELOG`, and a user-visible "your first `run_format_code` after upgrading
   may reformat" warning needs a durable home that is not a PR body. One short file, one
   index line; later notes append to it. Step 8 owns both edits.
2. **`docs/pyproject-configuration.md` gains a "Formatter selection" section.**
   `[tool.mcp-tools-py] formatter` is the first non-timeout key in that section, but the
   document is already the documented home for `[tool.mcp-tools-py]` as a whole — its
   `docs/README.md` entry describes it as covering the section, not only timeouts — so
   the key belongs there rather than in a new file. Step 8 owns it.
