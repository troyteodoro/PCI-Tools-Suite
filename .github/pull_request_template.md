## What changed

<!-- One or two sentences. The why matters more than the what. -->

## Invariants

Delete the lines that do not apply. These are the rules from CLAUDE.md that no gate can
fully check for you.

- [ ] **New data-plane table**: added to `DATA_PLANE_TABLES` *and* given RLS, FORCE, a
      policy and grants in the migration. (`alembic check` and the isolation suite cover
      the rest automatically.)
- [ ] **Evidence writes** are content-addressed and supersede rather than update.
      `collected_at` is set from when the evidence was true, not when it was ingested.
- [ ] **Any ingest path** runs PAN detection before anything is written to storage.
- [ ] **Rule changes** bump the rules-pack version and ship fixture tests. No
      `datetime.now()` and no I/O inside a rule — the clock is injected.
- [ ] **UI copy** states what evidence exists and what a rule found. It does not assert
      compliance; the QSA determines that.
- [ ] **Dependency change**: `make lock` was run and the regenerated
      `requirements*.txt` is in this PR.

## Verification

<!-- What you ran. `make test`, `make smoke`, a screenshot, the failing case now passing. -->
