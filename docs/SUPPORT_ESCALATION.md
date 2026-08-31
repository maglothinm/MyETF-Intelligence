# GitHub Actions escalation: stuck obsolete runs

Submitted **2026-08-30 13:37:17 UTC**, authenticated as **maglothinm**, to the
matching existing discussion in GitHub's official Community Actions category:
[support escalation](https://github.com/community/community/discussions/205874#discussioncomment-18207352).
Comment ID: `DC_kwDOEfmk4M4BFdJ4`; discussion: `205874`.

This is a **public Community support escalation**, not a private support ticket
or proof of containment. No staff resolution has been verified. It contains only
public repository/run metadata and sanitized GitHub error IDs, not credentials
or production ledger contents. The authenticated API returned the comment URL,
author, timestamp and exact submitted body. The message below is the submitted
payload; do not repost it or create duplicate discussions.

An authenticated read at **13:45 UTC** confirmed this comment remains present,
with no replies. The discussion was unanswered and complete comment/reply
pagination was checked; its older incident comments do not resolve these runs.

The owner explicitly authorized contacting GitHub and completing the existing
revision into production. Deferred features and all state-safety gates remain
unchanged. The initial hourly-follow-up request was rejected because recurring
authority was not explicit. The owner then explicitly approved hourly checks and
automatic resumption after containment. On **2026-08-30**, task follow-up
**polititrack-production-unblock** was created successfully and verified
**ACTIVE**, hourly, attached to this task. It stops after verified completion or
an owner stop request; it does not bypass state gates or post duplicate reports.
At the original submission, the Support portal remained at sign-in; the public
contact above succeeded without changing account credentials. See the later
checkpoint below for the separately attempted signed-in private-ticket route.

## Subsequent checkpoint — 2026-08-31 10:46 UTC

The existing Community comment remains present and unchanged, with zero replies
and no newer discussion comments/replies; pagination was complete. Both runs
remain queued attempt 1 with zero jobs/artifacts. This follow-up made no new post,
cancellation retry or deletion attempt.

Canonical main `ac6342ac85e5a395f1b8bab251b8f608c47249e0` now publishes a separate
owner-approved recovery record at `docs/incidents/senate-efd-2026-08-30.md`.
It records additional independently authorized cancellation/deletion/UI attempts,
all unsuccessful, and an unsent private Support draft because the signed-in
portal offered no applicable Actions route. That unsent draft does not replace
this submitted public escalation. No private ticket or containment is established.
Do not duplicate either report or repeat unchanged requests; continue the existing
hourly status checks. This follow-up retains its no-deletion and held-feature scope.

## Original submitted message

I am reporting another reproducible instance of the queued/not-yet-queued
contradiction, on behalf of the owner of public repository
`maglothinm/MyETF-Intelligence` (repository ID **1349678672**).

Two obsolete runs remain `queued` with `conclusion: null`, zero jobs and zero
artifacts:

- https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33219808359
- https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33221027676

Both bind to workflow ID **344663675**, path
`.github/workflows/legislative_trade_tracker.yml`, historical commit
`b9cf0f3e3863de69d92ae01f35f1c154a082f56a`. The workflow metadata now reports
`state: deleted`. Removing that obsolete workflow did not terminalize its runs.

At **2026-08-30 13:33:44-45 UTC**, authenticated repository-admin requests to both
`POST /repos/maglothinm/MyETF-Intelligence/actions/runs/{run_id}/cancel` and
`POST /repos/maglothinm/MyETF-Intelligence/actions/runs/{run_id}/force-cancel`
returned **HTTP 409**, with the exact message:

> Cannot cancel a workflow run that has not been queued yet.

Immediately re-reading each run still returned `queued`. GitHub request IDs:

| Run | Endpoint | X-GitHub-Request-Id |
|---|---|---|
| 33219808359 | cancel | D8C1:160B1:C57BC63:28DE694D:6A943138 |
| 33219808359 | force-cancel | D8C1:160B1:C57BD68:28DE6C88:6A943139 |
| 33221027676 | cancel | D8C1:160B1:C57C0D4:28DE780B:6A943139 |
| 33221027676 | force-cancel | D8C1:160B1:C57C1BE:28DE7B4B:6A943139 |

Other recent workflows in this repository complete successfully. This is not a
claim that all Actions are down. These particular stale runs block our controlled
production release: if old workflow code starts later, it can upload stale
production-state artifacts. We will not assume a deleted workflow or an empty jobs
list makes already queued runs harmless.

**Could GitHub staff terminally cancel these exact two runs, or provide
authoritative confirmation that neither can execute or upload artifacts?** If a
supported customer-side procedure exists, please explain whether it permanently
invalidates these already queued runs, including after Actions is re-enabled.

Please preserve the repository, all production artifacts and unrelated runs. We
are not requesting a state reset, artifact deletion, or execution/rerun of the old
workflow. A terminal cancellation or documented scheduler-level containment is
the outcome needed. Thank you.
