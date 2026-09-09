# PolitiTrack active handoff

Updated **2026-09-09 — Legislative recovery implementation**. Canonical repository **1349678672 — maglothinm/MyETF-Intelligence**, default branch **main**.

## Additional active owner request — Operations Run now controls

Issue #164 is implemented on `codex/operations-run-now`, pending exact-head CI and
a coordinated release after Legislative recovery acceptance. The owner can start
the three existing jobs using the existing signed-in account; public/ordinary
review accounts cannot dispatch. Additive receipts survive refresh and browser
clearing. Production images, schedules, IAM and schemas have not changed for #164.
See [the implementation and activation contract](operations-manual-runs.md).
Preserve the owner's user-completed sign-in; never reset their password or session.

## Active owner request — Legislative recovery

The owner requires a permanent fix: failures, including ambiguous old alert
attempts, must not obstruct later collection. Runtime Legislative, Executive and AI
now stage alerts with the atomic successful snapshot; per-record delivery claims
and uncertainty survive restart independently. The pinned September 8 no-delivery
proof resolves only that exact legacy alert fence. No old flag or history is edited.
Complete-source validation and writer locks remain mandatory.

Finish exact-head CI including PostgreSQL regressions, integrate issue #159's
merged source and wait for its production ownership handback. Then fence/drain the
existing schedules, deploy the tested image, install the additive outbox schema,
and verify controlled producers plus a later natural Legislative run. Do not use
an old direct-send image after accepting queued-channel snapshots. Production
recovery is not yet accepted. [Contract and evidence](incidents/2026-09-09-legislative-recovery.md).

## Accepted personal acknowledgement request

Issue #159 / PR #160 is merged and deployed: browser clearing no longer deletes
personal parser acknowledgement history. Each person has a separate account in
private PostgreSQL. The owner's four original records were recovered with their
original timestamps. **Owner password setup remains a user action** using the
privately delivered single-use link; never set a password for the owner or ask
them to re-acknowledge the four records.

## Exact release and evidence

- Runtime source: `c0eaeb430aa7f665283f9ee560cf72fbe9c257cf`.
- Image on all six resources: `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:5428e1333ceff18b7c2e1f7fd46f3e82652b6c2cb7b94d1fbee20b099fa19ec6`.
- Build: `c84e6510-9825-4c84-b512-cf82d18ed627`; web: `polititrack-web-r159-persist-0909`.
- CI attempts 1: `34351334909` and `34351334927`, both successful.
- Local tests: 1,173 passed; 18 optional/local integration skips.
- Runtime PostgreSQL CI: 471 passed; one SQLite concurrency skip.
- Live served assets: 77 DOM checks; live API account isolation, cookie clearing,
  new sign-in, Restore/import protection and fresh-web-revision persistence passed.
- Both acceptance accounts were disabled after verification; history retained.

See [the accepted release](releases/2026-09-09-personal-review-acknowledgements.md)
and [account administration](parser-review-acknowledgements.md). Raw setup tokens,
test passwords and private recovery data must remain out of repository/issue logs.

## Next safe action and ownership

The owner sets their password, then signs in to see their four saved
acknowledgements. Future browser clears require only sign-in. New people need
their own administrator-issued invitation. Password recovery preserves the same
account identity and acknowledgement history.

Return this exact receipt to **Restore Legislative collection** before handing
back shared release ownership. That separate task is implementing durable
notification isolation; it must rebase onto the merged #159 source and preserve
the personal review tables/configuration. No other shared release may overlap.

All four original schedules are ENABLED; Filing Vault remains PAUSED. Legislative
generation 232, failed run `065d5330-abca-4eda-b683-64e85f2dcbe7`, and the original
side-effects guard remain intact. The fenced Dashboard head advanced from
332 to 333 with exact
parent continuity; other protected heads did not change during the cutover.
Natural runs may advance them after resume. Refresh live facts before future
changes. No rebaseline, rewind, guard bypass, new IAM grant, alternate writer,
or unrelated PR #154 activation occurred. Prior Phase 5 certificates are historical.
