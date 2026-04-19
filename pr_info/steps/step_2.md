# Step 2: Add obsidian-wiki and search_reference_files permissions

## LLM Prompt

> Read `pr_info/steps/summary.md` for context. Implement Step 2: add 11 `mcp__obsidian-wiki__*` permissions (between tools-py and workspace blocks) and `mcp__workspace__search_reference_files` (after `mcp__workspace__search_files`) in `.claude/settings.local.json`. No code quality checks needed — config-only change.

## WHERE

- `.claude/settings.local.json`

## WHAT

### Insert obsidian-wiki permissions (after `mcp__tools-py__get_library_source`, before `mcp__workspace__get_reference_projects`):

```json
"mcp__obsidian-wiki__add-tags",
"mcp__obsidian-wiki__create-directory",
"mcp__obsidian-wiki__create-note",
"mcp__obsidian-wiki__delete-note",
"mcp__obsidian-wiki__edit-note",
"mcp__obsidian-wiki__list-available-vaults",
"mcp__obsidian-wiki__move-note",
"mcp__obsidian-wiki__read-note",
"mcp__obsidian-wiki__remove-tags",
"mcp__obsidian-wiki__rename-tag",
"mcp__obsidian-wiki__search-vault",
```

### Insert workspace permission (after `mcp__workspace__search_files`):

```json
"mcp__workspace__search_reference_files"
```

## HOW

- Use `mcp__workspace__edit_file` with 2 edits
- Obsidian-wiki block: match on `"mcp__tools-py__get_library_source",` and append the new lines after it
- search_reference_files: match on `"mcp__workspace__search_files"` and append the new line after it

## Commit

```
chore(config): add obsidian-wiki and search_reference_files permissions (#172)
```
