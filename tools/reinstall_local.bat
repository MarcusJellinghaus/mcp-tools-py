@echo off
REM Reinstall mcp-tools-py in editable mode (developer convenience).
REM Resolves an mcp-coder from OUTSIDE the repo venv, drives `mcp-coder install`
REM against this repo, then activates the venv in the caller's shell.

setlocal
for %%d in ("%~dp0..") do set "REPO=%%~fd"
set "REPO_BIN=%REPO%\.venv\Scripts"

REM The install rewrites %REPO_BIN%\mcp-coder.exe, so the driver must not be
REM that file: Windows locks a running executable against replacement.
set "MC="
if defined MCP_CODER_VENV_PATH if exist "%MCP_CODER_VENV_PATH%\mcp-coder.exe" if /i not "%MCP_CODER_VENV_PATH%"=="%REPO_BIN%" set "MC=%MCP_CODER_VENV_PATH%\mcp-coder.exe"
if not defined MC for /f "delims=" %%i in ('where mcp-coder 2^>nul') do if not defined MC if /i not "%%~dpi"=="%REPO_BIN%\" set "MC=%%i"
if not defined MC (
    echo [FAIL] No mcp-coder found outside %REPO%\.venv.
    echo        reinstall_local rewrites the repo venv, so it cannot be driven from it.
    echo        Install the tool env first ^(pip install mcp-coder^) or set
    echo        MCP_CODER_VENV_PATH to its Scripts/bin directory.
    exit /b 1
)

"%MC%" install "%REPO%" ^
    --source local ^
    --local-path "%REPO%" ^
    --refresh
if errorlevel 1 (
    echo [FAIL] mcp-coder install failed
    exit /b 1
)
endlocal & call "%~dp0..\.venv\Scripts\activate.bat"
