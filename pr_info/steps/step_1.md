# Step 1 — probe.py: stdlib info field + scope subcommand

Part of the plan in `pr_info/steps/summary.md` (issue #228). Read that file first.

## Precondition

`src/mcp_tools_py/utils/target_scripts/probe.py` still has `_info()`, `main()` and
`_USAGE` matching the current repository content (no unrelated rewrite in progress).
If it does not, write one line to `pr_info/.blocked.txt` describing the mismatch and
stop.

## WHERE

- `src/mcp_tools_py/utils/target_scripts/probe.py` (implementation)
- `tests/test_environment_info.py`, class `TestProbeScript` (tests — real subprocess,
  no mocking, matching that class's existing style)

## WHAT

- Modify `_info(module_names: list[str]) -> dict[str, object]`: add key
  `"stdlib": sysconfig.get_paths()["stdlib"]` to the returned dict (next to
  `"sys_path"`). `sysconfig` is already imported.
- Add `_scope(name: str) -> str`: resolve `name` to its directory.
- Modify `main(argv: list[str]) -> int`: add a `scope NAME` branch.
- Update `_USAGE` to mention `probe.py scope NAME`.

## HOW

No new imports needed (`importlib.util`, `os.path`, `sysconfig`, `sys` already
imported). `_scope` raises `LookupError` on failure; `main()` catches it at the call
site and reports it the same way the existing `locate`/`source` branches report
their own failures (message, non-zero exit) — it must not propagate.

## ALGORITHM (`_scope`)

```
spec = importlib.util.find_spec(name)   # may raise -> re-raise as LookupError
if spec is None: raise LookupError(f"module '{name}' not found")
locations = list(spec.submodule_search_locations or [])
if locations: return locations[0]              # package
if spec.origin and isfile(spec.origin): return dirname(spec.origin)  # module
raise LookupError("no file location")
```

In `main()`: `if len(argv) == 3 and argv[1] == "scope":` call `_scope(argv[2])`,
write the directory to stdout and return 0 on success; on `LookupError`, print the
message to stderr and return 1.

## DATA

- stdout (success): absolute directory path, no trailing newline required by the
  caller (the parent strips it).
- stderr (failure): one-line message naming `name`.
- Exit code: 0 success, 1 name not resolvable, 2 unchanged usage-error case.

## Tests (write first, see them fail, then implement)

In `TestProbeScript` (`tests/test_environment_info.py`), run the real script under
`sys.executable` via `execute_command`, exactly like the existing tests in that class:

- `test_real_child_reports_the_stdlib_directory`: `probe.py info json` → parse JSON,
  assert `blob["stdlib"]` is a directory and `(Path(blob["stdlib"]) / "os.py").is_file()`.
- `test_real_child_resolves_a_package_scope`: `probe.py scope json` → return code 0,
  `(Path(stdout.strip()) / "__init__.py").is_file()`.
- `test_real_child_resolves_a_dotted_module_scope`: `probe.py scope json.decoder` →
  return code 0; the resulting directory equals the one from the previous test (the
  module's root package directory, not a `dirname` one level too deep).
- `test_real_child_scope_reports_unknown_name`: `probe.py scope nosuchmodule_xyz123` →
  non-zero exit, stderr mentions `nosuchmodule_xyz123`.

## Commit

One commit: `feat(probe): add stdlib field and scope subcommand`

## LLM prompt

> Read `pr_info/steps/summary.md` for the overall feature context, then implement
> `pr_info/steps/step_1.md` only. Write the four tests described under "Tests" into
> `TestProbeScript` in `tests/test_environment_info.py` first, run them with
> `mcp__mcp-tools-py__run_pytest_check` scoped to that file and confirm they fail for
> the right reason (missing `stdlib` key / unknown `scope` subcommand). Then implement
> `_info`, `_scope` and the `main()` branch in
> `src/mcp_tools_py/utils/target_scripts/probe.py` exactly as specified under WHAT/HOW/
> ALGORITHM/DATA, update `_USAGE`, and re-run the tests until they pass. Run
> `mcp__mcp-tools-py__run_pylint_check`, `mcp__mcp-tools-py__run_pytest_check` (unit:
> `extra_args=["-n", "auto", "-m", "not integration"]`) and `mcp__mcp-tools-py__run_mypy_check`
> — all must pass. Then run `mcp__mcp-tools-py__run_format_code`, stage the two changed
> files, and create exactly one commit with the message
> `feat(probe): add stdlib field and scope subcommand`. If the precondition above does
> not hold, write one line to `pr_info/.blocked.txt` and stop instead.
