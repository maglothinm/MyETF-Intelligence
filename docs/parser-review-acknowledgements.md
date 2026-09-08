# Manual Parser Exception acknowledgement contract

Issue: [#155](https://github.com/maglothinm/MyETF-Intelligence/issues/155).

Acknowledgement means the user reviewed a known parser exception and does not
want it counted as requiring attention unless its logical identity changes.
It is browser-local presentation state, not parser resolution or evidence deletion.

## Identity and retained evidence

`scripts/review_identity.py` defines `logical_review_id` from source, a tagged
filing identity, and `exception_code`. Filing identity prefers `report_id`, then
`filing_key`, `source_record_id`, and finally `source_url`. The versioned SHA-256
input excludes reason, filer, dates, and other display metadata. A source/report
identity is preferred to a URL so URL formatting changes do not change an identity.
New parser families must supply a distinct code; a materially different defect in
the same filing must not reuse the old code. Current producer codes are:

- `paper_filing_manual_review`: House scanned forms and Senate image viewers.
- `unparseable_transaction_table`: document text lacks reliable transaction rows.
- `disclosure_access_required`: OGE request-only access, a separate inventory.

`missing_required_transaction_fields` and `unsupported_disclosure_format` are
also recognized parser codes for explicitly classified future producers.

New reviews use the logical ID as their evidence ID. Existing `review_id` values
and pending-review JSONL bytes remain intact. Reprocessing compares logical
identities against retained reviews before sending a new-review notification or
appending evidence. It preserves the original evidence ID even after its entry
has aged out of the bounded `seen_reviews` index.

Publication adds logical identities and codes to retained review projections,
JSON and CSV. Known pre-code producer messages map to their explicit code, including
the two Senate image-viewer records observed in production on 2026-09-08. Unknown
legacy messages keep their individual evidence ID as their matching key; publication
does not guess that unrelated exceptions are the same. This compatibility classifier
is only for old records. Producers carry codes independently of diagnostic wording.

## Browser lifecycle and compatibility

The existing key `polititrack.manual-review-acknowledgements.v1` and version 1
record shape remain readable. Each acknowledgement retains its original `id` and
timestamp and may add `logical_review_id`. A successful publication's complete
`manual_exception_identities` map lets the browser learn logical identities for
old ID-only acknowledgements, including records outside the eight-row overview.
Both legacy IDs and learned logical identities participate in matching. An old
acknowledgement with a known different logical identity never suppresses a reused
evidence ID. Old publications without identity maps still match original IDs.

Current-publication absence never removes acknowledgements, including zero-row
publications, reloads, and cross-tab storage events. The deliberate retention policy
keeps the 500 most recently acknowledged records; saving beyond that bound evicts
the oldest. There is no absence-based or time-based expiry.

**Restore to active review** removes the selected acknowledgement and every
stored alias for its logical identity. Later publication or refresh cannot revive
that acknowledgement through another learned alias. The retained evidence remains
available, and the acknowledged inventory remains reversible.

Browser storage can still be cleared externally by the user/browser, and browsers
that deny storage retain acknowledgements only for the page session. The fix cannot
recover acknowledgement history already erased by an older deployed build.

## Publication integrity and verification

Published counts and `manual_exception_ids` continue to describe retained production
rows and must match `pending-reviews.json`/CSV. Acknowledgements only affect local
active attention. `validateReviews()` preserves its count/category/ID checks and
additionally verifies the new logical identity map against loaded rows. Failed or
older refreshes do not teach acknowledgements from a rejected publication.

The regression suite covers acknowledgement/storage, zero/partial/returning
publications, repeated 2 -> 0 -> 1 -> 2 transitions, legacy-only browser migration,
wording and evidence-ID changes, materially different identities, restore of all
aliases, bounded retention, and JSON/CSV/model consistency. Ingestion tests check
stable codes and deduplication without rewriting retained evidence.

Local tests and PR checks do not certify live ingestion/publication. Deployment
through the existing Runtime v2 release procedure and browser acceptance against
that deployed build are separate release steps.
