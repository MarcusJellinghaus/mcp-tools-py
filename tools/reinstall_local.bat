@echo off
setlocal enabledelayedexpansion
REM Reinstall mcp-tools-py package in development mode
REM Usage: call tools\reinstall_local.bat  (from project root)
echo =============================================
echo MCP-Tools-Py Package Reinstallation
echo =============================================
echo.

REM Determine project root (parent of tools directory)
set "PROJECT_DIR=%~dp0.."
pushd "!PROJECT_DIR!"
set "PROJECT_DIR=%CD%"
popd

set "VENV_DIR=!PROJECT_DIR!\.venv"
set "VENV_SCRIPTS=!VENV_DIR!\Scripts"

REM Silently deactivate any active venv (will reactivate correct one at end)
call deactivate 2>nul

echo [0/7] Checking Python environment...

REM Check if uv is available
where uv >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] uv not found. Install it: pip install uv
    exit /b 1
)
echo [OK] uv found

REM Check if local .venv exists
if not exist "!VENV_SCRIPTS!\activate.bat" (
    echo Local virtual environment not found at !VENV_DIR!
    uv venv .venv
    echo Local virtual environment created at !VENV_DIR!
)
echo [OK] Target environment: !VENV_DIR!
echo.

echo [1/7] Uninstalling existing packages...
uv pip uninstall mcp-coder mcp-tools-py mcp-config mcp-workspace --python "!VENV_SCRIPTS!\python.exe" 2>nul
echo [OK] Packages uninstalled

echo.
echo [2/7] Installing mcp-tools-py (this project) in editable mode...
REM Editable install pulls all deps (including mcp-workspace,
REM mcp-config) from PyPI first.
pushd "!PROJECT_DIR!"
uv pip install -e ".[dev]" --python "!VENV_SCRIPTS!\python.exe"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Installation failed!
    popd
    exit /b 1
)
popd
echo [OK] Package and dev dependencies installed

echo.
echo [3/7] Overriding dependencies with GitHub versions...
REM Validate read_github_deps.py succeeds before parsing its output
"!VENV_SCRIPTS!\python.exe" tools\read_github_deps.py > nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] read_github_deps.py failed!
    "!VENV_SCRIPTS!\python.exe" tools\read_github_deps.py
    exit /b 1
)
REM Read GitHub dependency overrides from pyproject.toml
for /f "delims=" %%C in ('"!VENV_SCRIPTS!\python.exe" tools\read_github_deps.py') do (
    echo   %%C
    %%C --python "!VENV_SCRIPTS!\python.exe"
    if !ERRORLEVEL! NEQ 0 (
        echo [FAIL] GitHub dependency override failed!
        exit /b 1
    )
)
echo [OK] GitHub dependencies overridden from pyproject.toml

echo.
echo [4/7] Reinstalling local package (editable)...
pushd "!PROJECT_DIR!"
uv pip install -e . --python "!VENV_SCRIPTS!\python.exe"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Local editable reinstall failed!
    popd
    exit /b 1
)
popd
echo [OK] Local editable install takes precedence

echo.
echo [5/7] Installing LangChain and MLflow dependencies...
uv pip install langchain langchain-anthropic mlflow --python "!VENV_SCRIPTS!\python.exe"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] LangChain/MLflow installation failed!
    exit /b 1
)
echo [OK] langchain, langchain-anthropic, mlflow installed

echo.
echo [6/7] Verifying CLI entry points in venv...

if not exist "!VENV_SCRIPTS!\mcp-tools-py.exe" (
    echo [FAIL] mcp-tools-py.exe not found in !VENV_SCRIPTS!
    echo   The entry point was not installed into the virtual environment.
    exit /b 1
)
echo [OK] mcp-tools-py.exe found in !VENV_SCRIPTS!

if not exist "!VENV_SCRIPTS!\mcp-workspace.exe" (
    echo [FAIL] mcp-workspace.exe not found in !VENV_SCRIPTS!
    echo   The entry point was not installed into the virtual environment.
    exit /b 1
)
echo [OK] mcp-workspace.exe found in !VENV_SCRIPTS!

if not exist "!VENV_SCRIPTS!\mcp-coder.exe" (
    echo [FAIL] mcp-coder.exe not found in !VENV_SCRIPTS!
    echo   The entry point was not installed into the virtual environment.
    exit /b 1
)
echo [OK] mcp-coder.exe found in !VENV_SCRIPTS!

echo.
echo [7/7] Verifying CLI functionality...
"!VENV_SCRIPTS!\mcp-tools-py.exe" --help >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] mcp-tools-py CLI verification failed!
    exit /b 1
)
echo [OK] mcp-tools-py CLI works

"!VENV_SCRIPTS!\mcp-workspace.exe" --help >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] mcp-server-filesystem CLI verification failed!
    exit /b 1
)
echo [OK] mcp-server-filesystem CLI works

"!VENV_SCRIPTS!\mcp-coder.exe" --help >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] mcp-coder CLI verification failed!
    exit /b 1
)
echo [OK] mcp-coder CLI works

echo.
echo =============================================
echo Reinstallation completed successfully!
echo.
echo Entry points installed in: !VENV_SCRIPTS!
echo   - mcp-tools-py.exe
echo   - mcp-workspace.exe
echo   - mcp-coder.exe
echo =============================================
echo.

REM Pass VENV_DIR out of setlocal scope so activation persists to caller
endlocal & set "_REINSTALL_VENV=%VENV_DIR%"

REM Deactivate wrong venv if one is active
if defined VIRTUAL_ENV (
    if not "%VIRTUAL_ENV%"=="%_REINSTALL_VENV%" (
        echo   Deactivating wrong virtual environment: %VIRTUAL_ENV%
        call deactivate 2>nul
    )
)

REM Activate the correct venv (persists to caller's shell)
if not "%VIRTUAL_ENV%"=="%_REINSTALL_VENV%" (
    echo   Activating virtual environment: %_REINSTALL_VENV%
    call "%_REINSTALL_VENV%\Scripts\activate.bat"
)

set "_REINSTALL_VENV="
