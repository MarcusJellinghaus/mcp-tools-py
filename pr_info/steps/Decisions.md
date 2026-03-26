# Decisions

## 1. Merge Steps 2 and 3 into a single step

Steps 2 (signature change) and 3 (batch loop) were merged because step 2 alone creates
a broken transitional state where multi-element lists are silently truncated (only
`symbol_names[0]` is processed). The merged step changes the signature and implements
the batch logic atomically.

## 2. Duplicate check in validation

Added a duplicate check within `symbol_names` to the upfront validation:
`if len(symbol_names) != len(set(symbol_names))` returns an error. This prevents
confusing behavior when the same symbol is listed twice.

## 3. Dry-run algorithm for batch moves

For batch dry-run: create the dest file once (if needed), loop through all symbols
accumulating change previews, then clean up the temp file once at the end. Avoids
per-symbol temp file creation/cleanup.

## 4. "All-or-nothing" applies to validation only

The all-or-nothing guarantee covers **validation** (symbol existence, collision checks,
duplicate checks). Runtime rope errors during the actual move loop are best-effort — if
the 2nd symbol fails after the 1st has been moved, there is no rollback. This is
acceptable because validation already confirmed the symbols exist and no collisions are
present. The test `test_move_symbol_batch_validation_all_or_nothing` tests validation
failures, not runtime errors.

## 5. Test numbering for Step 5 (manual test plan)

Existing Test 7 uses 7a (dry run), 7b (apply), 7c (teardown). New batch tests are
numbered 7d (batch dry run), 7e (batch apply), 7f (batch teardown) to avoid conflicts
with existing 7c.

## 6. Step renumbering after merge

After merging old Steps 2+3:
- Step 1: from-global preference (unchanged)
- Step 2: Batch move_symbol (merged)
- Step 3: Self-import removal (was Step 4)
- Step 4: Result output with review reminders (was Step 5)
- Step 5: Manual test plan update (was Step 6)
