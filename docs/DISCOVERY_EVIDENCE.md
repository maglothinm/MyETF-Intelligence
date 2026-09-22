# Information value at discovery

`information_value_at_discovery` is factual evidence about a disclosed security
transaction, not a score for a person, issuer, or investment recommendation.
It does not participate in existing opportunity qualification or notifications.

The evidence object stores transaction date, the first retained observation,
transaction-date closing reference, first usable discovery quote and provenance,
calendar-day observation lag, quote lag, percentage movement, and movement in
transaction-reference ATR units when that ATR exists. Positive and negative
movement are reported with their signs for both purchases and sales. A reference
close is not an execution price; observation lag does not establish filing
compliance or an agency's submission/receipt date.

The deterministic status is `measured` only with supported prices, dates, quote
provenance/quality and compatible security, currency and corporate-action basis.
Otherwise it is `unknown` with explicit reasons and null unsupported movements.
Absent ATR leaves only the ATR result unknown. Quote capture is per transaction;
adding another trade in an already-observed security cannot borrow a quote from
before that trade was first observed. Later quotes do not overwrite the first
usable quote. Retained Current Opportunity discovery anchors remain usable when
their documented quality gate and the transaction's observation time agree.

Legacy AI markets retain useful prices, provider lists and timestamps but do not
necessarily prove feed quality, an exact reference session or compatible split
basis. Their original values are published under `retained_market_evidence`.
They are never relabeled as a verified first usable quote or used to manufacture
a complete historical comparison. This limitation is observable as `unknown`.

The existing AI producer appends `information-value-at-discovery.jsonl`, with
per-object integrity digests, inside its restored namespace. Snapshot validation
checks this ledger. No provider request, separate writer, schedule, rebaseline,
old analysis rewrite or LLM answer is required to produce the evidence report.
The AI data model attaches it by trade ID; Current Opportunity stores the object
per trade in its immutable evaluation. The dashboard publishes the existing AI
JSON/CSV plus dedicated `information-value-at-discovery.json` and `.csv` exports.
The AI table and Current Opportunity details expose the evidence and reasons.

# Independent manual source uploads

The scheduled Executive entry point acquires its existing namespace advisory
lock, restores and validates the latest snapshot, then runs queued manual uploads
for already-known filing identities before attempting fresh OGE collection.
`executive_manual_ocr` is a maintenance receipt inside that same lease, not a new
scheduled producer. It commits through the existing validated atomic snapshot
path and acknowledges private inbox items only after that commit. The collector
then consumes this committed successor as its parent.

An OGE failure therefore remains a failed collection while a preceding manual
extraction remains committed and reviewable. Collector history explicitly excludes
maintenance receipts. Operations reports manual-upload OCR separately. Original
collection success timestamps, first observations, automatic downloads, page
limits/backoff, source identity, extraction caches and review-before-import stay
intact. A pass journal makes post-commit acknowledgement replay produce a unique
maintenance snapshot without repeating an import. Unknown identities and work
still in backoff remain queued. Raw uploads never enter public exports or Git.
