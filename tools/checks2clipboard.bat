@echo off
setlocal enabledelayedexpansion

REM Run pylint with specified parameters
echo Running Pylint checks...
pylint -E ./src ./tests > checks_output.txt 2>&1
set PYLINT_EXIT_CODE=%errorlevel%

REM Check if Pylint found any issues
if %PYLINT_EXIT_CODE% neq 0 (
    (
        echo INSTRUCTIONS FOR LLM: PYLINT ANALYSIS
        echo Pylint has detected potential critical errors in the source code:
        echo - Review serious code quality issues
        echo - Focus on:
        echo   1. Critical syntax errors
        echo   2. Import errors
        echo   3. Undefined variables
        echo.
        type checks_output.txt
    ) > checks_clipboard.txt

    type checks_clipboard.txt | clip
    echo Pylint found critical code errors. Output copied to clipboard.
    del checks_output.txt
    del checks_clipboard.txt
    exit /b 1
) else (
    echo Pylint check passed - No critical errors found
)

REM Run pytest after Pylint passes
echo Running Pytest checks...
pytest tests --tb=short -v > checks_output.txt 2>&1
set PYTEST_EXIT_CODE=%errorlevel%

REM Parse pytest output for detailed information
for /f "tokens=*" %%i in ('findstr /r /c:"[0-9]* passed" /c:"[0-9]* failed" /c:"[0-9]* error" /c:"[0-9]* skipped" checks_output.txt') do (
    set PYTEST_SUMMARY=%%i
)

REM Check pytest results with detailed exit code handling
if %PYTEST_EXIT_CODE% equ 0 (
    REM Success case - may include passed tests and/or skipped tests
    if defined PYTEST_SUMMARY (
        echo Pytest completed successfully: !PYTEST_SUMMARY!
    ) else (
        echo Pytest completed successfully
    )
) else if %PYTEST_EXIT_CODE% equ 1 (
    REM Test failures detected - filter out PASSED tests from output
    (
        echo INSTRUCTIONS FOR LLM: PYTEST RESULTS
        echo Pytest has found test failures in the test suite:
        echo - Carefully review test failures and errors
        echo - Investigate potential causes:
        echo   1. Broken test assertions
        echo   2. Unexpected test behaviors
        echo   3. Potential code implementation issues
        echo - Provide specific recommendations for fixing test failures
        echo - NOTE: SKIPPED tests are not considered problems and can be ignored
        echo.
        if defined PYTEST_SUMMARY (
            echo Test Summary: !PYTEST_SUMMARY!
            echo.
        )
        REM Filter out PASSED tests to reduce noise
        findstr /v /r /c:"::.*PASSED" /c:".*PASSED$" checks_output.txt
    ) > checks_clipboard.txt

    type checks_clipboard.txt | clip
    echo Pytest detected test failures. Output copied to clipboard.
    del checks_output.txt
    del checks_clipboard.txt
    exit /b 1
) else if %PYTEST_EXIT_CODE% equ 2 (
    echo Pytest was interrupted by user
    del checks_output.txt
    exit /b 2
) else if %PYTEST_EXIT_CODE% equ 3 (
    (
        echo INSTRUCTIONS FOR LLM: PYTEST INTERNAL ERROR
        echo Pytest encountered an internal error:
        echo - This usually indicates a pytest configuration issue
        echo - Check pytest version compatibility
        echo - Review pytest.ini or pyproject.toml configuration
        echo - Verify all pytest plugins are properly installed
        echo.
        REM Filter out PASSED tests to reduce noise
        findstr /v /r /c:"::.*PASSED" /c:".*PASSED$" checks_output.txt
    ) > checks_clipboard.txt

    type checks_clipboard.txt | clip
    echo Pytest internal error. Output copied to clipboard.
    del checks_output.txt
    del checks_clipboard.txt
    exit /b 3
) else if %PYTEST_EXIT_CODE% equ 4 (
    (
        echo INSTRUCTIONS FOR LLM: PYTEST USAGE ERROR
        echo Pytest command line usage error:
        echo - Check pytest command arguments
        echo - Verify test paths exist
        echo - Review pytest configuration syntax
        echo.
        REM Filter out PASSED tests to reduce noise
        findstr /v /r /c:"::.*PASSED" /c:".*PASSED$" checks_output.txt
    ) > checks_clipboard.txt

    type checks_clipboard.txt | clip
    echo Pytest usage error. Output copied to clipboard.
    del checks_output.txt
    del checks_clipboard.txt
    exit /b 4
) else if %PYTEST_EXIT_CODE% equ 5 (
    echo Pytest found no tests to run
    if defined PYTEST_SUMMARY (
        echo Summary: !PYTEST_SUMMARY!
    )
    del checks_output.txt
    REM Continue to mypy - no tests is not necessarily a failure
) else (
    REM Unknown exit code - filter out PASSED tests
    (
        echo INSTRUCTIONS FOR LLM: PYTEST UNKNOWN ERROR
        echo Pytest returned an unexpected exit code: %PYTEST_EXIT_CODE%
        echo - This may indicate a plugin-specific error
        echo - Check pytest plugin documentation
        echo - Review system and environment configuration
        echo.
        REM Filter out PASSED tests to reduce noise
        findstr /v /r /c:"::.*PASSED" /c:".*PASSED$" checks_output.txt
    ) > checks_clipboard.txt

    type checks_clipboard.txt | clip
    echo Pytest returned unexpected exit code %PYTEST_EXIT_CODE%. Output copied to clipboard.
    del checks_output.txt
    del checks_clipboard.txt
    exit /b %PYTEST_EXIT_CODE%
)

REM Run mypy if Pylint and Pytest passed or only had skipped tests
echo Running Mypy type checking...
python -m mypy src tests > checks_output.txt 2>&1
set MYPY_EXIT_CODE=%errorlevel%

REM Check mypy results
if %MYPY_EXIT_CODE% neq 0 (
    (
        echo INSTRUCTIONS FOR LLM: MYPY TYPE CHECKING RESULTS
        echo Mypy has found type checking issues in the code:
        echo - Review type annotation problems
        echo - Fix issues related to:
        echo   1. Missing type annotations
        echo   2. Incompatible types
        echo   3. Optional/None handling errors
        echo   4. Function return type mismatches
        echo - Ensure all code follows strict typing standards
        echo - special cases:
        echo   - in the case of `@pytest.fixture`, if necessary `# type: ignore[misc]` could be added
        echo.
        type checks_output.txt
    ) > checks_clipboard.txt

    type checks_clipboard.txt | clip
    echo Mypy detected type checking errors. Output copied to clipboard.
    del checks_output.txt
    del checks_clipboard.txt
    exit /b 1
) else (
    echo Mypy check passed - No type errors found
)

REM If all checks pass
echo.
echo All checks passed successfully!
if defined PYTEST_SUMMARY (
    echo Final test summary: !PYTEST_SUMMARY!
)
echo No issues detected.
del checks_output.txt 2>nul
exit /b 0
