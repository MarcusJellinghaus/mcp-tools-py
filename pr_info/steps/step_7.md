# Step 7 — Documentation

Implements **Decision 14**. See [summary.md](./summary.md).

Two of these lines are the same defect this issue exists to remove, living in a
different file. Independent of Steps 5 and 6; do last so it describes the shipped
behaviour.

## WHERE

| File | Line(s) | Change |
|---|---|---|
| `README.md` | `:101-102` | parameter table |
| | `:125` | precedence bullet |
| | `:132` | Environment Configuration paragraph |
| | `:145` | "Correct Configuration" JSON example |
| | `:163` | "Incorrect Configuration" JSON example |
| | `:174` | troubleshooting: "No module named pytest" |
| | `:175` | troubleshooting: "ruff not found" |
| | `:176` | troubleshooting: startup/caching claim |
| `docs/architecture/architecture.md` | `:224` | Deployment View bullet |

Line numbers are current as of `bfd4cc8`; #226 already shifted
`architecture.md` (the issue cites `:213`). Re-read before editing.

## WHAT

**`README.md:101-102`** — `--python-executable` leads. `--venv-path` is either
dropped from the table or listed as deprecated: still accepted, still resolves the
interpreter, no longer used for tool detection. Delete the sentence "Required for
the ones located as binaries: ruff, bandit, vulture, tach and lint-imports" — that
is now false.

**`README.md:125`** — the precedence bullet stays true (`--venv-path` still wins
for interpreter resolution) but should say that is now its only effect.

**`README.md:132`** — currently: "ruff, bandit, vulture, tach and lint-imports are
located as binaries inside `--venv-path`". They are located next to
`--python-executable`. Rewrite.

**`README.md:145` and `:163`** — both JSON examples pass `--venv-path`. Switch to
`--python-executable`, e.g. `"${VIRTUAL_ENV}\\Scripts\\python.exe"`.

**`README.md:174`** — currently recommends checking `--venv-path` as the fix for
"No module named pytest". That is the misdiagnosis this issue removes. Name
`--python-executable`.

**`README.md:175`** — currently: "these tools are located as binaries inside
`--venv-path`. Set `--venv-path`...". They are found next to the interpreter.

**`README.md:176`** — currently: "Tool availability is checked at startup and
cached for the session." Untrue since #167 made the probe group lazy, and stale in
exactly the way this change targets. Replace with something accurate: the console-
script tools are located at startup; the rest are checked on first use; both
results are cached for the session, so restart after installing.

**`docs/architecture/architecture.md:224`** — "Optional: `--venv-path` to use a
specific virtual environment for tool execution" → `--python-executable`.

## HOW

- Every one of these leads with `--python-executable`.
- Worth one short paragraph or troubleshooting bullet, since it is new behaviour a
  user can hit: a missing `--python-executable` now fails at startup with
  `FileNotFoundError` naming the flag (Decision 12). Both `.mcp.json` shapes build
  that value by interpolating an environment variable — `${VIRTUAL_ENV}` here,
  `${MCP_CODER_VENV_DIR}` in mcp-config — so an unset variable now fails loudly
  instead of degrading to fifteen tool-level messages.
- Do not document a `--venv-path` removal. It is soft-deprecated.

## ALGORITHM

None.

## DATA

None.

## TESTS

No new tests — documentation only. Verify by reading `--help` output against the
README parameter table, and confirm no `--venv-path` recommendation survives:

```
mcp__mcp-workspace__search_files(pattern="--venv-path", glob="**/*.md")
```

Remaining hits should only be deprecation notes.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_7.md`. Steps 1-6 are done.
>
> Implement Step 7 only: update `README.md` and `docs/architecture/architecture.md`
> so every mention of environment configuration leads with `--python-executable`.
> Covered: the parameter table, the precedence bullet, the Environment
> Configuration paragraph, both JSON examples, all three troubleshooting bullets,
> and the Deployment View bullet in the architecture doc. Re-read the files for
> current line numbers first — #226 already shifted the architecture doc.
>
> Two of these are the same misdiagnosis this issue exists to remove: the
> troubleshooting entry recommends `--venv-path` as the fix for "No module named
> pytest", and the claim that "ruff, bandit, vulture, tach and lint-imports are
> located as binaries inside `--venv-path`" is now false — they are found next to
> the interpreter. One line below, "Tool availability is checked at startup and
> cached for the session" has been untrue since #167 made the probe group lazy;
> replace it with an accurate description of the eager/lazy split.
>
> Document `--venv-path` as soft-deprecated — still accepted, still resolves the
> interpreter, no longer used for tool detection. Do not describe it as removed.
>
> Add a brief note that a `--python-executable` pointing at a non-existent path now
> fails at startup, since both real `.mcp.json` shapes build that value by
> interpolating an environment variable.
>
> Documentation only — no code, no tests. Then run `run_format_code` and
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])` to confirm
> nothing regressed. Commit as one commit.
