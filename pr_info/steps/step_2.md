# Step 2: Document the venv requirement

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_2.md`), then implement this step exactly. Make minimal edits; do not rewrite `INSTALL.md`. Do not change anything outside the files listed under WHERE. Do not edit `pr_info/TASK_TRACKER.md`. Produce one commit.

## WHERE

- `README.md`
- `INSTALL.md`
- `docs/architecture/architecture.md`

## WHAT

Documentation edits only. No functions and no new tests: the docs have no test harness, so the checks under ALGORITHM verify this step.

### `README.md`

1. At the top of `## Installation`, before the "See INSTALL.md" line, add:

   > **Install mcp-tools-py in a virtual environment** (venv, virtualenv or uv). Its console-script tools are looked up only next to the interpreter it runs on, so installs that put scripts elsewhere are not supported: `pip install --user`, global installs on Windows, conda on Windows. This applies to mcp-tools-py's own environment. `--python-executable` names your project's environment separately.
   >
   > MCP clients do not activate a virtual environment. In client configs, set `command` to the script's full path (`<venv>\Scripts\mcp-tools-py.exe` on Windows, `<venv>/bin/mcp-tools-py` elsewhere). Pass `--python-executable` unless mcp-tools-py is installed in the project's own environment.

   Add these as plain paragraphs, not as a blockquote.

2. In "Quick install", and in step 1 of "Automated Setup", put these lines before the `pip install git+...` line, in the same code block:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. In the **tool env** bullet under `## Environment Configuration`, add after "It is **not** configurable.": `It must be a virtual environment; see [Installation](#installation).`

4. In the `"ruff is not available"` troubleshooting bullet, add at the end: `If mcp-tools-py was installed outside a virtual environment, redo the install inside one.`

5. Boy Scout, add deptry in the Environment Configuration section:

   | Current text | New text |
   |---|---|
   | `with pytest, pylint and mypy installed in it` | `with pytest, pylint, mypy and deptry installed in it` |
   | `reports pytest, pylint and mypy as missing` | `reports pytest, pylint, mypy and deptry as missing` |
   | `if those three are not installed in it` | `if those four are not installed in it` |
   | `"No module named pytest"** (or pylint/mypy)` | `"No module named pytest"** (or pylint/mypy/deptry)` |
   | `pytest, pylint and mypy are answered by a probe` | `pytest, pylint, mypy and deptry are answered by a probe` |
   | `after installing one of those three` | `after installing one of those four` |

Leave these unchanged: "Using as a Dependency", the `--venv-path` mentions, all client config examples, the "Development install" snippet.

### `INSTALL.md`

1. **Methods 1 and 2:** at the top of each code block, add:

   ```bash
   # Create and activate a virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate

   ```

2. **Method 3:** change `# Create a virtual environment (recommended)` to `# Create a virtual environment (required)`. "Method 2 ... (Recommended)" stays, because it does not describe a venv.

3. **`### Windows`:** replace the content with the following, which removes "Adding to PATH":

   ````markdown
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
   ````

4. **`### macOS`:** replace the content with one block. System Python has no prerequisite left, so the two subsections merge:

   ````markdown
   ```bash
   # With Homebrew Python, check that it is the one in use
   which python3
   # Should show: /opt/homebrew/bin/python3 or /usr/local/bin/python3

   python3 -m venv .venv
   source .venv/bin/activate
   pip install mcp-tools-py
   ```
   ````

5. **`### Linux`:** replace the content with per-distribution prerequisites and one shared block of venv steps:

   ````markdown
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
   ````

6. **`## Configuration`:** add at the top, before "After installation, ...":

   `MCP clients do not activate a virtual environment, so replace `mcp-tools-py` in the examples below with the script's full path and add `--python-executable` where needed. See the client config note under `## Installation` in [README.md](README.md).`

   Leave the examples unchanged.

7. **"Command Not Found", step 2:** replace the code block with:

   ```bash
   ls .venv/bin/mcp-tools-py  # Unix/macOS
   dir .venv\Scripts\mcp-tools-py.exe  # Windows
   ```

8. **"Permission Errors":** replace the section body with:

   ````markdown
   If you get permission errors during installation, install into a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install mcp-tools-py
   ```
   ````

Leave these unchanged: "Installation in Virtual Environments" including Poetry and Pipenv, "Import Errors" including `--force-reinstall`, "Uninstallation", and the stale `src.main` references.

### `docs/architecture/architecture.md`

Change line 231 to:

```markdown
- Installed into a virtual environment via `pip install` (end user) or `pip install -e ".[dev]"` (development)
```

## HOW

No code integration. The cross-references are the `#installation` anchor in `README.md` and the link from `INSTALL.md` to `README.md`.

## ALGORITHM

1. Make the edits above.
2. Use `search_files` on `INSTALL.md` for `--user`, `USER_BASE`, `\.local/bin`, `pipx` and `setx`. Each must return nothing.
3. Use `search_files` on `INSTALL.md` for `pip install mcp-tools-py`. Each hit must follow venv activation, be the commented `.venv\Scripts\python.exe -m pip` fallback, or be `--force-reinstall`.
4. Use `git diff` to confirm that the client config examples, "Using as a Dependency" and the `--venv-path` mentions in `README.md` are untouched.
5. Run pylint, pytest (`extra_args=["-n", "auto", "-m", "not integration"]`) and mypy, then `run_format_code`.
6. Commit only the three doc files.

## DATA

No data structures or return values.

## Preconditions

- This step changes no Python code, so if pylint, pytest or mypy fail, write one line to `pr_info/.blocked.txt` naming the failing check and stop.

## Commit message

```
docs: require a virtual environment for mcp-tools-py
```
