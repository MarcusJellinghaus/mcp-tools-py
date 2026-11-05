# Step 1: Remove the bare `mcp` requirement and verify the resolve is unchanged

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_1.md`, then implement
> Step 1. Follow the order below exactly: the baseline must be captured before
> `pyproject.toml` is edited. Do not add a permanent test, and do not change the CI
> install steps. This step produces exactly one commit.

## WHERE

- `pyproject.toml`: `[project] dependencies`
- `docs/architecture/architecture.md`: line 48
- `.scratch/test_probe.py`: temporary, deleted before the commit

## WHAT

No production functions change. The temporary probe has these functions:

```python
def _compile() -> str: ...
def test_capture_baseline() -> None: ...
def test_single_mcp_requirement() -> None: ...
def test_resolve_unchanged_and_mcp_1x() -> None: ...
def test_tools_listed() -> None: ...
```

## HOW

### 1. Write the probe

Save this as `.scratch/test_probe.py`:

```python
import asyncio
import re
import subprocess
import tomllib
from pathlib import Path

from mcp_tools_py.server import create_server

BASELINE = Path(__file__).parent / "compile_before.txt"
PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _compile() -> str:
    return subprocess.run(
        ["uv", "pip", "compile", "pyproject.toml", "--python-version", "3.11"],
        cwd=PYPROJECT.parent,
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout


def test_capture_baseline() -> None:
    BASELINE.write_text(_compile(), encoding="utf-8")


def test_single_mcp_requirement() -> None:
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    found = [d for d in project["dependencies"] if re.match(r"mcp(\[|[<>=])", d)]
    assert found == ["mcp[cli]>=1.3.0,<2.0.0"]


def test_resolve_unchanged_and_mcp_1x() -> None:
    after = _compile()
    assert after == BASELINE.read_text(encoding="utf-8")
    assert re.search(r"^mcp(\[cli\])?==1\.", after, re.MULTILINE)


def test_tools_listed() -> None:
    tools = asyncio.run(create_server(Path(".")).mcp.list_tools())
    assert tools
```

### 2. Capture the baseline

```python
mcp__mcp-tools-py__run_pytest_check(
    extra_args=["-p", "no:cacheprovider", ".scratch/test_probe.py::test_capture_baseline"]
)
```

If this fails because `uv` is missing or the compile errors, write one line to
`pr_info/.blocked.txt` and stop.

### 3. Edit `pyproject.toml`

```diff
-    "mcp>=1.3.0,<2.0.0",
+    # <2.0.0: mcp 2.x drops mcp.server.fastmcp (FastMCP -> MCPServer). See #216.
     "mcp[cli]>=1.3.0,<2.0.0",
```

### 4. Edit `docs/architecture/architecture.md` line 48

```diff
-**Runtime**: `mcp`, `mcp[cli]`, `pylint`, ...
+**Runtime**: `mcp[cli]`, `pylint`, ...
```

Leave line 42 as it is ("using `mcp` (FastMCP)"): it names the package, not a requirement.

### 5. Run the remaining probes

```python
mcp__mcp-tools-py__run_pytest_check(
    extra_args=[
        "-p", "no:cacheprovider",
        ".scratch/test_probe.py::test_single_mcp_requirement",
        ".scratch/test_probe.py::test_resolve_unchanged_and_mcp_1x",
        ".scratch/test_probe.py::test_tools_listed",
    ]
)
```

If any probe fails, write one line to `pr_info/.blocked.txt` and stop. The line must name
the failing probe. Do not change the dependency list to make a probe pass.

### 6. Delete the probes

```python
mcp__mcp-workspace__delete_directory(".scratch", recursive=True)
```

### 7. Run the quality checks

Run these after deleting `.scratch/`, so the probe is not collected by the full run:

```python
mcp__mcp-tools-py__run_pylint_check()
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])
mcp__mcp-tools-py__run_mypy_check()
```

Do not use `-m "not integration"`: the full run is what covers `tests/test_startup_time.py`.

### 8. Write the commit message

Write this message to `pr_info/.commit_message.txt`. Do not format, stage or commit: the
implement workflow does that:

```
chore(deps): remove redundant bare mcp dependency (#204)
```

## ALGORITHM

```text
baseline = uv pip compile pyproject.toml --python-version 3.11
remove the bare mcp line; add the cap comment; update the docs list
after = the same compile command
require after == baseline, and mcp pinned to 1.x
require exactly one mcp requirement, and a non-empty tool list
delete .scratch/; run pylint, pytest and mypy; write the commit message file
```

## DATA

No production data structures or return values change.

- `.scratch/compile_before.txt`: the `uv pip compile` stdout captured before the edit
- `_compile()` returns that same stdout as a `str`
- `list_tools()` returns a non-empty list of tools

## Done when

- `pyproject.toml` has a single `mcp` requirement: `mcp[cli]>=1.3.0,<2.0.0`
- The compile output is identical before and after the edit, and pins `mcp` to 1.x
- `list_tools()` returns a non-empty list
- `tests/test_startup_time.py`, pylint, the full pytest suite and mypy pass
- `.scratch/` is gone
