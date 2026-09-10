# Investor alerts, OGE health and table navigation

Implementation for [issue #168](https://github.com/maglothinm/MyETF-Intelligence/issues/168),
including the compact-cell work from #119. Canonical repository ID: **1349678672**.
Branch: `codex/alerts-oge-navigation`; base:
`86cb05cdcb248e3308dce52eca9a0ab7859d61e6`.

## Delivered behavior

- New-browser sound defaults to all eligible notification events. The first real
  click or key press activates audio under browser autoplay rules. Existing saved
  Off, quiet hours, category mutes, volume, history and cross-tab deduplication
  remain respected. Opening a page does not replay old alerts.
- `config/investor_notifications.json` enables owner email to
  `maglothinm@gmail.com`. Current usable Investor Edge profiles alert once when
  first observed strictly above **60.0**, and on a later observed crossing back
  above that boundary. Exactly 60.0 does not qualify. Incomplete minimum samples,
  unavailable/stale profiles and synthetic records cannot qualify or reset history.
- The existing Watchlist and High Priority AI alert path queues this same Gmail
  recipient. Weak Signal and Archive Only do not qualify. Existing historical
  bootstrap suppression and analysis delivery identities remain intact.
- An additive `investor-edge-alerts.json` inside the AI state snapshot records
  threshold episodes. Intents use the existing Runtime outbox and commit with
  the successful AI snapshot. Missing credentials leave delivery pending while
  collection continues. An uncertain provider submission retains its existing
  per-record fence; it is not blindly retried or treated as successful delivery.
- Operations shows OGE check status, last attempt/success, age, expected cadence,
  next check, retained/processed filing counts, transactions, access-required
  records and parser exceptions. A successful Runtime Executive execution proves
  its mandatory OGE discovery completed. Older workflow-only evidence is unknown;
  an Executive failure does not assert that OGE itself failed. No new writer or
  schedule is introduced.
- Signals Analysis previews contain up to 220 characters and four displayed
  lines; Evidence uses three lines plus source actions. Exact full text remains
  in the shared hover/focus/tap reader and full-text search. All evidence URLs
  remain available. Other Signals cells also fit four lines and expose their
  rendered values without revealing intentionally unavailable scores.
- Wide tables have a synchronized top scrollbar, left/right buttons and keyboard
  navigation. This covers the workspace sections, standalone Investor Edge,
  Filing Vault and nested profile outcome tables. Controls initialize when
  collapsed content opens. Wallboard overflow is scrollable.

## Verification

- Canonical local `tests/` suite: **1,226 passed, 37 skipped**. Skips require
  optional tools or services, including real PostgreSQL. The intentional duplicate
  ZIP-member rejection fixture emitted its expected warning.
- Final sound status adjustment: **33 browser engine/integration tests passed**.
- Generated DOM tests cover hostile and long content, exact full text, all
  evidence sources, search beyond the preview, touch/focus/Escape, unavailable
  scores, top-scroll synchronization and aging OGE health.
- Threshold tests cover 59.9, 60.0, 60.01, 100, out-of-range/malformed values,
  independently owned profiles, restart deduplication, crossings, unavailable
  evidence, missing credentials, suppressed execution and recipient validation.
- Repository `verify.sh`, JavaScript syntax and UTF-8 checks passed.
- Real in-app browser inspection of a local build using read-only published JSON
  at **1280, 700 and 390 px** found compact Signals rows around **93 px**, compared
  with **946–1032 px** before the change. The top scrollbar reached the exact right
  edge, and a 735-character analysis opened wholly within the viewport.
- Overview, Signals, Investor Edge, Agent, all Records sections, Operations and
  the three standalone pages were checked for overflow. The standalone Investor
  Edge copy had 2,499 table containers; only its visible table received a control
  until profile details opened. Local authenticated APIs were unavailable as
  expected; no live account or source state was edited.
- Exact-head Actions run IDs and conclusions are recorded in the linked PR.
  Local checks do not certify deployment or external email delivery.

## Production boundary and activation

No production change was made during implementation. The observed accepted live
web revision was `polititrack-web-00039-ps5`, runtime source
`9f1a59105f2ac7cfa6ed3f764d9ab4b3d5483301`, image digest
`sha256:916f23124c028467079b305f50681336fc0b1e6e553cdb4fefe491dc2d380ef1`.
The [accepted recovery receipt](releases/2026-09-09-legislative-recovery.md)
remains historical authority. This work produced no protected artifact, replaced
no snapshot and performed no rebaseline. Schedules, accounts, acknowledgements,
notification history and existing producer ownership remain unchanged.

Gmail sender credentials were absent from the live AI job, Secret Manager and
repository secret-name inventory. To activate delivery:

1. Coordinate a single tested production release with pending Operations #164
   activation. Refresh live heads, image configuration and personal/state history
   before beginning. Do not activate unrelated Current Opportunity #154.
2. Configure a Gmail sender address and app password securely in Google Secret
   Manager; expose them only to the existing AI job as `GMAIL_ADDRESS` and
   `GMAIL_APP_PASSWORD` with narrow secret access. Do not place secrets in chat,
   Git, command-line literals, simulation credentials or published JSON.
3. Deploy the reviewed recipient-aware, outbox-compatible image under the
   established release procedure and publish the updated dashboard. Preserve
   all existing schedules, state heads and personal data.
4. Verify exact served assets, narrow-window behavior, a natural Executive/OGE
   success and AI snapshot continuity. Distinguish queued intent, provider
   acceptance and inbox receipt; no email has been sent by this implementation.
5. Keep accepted crossing history and recipient-aware intents on any rollback.
   Do not revert to an image that ignores an intended Gmail recipient, deletes
   this journal or bypasses the durable outbox.

The dashboard's saved browser sound preferences are separate from email policy.
For an existing browser saved Off, select All notification sounds and enable
sound once; this does not change account data or background email delivery.
