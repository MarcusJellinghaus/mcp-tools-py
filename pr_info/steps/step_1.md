# Step 1: Add `[tool.mcp-coder.from-github]` config to pyproject.toml

## Context

See [summary.md](summary.md) and issue #128.

## WHERE

- `pyproject.toml` — insert new section after `[tool.pylint.messages_control]` block, before the `# Include tools directory` comment and `[tool.setuptools]`.

## WHAT

Add the following TOML section:

```toml
[tool.mcp-coder.from-github]
# Installed WITH deps (leaves — picks up new external deps)
packages = [
    "mcp-config-tool @ git+https://github.com/MarcusJellinghaus/mcp-config.git",
    "mcp-workspace @ git+https://github.com/MarcusJellinghaus/mcp-workspace.git",
]
# Installed WITHOUT deps (depend on siblings — avoid downgrading)
packages-no-deps = [
    "mcp-coder @ git+https://github.com/MarcusJellinghaus/mcp_coder.git",
]
```

## HOW

Single edit: insert the block between the `[tool.pylint.messages_control]` section and the `[tool.setuptools]` section in `pyproject.toml`.

## DATA

No functions, no return values, no algorithms. This is a static configuration block.

## Tests

No tests required — this is a config-only change with no code impact. The issue explicitly states: "no code or test changes needed."

## Verification

1. Run `mcp__tools-py__run_pylint_check` — must pass (config-only, no code touched)
2. Run `mcp__tools-py__run_pytest_check` — must pass (no behavior change)
3. Run `mcp__tools-py__run_mypy_check` — must pass (no type changes)
4. Validate TOML syntax is correct (no parse errors)

## Commit

One commit: `chore: add [tool.mcp-coder.from-github] config to pyproject.toml`

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.

Implement step 1: Add the [tool.mcp-coder.from-github] section to pyproject.toml.
Insert it after [tool.pylint.messages_control] and before [tool.setuptools],
using the exact content specified in the step file.

After editing, run all three code quality checks (pylint, pytest, mypy).
Then commit with message: "chore: add [tool.mcp-coder.from-github] config to pyproject.toml"
```
