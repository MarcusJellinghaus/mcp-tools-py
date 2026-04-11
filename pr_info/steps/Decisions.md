# Decisions Log

1. **Bandit version bumped to `>=1.7.5`** — v1.7.5 is the minimum that supports auto-discovery of `pyproject.toml` and `.bandit` config files.

2. **`errors` is a required field in `BanditResult`** — Removed misleading note about `errors` defaulting to `[]`. It is a required positional field in the NamedTuple.

3. **Return code handling uses `> 1` instead of `== 2`** — Bandit can return codes other than 2 on error. Using `> 1` is more robust.

4. **Integration tests added to Step 5** — `test_integration.py` covers tool-level behavior: unavailability message, happy path with mocked runner, and error handling.

5. **Forbidden-imports contract must include `code_checker_bandit`** — Step 6 now notes the `[importlinter:contract:forbidden-imports]` `forbidden_modules` list must also be updated.

6. **Step 1 marked as dependency pre-step** — The `bandit>=1.7.5` dependency should be installed before implementation begins.
