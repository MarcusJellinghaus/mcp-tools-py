@echo off
cls
setlocal enabledelayedexpansion
REM Simple launcher for Claude Code with MCP servers
REM Assumes you're running from the project root

REM Check if virtual environment is activated
if "!VIRTUAL_ENV!"=="" (
    if not exist ".venv\Scripts\activate.bat" (
        echo ERROR: Virtual environment not found at .venv
        echo Please run: python -m venv .venv
        echo Then: pip install -e ".[dev]"
        echo Then try again.
        exit /b 1
    )
    echo Activating virtual environment...
    call .venv\Scripts\activate.bat
    if "!VIRTUAL_ENV!"=="" (
        echo ERROR: Failed to activate virtual environment
        echo Please check .venv\Scripts\activate.bat
        exit /b 1
    )
)

REM Set project directories for MCP servers
set "MCP_CODER_PROJECT_DIR=%CD%"
set "MCP_CODER_VENV_DIR=%CD%\.venv"

REM Start Claude Code
echo Starting Claude Code with:
echo VIRTUAL_ENV=!VIRTUAL_ENV!
echo MCP_CODER_PROJECT_DIR=!MCP_CODER_PROJECT_DIR!
echo MCP_CODER_VENV_DIR=!MCP_CODER_VENV_DIR!
C:\Users\%USERNAME%\.local\bin\claude.exe %*

REM Reset terminal state after Claude exits (workaround for dirty terminal bug)
REM See https://github.com/anthropics/claude-code/issues/38761
for /f %%a in ('echo prompt $E ^| cmd') do set "ESC=%%a"
<nul set /p="!ESC![?2004l!ESC![?1l!ESC![?25h!ESC![J"
