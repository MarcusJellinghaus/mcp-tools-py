@echo off
REM Run import-linter to check architectural boundaries
REM Configuration is in .importlinter file (INI format)
REM
REM Usage from Git Bash: cmd //c "tools\lint_imports.bat"
REM Usage from cmd.exe:  tools\lint_imports.bat

where lint-imports >nul 2>&1
if errorlevel 1 (
    echo ERROR: lint-imports not found. Install with: pip install import-linter
    exit /b 1
)

lint-imports %*
exit /b %ERRORLEVEL%
