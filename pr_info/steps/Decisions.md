# Decisions

## Version reporting follows the issue literally (plan review, round 5)

Each formatter step reports its version by running `<binary> --version` on the same
resolved binary the step invokes, inside that step's own timeout budget. A failure to
determine the version (timeout, execution error, unparsable output) yields `"unknown"` and
never fails the step. This replaces the earlier package-metadata lookup
(`importlib.metadata` / `get_environment_info(...).distributions`) and its "deviation from
the issue text" note. Environment threading stays, because `formatter_binary(name,
environment)` still needs it to resolve the binary.

## `per-file-ignores` keys with no leading literal segment are skipped (plan review 2, round 1)

When a glob key has no leading literal segment (`"*.py"`, `"**/test_*.py"`), the prefix is
empty and `per_file_ignores_notice` skips the key: no notice. This is a documented false
negative, consistent with "a false negative just means no notice".

## Ruff floor raised to 0.16.8 (user decision)

`pyproject.toml` requires `ruff>=0.16.8` instead of `>=0.9.0`. The step 4 and step 5
parsers depend on output verified against 0.16.8: the `ruff format --check` markers
`unformatted:` / `invalid-syntax:` (older ruff printed `Would reformat: <path>`) and the
syntax-error JSON diagnostic.

## Syntax-error diagnostic predicate follows the probe (user-requested probe)

Probed against the installed ruff 0.16.9: the syntax-error JSON diagnostic has
`code == "invalid-syntax"`, not `null`, and a syntax error makes the `ruff check --select I`
pre-check and `--fix` run exit 1, not 2. Step 5 therefore uses
`not m.code or m.code == "invalid-syntax"` as its one syntax-error predicate, and the
"stop and report if exit 2" probe instruction becomes a stated, verified fact.

## ruff and vulture join the definition of done (plan review 2)

CI runs `ruff check src tests` and `vulture src tests vulture_whitelist.py
--min-confidence 60`, so every step's checks include `run_ruff_check` and
`run_vulture_check`. Names vulture cannot see being used go into `vulture_whitelist.py` as
bare names, following the existing autouse-fixture entries: `python_executable` (step 2),
`_fixed_formatter_binary` (step 2, reused by steps 4 and 5), `_fixed_version_line` (step 3,
reused by steps 4 and 5) and `_declare_formatter` (step 6).

## `test_tool_unavailable_returns_error` deletes the black stub (plan review 2)

`PythonEnvironment` is a frozen dataclass, so patching `binary` on the instance raises
`FrozenInstanceError`. The rewrite deletes the black stub from the `tool_context` fixture's
script directory, as the fixture docstring documents.

## `per-file-ignores` prefix matching stays (plan review 2, rejected change)

Dropping the prefix matching was proposed and rejected: the issue's Decisions table
requires the notice to name the covered directories.

## Plan review 3

- **Runner tests pin binary lookup.** The existing black/isort runner tests mock
  `execute_command` only; after step 2 they would resolve the binary through
  `PythonEnvironment.resolve()` on the real `sys.executable`. An autouse
  `_fixed_formatter_binary` fixture patches `<runner module>.formatter_binary` in the
  black, isort and both ruff runner test modules; unmocked tests restore the real function.
- **Step 8 grep criterion.** No survivor count. Every remaining hit outside `pr_info/` is a
  listed do-not-change line or a line rewritten in step 8.
- **Step 8 covers the stale `architecture.md` module bullets:** a new
  `utils/ruff_parsing.py` bullet, the `utils/project_config.py` bullet, and the
  `formatter/` bullet. Line 173 still does not change.
- **`ruff format` stderr path regex** is `error: Failed to parse (.+?):\d+:\d+`, so a
  drive-letter colon does not cut an absolute Windows path.
- **Churn test uses stdlib-only imports**, so first-party / third-party classification in a
  tmp project cannot produce a spurious diff.
- **No `ImportError` test for the old `code_checker_ruff` import path.** It tests a
  decision, not behaviour; the deleted modules enforce it.
- **Rejected:** returning copies from `resolve_steps` — speculative.

## Plan review 4

- **`per-file-ignores` codes match exactly.** Only `"ALL"`, `"I"` or `I` followed by digits
  (`^I\d*$`) trigger the notice; a bare `I` prefix would also match `INP001`, `ICN`, `ISC`
  and `INT`. Step 5 adds an `INP001` no-notice test.
- **`extend-per-file-ignores` is not read.** Listed as a known false negative next to the
  empty-prefix key.
- **`test_invalid_step_raises_valueerror` is tightened** to match
  `Invalid formatter steps: ['ruff']`, since `"ruff"` alone matches the valid-steps list
  after step 6.
- **`README.md:44` needs no edit.** The issue lists it, but it names only
  `run_format_code`; recorded as verified in step 8's do-not-change table.
- **`utils/ruff_parsing.py` gets a module docstring** — ruff's `D` rules apply to `src/`.
- **Rejected:** skipping the `--fix` pass when the pre-check finds nothing fixable — an
  optimisation; the two-invocation design follows the issue.

## Plan review 5

- **Launch-mode change recorded, not acted on.** Moving black/isort from `python -m` to
  the console script changes how mcp-coder-utils launches them (file-redirected Python
  isolation versus piped output with `PYTHONUTF8=1`). A Windows probe found identical
  results in both modes, so step 2 documents it and adds no code.
- **`_unparsable_block` uses neutral wording**, `"The formatter could not parse these
  files."`. The probe reproduced isort's skip without piped stdout, so no cause is asserted.
