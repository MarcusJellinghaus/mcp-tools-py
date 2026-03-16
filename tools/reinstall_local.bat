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
set "VENV_PIP=!VENV_SCRIPTS!\pip.exe"

echo [0/4] Checking Python environment...

REM Check if local .venv exists
if not exist "!VENV_SCRIPTS!\activate.bat" (
    echo [FAIL] Local virtual environment not found at !VENV_DIR!
    echo Please create it first: python -m venv .venv
    exit /b 1
)

if not exist "!VENV_PIP!" (
    echo [FAIL] pip.exe not found in !VENV_SCRIPTS!
    echo The virtual environment may be corrupted. Recreate it: python -m venv .venv
    exit /b 1
)

echo [OK] Using venv pip: !VENV_PIP!
echo.

echo [1/4] Uninstalling existing packages...
REM Note: mcp-config is uninstalled here but will be automatically reinstalled
REM as a dependency when mcp-tools-py is installed (see pyproject.toml)
"!VENV_PIP!" uninstall mcp-tools-py mcp-config mcp-server-filesystem -y
echo [OK] Packages uninstalled

echo.
echo [2/4] Installing in development mode with dev dependencies...
pushd "!PROJECT_DIR!"
"!VENV_PIP!" install -e ".[dev]"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Installation failed!
    popd
    exit /b 1
)
popd
echo [OK] Package and dev dependencies installed

echo.
echo [3/4] Verifying CLI entry points in venv...

if not exist "!VENV_SCRIPTS!\mcp-tools-py.exe" (
    echo [FAIL] mcp-tools-py.exe not found in !VENV_SCRIPTS!
    echo   The entry point was not installed into the virtual environment.
    exit /b 1
)
echo [OK] mcp-tools-py.exe found in !VENV_SCRIPTS!

if not exist "!VENV_SCRIPTS!\mcp-server-filesystem.exe" (
    echo [FAIL] mcp-server-filesystem.exe not found in !VENV_SCRIPTS!
    echo   The entry point was not installed into the virtual environment.
    exit /b 1
)
echo [OK] mcp-server-filesystem.exe found in !VENV_SCRIPTS!

echo.
echo [4/4] Verifying CLI functionality...
"!VENV_SCRIPTS!\mcp-tools-py.exe" --help >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] mcp-tools-py CLI verification failed!
    exit /b 1
)
echo [OK] mcp-tools-py CLI works

"!VENV_SCRIPTS!\mcp-server-filesystem.exe" --help >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] mcp-server-filesystem CLI verification failed!
    exit /b 1
)
echo [OK] mcp-server-filesystem CLI works

echo.
echo =============================================
echo Reinstallation completed successfully!
echo.
echo Entry points installed in: !VENV_SCRIPTS!
echo   - mcp-tools-py.exe
echo   - mcp-server-filesystem.exe
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
