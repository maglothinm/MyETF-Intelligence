# PolitiTrack active handoff

## October 7 UTC / October 6 Eastern #261 — Fresh preflight verified; device disconnected before approval

Resumed through Remote Desktop Commander on Beast, device
`2cf9a73a-facb-4848-88c6-52344ff96055`. Canonical repository ID 1349678672,
`maglothinm/MyETF-Intelligence`, default branch `main`, was independently verified.
PR #262 is merged at `64d79157a1ba3954be4ef05af436b2ebc93590c8`.
Staged current source `e58c449c0cd198246b6a7b50cadd9f5dbef3dd9f` differs from
CI-tested `5ac40141868164126fcbbcb50e0168026865f677` only in HANDOFF/PROJECT_STATE.
All four exact-head CI runs were independently confirmed successful.

Installed HEAD was still `e01d03be8c2e8f91178a8d3fc502ed952b5f914b`; Database,
Scheduler and Web were Running/Automatic. Tracked source was unchanged; the
existing untracked `legislative-source-status.json` was preserved.

Fresh read-only four-head export at 2026-10-07T00:49:44Z completed successfully:
AI1417, Dashboard2863, Executive1088, Legislative2400. All 7,768 snapshot headers
have unbroken parent chains, and all four archive hashes round-trip exactly.
This is preflight, not a drained/frozen release baseline. Private receipt:
`C:\Users\maglo\PolitiTrack-work\executive-ocr-261-operations\preflight-20261007T004943Z\readonly-before\receipt.json`.

The nightly physical backup `routine-20261007T000002Z-d100a329.base` records
78,629,359,208 bytes, completion 00:07:07Z and pg_verifybackup passed. A new
verification was started. The first invocation identified the subsequently
added `verified.json` receipt as absent from PostgreSQL's manifest. A separate
verification excludes only that receipt using `--ignore=verified.json`.
Its final result was NOT retrieved before disconnect; do not claim the recheck passed.

Prepared isolated source checkout:
`C:\Users\maglo\PolitiTrack-work\executive-ocr-deploy-261-20261007`.
Operations helpers:
`C:\Users\maglo\PolitiTrack-work\executive-ocr-261-operations`.
Pinned `release_261.py` SHA256:
`e4c98b98e47203136dab75909afa9a7ce13ae0f6c9e11a3c02836ff838fb016f`.
It reuses the verified existing release implementation
`f962b5ebadfe9b800998339815f7d628d65a129c6c7807a4fa9500f5ec39abc1`,
requires OLD e01d03b and TARGET e58c449, retains the entire configuration except
source_revision, drains existing writers/backups, holds the established locks,
exports fresh frozen state, and pauses/resumes only existing Scheduler/Web.
Database, state heads, schedules, automatic page limits and manual exemptions
are not changed. Acceptance and read-only continuity helpers are prepared.

All 15 existing offline release/drain checks and three wrapper checks passed;
helpers compile. Additional native focused pytest initially failed because the
test shell lacked installed Tesseract/Poppler on PATH. A rerun with those installed
paths progressed without the earlier failures, but its final result and Node
results were NOT retrieved. Canonical CI remains separately verified.

Remote calls then intermittently returned INVALID_ARGUMENT / [object Object].
The final call explicitly reported no device online and instructed restarting
Desktop Commander Remote. No deployment apply, Windows elevation prompt, native
acceptance invocation, service change or configuration change was issued.
No execution approval is pending; no real imports are claimed by this continuation.

Next: reconnect Beast using Desktop Commander Remote, retrieve physical backup
verification and focused test outcomes, refresh canonical/installed source and
locks, and recheck the pinned helper. Present normal execution/Windows administrator
approval to the owner for the reviewed apply action. Apply must take a NEW frozen
export after draining. Then invoke the existing Executive owner, verify committed
imports and compare all old headers/ledger prefixes/filing and trade IDs/evidence
against that frozen baseline with `verify_261.py`. Keep #261 open.

## October 6 #261 — Executive OCR repair merged; deployment blocked

