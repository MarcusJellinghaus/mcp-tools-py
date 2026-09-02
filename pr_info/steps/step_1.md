# Step 1 — `[tool.mypy]` owns the flag set

One commit. The config change and the flag removal cannot be split: writing the config
first is a no-op, removing the flags first makes this repo's type checking silently lax.

## WHERE

| File | Change |
|------|--------|
| `pyproject.toml` | `[tool.mypy]` gains two keys |
| `src/mcp_tools_py/code_checker_mypy/runners.py` | Main removal |
| `src/mcp_tools_py/code_checker_mypy/reporting.py` | Signature + coercion |
| `src/mcp_tools_py/checker_tools/mypy_tool.py` | MCP surface + docstring |
| `tests/test_code_checker_mypy/test_runners.py` | 2 call sites + new test |
| `tests/test_code_checker_mypy/test_integration.py` | 8 call sites + replaced test |
| `tools/mypy.bat`, `tools/checks2clipboard.bat`, `.github/workflows/ci.yml`, `.github/workflows/upstream-mypy-check.yml`, `CONTRIBUTING.md` | The five hardcoded flag sites |
| `README.md`, `docs/architecture/architecture.md`, `CONTRIBUTING.md` | Text made accurate by the removal |

## WHAT

### `pyproject.toml` — `[tool.mypy]` (currently lines 102-114)

Add, keeping the existing keys and the `[[tool.mypy.overrides]]` blocks untouched:

```toml
strict = true
warn_unreachable = true
```

`mypy_path`, `namespace_packages` and `explicit_package_bases` are already present, so the
import-resolution half of the migration is already satisfied here.

### `runners.py`

New signature (`strict` and `config_file` gone, `follow_imports` now optional):

```python
@log_function_call
def run_mypy_check(
    project_dir: str,
    python_executable: str,
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str | None = None,
    cache_dir: str | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> MypyResult:
```

Delete:

- `STRICT_FLAGS` (`:19-33`) and the `if strict:` block that applies it (`:104-106`)
- `--namespace-packages` and `--explicit-package-bases` from the command (`:100-101`)
- the `config_file` guard (`:108-109`)
- the `"strict": strict` log field (`:131`)
- **only** the `env["MYPYPATH"] = ...` assignment (`:137`)

Keep `env = os.environ.copy()` (`:136`) and the `env=env` argument (`:143`) — the dict is
still needed, because `MYPY_NUM_WORKERS` is popped from it.

### `reporting.py`

`get_mypy_prompt` drops `strict` (`:82`, docstring `:96`, pass-through `:111`) and drops
the `follow_imports or "normal"` coercion (`:114`), passing `follow_imports=follow_imports`
straight through.

### `mypy_tool.py`

Drop `strict: bool = True` (`:24`), its docstring block (`:34-36`), the `"strict": strict`
log field (`:89`) and the pass-through (`:99`). The docstring opens with the policy
statement — this is the text every connected client reads:

```
"""Run mypy type checking on the project code.

mypy reads the project's `[tool.mypy]` configuration; the server adds only
output-formatting flags. A project with no mypy config is checked at mypy's
defaults and will report "passed".
```

The two internal docstrings (`runners.py`, `reporting.py`) only lose their `strict:`
line — they stay plain parameter lists. Restating the policy in all three re-creates the
three-way drift the issue documents.

### The five hardcoded flag sites — all become `mypy src tests`

| File | Line | Now |
|------|------|-----|
| `tools/mypy.bat` | 2 | `python -m mypy src tests` |
| `tools/checks2clipboard.bat` | 144 | `python -m mypy src tests > checks_output.txt 2>&1` |
| `.github/workflows/ci.yml` | 113 | `{name: "mypy", cmd: "mypy --version && mypy src tests"}` |
| `.github/workflows/upstream-mypy-check.yml` | 38 | `run: mypy src tests`; also retitle step `name:` (`:37`) and the header comment (`:4`), which both say `mypy --strict` |
| `CONTRIBUTING.md` | 217 | `python -m mypy src tests` |

Leave both `.bat` files' cwd handling alone: they rely on the invoker's cwd, and after
this change a wrong cwd still fails loudly because the relative `src tests` targets do
not resolve either.

### Text made inaccurate by the removal

- `README.md:77` — delete the `strict` table row.
- `README.md:427` — "Strict-mode type checking with configurable error codes" →
  type checking driven by the project's `[tool.mypy]`.
- `CONTRIBUTING.md:121` — "(mypy strict compliance)" → the config's settings.
- `docs/architecture/architecture.md:253` — "mypy (strict)" → "mypy".

## HOW

`execute_command` is imported into `runners.py` from
`mcp_tools_py.utils.subprocess_runner` (never `mcp_coder_utils` directly — `.importlinter`
enforces this). Tests patch it at `mcp_tools_py.code_checker_mypy.runners.execute_command`.

