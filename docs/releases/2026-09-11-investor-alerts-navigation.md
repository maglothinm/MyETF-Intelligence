# Investor alerts, OGE health and compact navigation release

Accepted 2026-09-12T00:24:24.042666+00:00. Repository **1349678672 — maglothinm/MyETF-Intelligence**.
The owner explicitly authorized full implementation and release on September 11.
The application changes are live. Gmail delivery remains incomplete: Owner-created Google app password has not yet been saved in the prepared Secret Manager form. No successful investor-alert email or inbox receipt is claimed.

## Delivered behavior

- New-browser sound defaults to all eligible events and arms after a normal user interaction. The owner's existing browser was set to All eligible events and visibly armed; its notification history was retained.
- Investor Edge profiles with usable evidence and a rating strictly above 60.0 stage Gmail alerts to maglothinm@gmail.com. Exactly 60.0 does not qualify. Existing AI Watchlist and High Priority signals use the same recipient. An additive crossing journal and the durable outbox prevent repeat notifications from ordinary refreshes.
- Operations displays OGE health from the existing Executive collector, separating request-required inventory from collection failure. Controlled OGE discovery found 4,073 Form 278-T listings; a subsequent original scheduled Executive run succeeded.
- Signals uses 220-character previews and four-line limits (Evidence three lines plus source controls), with complete text on hover/focus and accessible source links. Search retains full text.
- Wide tables have reachable synchronized top scrolling and keyboard controls. Layout checks cover all main sections and standalone pages at narrow widths.
- The complete Signals JSON now returns HTTP 200 through streamed gzip. Before release, its growing size caused HTTP 500 even though the dashboard readiness endpoint was healthy. No ledger records were removed.

## Build and verification

PRs [#169](https://github.com/maglothinm/MyETF-Intelligence/pull/169) and [#171](https://github.com/maglothinm/MyETF-Intelligence/pull/171) are merged. Runtime source `4deb31cb08fc38b0e38928aee609761f6c6579fd` is an ancestor of merged main `4b5b0a75cac06fb8a35af03c3b7b48ecaa42c04d`; their tested tree is `db330aad8b7b1f1a72f13942d46a2e540d26d1ae`.

Build `960864c8-87bc-4b77-a088-afbb87f85783` succeeded and produced `us-central1-docker.pkg.dev/project-38008d5f-4918-46e6-920/polititrack/runtime-v2@sha256:6bd42784caff11fae8bcec4373331e58986a3bc79216782f682d2ca5107b87bf`. All six existing resources match it; web revision `polititrack-web-00040-c2l` serves 100% of traffic. The earlier build `5001986c-b0c4-4cfc-88f0-cd8789bea30d` was superseded and never deployed.

Feature local suite: 1,226 passed, 37 optional/environment skips; final sound/navigation checks: 33 passed. Streaming correction local focused suite: 43 passed, 25 optional PostgreSQL skips. Final [Runtime CI 34659557574](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34659557574): **530 passed, 2 skipped**, including real PostgreSQL integration. [Investor main CI 34659136667](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34659136667) and [feature main Runtime CI 34659244278](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/34659244278) succeeded. Feature PR checks were `34474763564` and `34474763566`.

Exact served asset hashes, complete JSON response counts, narrow-window measurements, and configuration receipts are in the [release receipt](2026-09-11-investor-alerts-navigation-receipt.json).

## State continuity

The existing schedules were paused and in-flight producers drained. A read-only baseline was captured at `2026-09-12T00:01:13.206125+00:00`. Each existing producer then appended a successful successor to its exact prior parent:

| Producer | Generation | Runtime run ID | Snapshot ID | Preserved parent SHA-256 |
|---|---|---|---|---|
| ai | 315 | 78793e6d-d07a-417d-8e0b-f4bf15d72b56 | 03104119-edd8-41e7-9aa7-ece69ae70f4f | 8fa7c84b8dd3fb98435d384c91bfb79044fb5c9c6128aa4b55c5ee5619dc32dc |
| dashboard | 568 | 57de892f-96fc-45ed-9f4d-b06c7fd2c446 | 627d4aac-a8d0-44ea-ab7a-ba0a20dd34dc | 5596cd0b4357747e686d835011a3e4504155b66041b0b8cf38200ec8cacb2767 |
| executive | 282 | 0713e476-caef-46da-b7f8-50d18ee44724 | b9fd4f39-bf17-466a-91bd-1570beda5303 | cf354cf8bfa78d114eea8522f8858bc8f7cbdbdfc41bb6de9982c3e1e3d24a70 |
| legislative | 465 | 41d1b8f5-a483-41ec-8926-1fa1d6e40229 | 0bfdd3ed-84b3-4aab-ba89-784db353373a | f38b871ab1640f2a6270a15e7d59a179fdd6e3e34b01bff20dc6be52205d5fd4 |

Accepted heads at `2026-09-12T00:17:48.452277+00:00` (they continue to advance normally):

| Producer | Generation | Snapshot ID | SHA-256 |
|---|---|---|---|
| ai | 315 | 03104119-edd8-41e7-9aa7-ece69ae70f4f | bdc8f731921a3cdb362c4df81722531f9a61875a3d7bebb04e626cd6157027a4 |
| dashboard | 568 | 627d4aac-a8d0-44ea-ab7a-ba0a20dd34dc | 2860606944c05ecd34123ac9580f958969866de4b89b2ecc0dbe4a48614b11f0 |
| executive | 283 | 96246a8a-d653-43ce-88b3-7ba571e041f6 | e4bc6e3722d04cb4e40434a3c0aff5c1f6e63f20adbcdec54fc2f94c126af27f |
| legislative | 465 | 0bfdd3ed-84b3-4aab-ba89-784db353373a | a2176f5211f92b7c7543c8a0c0c382478b8fe99159d6dacbeeb0562222ed7792 |

Every pre-release snapshot metadata hash, the original September 9 incident row and payload proof, all three account rows, eight acknowledgements, and prior notification history matched the baseline. Current snapshot payloads and file manifests verified. No migration, rebaseline, rewind, review reset, or alternate state writer was used.

Successfully verified collectors were restored individually to their exact original schedules while AI/publication acceptance finished. All four original producer schedules are now ENABLED with identical timing, time zones, targets and retry settings. Filing Vault remains PAUSED. Natural Executive execution `polititrack-executive-md66c` succeeded on the released source after the original scheduler fired; no manual substitute is called a scheduled success.

## Email and remaining action

Gmail delivery remains incomplete: Owner-created Google app password has not yet been saved in the prepared Secret Manager form. No successful investor-alert email or inbox receipt is claimed.

The existing AI outbox is the only production delivery path. Missing credentials preserve pending intent without blocking collection. The prepared secret is `polititrack-gmail-app-password` in the existing production project. Its value must remain out of chat, Git, command-line literals and published receipts. When saved, bind versioned Gmail sender/password secrets only to the existing AI job, verify the real transport using a clearly labeled setup message, and distinguish provider acceptance from inbox receipt. Do not fabricate an investor signal to test delivery.

Operations manual-run controls #164 remain disabled and Current Opportunity #154 was not activated. Personal review sign-in and enablement are preserved. Future releases must retain the recipient-aware outbox and Investor Edge crossing history; an older direct-send or recipient-unaware image is not a safe rollback.
