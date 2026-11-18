@echo off
REM Run tach architectural boundary check
REM Configuration is in tach.toml
REM
REM Usage from Git Bash: ./tools/tach_check.sh
REM Usage from cmd.exe:  tools\tach_check.bat

where tach >nul 2>&1
if errorlevel 1 (
    echo ERROR: tach not found. Install with: pip install tach
    exit /b 1
)

echo Running tach architectural boundary check...
tach check %*
exit /b %ERRORLEVEL%
