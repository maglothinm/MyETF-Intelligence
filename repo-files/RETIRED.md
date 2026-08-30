# Recovery overlay retired

This directory intentionally contains no installable source, workflow, configuration,
or test files.

The August 25 recovery overlay was retired on August 29, 2026 because it predated the
canonical PolitiTrack cutover. Installing it would replace current runtime files and
reintroduce a second scheduled Legislative state writer. It also lacked the AI analyst,
dashboard publisher, Investor Edge tests, isolated Run Simulation, and the isolated
$10K portfolio simulator.

Use the checked-in files at the repository root as the only runtime source. Recover
production state only from the protected GitHub Actions artifacts named:

- `legislative-tracker-state`
- `executive-tracker-state`
- `ai-analysis-state`

Simulation artifacts use the separate `simulation-*` namespace. Never initialize a
new baseline as a substitute for a missing protected artifact.

Retiring this source overlay does not modify `.trade-tracker/`, Actions artifacts,
caches, releases, or any other user or production data.
