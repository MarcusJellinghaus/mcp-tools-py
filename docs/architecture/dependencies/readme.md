# Dependency Management

Practical guide for maintaining architectural boundary enforcement. For architecture overview and layer definitions, see [architecture.md](../architecture.md) Section 5.

## Why Both import-linter and tach?

| Feature | import-linter | tach |
|---------|---------------|------|
| Layer enforcement | Yes | Yes |
| Third-party isolation | Yes (`forbidden` contracts) | No |
| Submodule boundaries | Yes (`independence` contracts) | No |
| Circular dependency detection | Partial (`acyclic_siblings` contracts, not used here; a cycle across `layers` breaks the layer order) | Yes (`forbid_circular_dependencies`) |
| Explicit `depends_on` | No | Yes |

Use both — tach for high-level layers with explicit dependencies, import-linter for fine-grained import rules. Module-level import cycles are caught by pylint `R0401` (`cyclic-import`).

## How to Update

### `tach.toml`
1. Add/modify `[[modules]]` with `path`, `layer`, `depends_on`
2. Run `tach check`
3. Regenerate graph: `tools/tach_docs.bat` / `./tools/tach_docs.sh`

### `.importlinter`
1. Add `[importlinter:contract:name]` section (type: `layers`, `forbidden`, or `independence`)
2. Run `lint-imports`

### `vulture_whitelist.py`
1. Add symbol with comment: `_.attribute_name  # reason`
2. Run `vulture src tests vulture_whitelist.py --min-confidence 60`

## When to Add New Rules

- **New external dependency** → add import-linter `forbidden` contract to isolate it
- **New top-level module** → add to `tach.toml` with layer and `depends_on`
- **Two modules must stay independent** → add import-linter `independence` contract
- **Moving/renaming modules** → update both `tach.toml` and `.importlinter`
- **After any change** → regenerate visualizations and update `architecture.md` Section 5

## Visualization

The files `dependency_graph.html`, `pydeps_graph.dot`, and `pydeps_graph.svg` in this directory are generated — do not edit them manually. Regenerate after config changes:

```bash
tools/tach_docs.bat          # Mermaid graph → dependency_graph.html
tools/pydeps_graph.bat       # pydeps → pydeps_graph.dot (+ .svg if GraphViz installed)
```
