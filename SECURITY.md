# Security

This repository is a pilot starter kit, delivered with a guide in `docs/`. The guide and the [architecture](docs/architecture.md) say what its
security posture is today and what must be settled before it is used for real contracts or in production: retention and deletion, least-privilege
roles, secret storage and rotation, and monitoring (decisions C1 to C3 in the guide).

## Reporting a vulnerability

Replace this section with your own process when the repository moves into your organization. Until then, report a suspected vulnerability
privately to the people who delivered the repository to you. Do not open a public issue, and do not include a contract, a secret or a token in
the report.

## Handling secrets and data

- Secrets, tokens and contracts never belong in this repository. `.env` is git-ignored, and `python scripts/leak-scan.py` checks what Git would
  commit against the identifiers in your `.env`.
- The repository holds synthetic contracts only. `*.pdf` is git-ignored, and `eval/gold` accepts only the synthetic gold labels.
- Azure resources authenticate with managed identities and Entra tokens, not keys. The Function key that the analysis flow uses is stored in a text
  environment variable in the solution; the guide (decision C3) recommends replacing it.
- Document content, credentials and raw model results must not be logged.

## Keeping dependencies current

[Dependabot](.github/dependabot.yml) proposes weekly updates to the app's npm packages, the Python requirements and the workflows. After a change
to an app dependency, run `python scripts/gen-notices.py`; the tests fail until the third-party notices match the lockfile.

Known-vulnerability status on 19 November 2026 (run these again before you rely on them):

- `npm audit --omit=dev` in `contract-review/` found nothing in the packages the app ships.
- `npm audit` there lists seven moderate advisories, all from one denial-of-service advisory in `minimatch` (GHSA-g3hv-75wg-m249) that reaches the
  build through `typescript-eslint`, a development-only tool. The only fix offered is a pre-release version, so it is left as it is.
- `python -m pip_audit -r function/requirements.txt --no-deps` found nothing in the Function's pinned requirements, and `python -m pip_audit` found
  nothing in the packages the tests run against (install `pip-audit` first).