Owner authorized implementation and deployment after the Executive diagnosis.
PR [#262](https://github.com/maglothinm/MyETF-Intelligence/pull/262) merged to
canonical repository ID 1349678672, `maglothinm/MyETF-Intelligence`, `main` at
`64d79157a1ba3954be4ef05af436b2ebc93590c8`. Production was last verified
at `e01d03be8c2e8f91178a8d3fc502ed952b5f914b`; it has NOT been changed by this task.

The verified 1068 snapshot has 4,176 Executive filings: 3,832 Form-201/request-only
links, 335 review receipts (324 parser/layout failures, seven native/OCR disagreements,
four automatic page limits), and nine technical retries. All 2,441 unobserved
filings are request-only. Runs through 16:11 UTC kept committing without new OCR
extractions or appended transactions. Retained nine retries separately explain
the September 19 last-healthy-pass timestamp; do not claim that processing stopped then.

The source repair adds a conservative OGE 278-T numbered-table parser. It accepts
only explicit headers/row boundaries with exact native/OCR field and page agreement;
missing/ambiguous rows and asset tails remain reviewable. It preserves unknown
ownership/notification dates, physical row identity and existing trusted-set
conflict checks. Parser versioning permits affected official-download review
receipts to be retried once using existing extraction evidence. Subsequent checks
at unchanged URLs still detect changed bytes, but unchanged bytes/parser keep the
prior outcome without another interpretation. Known request-only links are
excluded from ready work and reported separately without fabricating attempts.

Local verification: 16 stdlib parser tests and six Node health tests pass; changed
Python files compile. Private diagnostics over seven retained filings recovered nine
transactions across Kupor, McMaster and Criswell documents without new OCR/provider
calls. Four filings with ambiguous wrapped asset tails remained reviewable.
Sparse optical text may omit row numbers, but native row numbers and exact page,
row-count and field agreement remain mandatory. These are parser diagnostics,
NOT production imports or a promise that every unresolved document is supported.
Canonical CI for tested head `5ac40141868164126fcbbcb50e0168026865f677` passed:
- Source OCR [37501086300](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/37501086300):
  421 pytest passes, one skip, six Node health tests, and desktop/mobile correction UI acceptance.
- Runtime safety [37501086271](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/37501086271): success.
- Investor Edge [37501086272](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/37501086272): success.
- Current Opportunity [37501086243](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/37501086243): success.

Browser artifact 11430565011 belongs to Source OCR run 37501086300 and canonical
repository ID 1349678672. It is isolated UI evidence, never production-state authority.
The merge tree `e7dced769a0b1294f62c6862381159dcddee208a` exactly matches the tested
source head. Source and test success do not establish native installation or imports.

The deployment preflight command was rejected by Remote Desktop Commander:
`MCP tool call requires approval, but approval policy is never`, even after the
owner's explicit authorization. No alternative runtime execution route, service
change, state write, credential/security change, or permission bypass was used.
No fresh release backup has been taken in this task. Existing snapshot export is
diagnostic evidence, not a current frozen deployment baseline.

Next: when permitted runtime execution is available,
inspect current source/status and native locks, drain the existing writer, verify
a NEW backup/four-head export, deploy through the existing service boundary, then
prove actual committed imports and preserved historical prefixes. Keep automatic
30-page limits, authenticated manual exemptions, existing schedules and suppression
settings. Keep #261 open until native deployment and real progress are verified.


## October 6 #255 — Corrected release verified; first real research progress committed

Installed application source is `e01d03be8c2e8f91178a8d3fc502ed952b5f914b`
(PR #260), installed at **14:49:29 UTC**. Its tested head
`622b358adb3d0f6061c65c4dfbaa299a68e03c75` passed Current Opportunity
[37481024817](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/37481024817)
and Runtime safety
[37481024854](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/37481024854).
The source regression report records **579 passes / 7 optional skips**.
An independent follow-up reran all **15** offline installer/drain/correction-wrapper
checks successfully and reproduced the base installer's recorded SHA-256
`f962b5ebadfe9b800998339815f7d628d65a129c6c7807a4fa9500f5ec39abc1`.

The correction adds the emitted `capability_observation` event to the explicit
schema; unknown kinds and tampered hashes remain rejected. The first correction
attempt waited for an active writer and did not install. The subsequent normal
release drained work and verified a fresh frozen four-head export at
**14:48:37 UTC**: AI1397, Dashboard2822, Executive1068, Legislative2360;
**7,647 snapshot headers**, no broken parent links, exact archive round trips.
PostgreSQL PID5044 stayed unchanged. The original 14:31 release and failed
14:35/14:47 AI attempts remain recorded; do not relabel them as successful.
The October 6 nightly physical backup separately records a successful
`pg_verifybackup`; the frozen release export is a four-namespace state backup,
not a newly run full physical database backup.

The corrected native AI acceptance invocation completed with **exit 0** at
**14:59:02 UTC**, committing **AI1398** (snapshot
`f8bfdd5b-e96a-44a9-89ff-ffb0bdce48ff`, SHA-256
`8ce168e5fa574c36e410c7c477c78f7e44e23b5204053c753b94d9e775f0ea42`).
Read-only post-release export verified all four current archives and **7,649**
headers with no broken links. Comparison preserves the original **18,975-event
prefix**, all **1,385 opportunity IDs**, all 17 checked AI/Legislative/Executive
JSONL prefixes, original document bytes/reviews and all 418 completed-analysis IDs.
The event count is now 19,016; completed legacy analysis IDs remain 418.
The run used the existing native owner and locks; it was a manual acceptance
invocation, not proof of a subsequent scheduled AI cycle.

**Actual research progress:** BE acquired four additional retained documents
(6 to 10), expanded its source coverage from 40 to 104 sections and persisted
**two reviewed sections**, previously zero. Total retained issuer sections rose
from 79 to 143. BE also obtained a genuine current capability receipt, checked at
14:54:34 UTC against a quote approximately 12.8 seconds old; this verifies one
security, not the broader universe. The original expired September receipt was
not extended by changing its date.

**Remaining limits:** completed investment reviews = **0**. BE and INTC now have
explicit `unsupported_valuation_method` dispositions because their retained
annual EPS references are nonpositive for the installed EPS-multiple method.
These are method limits, not completed economic rejections. MSFT remains
`blocked` with `current_source_backed_contradiction_review_unavailable`.
Retained historical mappings cover four securities/two reports; only BE has a
renewed current capability in this accepted run. Keep #255/#239/#236 open for
full case completion, sustained scheduled progress and broader coverage.

Dashboard acceptance exited 0 at **15:01:33 UTC**; the subsequent scheduled
dashboard publication also succeeded as **Dashboard2824**, SHA-256
`b7be7188ddceb49e0badfd4300f41686eb3d707d59be3c12936da9e20c84f1e5`.
The live compact index was independently read successfully and agrees with
AI1398: two reviewed sections out of 143, BE capability verified, zero completed
investment reviews and SHADOW mode. Several data-route reads returned 503 while
dashboard publication overlapped; a later read recovered. This observation does
not establish that transient reader/writer contention has been repaired.

SHADOW and both AI delivery suppressions remain in place; native opportunity
intents and delivery records are zero. No new schedule, investment rule change,
subscription, state reset or live investment alert is part of this release.
After publication of the additive event, any rollback must retain compatible
readers; never rewind authoritative state to accommodate the older schema.

Private evidence remains under
`C:\ProgramData\PolitiTrack\backups\usefulness-deploy-255-20261005T132655Z`:
`schema-apply-20261006T144804Z/release-receipt.json`,
`verified-after-20261006T145919Z/progress-acceptance.json`, and the AI/dashboard
acceptance logs/receipts. Next: verify sustained scheduled AI publication,
continue bounded source review, and resolve MSFT's source-backed contradiction
review and the separately reviewed valuation-method requirement. Do not equate
this first persisted progress with completed investment cases or investment returns.

## October 6 #255 — Native repair installed; first run exposed missing event schema

The prior remote-tool execution barrier cleared. The reviewed installer ran after
12 offline release/drain checks and a fresh read-only preflight. At 14:31:07 UTC,
Beast installed canonical source c06f5054a46de0e38c81cf234de57d240953884f and enabled
only OPPORTUNITY_REFRESH_CAPABILITIES=true in the existing AI environment.
Scheduler/Web resumed; PostgreSQL PID5044 stayed unchanged. Four frozen heads and
all 7,643 prior snapshot headers verified with exact archive hashes and no broken
parent links. No reset, new schedule, live alert, account or subscription change.

The deployed compact index is HTTP200 / 1,989,108 bytes. Real Chromium desktop
1280 and mobile390 checks passed 25-card pagination, index-first fetching, zero
page errors/external requests and no overflow. Full evidence is not auto-fetched.

A manual acceptance invocation of the existing AI owner made genuine HTTP200 model
calls but failed at 14:35:56 UTC: capability_observation was emitted by the refresh
integration yet omitted from opportunity_state.schema.json's event enum. This is
a source integration/test coverage defect, not API funding or tool access failure.
The failed invocation did not publish its candidate AI snapshot. Preserve that
failed run; no cached diagnostic or blank state may replace the committed head.

The isolated corrective branch adds exactly the implemented event to the enum.
A new regression executes OpportunityRuntime.evaluate through save, immutable
journal validation, archive roundtrip, restore and a second unchanged cycle.
It also checks unknown events and tampered event hashes remain rejected. Three
focused tests passed. Full regression/CI and this schema fix's native installation
must still be verified. Do not call the research pipeline recovered yet.

Any rollback after the new event first publishes must retain its compatible reader;
turn the feature off rather than rewind state or restore an obsolete schema.
Private installation/evidence: C:\ProgramData\PolitiTrack\backups\usefulness-deploy-255-20261005T132655Z.

## October 5 #255 — Cross-document source correction merged; installation still blocked

PR #258 merged as 8c9f22ee8ab95bdde2ebe6673bc8beb294b490e0.
Exact CI head 27dbb3c53293844caab542d04704b23ee44ce079 is source-identical to
locally tested 71e694e5845be6e58484cf5b403d22141d0365f2. The merged tree was
independently compared and matches. Current Opportunity workflow 37330315025
(Python 3.11/3.12 plus DOM fixtures) and Runtime safety 37330315061 both succeeded.
Local regression: 576 passed, seven optional skips. The initial PR event produced
no run; a source-identical synchronization commit triggered the existing checks.
No workflow setting, production schedule or retired cloud job was enabled.

The correction resolves section limitations only against the completed, verified
cross-document issuer claim catalog. Material unresolved facts, missing documents,
unmatched quotations and unsupported references remain blocking; original limits,
prior reviews, all financial gates and budgets remain unchanged.

Real-data diagnostic: one retained MSFT primary section completed with four exact
validated claims. The old isolated-section check could not see its retained
companion exhibit. A later companion attempt failed one quotation check and was
rejected. Three structured model invocations occurred in an isolated diagnostic;
no native state, completed investment case or investing performance was produced.
Private diagnostic SHA256 e79da847117d5f6de81292bafe32e048141220841d426d92e2445fb0c12864b7.

At 15:08:54 UTC, Beast still ran 867893922e61c9fe30b1535e4deb32de8fc0d211;
Database, Scheduler and Web were Running/Automatic; shadow and both suppressions
were unchanged; the refresh flag was absent and the installer did not exist.
The installer creation and a separate optional cache-validator append were
safety-blocked and were not rerouted. Independent permitted source work continued.

Connection settings were inspected: the app override is already Allow all actions,
while the global default is Allow low-risk actions. A switch of only Remote
Desktop Commander to Always ask was proposed for explicit owner oversight and
awaits the owner's specific choice. It is not a safety override or guaranteed fix.
No connection/security settings changed. Keep #255/#239/#236 open. The next release
must use the latest reviewed source and a fresh frozen state export, not an older
rejected installer template. Source repair, native installation and real-case
acceptance remain distinct. See docs/validation/usefulness-cross-document-20261005.json.

## October 5 #255 — Real-data validation found cross-document limitation defect

Continuation of the owner's instruction to resolve the repair. Production still
runs 8678939; no installer, service/configuration change or new native writer was
executed. The installer write was again rejected by the remote-tool safety check.
The connection's actual app-specific permission is already Allow all actions;
its global default is Allow low-risk actions. No permission was changed. A switch
to Always ask was proposed for explicit owner oversight, not as a safety override,
and awaits the owner's specific selection.

Independent in-memory validation now used the configured model and a retained
real MSFT filing. The primary section completed with four exact source-validated
claims. Its existing section-only limitation check correctly reported missing
Exhibit 99.1 information because it could not see the companion exhibit already
present elsewhere in the evidence cache. A companion-segment attempt subsequently
failed one exact-quotation check and was rejected, not counted as completed.
Three structured-model invocations were made; this is not a full investment case,
a production run, a fresh state freeze, or evidence of investing performance.

Source correction on `codex/usefulness-cross-document-review-20261005` moves
limitation adjudication after complete document acquisition and all section claim
verification, using the combined cited issuer catalog. Each original limitation
must have one disposition. Resolved material information needs valid claim IDs;
missing or invented references and unresolved material facts stay blocking.
Original limitations and prior section-only reviews remain preserved. Resumable
catalog review is hash-bound to the exact limitations, claims and source versions.
No economic gate, model choice, request budget or source-coverage gate is relaxed.
An optional additional cache-validator append was tool-blocked and NOT applied;
on-access integrity checks and the snapshot hash remain in place.

Final local regression: 576 passed, seven optional skips. The new three-cycle
TEST proves source reviews, cross-document resolution, case and semantic checks
must all finish before sufficient status. Canonical CI and merge are pending.
Read `docs/validation/usefulness-cross-document-20261005.json` for exact evidence.
Live release and real-case acceptance remain separate, blocked requirements.

## October 5 #255 — Source repair merged and verified; NOT installed

Canonical repository **1349678672**, `maglothinm/MyETF-Intelligence`.
PR **#256** merged as **580fb3f2bd701e5cf16d126024ba2e5a671a05a9** from exact tested source
**7a7d3343997ff783bfb2d5c8ad90722495cf4364**. The merge tree equals the tested source tree.
All four canonical PR workflows passed on that head: Current Opportunity
37313433785 (Python 3.11 and 3.12), Runtime v2 safety 37313434017,
Investor Edge 37313433906, Source upload/OCR 37313433956.

Final local regression: **567 passed / 7 optional skips**; **10 Node/axe passes**.
Chromium TEST at 1280 and 390 pixels verified index-first loading, full evidence
only after an explicit click, zero page errors/external requests and no horizontal
overflow. Four-cycle TEST retained earlier AI fixture state, produced one simulated
intent and made no real provider, notification or trading calls.

Implemented historical identity preservation separate from feed expiry, genuine
bounded opt-in SHADOW capability renewal, complete bounded streaming of markup-heavy
issuer documents, incremental section review despite explicit missing documents,
retained source-bound limitation adjudication, honest research/valuation dispositions,
completion timestamps/counts, exact trade-ID placeholder linkage, and a compact
paginated index with on-demand exact-evaluation evidence. All economic gates and
existing history/delivery/portfolio contracts remain unchanged. Read
`docs/USEFULNESS_REPAIR.md` and `docs/releases/2026-10-05-usefulness-source.json`.

Fresh read-only preflight at 12:36:34 UTC verified AI1367, Dashboard2762,
Executive1036 and Legislative2300; all four archive round trips passed and all
**7,465 snapshot headers** have unbroken parent chains. This is not a later frozen
release baseline. Subsequent exported-case inspection was tool-blocked. No denied
inspection was rerouted or used as a reason to install without verification.

**Production remains unchanged.** At 13:03:46 UTC, installed source was still
**867893922e61c9fe30b1535e4deb32de8fc0d211** and the existing Database, Scheduler
and Web services were Running/Automatic. No production configuration, service,
state, credential, schedule, subscription, notification or portfolio was changed.
The new refresh flag has not been enabled. No real-case improvement is claimed.

Next safe action: restore permitted case-data verification access; confirm current
source/configuration and actual native locks; take a NEW frozen four-head export;
then use normal Windows approval for the reviewed existing-service release.
Only the source SHA and explicit AI shadow-refresh flag may change. Observe actual
regular-session renewal, persisted section progress, case dispositions, preserved
histories and no AI delivery before accepting #255/#239/#236. Do not merely extend
the old receipt expiry, add a writer or manufacture a buy. Broader universe coverage
beyond the seed allowlist and investment performance remain separately unproven.

## September 30 #250 - Funding dashboard deployed; native AI persistence recovered

Canonical repository **1349678672**, `maglothinm/MyETF-Intelligence`.
Installed source **867893922e61c9fe30b1535e4deb32de8fc0d211** at **13:07:29 UTC**.
Its executable matches tested funding head `fdc6dc9` / merged PR #251; later
commits contain documentation only. All four canonical CI runs passed. The
installation regression passed **594 tests**, with 24 optional/platform skips.

The owner approved the normal Windows prompt. The installer waited for the
active AI writer to finish without interrupting paid work. Its source-status
hash assertion then failed AFTER installing source/configuration because the
collector had legitimately updated that untracked status file during the wait.
Read-only reconciliation proved its 13:05:11 modification predates the release,
and its state hash exactly matches the frozen authoritative Legislative state.
The original failed log is retained. No permission was bypassed, state rewound,
installer rerun or historical row changed to manufacture a passing receipt.
Future release helpers must capture this hash at the final frozen boundary.

Actual postconditions passed: existing database PID **5008** remained running;
scheduler/web restarted successfully; configuration differs only in source SHA;
billing metadata table exists with **zero fabricated owner observations**; the
private route returns **401 SIGN_IN_REQUIRED** with no-store headers to an
unauthenticated request. Existing account/review and snapshot histories remain.

The existing locked dashboard controller published **dashboard 2298** at
**13:09:37 UTC**, SHA `65624a7f83d753a7821fd85a2b9e6e2583b0e8499a66b2a65afa9f9add84c559`.
Funding HTML/JS/CSS match installed source bytes; the overview counter is present.
Actual local-browser reads at **1280 and 390 pixels** passed without page errors,
overflow, external requests or account writes. Authenticated owner balance entry
has not been exercised on production; no user session or balance was fabricated.

The preceding scheduled AI run also genuinely recovered publication: **AI1132**
committed at **13:06:56 UTC**, SHA
`da84a80efb905d6a4f73bd8e32dc4bf3257de1ed2dd9e30bb2e3388d9c3f0294`,
with 20 completed analyses and a **228,072,223-byte** uncompressed snapshot under
the unchanged safety cap. Original 8,596 opportunity events, 533 opportunity IDs,
376 completed-analysis IDs and all retained JSONL prefixes were preserved.
Completed-analysis IDs increased to 396. The release preserved all **6,092**
frozen snapshot headers with zero broken links. No AI delivery was queued.

This is funding deployment and first recovered AI publication, not investment
case or performance acceptance. Current Opportunity remains SHADOW; both AI
delivery suppressions stay true. The original capabilities are expired, all
79 retained issuer sections remain unreviewed, and no company dossier is ready.
Keep #239/#236 open and retain #246 for sustained operational acceptance.

The funding panel correctly leaves actual balances unknown until the owner signs
in to PolitiTrack and records the remaining amount in the correct provider account.
At initial verification its request scope was not yet reverified by a newly
instrumented native request. An optional passive follow-up watcher write was
tool-blocked before execution and was not rerouted. Keep #250 open for the first
authenticated owner-entry acceptance; no further installation is pending.
See `docs/releases/2026-09-30-billing-deployed.json` for exact evidence.
Private evidence: `C:\ProgramData\PolitiTrack\backups\billing-install-250-20260930T124844Z\release`.

## September 30 #250 - Renewed installation attempt stopped before release

The owner authorized installation again. The first normal Windows UAC prompt
was approved, but preflight found an old executive run marked running with no
actual writer lock. Its historical row was preserved. A revised installer now
checks actual PostgreSQL writer/backup locks plus current scheduler descendants,
not the historical status label. It still waits for real active jobs to finish.

The second normal UAC prompt returned cancellation before the revised helper
started. No repeated elevation or alternate installation was attempted. The
first idle installer was then canceled using ordinary process access; both of
its Python processes exited before any service/configuration/schema mutation.
No native producer, connector or security process was terminated.

Verified at 12:54:51 UTC: installed source remains **638abc0**, the configuration
is unchanged, and the billing metadata table is absent. PostgreSQL PID 5008,
scheduler PID 38196 and web PID 19376 remain running without restart by this
attempt. AI head 1131 and zero AI deliveries since SHADOW remain the last checked
facts. The scheduled AI run is making genuine HTTP 200 model requests; its final
publication is still pending. Do not turn those requests into acceptance claims.

The tested funding implementation remains merged via #251. An additional local
installation-focused regression passed **104 tests**, with 23 optional/platform
skips; JavaScript syntax and Git diff checks passed. Funding is still NOT live.
No balances were fabricated, credentials requested, payments made or live alerts
enabled. Keep #250/#246/#239/#236 open pending their respective acceptance gates.

Next safe action: obtain a new normal Windows administrator approval for the
revised pinned helper, refresh source identity and active locks, then deploy and
verify real publication, private routes and desktop/mobile live rendering.
Read `docs/releases/2026-09-30-billing-install-retry-blocked.json` for exact state.
Private evidence: `C:\ProgramData\PolitiTrack\backups\billing-install-250-20260930T124844Z`.

## September 30 #250 - Funding dashboard merged; installation approval canceled

Funding dashboard PR **#251** is merged as
**f6b51ad3b4a80847d1a459a56ed43522c6376973**. Tested head
**fdc6dc996f43fc5759a94d06f0ef26568856ecf6** passed 606 local tests (33
optional/platform skips), four canonical PR workflows and desktop/mobile TEST
browser acceptance. The API funding correction is real: the existing configured
API returned HTTP 200 / completed at 12:06:27 UTC. No dollar balance was returned.

**This dashboard change is NOT installed.** Windows returned 'The operation was
canceled by the user' during normal UAC elevation. The release helper never
started, no release log was created, and the new metadata table does not exist.
Installed source remains **638abc0**. PostgreSQL, scheduler and web services were
not changed by this attempt. SHADOW and both AI delivery suppressions remain true.
Do not retry elevation or use another installation route without renewed owner
approval. Request that the owner be at Beast and approve the next normal prompt.

The separate earlier manual AI recovery ended in TimeoutExpired at 12:17:57 UTC;
all four related processes exited without manual termination. AI head remains
1131; no successful AI persistence or investment evidence is claimed. Keep
#246/#239/#236 open independently of the funding UI. The expired capability
receipt was not renewed and no investment alert or order was authorized.

After approved installation, initialize only the additive billing metadata table,
verify native publication and live UI/routes, and have the owner record the
remaining API balance shown in the correct provider account. Balance values are
owner-reported observations; estimates are separate and missing coverage stays
unknown. No provider admin key, account upgrade or payment is required by the UI.
Read `docs/BILLING_STATUS.md` and the billing installation-blocked receipt.
Private evidence: `C:\ProgramData\PolitiTrack\backups\billing-dashboard-250-20260930T115321Z`.

## September 30 #250 - Funding dashboard implementation prepared

Owner clarified that the new payment now funds the OpenAI API, not ChatGPT.
A real minimal request at 12:06:27 UTC returned HTTP 200 / completed on the
existing configured model (10 input, 5 output tokens). This establishes API
request availability, not a dollar balance or investment-case completion.

Branch `codex/billing-dashboard-250-20260930`, based on main `54b9ed7`, adds a
private Funding & paid services overview counter and expanded Operating costs
page. Exact API/ChatGPT separation, live observed usage/error health, dated
owner-reported balances, conservative token-only estimates, low/stale/renewal
warnings and separate currency/request units are explicit. There are no paid
requests on page refresh or automatic payments. Unknown balances stay unknown.

Owner observations use the existing authenticated review session and append to
an additive PostgreSQL metadata table. Existing review revisions, trading state,
notifications and scheduled writers are unchanged. The native usage journal gets
only a private scope digest, purpose and whitelisted error codes. Financial
amounts remain private; public snapshot assets contain no owner balance values.
Read `docs/BILLING_STATUS.md` for boundaries and operator schema initialization.

Local acceptance: 606 tests passed, 33 skipped (including optional PostgreSQL
cases not enabled locally); offline browser login/save tests passed at 1280 and
390 pixels with no script errors or horizontal overflow. Canonical CI, merge,
operator schema initialization and live release verification are still pending.
Installed source remains `638abc0`; the earlier manual AI recovery remained
running at last inspection, so no new authoritative AI snapshot is claimed.
SHADOW and both AI delivery suppressions remain enabled. The original capability
receipt is expired; issuer/model review and #246/#239/#236 remain open.

## September 30 #246 - Repair deployed; persistence acceptance still blocked

Installed source **638abc04cde135fb4240046160875a2723b01a1d** at11:18:31UTC
through normal Windows UAC. The executable matches tested d520aa7; only docs
differ. Fresh read-only four-head export verified6074 headers and zero broken
links. Database PID5008 never restarted; scheduler/web restarted; readyz200.
Current Opportunity remains SHADOW; both AI delivery suppressions remain true.

The user's added credits did not establish API recovery: an actual11:19UTC
request still returned exhausted account quota. The manual recovery controller
invocation was pending at its last permitted read; its later outcome/API-usage
read was platform-blocked. Do not claim a new AI snapshot or scheduled success.
Quota integration and free-provider verification writes were separately blocked
before execution. No denied operation was attempted through another route.
No capability renewal, completed investment case or investing performance is
accepted. Keep #246/#239/#236 open. The owner must resolve actual API account
availability, and tool read/write blocks must be cleared before verification.

See **docs/releases/2026-09-30-resume.md** for exact evidence and next actions.
Private evidence: C:\ProgramData\PolitiTrack\backups\runtime-resume-20260930T111742Z.

## September 29 #246 â€” Repair merged; deployment safely rolled back at file-access block

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Snapshot repair **PR #247** is merged as **4aeb2a6e78d869a33333f0e1d099189a6239dfbd**.
Exact tested head **d520aa7d8a4894195ed3ad64aea10a8348b6c04d** passed 519 local
relevant tests (one skipped) and canonical CI **36587550280**, **36587550107**,
**36587550200**. The complete historical suite is not claimed Windows-compatible:
its legacy Linux-only fcntl imports prevent collection of several unrelated tests.

**The repair is NOT deployed.** The existing-service release attempt reached a
fresh verified four-head freeze (5,884 headers, no broken links) but Windows
rejected atomic replacement of `config/runtime.json` with PermissionError/WinError 5.
The original configuration is byte-identical to its private backup. The helper
rolled source back to **efae28e99f02dabb0122a6cb53062ecc2bbe13e2** and restarted
the original scheduler/web services. PostgreSQL PID **5008** never restarted.
No authoritative snapshot from the repaired source exists; AI remains **1131**
(last committed 06:15:28 UTC). No AI delivery was queued since shadow activation.

Windows Restart Manager identifies Desktop Commander's `node.exe` PID **34184**
as the application using `runtime.json`. The exact share/locking mode was not
observed. The operation was already administrator-elevated, the file is not
read-only, and its administrator/owner ACLs allow full control. No matching
Defender controlled-folder-access event was returned. Do not force-close handles,
kill security/connector processes, weaken ACLs or bypass the separate tool block.
Request that the owner fully restart/reconnect Desktop Commander and authorize
the release/quota-edit retry. Take a NEW frozen export on the next attempt; do not
reuse/overwrite the existing freeze or blindly rerun the dated deployment helper.

The two original causes are established: 7,975 full no-work evaluation copies
amplified snapshot growth beside only 620 actual evaluations, and the retained
OpenAI response identifies a nontransient exhausted account quota. The source
repair makes repeated identical missed-work states idempotent and deduplicates
exact JSON subtrees. Private real-state pack/restore/repack preserved all 8,596
events, 533 projections and 1,607 other files, reducing the full uncompressed
snapshot from 526,698,384 to **225,361,624 bytes** under the unchanged 512-MiB cap.
See `docs/OPPORTUNITY_STORAGE.md` and the September 29 source/blocker receipts.

A local `scripts/openai_health.py` draft remains UNCOMMITTED and UNINTEGRATED.
Its quota-handling integration was tool-blocked; no durable cooldown is active.
**Do not fund the API before the snapshot repair is deployed and verified:** the
old release can otherwise spend on analyses whose oversized snapshots fail to
publish. After safe publication is restored, resolve the existing API quota
without a new subscription, then complete genuine capability and issuer review.
No balance, subscription, credential or model was changed.

The original capability receipt expired at **2026-09-29T14:44:22Z**; no renewal
was fabricated. Retained issuer evidence has 17 documents/79 sections, zero
model-reviewed sections and zero accepted investment dossiers. Keep SHADOW and
AI delivery suppression; keep #246/#239/#236 open. A compatible codec/reader must
remain in any rollback build after encoded state first publishes; never rewind
an authoritative head to accommodate an obsolete executable.

Private evidence: `C:\ProgramData\PolitiTrack\backups\runtime-growth-429-20260929`.
Worktree: `C:\Users\maglo\PolitiTrack-work\runtime-growth-429-20260929`.
Current follow-up branch `codex/runtime-growth-blockers-20260929` is documentation
only. The original repair branch retains the exact tested implementation.

## September 28 #239 — Deployed on Beast; first scheduled shadow run succeeded

Owner authorized steps 2–6 autonomously. Merged #243 revision
`5e6d53e080c76335280074a4224eae7427586716` was installed at 15:05 UTC using the
existing scheduler/web service boundaries. PostgreSQL PID 5008 was not restarted.
Fresh frozen export/repack verification passed for all four heads and 5,630
historical snapshot headers had no broken parent links. The existing untracked
source-status file was preserved; no head was reset or replaced.

The verified, pinned provider receipt covers three companies (BE, INTC, MSFT)
and the SPY benchmark, with two explicitly checked House report-to-bioguide links.
Those links were checked against original public disclosure pages and the Clerk's
member directory. All other unresolved identities remain unresolved. LocalService
was granted Read access to the existing Massive key file only; no broad user grant
or credential/account change. Current Opportunity is configured **shadow** in the
existing AI invocation; AI alert and notification dispatch are explicitly suppressed.
The receipt expires 2026-09-29 14:44:22 UTC; renewal/expanded identity verification
is not inferred from mere file presence or extended silently.

The normal 15:14 UTC AI run committed generation **1101**, snapshot
`6dfba9fcae67cc2681daa4c322570f2a16b6892d8e4f0270a5d0e232bbb29b57`.
Its committed opportunity state is shadow and contains the successful capability
import, 12 real Massive requests, current Finnhub prices, SEC facts, two downloaded
issuer documents/four text sections, 20 evaluated groups, and zero opportunity
alert intents/deliveries. No section model reviews have completed yet. The served
Current Opportunity projection reports shadow and the Operating costs page is HTTP
200. Empty measured API usage is explicitly unknown historical cost, not a $0 bill.

The first run exposed review scheduling that would leave verified, unfinished
cases behind 1,365 unresolved groups. The deployment branch adds identity-ready
review priority plus true round-robin ordering ahead of duration-dependent
timestamps, and start-minute-based review deadlines to avoid missing the next
30-minute slot merely because downloads took minutes. Unresolved rows remain in
bounded audit work, no buying/entry/evidence threshold is relaxed, and retained
source records, original anchors and notification history are not rewritten.
Local targeted regression: **288 passed**. Exact-head CI and guarded service
installation of this corrective patch remain distinct from these tests.

Keep #239/#236 open. Live investment notifications are not enabled. Full issuer
case review, a further zero-new-filing scheduled cycle, continuity checks and live
readiness assessment remain to be completed; initial data access is not proof of
an actionable investment or complete universe coverage.


## September 28 #239 — Owner key validated; actual free feeds verified, activation not applied

The owner entered the key through the corrected masked Windows dialog. The
14:35 UTC successful setup receipt verifies MSFT metadata, 499 daily bars through
September 25, eight dividends and a securely retained local credential. No key is
stored in this repository or these notes. PR #242 merged as
c5d754647c5074165573d1aaf959cabafc385222 after both exact-head CI runs succeeded.

Additional bounded read-only checks verified current/as-of security metadata and
499 daily bars each for BE, INTC, MSFT and benchmark SPY. Existing Finnhub quotes
were 15–34 seconds old at observation. These are actual API response checks, not
investment recommendations, complete feed licensing claims or universe-wide
identity certification. No paid subscription or model call was made for the probes.

A fresh read-only snapshot export verified AI 1099, Dashboard 2111, Executive 766,
and Legislative 1649, with archive round-trip hashes and new-reader validation.
The running source remains 83501363c719aa14a46e141ef4c94cfb0532d23b and Current
Opportunity remains OFF. No production service, scheduler, setting, state or
portfolio was changed. The credential currently permits owner/admin/SYSTEM only;
the existing LocalService runtime has not been granted access by this session.

The attempted combined source-verification/capability-configuration write was
blocked by the tool safety check before execution. The target capability file
was confirmed absent. Do not bypass that boundary or manufacture capabilities.
No source-filer capability mapping was imported. Deployment requires the permitted
verification/configuration path and a fresh release-time state check; this earlier
preflight must not be reused as a frozen later deployment baseline.

Branch codex/free-stack-shadow-20260928 contains an unactivated, pinned shadow-only
capability import and a guard against assigning common-stock identity to options
or bonds. It has not been installed or enabled. Source/test status is recorded in
its PR. No owner re-entry of the valid key is needed.


## September 28 #239 — Windows Ctrl+V input defect identified and corrected

The saved key from the resumed setup consisted solely of the Ctrl+V control
character (length one, nonprintable), not the owner's API key. A bounded direct
request returned plain HTTP 400. This explains why the hidden console prompt did
not authenticate; no bad-key/subscription verdict is drawn about the real key.
The unusable control-only file was preserved privately and removed from the active
credential path; no valid credential or production state was overwritten.

Branch `codex/massive-setup-recovery-20260928`, PR #242: use a native Windows
masked password dialog supporting Ctrl+V; reject nonprintable, whitespace,
non-ASCII and implausibly short input before saving or sending. Preserve securely
entered credentials independently of verification and retain redacted endpoint
failure diagnostics. Latest metadata requests omit the unnecessary date filter.

The owner must paste the real key once in the new local dialog. Successful actual
free-data access and deployment remain unverified; production settings/services
and Current Opportunity OFF are unchanged. No paid subscription or trade.


## September 28 #239 — Recover failed Massive setup without discarding credentials

The owner entered a key locally, but the saved probe receipt reports
`massive_http_400`, `success=false`, and no credential file. No history pages or
endpoint diagnostics were retained, so the failing stage/root cause is not yet
established. Closing the launcher was not successful account setup.

Branch `codex/massive-setup-recovery-20260928` from canonical main
`4f805818562b66b6c0971c1496c62410dfa62ecd` adds bounded secret-redacted HTTP
request diagnostics, requests latest metadata without the unnecessary date filter,
and securely preserves locally entered credentials before network validation.
Credential storage never sets provider capability or activates production.
Focused offline validation: 38 tests passed. The owner must re-enter the key once
because the old routine discarded it. Actual provider/release/shadow verification
remains pending. Installed application and services remain unchanged.


## September 24 #239 — Free stack merged; owner API key is the next setup input

PR **#240** merged as **0b70118fc8911e54e427d0011a43672a7029f8ab**;
the tree exactly matches tested head **41eb60b90d65e49ed9578d60c41810884ba62318**.
Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
All four exact-head CI workflows succeeded: Current Opportunity 36035728639,
Investor Edge 36035728339, Runtime safety 36035728272, source OCR 36035728574.
Local verification: 518 Python passes / one optional PostgreSQL-service skip,
eight Node/axe passes, and headless Edge cost-page checks at 1280/390 pixels.

Massive free EOD history, explicit splits, rate limiting and restart caching are
implemented for the Current Opportunity/research path with Finnhub/SEC retained.
The test-only free adapter cycle passed the investment case gates and preserved
old state. API usage/cost estimates and the separate cost screen are implemented;
no invoice or historical unmetered charge is fabricated.

The **PolitiTrack Free Data Setup** launcher is on Beast's Desktop, pinned to the
tested clean source. It requests a free Massive key locally with hidden input,
performs a read-only provider probe and creates a restricted credential file after
success. It does not create an account, purchase a plan, activate a capability,
change production settings, enable an alert or place a trade. No Massive key was
present at closeout. Do not ask the owner to paste credentials into chat.

Installed application remains 83501363c719aa14a46e141ef4c94cfb0532d23b with Current
Opportunity OFF; no services, production settings, histories or portfolios changed.
No new scheduler or cloud writer was created. Retired GitHub writers remain disabled.
After local key setup, verify actual free-tier responses, precise capability/source
identities and a fresh authoritative snapshot baseline; then use normal Windows
release approval and observed shadow cycles. Keep #239/#236 open for live acceptance.
See `docs/releases/2026-09-24-free-stack-source.json` and `docs/FREE_MARKET_STACK.md`.


## September 24 #239 — Free market stack implementation; activation awaits owner key

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Branch `codex/free-market-stack-20260924`, based on main
`b158d177b222d93bc785570e1c5e5ec8c5dc90f4`. The owner approved Massive Basic free
history + existing Finnhub quotes + SEC, not a paid Alpha Vantage subscription.

Implemented explicit Massive history selection, raw OHLC/dated split reconciliation,
separate dividend provenance, two-year coverage limits, safe resumable pagination,
shared five/minute pacing, snapshot-owned derived caching, truthful daily-window
scope and matched research. Added API request/token accounting and a separate
Operating costs screen; missing usage is not a zero bill and token estimates are
not invoices. No model upgrade or additional paid call is made by a test.

A local hidden-input setup/probe helper accepts the owner's free API key without
putting it in Git, logs or command arguments. Current runtime has no Massive key;
no real Massive response, account creation or capability activation is claimed.
The data adapter is not a silent migration of legacy Investor Edge prices or old
paper accounting. Current Opportunity remains OFF on installed source
`83501363c719aa14a46e141ef4c94cfb0532d23b`; production configuration and services
are unchanged. See `docs/FREE_MARKET_STACK.md` for exact scope and setup.

Local verification: **518 Python passes / one optional PostgreSQL-service skip**;
**eight Node/axe checks passed**. The free adapter executed the existing decision
cycle with TEST provider responses and no Alpha key, preserved original AI state,
and generated one simulated intent. No actual market/model/notification call was
made by the tests. See `docs/validation/free-market-stack-local.json`.

Next: exact-head CI/review, owner free key and actual response tests, genuine
provider/security/owner receipts, fresh authoritative snapshot preflight, then
the existing Windows release boundary and scheduled shadow acceptance. No live
investment alerts, subscriptions, orders, new writers or cloud reactivation.


## September 24 #236 — PR #237 merged; state preflight passed, data activation blocked

Owner reviewed the implementation and instructed “Reviewed. Proceed.” Canonical
repository ID **1349678672**, `maglothinm/MyETF-Intelligence`. PR #237 merged at
15:00:10 UTC as **268e6e5fca4895300192028f869c1d6f38fb9d13**. Its tree exactly
matches reviewed/tested head **ee7564863f205e2066c41c89cb605478521d238c**.
All four exact-head CI workflows passed attempt 1: Current Opportunity 36003133613,
Runtime safety 36003133764, source OCR 36003133456, Investor Edge 36003133466.

The previous snapshot-read tool blocker is cleared. A read-only repeatable-read
transaction exported authoritative AI 908, Dashboard 1728, Executive 757 and
Legislative 1625. Every archive unpack/repack hash matched, the new AI reader
validated the existing state, and all **5,018** retained snapshot headers form
unbroken parent chains matching those heads. Private raw exports remain outside
Git on Beast. This is verified read-only preflight, not a production restore or
permission to reuse an old baseline at a later deployment.

The exact configured Alpha Vantage daily-adjusted endpoint still returned zero
bars and a premium-only message. The published entry monthly tier is $49.99 for
75 requests/minute; no subscription was purchased or cost approved. This proposed
tier is for historical data, not a substitute delayed quote. Finnhub returned a
positive regular-session quote 19.44 seconds old; full entitlement/identity
capability receipts are not yet established. No capability file was fabricated.

Beast remains on **83501363c719aa14a46e141ef4c94cfb0532d23b**; Current Opportunity
is **OFF**. Database/web/scheduler remain Running/Automatic, without a restart,
configuration change, new alert, order, source approval, or cloud/legacy activation.
The remote token is not elevated; normal Windows approval remains necessary at
actual release time. Issue #236 stays open for operational acceptance.

Next: obtain the owner's decision on historical-data access; verify real provider
responses and exact security/owner capability evidence; then take a fresh baseline
and use the existing Beast service boundary for shadow deployment and scheduled
acceptance. Live investment notifications and brokerage orders remain out of scope.
See `docs/releases/2026-09-24-investment-decision-preflight.json` for exact receipts.

## September 24 #236 — Investment Decision v2 source implementation, not deployed

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Branch `codex/investment-decision-v2-20260924` from `main`
`deb18f6632017c8a762a8d9dec2799f82cc6a845`. Installed Beast source inspected at
`83501363c719aa14a46e141ef4c94cfb0532d23b`; Current Opportunity remains OFF.

Implemented case-level source guards, resumable SEC document/exhibit reviews,
exact claim passages, distinct risks/uncertainties/thesis breakers, company
scenario dossiers, post-analysis quotes, conditional post-decision research,
and dashboard/CSV/JSON under the existing AI snapshot writer. Mode, channels,
old ledgers/reviews/portfolios and cloud retirement remain unchanged.

Local final broad regression: 437 passed / 0 skipped. TEST return/restart fixture:
one simulated opportunity intent, no real calls/messages/trades. Provider probe:
Alpha Vantage returned a premium-endpoint response with no required bars;
Finnhub responded but zero-delay entitlement remains unverified. Authoritative
snapshot preflight was tool-blocked, not executed. Do not activate shadow/live
until documented state/provider gates pass. No production deployment is claimed.
See `docs/INVESTMENT_DECISION_V2.md` and `docs/validation/investment-decision-v2.md`.
Issue #236 remains open for operational acceptance; PR #237 records exact-head CI.


## September 23 #232 - activated on Beast; complete directory and search verified live

Canonical repository ID **1349678672**, `maglothinm/MyETF-Intelligence`.
Session branch `codex/profiles232-live-receipt`, based on main
`a5904b0af624c3f2b40daf10912e24c7b01e26d8`; this receipt changes documentation only.
[PR #233](https://github.com/maglothinm/MyETF-Intelligence/pull/233) release
**83501363c719aa14a46e141ef4c94cfb0532d23b** is installed and configured on Beast, matching tested source
**a37133f08d4e77b164e89d27bb4625ec31b89c40**. The earlier canceled approval attempt is superseded by the
owner-authorized retry and successful normal Windows approval.

### Activation and autonomous publication

The existing release helper completed at **2026-09-23T12:13:56.9228612Z**, using
the existing scheduler/web stop-start boundaries. Database PID **25732** remained
running; web PID **37084** and scheduler PID **39472** are running with automatic
startup. The readiness endpoint returned HTTP 200. No manual AI/dashboard producer
run was invoked: the existing native scheduler published both new heads successfully
with `trigger_source=external_scheduler`, through the existing writer locks:

| Namespace | Generation | Committed UTC | Snapshot SHA-256 |
|---|---:|---|---|
| AI | 855 | 2026-09-23 12:14:35.889504 | `2f5a4a08f6efaadfaac5a2f715c1af22b4bd870e060d42a5978507dc9b0c2448` |
| Dashboard | 1622 | 2026-09-23 12:17:22.266089 | `ac85360a1b473201b913b3c963c17bdcd3437c25cd58345625be88c0efd20cb1` |

Both heads record source revision `83501363c719aa14a46e141ef4c94cfb0532d23b`. Read-only verification at
**2026-09-23T12:17:52.587355+00:00** found **1,028 distinct owner profiles covering all
975 known filer names**, including Donald Trump. All published filing names are
represented. Persisted AI, served JSON and CSV agree exactly; seven served data/UI
routes match the committed dashboard snapshot bytes. The existing per-run budgets
remain 30 historical observations and 40 provider requests; the accepted AI run used
30 and 40 respectively. These are background limits, not directory admission limits.

At **2026-09-23T12:18:08.803926+00:00**, real Edge checks against the deployed site passed
on both root/standalone views at 1280 and 390 pixels: name-order/case-independent
Donald Trump lookup, pending-review filter, automatic matching Building history
expansion, clear and responsive layout. No JavaScript errors occurred and the browser
was restricted to read-only local requests.

### Tests and continuity

Previously completed source validation: **412 local regression passes** under the
same UTF-8 configuration as Beast, plus offline browser/replay checks. Offline replay
retained all 62 prior profile identities, 1,519 observations and history-ledger bytes
with zero provider calls. All four exact-tested-head CI runs passed:

- [Investor Edge tests 35857964119](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964119): attempt 1 success.
- [Runtime v2 safety tests 35857964150](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964150): attempt 1 success.
- [Source upload and OCR tests 35857964122](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964122): attempt 1 success.
- [Current Opportunity offline tests 35857964184](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/35857964184): attempt 1 success.

The after-activation and after-publication read-only fingerprints match all **4,706**
immutable snapshot headers at cutoff `2026-09-23T12:02:16.803496+00:00`, digest
`7d77ad4fde7c22093e23f7424666093f`. There are **zero broken snapshot parent links**.
Installed untracked `legislative-source-status.json` still matches SHA-256
`E5C1B22AB61D88DB8FA75B228DBF3A499734C37DDD26B22DB445C8B3F7226BF2`. PostgreSQL immutable heads remain the
authority; no protected GitHub recovery artifact was restored or replaced. No
rebaseline, new writer/schedule, filing upload or cloud/legacy activation occurred.

### Review boundary and next safe action

Donald Trump's Self profile is visible with 519 retained transactions, one pending
source review, and `building / insufficient_completed_observations`. His original
30-page manual upload `a816c4f5-3327-4cdd-9930-a94b53927a64` remains `needs_review`,
with receipt `fe768ffad0909dbba9095b89615561a5fc3c259423f4a22b191737fbe5e50a3f`.
Directory publication does not approve it or resolve the suspected municipal-bond
ticker classification. [#225](https://github.com/maglothinm/MyETF-Intelligence/issues/225)
retains the independent original pending-upload outage acceptance boundary.

Activation and live acceptance for [#232](https://github.com/maglothinm/MyETF-Intelligence/issues/232)
are complete. Completion receipt is
`C:\ProgramData\PolitiTrack\backups\profiles232-complete.json`, with `accepted=true`
and the expected installed revision. It supersedes the installer-time
`live_publication_verified=false` checkpoint and makes the prepared Desktop launcher
a no-op for this completed release. User-facing reports and verification JSON are
retained in the task outputs folder. Use the live name/status controls; no further
activation is needed. Leave the existing scheduler to continue bounded evidence
collection. Handle original source review and #225 separately without re-uploading,
requeueing, approving, or manufacturing evidence as part of this directory fix.
