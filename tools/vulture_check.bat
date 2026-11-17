@echo off
REM Check for dead/unused code using vulture
REM
REM Usage from cmd.exe: tools\vulture_check.bat

where vulture >nul 2>&1
if errorlevel 1 (
    echo ERROR: vulture not found. Install with: uv pip install vulture
    exit /b 1
)

echo Checking for dead code...
vulture src tests vulture_whitelist.py --min-confidence 60 %*
exit /b %ERRORLEVEL%
