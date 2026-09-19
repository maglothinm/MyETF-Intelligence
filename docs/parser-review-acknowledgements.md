# Personal Manual Parser Exception acknowledgements

Issue [#159](https://github.com/maglothinm/MyETF-Intelligence/issues/159) replaces
the browser-only storage in issue #155. Each person has a separate account and
saved review history in the existing private Cloud SQL PostgreSQL database.
Clearing browser data signs the person out; signing in restores their history.
Acknowledgement records that a person reviewed an exception. It does not resolve
the parser defect, delete evidence, or change another person's queue.

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

The public dashboard remains readable without an account. Personal state requires
sign-in through `/api/reviews/`. An administrator provisions an invitation using
the existing IAM-protected admin job. There is no public registration endpoint.
The owner chooses a 14–256 character password or passphrase using a private,
single-use activation link. Passwords use Werkzeug scrypt hashing; random
activation/session tokens are stored only as SHA-256 hashes. Activation links
expire after seven days and sessions after thirty days. Tokens go in the URL
fragment, which the app immediately removes, then in the activation POST body.
Never put raw tokens or passwords in repository files, issues, execution args,
logs, screenshots, or public release evidence.

The session cookie is Secure, HttpOnly, SameSite=Strict, host-only, and scoped to
`/`. Mutations require the exact configured HTTPS Origin, JSON, and a custom
same-origin request header. Responses are private/no-store. Database-backed
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

The existing admin job exposes these commands:

- `review-init-db`: create only the additive personal account/review tables.
- `review-invite --username NAME --invitation-sha256 HASH`: provision an account;
  existing account identities are never replaced.
- `review-reset --username NAME --account-id ID --invitation-sha256 HASH`:
  prepare recovery for that exact enabled account, preserving history.
- `review-import --account-id ID --payload-base64 DATA`: validate and import
  version-1 recovered data against the verified dashboard publication.
- `review-status --account-id ID`: inspect that account's durable state.
- `review-disable --username NAME`: revoke access while retaining history.

The default feature flag is off. Initialize the new schema before enabling
`RUNTIME_PERSONAL_REVIEWS_ENABLED=true` and set `RUNTIME_REVIEW_ORIGIN` to the exact
production HTTPS origin. Terraform records these as `personal_reviews_enabled`
and `personal_review_origin`. Existing private database credentials and networking
are reused; no public SQL, new IAM grant, alternate producer, or secret is needed.
The existing Cloud SQL backup/PITR policy covers these tables; backup configuration
must be verified during release, not inferred from source configuration.

Deploy through the agreed Runtime v2 release owner. Preserve accepted snapshots,
producer history, fences, and unrelated incident ownership. If a rollout fails,
disable the feature and restore the previously accepted image through the existing
release procedure while retaining all new account/review rows. Never rewind a
producer head or delete personal data to roll back this feature. An old dashboard
may show its historical browser-local state; that is not the durable account state.

## Verification

SQLite and PostgreSQL tests exercise account isolation, session loss, password
recovery, commit rollback, idempotency, stale revisions, original timestamps,
Restore tombstones, publication absence, authentication boundaries, and concurrent
PostgreSQL writes. Generated dashboard DOM tests exercise clearing storage and
signing back in, two accounts, stale tabs, failed saves, explicit legacy imports,
activation-token handling, and more than 500 saved records.

CI checks and live acceptance are separate evidence. Live acceptance must verify
the exact deployed source/digest, database migration and owner recovery, public
publication continuity, and two isolated test accounts through sign-out/browser
clearing and renewed sign-in. Disable test accounts afterward without deleting
their audit history. The owner's real password remains a user setup step.
