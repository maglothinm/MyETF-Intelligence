# Artifact-only state revision

This revision leaves `AGENTS.md` unchanged. Repository ID `1349678672` and branch
`main` are literal production gates. No Git branch, cache, external journal, or
simulation is an alternate source for Legislative, Executive, or AI state.

## Restore and publication

All six consumers use `scripts/protected_state.py`. It lists every artifact page
by protected name across the repository, examines the newest candidate, binds it
to one exact successful producer run/attempt/job and ancestor commit, and scans
all relevant run IDs for a newer successful producer. A rerun of an old run ID is
not omitted. Expired, unexpected, failed-attempt, incomplete, or ambiguous output
blocks restoration; it never causes fallback to an older artifact.

Archives are extracted into isolated staging. Path traversal, symlinks, duplicate
paths, malformed JSON, incomplete file inventories, schema failures, changed
hashes, missing IDs, and broken ledger prefixes are rejected before installation.
Read-only consumers receive non-writable clones. Producer state is sealed against
its restore receipt immediately before upload; authority is rechecked and exactly
one successful current-run history row must have been appended. Consumers still
require the producer job and attempt to have completed successfully.

Each protected artifact gains `protected-state-manifest.json` with full file
inventory, SHA-256, sizes, JSONL counts, repository/branch/workflow/run/job/attempt
identity, predecessor, and generation. Manifest validation reads the immediate
predecessor and checks actual bytes/IDs, not just self-reported counters.

Pre-manifest state is accepted only through the exact independently verified
`protected-state-migration.json` allowlist. It is not a fallback or permanent pin.
If an old production workflow creates a newer unmanifested artifact before this
revision lands, export and verify that successor against the captured checkpoint
and review an allowlist update. Never bypass validation or initialize blank state.
Missing/expired immediate predecessors require explicit recovery.

## Investor Edge continuity

Scoring uses matched split/dividend-adjusted stock and benchmark sessions with
versioned price metadata and cutoff checks. Insufficient effective samples yield
`insufficient_data` and a zero modifier. Apply the bounded modifier after the base
hard cap, then reapply the cap; negative modifiers can lower a capped score.

Stable filer IDs are used only when present in source data; no identifier is
invented. Prior profile keys remain as aliases when an identity is upgraded.
Inactive observations are archived, not deleted. Hash-keyed archive revisions
retain the original observation identity/payload. Pending horizons may mature;
completed outcomes and archived records cannot be rewritten or discarded.

## Owner-held scope

Simulation Gmail, extra durable result storage, the persistent Git-backed paper
agent, the Git-backed AI recovery journal, and the dependent dispatch Worker are
on hold. Their local drafts are recoverable under ignored
`.remediation/held-feature-drafts/`, not in active source/workflows or commits.

Run Simulation has one computation job and one one-day TEST dashboard artifact.
It verifies source directory hashes before publication. The historical $10K replay
keeps only `simulation-state`, appending exactly one result to the retained prefix.
Neither receives real alert/provider credentials or writes protected state.

Production candidate-delivery behavior remains the existing implementation.
Durable notification recovery/ambiguous-send handling is not claimed solved.
The historical replay is not a persistent cash/holdings agent. The dashboard
control remains the existing Actions entry point, not authenticated direct dispatch.

## Verification and promotion gates

- `python -m pytest -q` covers active `tests/`; historical `backend/tests` requires
  an absent retired `api` package and remains preserved but outside active CI.
- `bash verify.sh` checks the retired installer cannot mutate a target, preserves
  its tombstone-only payload, tests state behavior/workflow wiring, checks source
  and embedded syntax, builds dashboard assets, and checks the recovery manifest.
- `python scripts/verify_repository.py --node <node-path>` supports Windows and
  explicitly reports skipped Bash checks if Bash is unavailable. Text recovery
  manifest checks use canonical LF bytes; production checkpoint hashes never do.
- CI runs the entire active suite and mandatory Linux/Bash checks. It has read-only
  repository access and no live alert/provider credentials.

Local tests and a review branch are not live acceptance. Do not dispatch production,
merge for cutover, rename, or retire legacy settings while obsolete queued writers
`33219808359` and `33221027676` remain uncontained. Issue #1 stays open.
