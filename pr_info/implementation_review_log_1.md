# review-implementation review log 1

## Round 1 — 2026-11-22
**Findings**:
Reviewing the #294 branch diff. Checking how the summary dict is built, then the tests.Still reviewing; checking that `-o addopts=` survives `sanitize_extra_args` and that the reply-level tests cover it.src/mcp_tools_py/code_checker_pytest/marker_hint.py:65 — low — `_skip_kwargs` accepts any identifier as a kwarg value and any `_IDENT` token as a kwarg key. pytest's `single_kwarg` only accepts a string, an integer or `True`/`False`/`None` as the value, and the key must pass `isidentifier()` and must not be a Python keyword. So an expression like `a(x=foo) and not unit` counts as valid, `unit` is treated as negated and gets no hint on the resulting exit 4 when strict markers are off. That contradicts the plan's claim that the parse accepts exactly what pytest's grammar accepts (decision 17's fallback is "can't be parsed → every unregistered name counts").
**Decisions**:
Verdict(decision='tasks', tasks=["Tighten `_skip_kwargs` in src/mcp_tools_py/code_checker_pytest/marker_hint.py:65 to match pytest's `single_kwarg` grammar. Reject a kwarg key that fails `str.isidentifier()` or is a Python keyword (`keyword.iskeyword`). Accept as the value only a quoted string, an integer literal, or `True`/`False`/`None`, and reject bare identifiers such as `foo`. On rejection, report the expression as unparseable so that decision 17's fallback applies and every unregistered name counts.", 'Add unit tests in the marker_hint tests: `a(x=foo) and not unit` should be treated as unparseable, so `unit` gets a hint on exit 4. A keyword key such as `a(if=1)` should also be unparseable. Valid forms `a(x=1)`, `a(x="s")` and `a(x=True)` should still parse.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-11-22
**Findings**:
Reviewing the #294 diff — checking test coverage for the acceptance list next.Review done: the plan's design and all 19 decisions are implemented as specified. The tests cover the acceptance list, including the >500-char stderr case and the unattended contract. One deviation from decision 5 is deliberate and tested: under xdist, a clean pass whose `-m` comes from the project defaults still shows the `addopts` line, because xdist never passes the deselected count back. The only finding is a minor parser mismatch:

src/mcp_tools_py/code_checker_pytest/marker_hint.py:36 — low — `_TOKEN` accepts quoted strings containing a backslash, and newlines count as whitespace. pytest's Scanner rejects both (`escaping with "\" not supported`; only space and tab are skipped). So `scan_expression` reports such expressions as valid, and decision 17's "unparseable → every unregistered name counts" fallback doesn't apply. A negated unknown name then gets no hint on a `Wrong expression passed to '-m'` exit 4 when strict markers are off.
**Decisions**:
Verdict(decision='tasks', tasks=["Bring the `_TOKEN` scanner in src/mcp_tools_py/code_checker_pytest/marker_hint.py:36 in line with pytest's Scanner. Treat a quoted string that contains a backslash as unparseable. Skip only spaces and tabs as whitespace, so a newline or any other whitespace character makes the expression unparseable. In both cases `scan_expression` must report the expression as invalid, which triggers decision 17's 'every unregistered name counts' fallback.", 'Add unit tests to the marker_hint tests. An expression with a backslash inside a quoted kwarg value, such as `a(x="b\\\\c") and not unit`, should be unparseable so that `unit` gets a hint on exit 4. The same applies to an expression containing a newline, such as `a and\\nnot unit`. Tab-separated tokens should still parse.'], escalate_reason=None)
**Changes**:
applied
