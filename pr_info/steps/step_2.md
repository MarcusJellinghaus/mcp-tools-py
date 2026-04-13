# Step 2: Update `reinstall_local.bat` — silent deactivate + finalization step

> **Context**: See [summary.md](summary.md) for overall plan. This is step 2 of 2.

## Goal

Two changes to `tools/reinstall_local.bat`:
1. Replace the venv error guard with silent `call deactivate 2>nul`
2. Add finalization step after GitHub overrides, renumber steps 6→7

## No Tests (batch script — not unit-testable)

## Implementation

### WHERE
- `tools/reinstall_local.bat`

### WHAT — Change A: Silent Deactivate

**Remove** the entire venv guard block:
```bat
REM Guard: if a venv is active, it must be the project-local .venv
if defined VIRTUAL_ENV (
    if /I not "!VIRTUAL_ENV!"=="!VENV_DIR!" (
        ...
        exit /b 1
    )
)
```

**Replace with:**
```bat
REM Silently deactivate any active venv (will reactivate correct one at end)
call deactivate 2>nul
```

Place this right after `set "VENV_SCRIPTS=..."` and before the `echo [0/7]` line.

### WHAT — Change B: Add Finalization Step + Renumber

Insert new step **after** step 3 (GitHub overrides) and **before** step 4 (LangChain/MLflow):

```bat
echo.
echo [4/7] Reinstalling local package (editable, no deps)...
pushd "!PROJECT_DIR!"
uv pip install -e . --no-deps --python "!VENV_SCRIPTS!\python.exe"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Local editable reinstall failed!
    popd
    exit /b 1
)
popd
echo [OK] Local editable install takes precedence
```

### WHAT — Change C: Renumber All Steps

| Old | New | Label |
|-----|-----|-------|
| `[0/6]` | `[0/7]` | Checking Python environment |
| `[1/6]` | `[1/7]` | Uninstalling existing packages |
| `[2/6]` | `[2/7]` | Installing in editable mode |
| `[3/6]` | `[3/7]` | Overriding with GitHub versions |
| *(new)* | `[4/7]` | Reinstalling local package (no deps) |
| `[4/6]` | `[5/7]` | Installing LangChain and MLflow |
| `[5/6]` | `[6/7]` | Verifying CLI entry points |
| `[6/6]` | `[7/7]` | Verifying CLI functionality |

## Checks
- Run pylint, pytest, mypy — all must still pass (no Python changes, just confirming no regressions)
- Commit: `feat: add finalization step and silent deactivate to reinstall_local.bat (#157)`

---

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_2.md.
Implement step 2: Update tools/reinstall_local.bat.
1. Replace the venv error guard with silent deactivate
2. Add finalization step [4/7] after GitHub overrides
3. Renumber all steps from 6 to 7
4. Run all checks (pylint, pytest, mypy) to confirm no regressions
5. Commit with message: feat: add finalization step and silent deactivate to reinstall_local.bat (#157)
```
