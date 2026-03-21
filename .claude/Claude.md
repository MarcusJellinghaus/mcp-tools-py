--- This file is used by Claude Code - similar to a system prompt. ---

# ⚠️ MANDATORY INSTRUCTIONS - MUST BE FOLLOWED ⚠️

**THESE INSTRUCTIONS OVERRIDE ALL DEFAULT BEHAVIORS - NO EXCEPTIONS**

## 🔴 CRITICAL: ALWAYS Use MCP Tools

**MANDATORY**: You MUST use MCP tools for ALL operations when available. DO NOT use standard Claude tools.

**BEFORE EVERY TOOL USE, ASK: "Does an MCP version exist?"**

### Tool Mapping Reference

| Task | ❌ NEVER USE | ✅ USE MCP TOOL |
|------|--------------|------------------|
| Read file | `Read()` | `mcp__filesystem__read_file()` |
| Edit file | `Edit()` | `mcp__filesystem__edit_file()` |
| Write file | `Write()` | `mcp__filesystem__save_file()` |
| Run pytest | `Bash("pytest ...")` | `mcp__tools-py__run_pytest_check()` |
| Run pylint | `Bash("pylint ...")` | `mcp__tools-py__run_pylint_check()` |
| Run mypy | `Bash("mypy ...")` | `mcp__tools-py__run_mypy_check()` |
| Git operations | ✅ `Bash("git ...")` | ✅ `Bash("git ...")` (allowed) |

## 🔴 CRITICAL: Code Quality Requirements

**MANDATORY**: After making ANY code changes (after EACH edit), you MUST run ALL THREE code quality checks using the EXACT MCP tool names below:

```
mcp__tools-py__run_pylint_check
mcp__tools-py__run_pytest_check
mcp__tools-py__run_mypy_check
```

This runs:

- **Pylint** - Code quality and style analysis
- **Pytest** - All unit and integration tests
- **Mypy** - Static type checking

**⚠️ ALL CHECKS MUST PASS** - If ANY issues are found, you MUST fix them immediately before proceeding.

### 📋 Pytest Execution Requirements

**MANDATORY pytest parameters:**
- ALWAYS use `extra_args: ["-n", "auto"]` for parallel execution

**Available markers in pyproject.toml:**
- `integration`: Integration tests requiring external resources

**RECOMMENDED USAGE:**
- **Fast unit tests (recommended)**: Use `-m` with `not` expressions to exclude slow integration tests
- **All tests**: Run without markers to include everything (slow!)
- **Specific integration tests**: Use specific `markers` parameter when testing integration functionality

**Examples:**

```python
# RECOMMENDED: Fast unit tests (excludes integration tests)
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])

# All tests including slow integration tests (not recommended for regular development)
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto"])

# Specific integration tests (only when needed)
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto"], markers=["integration"])
```

**Important:** Without the `-m "not integration"` exclusions, pytest runs ALL tests including slow integration tests that may require external resources. For regular development, always use the exclusion pattern as shown in the first example above.

## 📁 MANDATORY: File Access Tools

**YOU MUST USE THESE MCP TOOLS** for all file operations:

```
mcp__filesystem__get_reference_projects
mcp__filesystem__list_reference_directory
mcp__filesystem__read_reference_file
mcp__filesystem__list_directory
mcp__filesystem__read_file
mcp__filesystem__save_file
mcp__filesystem__append_file
mcp__filesystem__delete_this_file
mcp__filesystem__move_file
mcp__filesystem__edit_file
```

**⚠️ ABSOLUTELY FORBIDDEN:** Using `Read`, `Write`, `Edit`, `MultiEdit` tools when MCP filesystem tools are available.

### Quick Examples

```python
# ❌ WRONG - Standard tools
Read(file_path="src/example.py")
Edit(file_path="src/example.py", old_string="...", new_string="...")
Write(file_path="src/new.py", content="...")
Bash("pytest tests/")

# ✅ CORRECT - MCP tools
mcp__filesystem__read_file(file_path="src/example.py")
mcp__filesystem__edit_file(file_path="src/example.py", edits=[...])
mcp__filesystem__save_file(file_path="src/new.py", content="...")
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto"])
```

**WHY MCP TOOLS ARE MANDATORY:**

- Proper security and access control
- Consistent error handling
- Better integration with the development environment
- Required for this project's architecture

## ✍️ Writing Style

**Be concise.** Keep code comments, commit messages, documentation changes, and prompt additions short and direct. If one line works, don't use three.

## 🚨 COMPLIANCE VERIFICATION

**Before completing ANY task, you MUST:**

1. ✅ Confirm all code quality checks passed using MCP tools
2. ✅ Verify you used MCP tools exclusively (NO `Bash` for code checks, NO `Read`/`Write`/`Edit` for files)
3. ✅ Ensure no issues remain unresolved
4. ✅ State explicitly: "All CLAUDE.md requirements followed"

## 🔧 DEBUGGING AND TROUBLESHOOTING

**When tests fail or skip:**
- Use MCP pytest tool with verbose flags: `extra_args: ["-v", "-s", "--tb=short"]`
- For integration tests, check if they require external configuration (tokens, URLs)
- Never fall back to `Bash` commands - always investigate within MCP tools
- If MCP tools don't provide enough detail, ask user for guidance rather than using alternative tools

## 🔧 MCP Server Issues

**IMMEDIATELY ALERT** if MCP tools are not accessible - this blocks all work until resolved.

## 🔄 Git Operations

**MANDATORY: Before ANY commit:**

```bash
# ALWAYS run format_all before committing
./tools/format_all.sh   # Linux/macOS
tools\format_all.bat    # Windows

# Then verify formatting worked
git diff  # Should show formatting changes if any
```

**Format all code before committing:**

- Run `./tools/format_all.sh` (or `tools\format_all.bat` on Windows) to format with black and isort
- Review the changes to ensure they're formatting-only
- Stage the formatted files
- Then commit

**ALLOWED git operations via Bash tool:**

```
git status
git diff
git log
git fetch
git ls-tree
```

**⚠️ Bash discipline (applies to subagents too):**

- No `cd` prefix, no `git -C` — the working directory is already correct. Just `git status`, never `git -C "/some/path" status`.
- Stick to approved commands above. Avoid unapproved bash commands — they trigger user authorization prompts and interrupt the workflow.
- Do not chain approved commands with unapproved ones (e.g. `git status && echo "---" && git diff`). The `echo` makes the whole command unapproved. Run approved commands separately instead.

**Git commit message format:**

- Use standard commit message format without advertising footers
- Focus on clear, descriptive commit messages
- No Claude Code attribution or links

**Pull Request format:**

- No "Generated with Claude Code" footer or similar attribution
- Focus on clear summary and test plan
- Keep PR descriptions concise and professional

## 📏 File Size Check

Check for large files (>750 lines) that may impact LLM context:

```bash
mcp-coder check file-size --max-lines 750
mcp-coder check branch-status --llm-truncate
```

For guidance on splitting large files, consider breaking them into smaller, focused modules.
