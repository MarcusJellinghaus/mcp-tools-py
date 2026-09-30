# Decisions

## Version reporting follows the issue literally (plan review, round 5)

Each formatter step reports its version by running `<binary> --version` on the same
resolved binary the step invokes, inside that step's own timeout budget. A failure to
determine the version (timeout, execution error, unparsable output) yields `"unknown"` and
never fails the step. This replaces the earlier package-metadata lookup
(`importlib.metadata` / `get_environment_info(...).distributions`) and its "deviation from
the issue text" note. Environment threading stays, because `formatter_binary(name,
environment)` still needs it to resolve the binary.
