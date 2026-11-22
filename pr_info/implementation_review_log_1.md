# review-implementation review log 1

## Round 1 — 2026-11-22
**Findings**:
Reviewing the #294 branch diff. Checking how the summary dict is built, then the tests.Still reviewing; checking that `-o addopts=` survives `sanitize_extra_args` and that the reply-level tests cover it.src/mcp_tools_py/code_checker_pytest/marker_hint.py:65 — low — `_skip_kwargs` accepts any identifier as a kwarg value and any `_IDENT` token as a kwarg key. pytest's `single_kwarg` only accepts a string, an integer or `True`/`False`/`None` as the value, and the key must pass `isidentifier()` and must not be a Python keyword. So an expression like `a(x=foo) and not unit` counts as valid, `unit` is treated as negated and gets no hint on the resulting exit 4 when strict markers are off. That contradicts the plan's claim that the parse accepts exactly what pytest's grammar accepts (decision 17's fallback is "can't be parsed → every unregistered name counts").
**Decisions**:
Verdict(decision='tasks', tasks=["Tighten `_skip_kwargs` in src/mcp_tools_py/code_checker_pytest/marker_hint.py:65 to match pytest's `single_kwarg` grammar. Reject a kwarg key that fails `str.isidentifier()` or is a Python keyword (`keyword.iskeyword`). Accept as the value only a quoted string, an integer literal, or `True`/`False`/`None`, and reject bare identifiers such as `foo`. On rejection, report the expression as unparseable so that decision 17's fallback applies and every unregistered name counts.", 'Add unit tests in the marker_hint tests: `a(x=foo) and not unit` should be treated as unparseable, so `unit` gets a hint on exit 4. A keyword key such as `a(if=1)` should also be unparseable. Valid forms `a(x=1)`, `a(x="s")` and `a(x=True)` should still parse.'], escalate_reason=None)
**Changes**:
applied
