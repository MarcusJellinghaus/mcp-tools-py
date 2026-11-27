# review-plan review log 1

## Round 1 — 2026-11-27
**Findings**:
Now knowledge base files and the source.Reviewing plan against code; checking test-file sizes and the existing `_patch_full_depth_clean` helper.Verifying the architecture-doc claim in step 3 against actual callers of `read_pyproject_tool_tables` / `_load_pyproject`.pr_info/steps/step_2.md:90 — medium — The `_project` helper always writes `where = ["src"]` and `testpaths = ["tests"]`, but tests 5 and 7 (`testpaths = ["tools/tests"]`) and test 6 (`where = ["."]`) need other values. `extra_toml` can't override them, because redefining `[tool.pytest.ini_options]` or `[tool.setuptools.packages.find]` makes the TOML invalid. Give the helper `where`/`testpaths` parameters, or say those tests write their own `pyproject.toml`.
pr_info/steps/step_2.md:103 — low — `[str(tmp_path / "tools")]` is listed as a `@pytest.mark.parametrize` value, but `tmp_path` doesn't exist when tests are collected. State that the absolute-path case is built inside the test body, for example as a callable or a placeholder that the test turns into a path.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_2.md (around line 90), give the `_project` helper `where` and `testpaths` parameters, defaulting to `["src"]` and `["tests"]`. Update tests 5 and 7 to pass `testpaths=["tools/tests"]` and test 6 to pass `where=["."]`, so none of them redefines `[tool.pytest.ini_options]` or `[tool.setuptools.packages.find]` through `extra_toml`.', 'In pr_info/steps/step_2.md (around line 103), take `[str(tmp_path / "tools")]` out of the `@pytest.mark.parametrize` values. Use a placeholder such as `"<abs>/tools"` and say that the test body replaces it with `str(tmp_path / "tools")`, because `tmp_path` doesn\'t exist when tests are collected.'], escalate_reason=None)
**Changes**:
applied
