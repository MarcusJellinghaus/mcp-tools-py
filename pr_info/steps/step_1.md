# Step 1: Migrate .mcp.json reference-project args to new KV format

## LLM Prompt

> Read `pr_info/steps/summary.md` for context. Implement Step 1: migrate the four `--reference-project` values in `.mcp.json` from the old `name=path` format to the new `name=X,path=Y,url=Z` format. Also rename `p_coder_utils` to `p_coder-utils`. No code quality checks needed — config-only change.

## WHERE

- `.mcp.json`

## WHAT

Replace each `--reference-project` value string (4 total):

| Old value | New value |
|-----------|-----------|
| `p_coder=${USERPROFILE}\\Documents\\GitHub\\mcp_coder` | `name=p_coder,path=${USERPROFILE}\\Documents\\GitHub\\mcp_coder,url=https://github.com/MarcusJellinghaus/mcp_coder` |
| `p_config=${USERPROFILE}\\Documents\\GitHub\\mcp-config` | `name=p_config,path=${USERPROFILE}\\Documents\\GitHub\\mcp-config,url=https://github.com/MarcusJellinghaus/mcp-config` |
| `p_workspace=${USERPROFILE}\\Documents\\GitHub\\mcp-workspace` | `name=p_workspace,path=${USERPROFILE}\\Documents\\GitHub\\mcp-workspace,url=https://github.com/MarcusJellinghaus/mcp-workspace` |
| `p_coder_utils=${USERPROFILE}\\Documents\\GitHub\\mcp-coder-utils` | `name=p_coder-utils,path=${USERPROFILE}\\Documents\\GitHub\\mcp-coder-utils,url=https://github.com/MarcusJellinghaus/mcp-coder-utils` |

## HOW

- Use `mcp__workspace__edit_file` with 4 edits (one per reference-project line)
- Preserve escaped backslashes (`\\`) in paths

## Commit

```
chore(config): migrate .mcp.json reference-projects to new KV format (#172)
```
