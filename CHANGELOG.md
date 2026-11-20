# Changelog

Releases of this source package, newest first. The handoff guide has its own version number, shown on its cover.

## 1.6

- The handoff guide's second page now fits on one page in Word. It ran a few lines over, which left the last paragraph alone on a nearly empty page
  and made the guide 12 pages instead of 11. Page 2's spacing was tightened and one sentence (what is not included, and how to keep the source) was
  shortened. Nothing else in the guide changed.

## 1.5

Made the repository ready for a team to pick up and own.

### Added

- `scripts/check.py`: one command that runs the Python lint, types and tests, then the app's lint, types, tests and build and the 3D page check.
  It needs no sign-in.
- Continuous integration (`.github/workflows/ci.yml`), optional CodeQL scanning, Dependabot, a pull request template, `SECURITY.md`,
  `CONTRIBUTING.md`, `.editorconfig`, `.nvmrc` and `.python-version`.
- `pyproject.toml` with the ruff, mypy and coverage configuration. The Python code passes all three, the coverage floor is 80%, and
  `scripts/provision-dataverse.py` is now tested.
- `THIRD-PARTY-NOTICES.md`, generated from the lockfile by `scripts/gen-notices.py`. It also ships inside the Code App package, and the 3D page
  prints the notices for the packages it contains.
- `docs/development.md` (working conventions and common tasks) and `docs/ask-this-contract.md`, both moved out of the README.
- Tests that read the counts of tables, flows and checklist items out of the documents and the app's own text and compare them with the schema,
  the flows and the checklist.

### Changed

- The README is a front door: status, where to start, how it works, a quick check, the known limits and licensing. Its command reference moved to
  `docs/development.md`, and statements that only described the reference environment were removed.
- The generated list of Power Apps data sources is committed, so a clean clone type-checks and builds the app.
- The handoff guide is version 1.3. It now says that a build-and-test CI workflow is included and a deployment pipeline is not, and that the
  source arrives as a private repository or a zip.
- The solution file `dataverse/VizientContractPOC_unmanaged.zip` is refreshed: its app has the corrected How it works text and carries the
  third-party notices.
- The Function's direct dependencies are pinned to the versions the tests ran against (they were ranges), and none has a known vulnerability.

### Fixed

- The README, two documents and the app's How it works text said three tables and "both flows". There are four of each.
- The README described two of the four flows.

## 1.4

- The 3D architecture page `docs/architecture-3d.html`: the Code App's How it works scene as one self-contained file.
- Corrected the scene and the How it works text: four tables and 57 columns, and the flows send files under 4 MiB.
- Handoff guide version 1.2. Refreshed the solution file.

## 1.3

- The architecture document and diagram, the importable Power Platform solution file, the retention findings and handoff guide version 1.1.
- The solution guard fails on any component the project does not declare.

## 1.2

- The guide and the sizing workbook explain the 4 MiB limit and what its fix needs.

## 1.1

- US spelling of "license" on the Time and cost page.

## 1.0

- First cut: the pilot's source, the runbooks, the sizing workbook and the handoff guide.
