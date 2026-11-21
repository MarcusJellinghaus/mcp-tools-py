# Step 7 — README and architecture docs name pytest-json-report

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_7.md`).
> Steps 1–6 are already done. This step changes docs only (no tests).
> Run `run_format_code`, pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `README.md`
- `docs/architecture/architecture.md`

## WHAT

Name `pytest-json-report` everywhere the project-env packages are listed. Keep each
edit minimal; match the surrounding wording.

### README.md

| Spot | Change |
|---|---|
| "Optional Parameters → Python Configuration", `--python-executable` row | "pytest, pylint, mypy and deptry run in it …, with deptry **and pytest-json-report** installed" |
| "Environment Configuration", project-env bullet | "pytest (with pytest-json-report), pylint, mypy and deptry"; add: pytest-json-report is a runtime dependency of mcp-tools-py, so it is present when mcp-tools-py is installed into the project env — installing mcp-tools-py in its own environment does not put it into the project's environment |
| "Correct Configuration" | "with pytest, pytest-json-report, pylint, mypy and deptry installed in it" |
| "Incorrect Configuration" | add pytest-json-report to the list; "those four" → "those five" |
| Troubleshooting "No module named pytest" | "(or pylint/mypy/deptry)" also covers "pytest-json-report is not available"; same advice: install it in the project's environment |
| Troubleshooting "After installing missing tools" | pytest, pylint, mypy, deptry, **pytest-json-report and pytest-cov** are answered by the cached probe, so a refusal persists until the MCP server restarts; restart after installing any of them |

### docs/architecture/architecture.md

| Spot | Change |
|---|---|
| §5 Module Overview, `utils/tool_context.py` bullet | project env "used by pytest (with pytest-json-report), pylint, mypy and deptry"; mention the third question: is a distribution (pytest-json-report, pytest-cov) installed |
| §7 Deployment View, project-env bullet | "pytest, pytest-json-report, pylint, mypy and deptry" |
| "Only pytest, pylint, mypy and deptry need the configurable environment" paragraph | add that pytest-json-report must sit in the same env, since pytest loads it as a plugin |

§2 Dependencies → Runtime already names pytest-json-report; leave it.

## Check

Search `README.md` and `docs/` for "pylint, mypy and deptry" and "deptry" lists; every
project-env package list must now include pytest-json-report.
