@echo off
echo ============================================
echo   Environment Check - mcp-tools-py
echo ============================================
echo.
echo --- Version Control ---
git --version
gh --version
echo.
echo --- Python ---
python --version
pip --version
echo.
echo --- Formatting ---
black --version
isort --version-number
echo.
echo --- Linting and Quality ---
pylint --version
mypy --version
vulture --version
echo.
echo --- Testing ---
pytest --version
echo.
echo --- Architecture and Dependencies ---
pydeps --version
pycycle --version
tach --version
lint-imports --version
echo.
echo --- MCP Servers ---
mcp-tools-py --version
mcp-workspace --version
mcp-coder --version
echo.
echo ============================================
echo   Done
echo ============================================
