# Contributing

This repository is a pilot starter kit that you now own. These notes keep a change consistent with how it was built.

1. Read [Working in this repository](docs/development.md): the checks, the rules the repository follows and how to make the common changes.
2. Make the change on a branch and run `python scripts/check.py`. It needs no sign-in. Fix what it reports.
3. Open a pull request. The template lists what to confirm, and continuous integration runs the same checks.

Two rules matter more than the rest. Everything in the Power Platform lives inside the solution, created through `dataverse/schema.json` and the
provisioning scripts, never by hand and moved in later. And the repository holds synthetic contracts only: a real contract, or the labels for one,
must never be committed.

Report a vulnerability as [SECURITY.md](SECURITY.md) describes, not in a public issue.
