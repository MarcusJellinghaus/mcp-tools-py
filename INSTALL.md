# Installation Guide for MCP Tools Py

## Prerequisites

- Python 3.11 or higher
- pip (Python package installer)
- git (for development installation)

## Installation Methods

### Method 1: Install from PyPI (When Available)

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the latest release
pip install mcp-tools-py

# Verify installation
mcp-tools-py --version
mcp-tools-py --help
```

### Method 2: Install from GitHub (Recommended)

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install directly from the main branch
pip install git+https://github.com/MarcusJellinghaus/mcp-tools-py.git

# Or install a specific version/tag
pip install git+https://github.com/MarcusJellinghaus/mcp-tools-py.git@v1.0.0

# Verify installation
mcp-tools-py --help
```

### Method 3: Development Installation

For contributors or when you need to modify the code:

```bash
# Clone the repository
git clone https://github.com/MarcusJellinghaus/mcp-tools-py.git
cd mcp-tools-py

# Create a virtual environment (required)
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"

# Verify installation
mcp-tools-py --help

# Run tests to ensure everything works
pytest
```

## Post-Installation Verification

### 1. Verify CLI Command

```bash
# Check if command is available
which mcp-tools-py  # Unix/macOS
where mcp-tools-py  # Windows

# Test the command
mcp-tools-py --version
mcp-tools-py --help
```

### 2. Verify Python Module

```bash
# Test as Python module
python -m mcp_tools_py --help

# Verify import works
python -c "import mcp_tools_py; print('✓ Package imported successfully')"
```

## Installation in Virtual Environments

### Creating a Project-Specific Installation

```bash
# Navigate to your project
cd /path/to/your/project

# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # Unix/macOS
.venv\Scripts\activate      # Windows

# Install MCP Tools Py
pip install mcp-tools-py
```

### Using with Poetry

```bash
# Add to your project
poetry add mcp-tools-py

# Or add as development dependency
poetry add --dev mcp-tools-py

# Verify in poetry shell
poetry shell
mcp-tools-py --help
```

### Using with Pipenv

```bash
# Add to Pipfile
pipenv install mcp-tools-py

# Or as dev dependency
pipenv install --dev mcp-tools-py

# Verify in pipenv shell
pipenv shell
mcp-tools-py --help
```

## Platform-Specific Instructions

### Windows

1. **Command Prompt (cmd.exe)**
   ```batch
   python -m venv .venv
   .venv\Scripts\activate
   pip install mcp-tools-py
   mcp-tools-py --help
   ```

2. **PowerShell**
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1

   # If Activate.ps1 is blocked by the execution policy, skip activation and
   # use the venv's interpreter directly, instead of the two commands below:
   #   .venv\Scripts\python.exe -m pip install mcp-tools-py
   #   .venv\Scripts\python.exe -m mcp_tools_py --help

   pip install mcp-tools-py
   mcp-tools-py --help
   ```

### macOS

```bash
# With Homebrew Python, check that it is the one in use
which python3
# Should show: /opt/homebrew/bin/python3 or /usr/local/bin/python3

python3 -m venv .venv
source .venv/bin/activate
pip install mcp-tools-py
```

### Linux

1. **Ubuntu/Debian**
   ```bash
   # Install venv support if needed
   sudo apt update
   sudo apt install python3-venv
   ```

2. **Fedora/RHEL**
   ```bash
   # Install pip if needed
   sudo dnf install python3-pip
   ```

Then, on either distribution:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install mcp-tools-py
```

## Configuration

MCP clients do not activate a virtual environment, so replace `mcp-tools-py` in the examples below with the script's full path and add `--python-executable` where needed. See the client config note under `## Installation` in [README.md](README.md).

After installation, you need to configure MCP Tools Py for your preferred client.

### Claude Desktop Configuration

1. Locate your Claude Desktop configuration file:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/claude/claude_desktop_config.json`

2. Add the MCP Tools Py configuration:

   ```json
   {
     "mcpServers": {
       "mcp-tools-py": {
         "command": "mcp-tools-py",
         "args": [
           "--project-dir",
           "/path/to/your/project",
           "--log-level",
           "INFO"
         ]
       }
     }
   }
   ```

   **For development mode:**
   ```json
   {
     "mcpServers": {
       "mcp-tools-py": {
         "command": "python",
         "args": [
           "-m",
           "src.main",
           "--project-dir",
           "/path/to/your/project"
         ],
         "env": {
           "PYTHONPATH": "/path/to/mcp-tools-py/"
         }
       }
     }
   }
   ```

3. Restart Claude Desktop to apply the changes.

### VSCode Configuration

VSCode 1.102+ supports MCP servers natively. Create or edit the configuration file:

**For workspace configuration (.vscode/mcp.json in your project):**
```json
{
  "servers": {
    "mcp-tools-py": {
      "command": "mcp-tools-py",
      "args": ["--project-dir", "."]
    }
  }
}
```

**For user profile configuration:**
- **Windows**: `%APPDATA%\Code\User\mcp.json`
- **macOS**: `~/Library/Application Support/Code/User/mcp.json`
- **Linux**: `~/.config/Code/User/mcp.json`

```json
{
  "servers": {
    "mcp-tools-py": {
      "command": "mcp-tools-py",
      "args": ["--project-dir", "/path/to/your/projects"]
    }
  }
}
```

## Troubleshooting Installation

### Command Not Found

If `mcp-tools-py` command is not found after installation:

1. **Check installation location:**
   ```bash
   pip show mcp-tools-py
   ```

2. **Check if scripts were installed:**
   ```bash
   ls .venv/bin/mcp-tools-py  # Unix/macOS
   dir .venv\Scripts\mcp-tools-py.exe  # Windows
   ```

3. **Use Python module as fallback:**
   ```bash
   python -m mcp_tools_py --help
   ```

### Permission Errors

If you get permission errors during installation, install into a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install mcp-tools-py
```

### Import Errors

If you get import errors when running the command:

```bash
# Reinstall with all dependencies
pip install --force-reinstall mcp-tools-py

# Check for conflicting packages
pip list | grep mcp

# In development mode, ensure you're in the right directory
cd /path/to/mcp-tools-py
pip install -e .
```

## Testing the Installation

You can test the MCP server using the MCP Inspector:

### For Installed Package
```bash
npx @modelcontextprotocol/inspector mcp-tools-py --project-dir /path/to/project
```

### For Development Mode
```bash
npx @modelcontextprotocol/inspector \
  python \
  -m \
  src.main \
  --project-dir /path/to/project
```

## Uninstallation

To remove MCP Tools Py:

```bash
# Uninstall the package
pip uninstall mcp-tools-py

# Remove configuration files manually if needed
# Claude Desktop: Edit claude_desktop_config.json
# VSCode: Delete .vscode/mcp.json or edit user mcp.json

# Clean up cache (optional)
pip cache purge
```

## Getting Help

If you encounter issues:

1. Check the project's GitHub Issues: https://github.com/MarcusJellinghaus/mcp-tools-py/issues
2. Run the command with `--help` to see all available options
3. Use `--log-level DEBUG` for more detailed logging
4. Ask for help with detailed error messages and system information
