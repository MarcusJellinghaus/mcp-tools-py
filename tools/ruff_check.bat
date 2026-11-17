@echo off
REM Lint with ruff (rules from [tool.ruff.lint] in pyproject.toml)
REM
REM Usage from cmd.exe: tools\ruff_check.bat

where ruff >nul 2>&1
if errorlevel 1 (
    echo ERROR: ruff not found. Install with: uv pip install ruff
    exit /b 1
)

echo Linting with ruff...
ruff check src tests tools %*
exit /b %ERRORLEVEL%
