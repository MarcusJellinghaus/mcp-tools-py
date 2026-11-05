# Step 1: Remove `--venv-path` from the MCP configs

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`), then implement this step exactly. Do not change anything outside the files listed under WHERE. Do not edit `pr_info/TASK_TRACKER.md`. Produce one commit.

## WHERE

- `.mcp.json`
- `.mcp.macos.json`
- `.scratch/test_probe.py` (temporary, deleted before the commit)

## WHAT

Remove these two entries from the `mcp-tools-py` server's `args` in both files:

```json
        "--venv-path",
        "${VIRTUAL_ENV}",
```

Keep everything else byte for byte, including `--python-executable` and its `${VIRTUAL_ENV}` value, `${MCP_CODER_VENV_PATH}`, the `PYTHONPATH` env block, and each file's trailing newline or lack of one. Use `edit_file`, not a rewrite of the file.

No functions are added.

## HOW

No integration points: nothing in `src/` or `tests/` reads these files.

## ALGORITHM

Probe, written before the edit:

```python
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).parents[1]

@pytest.mark.parametrize("name", [".mcp.json", ".mcp.macos.json"])
def test_config(name):
    args = json.loads((ROOT / name).read_text(encoding="utf-8"))["mcpServers"]["mcp-tools-py"]["args"]
    assert "--venv-path" not in args
    assert "--python-executable" in args
```

1. Save the probe and run it with `run_pytest_check(extra_args=["-p", "no:cacheprovider", ".scratch/test_probe.py"])`. Both cases must fail on the `--venv-path` assertion.
2. Make the two edits.
3. Run the probe again. Both cases must pass.
4. Delete the probe with `delete_directory(".scratch", recursive=True)`.
5. Run pylint, pytest (`extra_args=["-n", "auto", "-m", "not integration"]`) and mypy, then `run_format_code`.
6. Commit only the two config files.

## DATA

Both files stay valid JSON. The resulting `mcp-tools-py` `args`, on Windows:

```json
[
  "--project-dir", "${MCP_CODER_PROJECT_DIR}",
  "--python-executable", "${VIRTUAL_ENV}\\Scripts\\python.exe",
  "--test-folder", "tests",
  "--log-level", "INFO"
]
```

`.mcp.macos.json` is the same, with `${VIRTUAL_ENV}/bin/python`.

## Preconditions

- If either file does not have `--venv-path` and `--python-executable` in the `mcp-tools-py` `args`, write one line to `pr_info/.blocked.txt` and stop.
- This step changes no Python code, so if pylint, pytest or mypy fail, write one line to `pr_info/.blocked.txt` naming the failing check and stop.

## Commit message

```
chore(mcp): remove deprecated --venv-path from MCP configs
```
