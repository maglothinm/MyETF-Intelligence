# PolitiTrack active handoff

## September 23 #232 - complete filer directory and search, source validation

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`, branch
`codex/all-filer-profiles` from `main` at `85b13ca52feb4346a0581561333f755d6ca3cf7c`.
Beast is still running `0c2ab975a837a1d2a28ca4e041019d0103413b54`; this checkpoint
does not claim the directory change is deployed.

The Investor Edge publisher now includes every named retained filer, including
filing-only/review-required entries and transactions with no eligible equity
purchases. Existing disclosed-owner identities remain separate. The old 40-profile
selection no longer limits visibility or admission to the fair historical queue.
The existing 30-observation and 40-market-request per-run budgets, 40-trade history
window, retention policy, scoring methodology/hash and single writer are unchanged.
Known catalog entries do not manufacture trades, prices, observations or reviews.
Missing evidence is explicitly unknown; source-review counts and reasons are
published in complete JSON and CSV. All prior profiles and observations remain
retained through the existing snapshot path.

Both root and standalone views have name/owner search, history-status filters,
match counts, clear controls and complete CSV download. Name terms match in either
order, case-insensitively; matching incomplete profiles are revealed in Building
history. Root filters and focus survive refresh. Existing assessment eligibility,
zero/negative measured values and notification rules are preserved.

Validation: **412 local regression passes**, including Node/jsdom/axe checks;
the run used UTF-8, matching Beast's launcher (one default-Windows-codepage test
read failed before rerunning under that configuration). Four real Edge browser
checks passed: root/standalone at 1280 and 390 pixels, with no JavaScript errors.
An offline replay of AI generation 854, Legislative 1517 and Executive 715 produced
**1,028 owner profiles covering all 975 known filer names**, including Donald Trump.
It preserved all 62 prior profile identities, 1,519 observations and all history
ledger bytes, made zero provider calls, and took about 7.2 seconds to refresh.
This offline result is not live acceptance. Trump remains building history with
his original source review pending; the suspected municipal-bond/CI classification
is not silently rewritten or accepted by directory publication.

Next: exact-head canonical CI and merge; activate through existing Beast service
boundaries with normal Windows administrator approval, then use the existing
locked AI/dashboard producers. Verify complete directory/export agreement, live
search, per-run budgets, prior snapshot fingerprints, untracked files and the
unchanged original manual-upload review receipt. Keep #232 open until live checks.
Issue #225 retains its separate pending-upload outage acceptance boundary; do not
re-upload, requeue, approve, rebaseline or revive cloud/legacy writers for this work.
