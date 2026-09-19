# Parser acknowledgement recurrence — September 9, 2026

The user did acknowledge all four exceptions on September 8. Read-only inspection of Chrome Default’s storage recovered all four original timestamps and matching logical identities. A later browser database deletion removed the acknowledgement key, notification history and site metadata. The surrounding bulk deletion affected 15 distinct origins. The initiator has not been established; neither a user action nor any particular cleanup program is assumed.

## Verified facts

- Canonical repository ID 1349678672, maglothinm/MyETF-Intelligence, main c51c17a2d0c37666e51ba24616bca5793a9d0b50; working tree initially clean.
- Production source remains 19e894ef1262a86d4e54e24a8a34f6b7f230f688. All six Runtime v2 resources still use image sha256:6a458b64fc9b3517f460b49eb82cf7e1e0d5d200a051ee907031c2e1b737d300.
- Web revision polititrack-web-00035-v7h receives 100% of traffic. Served app.js SHA-256 c102ebdfa382e89548a66386f4978fd82733378d92f475ee10b141ffca6757b2 matches the accepted September 8 release byte for byte.
- Current full review export and insights retain the identical four review IDs and logical identities. Counts: 4 manual exceptions, 1509 access-required records, 0 other.
- Readiness was ready, dashboard true; observed snapshot 8890d3ddc342241e9b416498c444ebfc8f7d9f4e34210131f3cfebde1ea6c21c. This is a read observation, not a new certificate.
- Chrome stored all four acknowledgements at database sequence 8396. A later tombstone at sequence 8763 deletes that key; sequences 8764–8766 delete notifications and site metadata. This differs from the previous application bug, which saved an empty acknowledgement array. The accepted app has no removeItem or clear operation for this key.
- Isolated DOM replay with today’s served files: missing storage gives 4 active; the recovered record gives 0 active / 4 acknowledged; refresh and recreated-page reload retain 0 active and the exact original timestamps. This is isolated replay, not an observed restoration in the user’s live Chrome tab.
- Historical code CI remains successful: runs 34245743277 and 34245743334, attempt 1, plus merge run 34246070619, attempt 1. Historical certificate artifact 9997087643 remains unexpired. Neither is new acceptance evidence for this investigation.

## Recovery and remaining work

The recovered JSON and a site-restricted recovery bookmark are in the task workspace outputs. No browser profile, production database, schedule, deployment or security setting was changed. The available browser control exposes only Codex’s in-app browser, so restoration in the user’s Chrome tab remains pending. Do not edit a running Chrome LevelDB database directly.

Identify the browser data-clearing action or cleanup program to prevent repeated loss. Browser-local acknowledgement storage cannot survive removal of that browser’s site data. Any move to account-backed acknowledgement state would be a separate application design change; it has not been implemented or deployed here.

The separate Legislative source-access/retry-guard incident remains outside this correction. No guard bypass, rebaseline, state rewind or new producer run occurred.