`@log_function_call` and the `@mcp.tool()` registration are unchanged.

## ALGORITHM — command construction in `runners.py`

```
command = [python, "-m", "mypy", "--output", "json", "--no-color-output",
           "--show-column-numbers", "--show-error-codes"]
if cache_dir:            command += ["--cache-dir", cache_dir]
if follow_imports:       command += ["--follow-imports", follow_imports]
for code in disable_error_codes or []:  command += ["--disable-error-code", code]
command += mypy_targets
env = os.environ.copy(); env.pop("MYPY_NUM_WORKERS", None)
```

Every flag left here is outside `OPTIONS_AFFECTING_CACHE`, which is what lets the server
share a cache with a plain `mypy` run.

## DATA

`MypyResult` (`models.py`) is unchanged. `get_mypy_prompt` still returns `str | None`.

## TESTS (write first)

### 1. `test_runners.py` — the command line and env, one parametrized test

No test anywhere currently asserts mypy's constructed command line. Fake
`execute_command`, capture `command` and `env`, assert in one place:

```python
def _capture(tmp_path: Path, **kwargs: object) -> tuple[list[str], dict[str, str]]:
    """Run run_mypy_check with execute_command faked; return (command, env)."""
```

The fake returns `CommandResult(return_code=0, stdout="", stderr="", timed_out=False)`.
`run_mypy_check` validates that target directories exist, so use `tmp_path` with
`target_directories=["."]`.

Assertions:

| Case | Expect |
|------|--------|
| default call | no `--strict`, no `--namespace-packages`, no `--explicit-package-bases`, no `--follow-imports` |
| default call | `"MYPYPATH" not in env`, `"MYPY_NUM_WORKERS" not in env` |
| ambient `MYPY_NUM_WORKERS` set via `monkeypatch.setenv` | still absent from `env` |
| `follow_imports="silent"` | `["--follow-imports", "silent"]` present |
| `disable_error_codes=["import", "arg-type"]` | one `--disable-error-code` pair each |

### 2. `test_integration.py` — config drives the outcome

Replaces `test_mypy_strict_vs_non_strict` (`:191-221`), whose subject disappears with the
`strict` parameter and whose unannotated fixture made the `>=` assertion vacuous anyway.
This is also the behaviour-neutrality test the migration needs.

Two temp projects, same unannotated source (`def func(x, y): return x + y`), real mypy:

- one with `pyproject.toml` containing `[tool.mypy]\nstrict = true` → reports
  `no-untyped-def`
- one with no config at all → no messages, `return_code == 0`

mypy discovers `pyproject.toml` from cwd, and the runner passes `cwd=project_dir`.

### 3. Drop `strict=` from the 10 existing call sites

`test_integration.py:48,86,109,146,170,180,208,216` and `test_runners.py:15,40`.
The remaining bare-`TemporaryDirectory` tests now run at mypy's defaults, since those
temp dirs have no config. Their fixtures are annotated, so plain mypy should still catch
them — **but this was reasoned, not run. Re-run and confirm; if any now passes vacuously,
add a minimal `[tool.mypy]` to that fixture rather than weakening the assertion.**

## VERIFICATION

```
mcp__mcp-tools-py__run_format_code
mcp__mcp-tools-py__run_pylint_check
mcp__mcp-tools-py__run_pytest_check   extra_args: ["-n", "auto"]
mcp__mcp-tools-py__run_mypy_check
mcp__mcp-tools-py__run_lint_imports_check
```

`run_mypy_check` must pass **through the new code path** — i.e. reading this repo's
freshly migrated `[tool.mypy]` with no flags of its own. That is the migration's own
proof. Expect it to be clean: the server has been enforcing these flags all along.

Additional manual check the issue asks for: **re-verify the flag equivalence on the
declared floor, `mypy>=1.13.0`** (`pyproject.toml:29`), not only on the installed
version. If that cannot be done in this environment, say so explicitly in the PR rather
than implying it was checked.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`, then implement step 1.
>
> This is one commit and it must be atomic: `pyproject.toml` gains `strict = true` and
> `warn_unreachable = true` in the **same** commit that removes `STRICT_FLAGS` and the
> five hardcoded `--strict` command lines. Do not split them in either direction.
>
> Work test-first: write the command-line/env assertion test and the config-driven
> integration test before touching `runners.py`, and confirm they fail for the right
> reason.
>
> Removing `strict` from `run_mypy_check` is a wire-visible breaking change to a
> published MCP parameter. It is deliberate and there is no deprecation window — note it
> in the PR description, since this repo has no CHANGELOG.
>
> Keep `env = os.environ.copy()` and the `env=env` argument. Drop only the `MYPYPATH`
> assignment and add `env.pop("MYPY_NUM_WORKERS", None)`.
>
> Use MCP tools for all file and git operations. Run `run_format_code` before committing,
> then pylint, pytest (`-n auto`), mypy and lint-imports.
