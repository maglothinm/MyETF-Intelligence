# PolitiTrack active handoff

## September 22 independent manual OCR and discovery evidence (#225) — merged; activation blocked

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Implementation branch `codex/manual-ocr-discovery-evidence`; PR [#226](https://github.com/maglothinm/MyETF-Intelligence/pull/226)
merged to main as `c46dcef215e4872912ba2995b67cb117725b05e2`.
Its source tree matches tested head `e5653120d4cd9d16303ec1ba3eda5488c1e2548e`.
The follow-up `codex/discovery225-activation-handoff` contains operational documentation only.

### Delivered source

Authenticated, allowlisted manual uploads for known Executive filings receive a
separate maintenance snapshot before fresh OGE collection, inside the existing
Executive lease. Collector failure cannot erase that committed extraction. The
maintenance receipt cannot advance collector freshness. Automatic-source limits,
review before import, post-commit acknowledgement and the single writer remain.

AI and Current Opportunity now retain per-transaction `information_value_at_discovery`
evidence with JSON/CSV/dashboard reporting. A first usable quote is immutable;
missing required evidence is `unknown`. Legacy prices retain their limitations.
The evidence describes securities and does not score public officials. See
[DISCOVERY_EVIDENCE.md](DISCOVERY_EVIDENCE.md). The legacy analyst is unchanged.

### Tests and merge evidence

Local regression: **547 passed, 7 skipped** (PostgreSQL cases); interface and
accessibility: **10 passed**. Final focused check: **31 passed, 1 skipped**.
The real PostgreSQL cases passed in canonical CI, including replay without duplicate
extraction/import, independent maintenance commits, and separate collector health.
All four exact-head runs completed successfully on attempt **1**:

| Workflow | Run |
|---|---|
| Source upload and OCR | [35770240188](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240188) |
| Runtime v2 safety | [35770240147](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240147) |
| Current Opportunity | [35770240223](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240223) |
| Investor Edge regression | [35770240357](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35770240357) |

### Live truth at 2026-09-22 19:01 UTC

Windows reported that the normal administrator prompt was canceled. Activation
did **not** start; there is no activation receipt for this release. Installed
application/config remain `dfb5c66ffc51b30b8afbdc283dbe10def4723f89`.
Database, web and scheduler remain Running/Automatic, with unchanged PIDs 25732,
24620 and 25956 respectively. Readiness is HTTP 200. The new discovery JSON/CSV
routes are still HTTP 404; AI generation 819 has no discovery ledger, and dashboard
generation 1551 is still on the previous source. Autonomous live reporting is
**not yet verified**. Existing AI/dashboard assets match their committed snapshot.
Upload authentication and invalid-Host rejection remain effective.

The originally pending 30-page upload changed during this session, before this
release: a normal successful Executive collection reached OCR at 18:41 UTC and
completed all 30 pages at 18:43 UTC. It is now **needs_review**, with reason
`upload_confirmation_required`, committed in Executive generation **693**, SHA-256
`fe768ffad0909dbba9095b89615561a5fc3c259423f4a22b191737fbe5e50a3f`.
The raw inbox payload was removed by normal post-commit cleanup. No owner approval
or import was performed. Do not re-upload, requeue, clear, or approve it to create
a demonstration. Its completion is not evidence of the new outage-independent path.

An isolated replay of the original committed receipt under an injected OGE outage
produced a maintenance commit with zero re-extractions and preserved review.
Real PostgreSQL CI also passed the outage/commit/replay cases. A live outage with
the original pending upload was **not recreated** because it had already completed.

An offline copy of retained source/AI snapshots produced **10,899** evidence
objects, all `unknown`; **311** retain legacy market evidence. Current Opportunity
is OFF and retained legacy records lack required verified first-discovery quote
quality/price-basis evidence. No discovery quote or historical provenance was
invented; configuration was not changed to manufacture a measured result.

All **4,511** snapshot headers created before
`2026-09-22T18:50:20.529501+00:00` retain digest
`7afd51f9c5019460fd9773d69396a10a`. The complete snapshot chain has **0** broken
parent links. PostgreSQL snapshots remain authoritative; no new protected GitHub
state artifact was produced by this source/test work. Legacy recovery artifact IDs
are not a replacement for these current heads. No rebaseline or cloud/legacy writer
activation occurred. Unrelated user files were not edited; normal running producers
may continue updating their own untracked status evidence.

### Next safe action

Keep [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225) open.
The prepared local package is
`C:\ProgramData\PolitiTrack\releases\discovery225\Apply.ps1`, pinned by arguments
to merged revision `c46dcef215e4872912ba2995b67cb117725b05e2` and tested head
`e5653120d4cd9d16303ec1ba3eda5488c1e2548e`. It checks canonical identity, tested
source, an idle producer window, snapshot continuity and untracked-file hashes;
restarts only the existing web/scheduler; and leaves PostgreSQL running.
No prompt remains active. Do not reopen a canceled prompt without owner action.

After owner-approved elevation, verify the activation receipt and unchanged old
snapshot headers, then the normal AI and dashboard producer revisions, persisted
ledger, JSON/CSV objects and live file hashes. Preserve the original upload's review
state. Source/CI success is not installation or live acceptance. No live outage proof
can be claimed for the original pending upload after its earlier completion.
