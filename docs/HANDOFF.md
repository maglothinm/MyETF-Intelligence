# PolitiTrack active handoff

## September 23 #225 — activated; large CSV field repair awaiting release

Canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`.
Beast successfully activated `c46dcef215e4872912ba2995b67cb117725b05e2` at
11:15:40 UTC after normal Windows administrator approval. Web and scheduler
restarted; PostgreSQL PID 25732 did not restart. Both pre-change history fingerprints
remain intact, including 4,693 headers before 11:03:40 UTC, with zero broken links.
The preserved untracked source-status file matched SHA-256
`126f9de9239dc5140c5885b71593b7e38391a0d60d522fa0a306cf53bc386aa7` after cutover.

A controlled invocation of the existing locked AI writer at 11:16:29 UTC failed
before snapshot commit: the new discovery CSV augmentation read a retained field
larger than Python's default 131,072-character CSV limit. The prior AI generation
852 remains authoritative. The normal scheduled dashboard run at 11:17 succeeded
on the activated source. Activation is proven; persisted discovery publication is
not yet accepted. No rollback across its new snapshots was attempted.

Branch `codex/discovery225-large-csv` fixes only that generated-export read: raise
the temporary reader limit to the actual file size and restore the previous
process-wide limit in `finally`. Do not truncate retained cells or rewrite analysis
history. The integration regression reproduced the original exact CSV error and
passes after the repair. Focused tests: 41 passed. Broader regression: 400 passed.
Offline finalization of actual retained snapshot copies exported all 311 analysis
rows, including a 208,461-character field, with every discovery object present,
unchanged analysis-history bytes and the original reader limit restored. No
provider, notification or production-state writes occurred in that offline check.

Next: wait for exact-head canonical CI, merge tested repair source, activate it
through the existing Beast service controls and normal Windows elevation, then
run the canonical AI/dashboard writers and verify their persisted evidence against
served JSON and CSV. Do not close #225 or claim live evidence publication yet.
The original 30-page upload is still needs_review with its original committed
receipt; do not re-upload, requeue or approve it for a demonstration. Its live
outage scenario was not recreated. Cloud/legacy producers remain retired.
