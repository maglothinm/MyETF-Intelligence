# PolitiTrack active handoff

Updated September 9, 2026. Canonical repository **1349678672 —
maglothinm/MyETF-Intelligence**, default branch **main**.

## Active owner request

The owner reports that the same four acknowledged parser exceptions reappeared.
Read-only investigation confirms the four original acknowledgements were saved
correctly in Chrome and subsequently deleted in a browser storage clear affecting
15 origins. The initiator is unverified. The live application, runtime digest and
review identities remain the accepted September 8 versions.

See [the investigation](incidents/2026-09-09-browser-acknowledgement-deletion.md).
Recovered data and a site-restricted recovery bookmark are in the task's local
outputs. Both the recovered data and bookmark passed isolated replay against the
currently served files: 0 active / 4 acknowledged, original timestamps preserved,
refresh/reload successful, repeat recovery idempotent, wrong origin unchanged.

## Pending next action

Restore the recovered acknowledgements in the owner's Chrome tab, then verify
0 active / 4 acknowledged there. The available browser control exposes only
Codex's in-app browser; live Chrome restoration has not occurred. Identify the
browser clearing action or cleanup program before claiming lasting recovery.
Do not directly edit the running Chrome storage database. Browser-only state
cannot survive external site-data removal; account-backed persistence is a
separate unimplemented design change.

## Preserved production boundary

No production, scheduler, browser profile or security setting was changed during
this investigation. Runtime source remains
`19e894ef1262a86d4e54e24a8a34f6b7f230f688`, image
`sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300`
on all six resources. The September 8 [release report](releases/2026-09-08-parser-acknowledgements.md)
remains the bounded feature-release record; this investigation is not a new
deployment or certificate.

The separate [Legislative incident](incidents/2026-09-08-legislative-retry-guard.md)
remains unresolved. Preserve the failed run, accepted history and retry guard.
No state initialization, rebaseline, rewind, guard bypass, alternate writer,
IAM expansion or PR #154 activation is authorized by this investigation.
