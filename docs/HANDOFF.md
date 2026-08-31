# PolitiTrack active handoff

Updated: **2026-08-31 UTC**
Work record: [issue #11 — Investor Edge historical bootstrap](https://github.com/maglothinm/MyETF-Intelligence/issues/11).

## Current task — released and verified

The owner requested “Release the commit”. Canonical repository **1349678672**
is currently **maglothinm/MyETF-Intelligence**, default branch **main**.
Implementation `b4a9049abcca16c40b88c9c05489e93ddad71d8f` was released through
[PR #15](https://github.com/maglothinm/MyETF-Intelligence/pull/15). Tested head
`c27e884a4981db4a84982bbf665962ec2e081daa` merged as
`676701ac1521458aefd72e2329d4e87c8781e41f`; their trees match.
Work remains on `codex/investor-edge-bootstrap` in the isolated worktree
`.remediation/investor-edge-worktree`. The commit containing this final handoff
is a documentation-only successor; the published executable build is `676701a`.

Concurrent [PR #14](https://github.com/maglothinm/MyETF-Intelligence/pull/14)
merged to main as `7a1108fb2e32c39f6af943395c1bb9b9a550d26f`.
This integration preserves Operations newest-first history, the Investor Edge
changes, both regression suites, and both durable design decisions.
The shared root checkout, unrelated work and legacy repository remain untouched.

## Completed work and verification

Investor Edge now reconstructs bounded retained filing history inside existing
trackers, discovers historical profiles independently of new AI candidates, and
continues fair bounded observations across zero-candidate runs. Global maintenance
failures prevent successful state promotion and candidate alert delivery.
Historical reconstruction creates no new filing/candidate notification event.
Both dashboards expose the full profile inventory and honest progress telemetry.
Scoring, configuration, protected artifact names and writer ownership are unchanged.

The integrated local suite passed **347 tests**, including optional DOM checks,
without skips. Focused merged DOM and native Operations wrappers, JavaScript syntax
and diff checks passed. The first full-suite attempt encountered test setup errors;
the fresh isolated test-directory run completed successfully.

Integrated [PR CI 33391078330](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391078330)
and [main CI 33391179298](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391179298)
both succeeded on attempt 1. Each passed **264 tests** and Linux `verify.sh`
reported **VERIFICATION PASSED**. Initial PR CI also passed before integration.

Automatic [Pages 33391179240](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33391179240)
succeeded on attempt 1. The exact-attempt restore and publication audit passed;
all **30** checked live public URLs matched its artifact bytes. The
[root Investor Edge view](https://maglothinm.github.io/MyETF-Intelligence/#investor-edge)
and standalone page rendered without console warnings/errors or document-width
overflow at 1280x720. Existing legacy population telemetry remains visibly
unavailable rather than falsely completed. Device, Safari, touch and audio tests
are not inferred from this desktop check.

Protected inputs and isolated simulator history remained unchanged. No production
writer, simulation, alert or heartbeat was manually dispatched; no credentials or
repository settings changed. Source caches and acceptance copies remain local,
not production-state authority.

Earlier detailed acceptance and limitations are preserved in
[the validation report](validation/investor-edge-bootstrap-2026-08-31.md)
and [PROJECT_STATE](PROJECT_STATE.md). Operations implementation and test evidence
remain recorded there and in decision D-2026-08-31-025; the Investor Edge decision
is D-2026-08-31-026. Detailed release verification stays in the ignored local
`.remediation/investor-edge-bootstrap/` evidence directory, including
`release-preflight/`, `release-postflight/` and exact CI receipts.

## Remaining limits and next safe action

The authorized code release and live publication are complete. Issue #11 remains
open for production acceptance; this release is not proof of live backlog reduction.

Code publication does not itself populate production profiles. Verify future
normal sole-writer artifact successors and actual market backlog reduction
separately. Never upload acceptance copies, rebaseline, or dispatch an alternate
writer. Preserve the existing obsolete-run manual-production gate and held PR #3.
Missing source originals, parser/OCR limitations, market coverage and physical
device acceptance remain as documented. The unchanged $10K simulator's predecessor
history rewrite needs its separate audit before future manual simulator work.
Rename/privacy, legacy retirement and Gmail delivery proof remain separate work.
