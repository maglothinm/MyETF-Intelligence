# Reviewed release of the OCR health publication correction

**Execution outcome:** This procedure completed at `2026-09-18T20:56:33.832832Z` with `DEPLOYED_WITH_OCR_WARNINGS`. All original schedules were restored; Vault remains paused. Do not replay it. See [final deployment and remaining acceptance](2026-09-18-ocr-deployed.md) for actual build/digest, executions, preservation, natural scheduling and the incomplete owner upload test. The preparation requirements below describe the reviewed procedure, not outstanding deployment work.

Issue #182; application correction [PR #186](https://github.com/maglothinm/MyETF-Intelligence/pull/186), merged source `a2a15edb30895ece37b690e50e0f95fb1eaa2649`. Exact PR-head OCR CI `35389493194` and Investor Edge CI `35389493190` passed. The immutable image build is `db933dc7-5e85-483f-b7b0-655a0ddf7dc0`; its completion/digest must be verified before preparation.

The previous acceptance failed because the public projection stripped the OCR heartbeat. Recovery verified preservation and returned all original schedules to ENABLED at `2026-09-18T20:02:20.643694+00:00`, with Vault PAUSED and OCR disabled. The migration and retained new-image state are preserved. This is a new reviewed release of a concrete correction, not a replay of the failed acceptance.

`scripts/ocr_health_repair_release.py` uses the original v2.2 engine unchanged, requiring SHA-256 `bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`, and the same checksum-pinned read-only audit. It requires both closed journal hashes:

- Original no-submission recovery: `cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`.
- Recovered deployed-image attempt: `75d1a7042faea337e2b79471a2f1b93b0981bfc60ecf4aa5d839516d4ee38f8c`.

Read-only `--prepare` checks every live runtime specification against the verified recovered configuration, every original schedule field/state, the exact successful repaired-source build and registry digest, and existing private database/recovery settings. It seals both attempts and their receipts, then writes one deterministic preparation workspace under the original workspace: `ocr-health-repair-a2a15edb3089`. Preparation never overwrites an existing workspace or performs a deployment. The copied recovery audit is explicitly predecessor evidence; it is not relabeled a frozen baseline.

The wrapper binds only the engine/audit release-identity constants to the independently verified repaired source/image. SQL, permissions, resource scope and release/recovery behavior are unchanged. It holds the original workspace lock and the new workspace lock, and rechecks all sealed old evidence on every journal write. Deployment starts at `preparing`, with empty steps and no success flags. It requires fresh preflight, inventory/drain, a new frozen baseline, controlled producer successors, full preservation/publication acceptance and verified restoration. Failed/closed repair attempts remain read-only and cannot be reopened. No extra schedule, IAM, account reset, state rewrite or downgrade is introduced.

Local verification: **59 passed**, including all 42 original engine checks plus read-only preparation, original configuration drift, incomplete/wrong-source builds, registry ambiguity, private-database requirements, predecessor tampering, empty successor state, closed-attempt refusal and immutable controller checksum cases. Canonical safety CI and actual preparation/deployment outcomes must be recorded separately. The original authorizations remain valid; no new general approval is requested.

After successful deployment, authenticated owner upload/correction/cleanup and a natural scheduled execution still require separate evidence. The sample's unclear asset labels must not be fabricated or approved from general deployment authorization.