- **Step 4's ` --> ` header parser uses `(.+?):\d+:\d+`**, the same anchor as the stderr
  regex, so absolute Windows paths survive. Test 7c covers it.

## Plan review 6

- **Step 8 do-not-change table covers every current grep hit.** Added `CONTRIBUTING.md:252`,
  `.claude/CLAUDE.md:3`, `utils/project_config.py:162` and `tests/test_formatter_tools.py:269`,
  all correct as written. `README.md:198` and `:205` take an enumeration edit as well as the
  count edit.
- **Churn-test pseudocode** uses positional arguments and `list(results) == [...]`.
- **Runners resolve the environment once:** `env = environment or PythonEnvironment.resolve()`,
  used for both the binary lookup and the missing-binary message's `env.bin_dir`.
- **`per-file-ignores` overlap compares path components**, not string prefixes; step 5 adds
  a `tests2/**` versus `tests` no-notice test.
- **Step 3 wording:** `truncate_output` moves verbatim; `combine_output` is extracted from
  inline code; the timed-out / execution-error early returns are not extracted.

## Continue past unparsable-file failures (user decision, simplified by supervisor)

The user chose "keep going when the only failure is unparsable files", so `ruff_format`
still formats the remaining files after `ruff_imports` hits a syntax error. The
supervisor simplified the implementation to "keep going when the failed step reported
unparsable files": the write-mode loop breaks on
`not result.success and not result.unparsable_files` (step 6); check mode is unchanged.
This avoids a new `FormatterResult` field (the issue's Decisions table already avoids
mcp_coder-visible `FormatterResult` changes) and per-runner flag logic. Continuing past a
step that also failed for another reason is harmless: the steps are independent and
idempotent, and that step still reports `success=False`. Timeouts, execution errors,
missing binaries, ruff exit 2 and malformed JSON never populate `unparsable_files`, so
they still stop the run; step 5 now states `unparsable_files=[]` explicitly on its
fix-run exit 2 and early returns. Behaviour change for black repos: black now runs after
an isort step that exited 0 but reported unparsable files. Step 7
test 6a now expects both ruff steps in the result, both `success=False` with
`src/bad.py` in `unparsable_files`, and the good file sorted and reformatted; the separate
`steps=["ruff_format"]` write-mode test is dropped as redundant.

## Plan review 7

- **Release note gains two points.** The known limitation: console scripts are looked up
  only in the tool-env interpreter's directory, which the move now extends to black and
  isort, so `pip install --user` and some conda layouts report "not available". No
  fallback is added; the issue chose one lookup rule for all four steps. And version
  drift: a project whose CI runs its own pinned black/isort should keep ranges compatible
  with mcp-tools-py's, as `README.md:152` advises.

## `ruff format --check` reads JSON (supervisor simplification, based on a probe)

A probe on ruff 0.16.9 showed `ruff format --check --output-format json` emits one
diagnostic per file with `code == "unformatted"` or `code == "invalid-syntax"`, which
`parse_ruff_json_output` parses unchanged. It also showed the default text output is not
stable: `[tool.ruff] output-format = "concise"` or `RUFF_OUTPUT_FORMAT=concise` removes the
line-leading markers and ` --> ` headers, while an explicit `--output-format` flag wins
over both. Step 4's check mode therefore passes `--output-format json` and keys
`files_changed` / `unparsable_files` on the diagnostic code. The marker-line parser,
`_ARROW_PATH` and its test 7c are removed (superseding the plan review 5 bullet on the
` --> ` header parser); write mode keeps the stderr `_FAILED_TO_PARSE` regex. The issue's
"key on the marker line" warning concerned text parsing and is satisfied by structured
output. `_is_syntax_error` and `_render_diagnostics` are defined once in `ruff_runner.py`
in step 4 and reused by step 5, and step 5's write-mode `output` uses `combine_output`.
