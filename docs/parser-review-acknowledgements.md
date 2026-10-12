# Personal Manual Parser Exception acknowledgements

Issue [#159](https://github.com/maglothinm/MyETF-Intelligence/issues/159) replaces
the browser-only storage in issue #155. Each person has a separate account and
saved review history in the existing private Runtime v2 PostgreSQL database.
Clearing browser data signs the person out; signing in restores their history.
Acknowledgement records that a person reviewed an exception. It does not resolve
the parser defect, delete evidence, or change another person's queue.

**Current runtime:** the owner's September 21 hosting decision moved the
authoritative PostgreSQL database and services to Windows Beast. References to
Cloud SQL and the original cloud rollout below are historical; they do not
authorize restarting cloud hosting. Personal account and review history remain
in the existing Runtime v2 database.

## Direct review actions and source OCR versions (#265)

Review / Sources at `/#records/reviews` exposes **Acknowledge manual review** and
**Restore to active review** on eligible review rows. Selecting an authenticated
action leaves the person in the review list and confirms success only after the
existing personal-review API commits the change.
Signed-out, stale-account, stale-revision and failed-save responses retain the
existing account checks and never display a successful acknowledgement.

The published review inventory also includes retained source OCR `needs_review`
receipts, even when a collector did not append a separate parser exception.
These are read-only dashboard projections; the source receipt, pending-review
ledger, filing, transaction and producer snapshot contents are not edited by
acknowledging a row. The distinct `source_ocr_manual_review` family does not inherit
older parser acknowledgements merely because the filing name or URL matches.

The source OCR logical identity binds the exact filing identity, retained source
document hash and structured review reason. Unchanged source bytes and review
family retain the acknowledgement across publication, ordinary retry and display
wording changes. New document bytes or a new review family require another
review; the prior personal history remains saved. When admission fails before
the bytes can be hashed, the identity is limited to that real recorded attempt
so a later unknown source version cannot inherit an old acknowledgement.
Contradictory or malformed source identity remains explicitly ineligible for an
acknowledgement rather than being guessed into another version.

Acknowledgement records manual review. It does not approve extraction, resolve a
parser/source error, waive document limits or import transactions. Those existing
source correction and transaction review actions retain their separate purpose.

### October 12 native delivery and acceptance

PR [#266](https://github.com/maglothinm/MyETF-Intelligence/pull/266) is installed on
Beast as `49c4229e69fe07b4570f2eccdc8ccb39cf566382`. Final tested source
`d64539dee1fbb7d120025ab213d8be8042fb8e37` shares the installed tree
`82f3c4ef9f55cd4f40a98369bad2b5841c37f059`. Canonical
[Source OCR CI 38243123539](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/38243123539)
passed on attempt 1 with 492 Python checks, 1 skip and 8 Node checks. Its generated
TEST site and in-memory personal API exercised direct row Acknowledge, saved
state after browser storage clearing/reload, and Restore at 1280 and 390 pixels,
without detail navigation or document overflow. No live personal state was used.

Native acceptance at `2026-10-12T11:57:53.109145–11:57:56.260339Z` verified the
served Dashboard3013 head and exact generated assets, then checked the signed-out
row action in live Edge at both widths. That browser inspection was read-only.
Separately, the real native API saved an acknowledgement at revision 1 in one
new TEST account, recovered it after logout and a fresh sign-in, and restored
the review at revision 2. The TEST account was then disabled with all sessions
revoked; subsequent sign-in and session access were rejected. Its Restore
tombstone and two audit events remain retained. Full-row fingerprints for the
original 3 accounts, 14 acknowledgement rows and 15 audit events were unchanged.
No owner review, password or account recovery was changed.

The final cross-namespace continuity check passed at `12:00:31.324574Z`, retaining
all 8,215 prior snapshot headers, 17 JSONL prefixes, 1,258 OCR-evidence files and
the original filing, review and trade IDs. Personal totals increased only by the
disabled TEST account, one Restore tombstone and two audit events. The exact
source, CI artifact, native acceptance and preservation evidence is recorded in
the sanitized [#265 receipt](validation/dashboard-source-reviews-20261012.json).
The application delivery is accepted. Issue #265 remains open only for separate
legacy dashboard-cache housekeeping, interrupted by the RDC connection before a
second maintenance operation began. That interruption does not undo the completed
acknowledgement acceptance or justify repeating account setup or recovery.

## Identity and retained evidence

`scripts/review_identity.py` derives `logical_review_id` from source, a tagged
filing identity, and `exception_code`. Filing identity prefers `report_id`, then
`filing_key`, `source_record_id`, and finally `source_url`. The versioned SHA-256
input excludes diagnostic wording, filer, dates, and display metadata. New parser
families must supply a distinct code; materially different defects must not reuse
an old code. Current codes include `paper_filing_manual_review`,
`unparseable_transaction_table`, and the separate `disclosure_access_required`.

Existing evidence IDs and pending-review JSONL bytes remain intact. Retained
logical identities prevent duplicate ingestion even after a bounded seen index
ages out. Publication supplies the same identity map in insights, complete JSON,
and CSV. Known pre-code messages receive explicit compatibility codes; unknown
legacy exceptions retain their individual identity rather than being guessed
into an unrelated exception. Count/category/ID consistency remains mandatory.

## Durable personal history

`runtime_v2/review_accounts.py` owns five additive tables: accounts, hashed
sessions, acknowledgement state, append-only review events, and authentication
rate-limit buckets. It never initializes or changes producer snapshot tables.
The primary acknowledgement key is `(account_id, logical_review_id)`.

Each save locks the account row and atomically commits the acknowledgement,
audit event, and account revision. A request UUID supports idempotent retries;
the expected revision prevents stale tabs from overwriting newer choices. The
authenticated account determines ownership. The client also supplies its
expected account ID so a tab showing Alice cannot save after another tab signs
in as Bob. This ID is a concurrency check, never authentication authority.

**Restore to active review** retains a false acknowledgement tombstone and an
audit event. Later imports cannot recreate that acknowledgement through an old
evidence alias. An explicit subsequent acknowledgement can acknowledge it again.
Publication absence, service restarts, deployments, password recovery, and browser
clearing do not delete review history. There is no 500-record or time-based
eviction of server-side acknowledgements. New logical identities remain active.
Personal state is never added to public dashboard exports or producer snapshots.

## Sign-in and recovery

The dashboard remains readable without an account. Personal state requires
sign-in through `/api/reviews/`. On Beast, an administrator provisions an
invitation through the existing `python -m runtime_v2.cli review-invite` command
under the established private native runtime environment. The original
IAM-protected cloud admin job is historical and must not be reactivated.
There is no public registration endpoint.
The owner chooses a 14–256 character password or passphrase using a private,
single-use activation link. Passwords use Werkzeug scrypt hashing; random
activation/session tokens are stored only as SHA-256 hashes. Activation links
expire after seven days and sessions after thirty days. Tokens go in the URL
fragment, which the app immediately removes, then in the activation POST body.
Never put raw tokens or passwords in repository files, issues, execution args,
logs, screenshots, or public release evidence.

The session cookie is HttpOnly, SameSite=Strict, host-only, and scoped to `/`.
The current native `RUNTIME_LOCAL_ONLY=true` boundary uses
`http://127.0.0.1:8765` and `polititrack_local_session`, without the Secure flag
because this is the explicit HTTP loopback deployment. Mutations must match the
configured Origin and exact host, and the client address must be `127.0.0.1`.
The remote deployment code retains its HTTPS-only Origin requirement and Secure
`__Host-` cookie; that code does not authorize restoring cloud hosting.
Mutations also require JSON and a custom same-origin request header.
Responses are private/no-store. Database-backed
rate limits apply across web instances. Password recovery preserves the stable
account ID and all reviews, consumes a new invitation, and revokes old sessions.
Administrative account disabling also revokes sessions without deleting history.
Users who forget a password request an administrator-issued recovery link; they
must not receive a replacement account that silently abandons their history.

The interface confirms success only after the database commit. A failed save
leaves the previous result visible with an error. Unavailable or signed-out
personal state is explicitly unknown; it is never rendered as zero saved reviews.

## Legacy acknowledgement recovery

The old `polititrack.manual-review-acknowledgements.v1` key is read only for an
explicit, signed-in **Import my previous acknowledgements** action. Import never
runs automatically on a shared browser. The original evidence IDs and timestamps
are retained. The current verified publication must establish each logical
identity; unknown records are skipped and their original backup remains intact.
Import is additive, at most 500 records per request, and never overwrites an
existing acknowledgement or Restore tombstone. This import limit is not a
server-history retention limit.

The four acknowledgements recovered on September 9 are an owner-authorized
migration into the owner's stable account, preserving their September 8 times.
The separate recovery file is private operational evidence, not a fixture or a
new parser baseline. Do not migrate them into every person's account.

## Administration and rollout

The existing Runtime v2 CLI exposes these commands. Use the private native
environment on Beast; do not copy credentials into shell arguments or evidence.

- `review-init-db`: create only the additive personal account/review tables.
- `review-invite --username NAME --invitation-sha256 HASH`: provision an account;
  existing account identities are never replaced.
- `review-reset --username NAME --account-id ID --invitation-sha256 HASH`:
  prepare recovery for that exact enabled account, preserving history.
- `review-import --account-id ID --payload-base64 DATA`: validate and import
  version-1 recovered data against the verified dashboard publication.
- `review-status --account-id ID`: inspect that account's durable state.
- `review-disable --username NAME`: revoke access while retaining history.

The default feature flag remains off in code. Beast already has the additive
schema and `RUNTIME_PERSONAL_REVIEWS_ENABLED=true`; #265 reuses them and does not
repeat initial setup, migrate the owner's history or change the flag. The native
host sets `RUNTIME_REVIEW_ORIGIN` to its exact loopback origin. The existing
physical PostgreSQL backup includes the personal-review tables. For this release,
the nightly backup independently passed `pg_verifybackup` at
`2026-10-12T11:30:46.241Z`; the final frozen export also captured account,
acknowledgement and audit continuity before installation. These are observed
receipts, not an inference from backup configuration.

The original #159 cloud rollout required additive schema creation before enabling
the feature, an exact production HTTPS origin, the existing private Cloud SQL
database and verification of its backup/PITR policy. Its Terraform settings and
admin job are historical deployment context. They do not describe current backup
proof or authorize a second runtime.

Deploy through the agreed native Runtime v2 release owner and the existing
service boundary. Preserve accepted snapshots, producer history, fences and
unrelated incident ownership. Any recovery must follow the existing procedure
and retain all account/review rows. Never rewind a producer head or delete
personal data to roll back the feature. An old dashboard may show its historical
browser-local state; that is not the durable account state.

## Verification

SQLite and PostgreSQL tests exercise account isolation, session loss, password
recovery, commit rollback, idempotency, stale revisions, original timestamps,
Restore tombstones, publication absence, authentication boundaries, and concurrent
PostgreSQL writes. Generated dashboard DOM tests exercise clearing storage and
signing back in, two accounts, stale tabs, failed saves, explicit legacy imports,
activation-token handling, and more than 500 saved records.

CI checks and live acceptance are separate evidence. The original #159 rollout
required the exact deployed source/digest, database migration and owner recovery,
publication continuity, and two isolated test accounts through sign-out/browser
clearing and renewed sign-in. That original migration contract is not permission
to repeat an owner recovery during a later UI release.

For #265, CI verifies account isolation and actual browser save/reload/Restore;
native acceptance verifies the installed assets, live row layout, and one new
TEST account through durable API save, fresh sign-in and Restore. Disable that
test account afterward without deleting its audit history and compare all
pre-existing account/review/event rows before and after. The original owner's
password remains private and is not part of acceptance.
