# Step 6 — Soft-deprecate `--venv-path`

Implements **Decisions 2 and 11**. See [summary.md](./summary.md) §7.

After Steps 3 and 5 the flag no longer drives detection or the pytest `PATH`
prepend. It keeps exactly one job: resolving the interpreter. Independent of
Steps 5 and 7.

## WHERE

| File | Line(s) | Change |
|---|---|---|
| `src/mcp_tools_py/main.py` | `:30` | epilog example |
| | `:54-63` | `--venv-path` help → `argparse.SUPPRESS` |
| | `~:155` | deprecation warning before `create_server` |
| `tests/test_main_args.py` | new file | |

## WHAT

```python
parser.add_argument(
    "--venv-path",
    type=str,
    help=argparse.SUPPRESS,
)
```

In `main()`, after `setup_logging` and before `create_server`:

```python
if args.venv_path:
    logger.warning(
        "--venv-path is deprecated and will be removed; use --python-executable. "
        "It still resolves the interpreter but no longer affects tool detection.",
        extra={"venv_path": args.venv_path},
    )
```

Epilog line `:30` becomes:

```
mcp-tools-py --project-dir /path/to/project --python-executable .venv/Scripts/python.exe --test-folder tests
```

## HOW

- **Keep the flag accepted, and keep it resolving the interpreter with today's
  precedence.** The epilog currently advertises a `--venv-path`-only
  configuration; ignoring the flag for resolution too would silently point that
  setup at `sys.executable`, trading a loud false negative for a quiet one. Only
  detection and the `PATH` prepend stop using it — both already done.
- **The epilog change is not cosmetic.** `epilog` is printed as part of `--help`,
  so hiding the flag with `SUPPRESS` while the epilog advertises
  `--venv-path .venv` as a headline example would be self-contradictory.
- No hard removal: both `.mcp.json` files pass the flag and mcp-config still
  generates it (MarcusJellinghaus/mcp-config#56). The warning fires on every start
  until that repo is updated — expected, not a defect.
- Warn once, at startup, through `logger` — not `warnings.warn`. This is an STDIO
  MCP server; anything written to stdout corrupts the transport.

## ALGORITHM

None beyond the conditional above.

## DATA

No data-structure changes. `ToolServer.venv_path` and the `create_server`
`venv_path` parameter are unchanged.

## TESTS (write first)

New file `tests/test_main_args.py`:

1. `test_venv_path_hidden_from_help` — `parse_args`'s parser formats help without
   the string `--venv-path`. Build the parser via `parse_args` with a patched
   `sys.argv`, or refactor the parser construction into a helper if that reads
   better; keep it minimal.
2. `test_venv_path_still_accepted` — `--project-dir X --venv-path Y` parses and
   `args.venv_path == "Y"`.
3. `test_venv_path_logs_deprecation_warning` — run `main()` with `--venv-path` set
   (patch `create_server` and `setup_logging`), assert a WARNING containing
   "deprecated" via `caplog`.
4. `test_no_warning_without_venv_path` — same, flag absent, no such warning.
5. `test_epilog_does_not_advertise_venv_path` — the epilog text contains
   `--python-executable` and not `--venv-path`.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_6.md`. Steps 1-5 are done.
>
> Implement Step 6 only: in `src/mcp_tools_py/main.py`, set the `--venv-path`
> argument's `help` to `argparse.SUPPRESS`, rewrite the epilog example at line 30
> to lead with `--python-executable`, and log a deprecation WARNING at startup when
> the flag is supplied.
>
> Keep the flag accepted and keep it resolving the interpreter with today's
> precedence — the epilog advertises a `--venv-path`-only configuration, and
> dropping it from resolution too would silently redirect that setup to
> `sys.executable`. Only detection and the pytest PATH prepend stop using it, and
> both already have.
>
> The epilog edit is required, not cosmetic: argparse prints the epilog as part of
> `--help`, so suppressing the flag while the epilog advertises `--venv-path .venv`
> would contradict itself.
>
> Use `logger.warning`, not `warnings.warn` — this is an STDIO MCP server and
> anything on stdout corrupts the transport.
>
> Write the tests first, in a new `tests/test_main_args.py`.
>
> Then run, in order: `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
> `run_mypy_check`. All must pass. Commit as one commit.
