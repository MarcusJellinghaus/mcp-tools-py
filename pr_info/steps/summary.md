# Summary: require a venv install and drop `--venv-path` from MCP configs (#198)

## Goal

Document that mcp-tools-py must be installed in a virtual environment, and remove the deprecated `--venv-path` from this repo's MCP configs.

## Architectural / design changes

No runtime design changes and no `src/` changes. The change makes an existing constraint explicit:

- **Documented constraint:** `PythonEnvironment.binary()` looks for console scripts only next to the interpreter mcp-tools-py runs on (`src/mcp_tools_py/utils/python_environment.py`). Installs that put scripts elsewhere are therefore unsupported: `pip install --user`, global installs on Windows, conda on Windows.
- **Scope of the constraint:** it covers the **tool env** only. The project env named by `--python-executable` runs via `python -m` and has no such requirement. The docs must not read as if the project env has to be a venv.
- **Client configs:** MCP clients do not activate a venv, so a config needs the script's full path as `command`, plus `--python-executable` unless mcp-tools-py is installed in the project's own environment. This is documented in one note in `README.md`, which `INSTALL.md` links to. Existing examples stay unchanged.
- **Repo MCP configs:** `--venv-path ${VIRTUAL_ENV}` goes. It resolves to the same interpreter as the `--python-executable` value already passed, so the interpreter does not change. The deprecation warning stops, and a missing-interpreter error now names `--python-executable`.

The docs must not describe the unsupported installs as a confirmed failure. The limitation comes from comparing paths and a simulated layout, not from a reproduced failure on a real install.

## Files to modify

| File | Step | Change |
|---|---|---|
| `.mcp.json` | 1 | Remove `--venv-path` and its value |
| `.mcp.macos.json` | 1 | Remove `--venv-path` and its value |
| `README.md` | 2 | Venv requirement, client config note, venv snippets, tool env and troubleshooting text, deptry |
| `INSTALL.md` | 2 | Remove `--user` and PATH workarounds, add venv steps, link to the client config note |
| `docs/architecture/architecture.md` | 2 | Say the install goes into a virtual environment |

No files or folders are created by the implementation. A temporary `.scratch/` probe is used in step 1 and deleted before the commit.

## Testing approach

The issue needs no new tests: nothing reads the configs, and the flag's behaviour is already covered (`tests/test_main_args.py`, `tests/test_tool_availability/test_resolve_python_executable.py`). TDD applies only to step 1, through a throwaway probe that fails before the edit and passes after it. Step 2 is verified by searching the edited docs.

## Out of scope

- `src/` changes: the `binary()` lookup, the `--venv-path` CLI flag, `unavailable_message` wording.
- Existing client config examples (bare `command`, no `--python-executable`) in `README.md` and `INSTALL.md`.
- README mentions and tests that describe `--venv-path` as an accepted flag.
- "Using as a Dependency" in `README.md`.
- Stale `src.main` and `src/server.py` references.
- `docs/upgrade-notes.md`, `.mcp.linux.json`, sibling repos, the `pip install mcp-coder` hints in the `claude*` launchers.

## Steps

1. [Remove `--venv-path` from the MCP configs](./step_1.md)
2. [Document the venv requirement](./step_2.md)
