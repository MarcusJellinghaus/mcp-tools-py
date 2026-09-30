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
`_fixed_version_line` (step 3, reused by steps 4 and 5) and `_declare_formatter` (step 6).

## `test_tool_unavailable_returns_error` deletes the black stub (plan review 2)

`PythonEnvironment` is a frozen dataclass, so patching `binary` on the instance raises
`FrozenInstanceError`. The rewrite deletes the black stub from the `tool_context` fixture's
script directory, as the fixture docstring documents.

## `per-file-ignores` prefix matching stays (plan review 2, rejected change)

Dropping the prefix matching was proposed and rejected: the issue's Decisions table
requires the notice to name the covered directories.
