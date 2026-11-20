## What changed and why

## Before you merge

- [ ] `python scripts/check.py` passes (CI runs the same checks).
- [ ] Only synthetic contracts and made-up numbers: nothing from a real contract, and no identifier from your `.env`.
- [ ] A new Dataverse object was created through `dataverse/schema.json` and `scripts/provision-dataverse.py`, inside the solution, and `scripts/verify-solution.py` passes.
- [ ] A change to a solution component was followed by `scripts/pull-solution.py`, so `dataverse/solution/` matches.
- [ ] A change to the checklist updated both generated copies (see [Working in this repository](../docs/development.md)).
- [ ] A change to an app dependency was followed by `python scripts/gen-notices.py`.
- [ ] A document or the app's own text that repeats a count or a name was updated with the change.
