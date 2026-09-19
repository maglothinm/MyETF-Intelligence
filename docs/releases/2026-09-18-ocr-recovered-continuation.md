# OCR recovered-attempt continuation — issue #182

## Source change, not production acceptance

Canonical repository ID `1349678672`, `maglothinm/MyETF-Intelligence`.
The reviewed source starts from main `cb87786e6dd27f749570347054ed270523a88859`.
Runtime source/image remain `9402f6c9866e919c789845de96f4334058600cee` /
`sha256:5c9e1eee52a1e0e7b0be06f8c98f454ecb66c9320106ac183c1b327b71f6e2fc`.
No runtime application change or image rebuild is part of this controller patch.

The actual Cloud Shell controller was read through the existing authenticated
connection. Its complete bytes match installed SHA-256
`effe53abf63a7adaae8e44673a255dfe17d21fb1f8d030d279c6f36a0bfa0222`.
The actual journal still describes release `9de6a3cfc21a4ec9b51915301bdaa534`,
recovered before any submission, with empty steps and original schedules restored.
The previously reviewed journal checksum is
`cc89df4df75bf91210cb6394162ad2c8a4623e87531a875f6c87494f61adac4e`.

## Defect and bounded remedy

The old `run()` guard raises `Stop` for a closed attempt, but `main()` catches that
exception, writes the journal, and invokes `recover()`. Construction also writes
the journal before that guard. Therefore a rejected retry was not a read-only
rejection and could reach production recovery operations.

`scripts/ocr_release_controller.py` now carries the inspected controller in the
canonical repository. Closed-attempt rejection occurs before construction,
audit-helper loading, journal writes and cloud operations. Saved status is
explicitly identified as historical evidence, not a live observation.

The read-only `--review-recovered` mode checks this narrow recovery condition and
hashes every retained receipt. A successor requires the exact reviewed journal
SHA-256 via `--continue-recovered`; it is stored at
`<workspace>/ocr-continuations/<predecessor-release-id>/journal.json`. The original
`ocr-deployment` directory is never moved, overwritten or selected for new writes.

The successor:

- Accepts only verified restoration to the original configuration after an
  inventory failure before any submission; uncertain submissions, prior migration,
  a frozen baseline, changed restoration evidence or recovery errors are rejected.
- Retains a manifest of the predecessor journal and all receipt bytes, verifies
  them on every successor journal write, and rejects symlink paths.
- Uses the existing workspace lock and one deterministic successor location.
  Repeated calls retain that successor's identity and execution receipts. A closed
  successor and missing journal with retained receipts cannot start a new attempt.
- Starts at `preparing` and keeps fresh preflight, inventory, pause/drain and frozen
  baseline gates. It does not copy the old attempt's ready flags, roles, paused
  list, baseline or failed-wait state into the successor.
- Keeps all existing deployment scopes, source/image pins, receipt reconciliation,
  preservation audits, failure recovery and acceptance checks.

## Verification

42 offline tests pass in `tests/test_ocr_release_controller.py`. Tests prohibit
cloud subprocesses and HTTP calls and exercise retained bytes, drift detection,
closed CLI paths, ambiguous submissions, lock contention, orphan receipts,
symlink rejection, deterministic resumption and fresh baseline ordering.
Python compilation passes. AST comparison with the exact installed predecessor
shows only `Release.__init__`, `Release.persist` and `main` changed among existing
functions; all 38 other functions, including deployment operations, are unchanged.
New helper functions validate and locate the continuation.

Controller SHA-256:
`bde6921a252f956a5405cff0dc12d2eb8cbd01f1ec61304f08281bed947c568a`.
`.github/workflows/ocr_release_controller_tests.yml` adds a credential-free,
read-only-permission CI gate. Local checks are not a claim of completed CI.

## Remaining execution boundary

The original remote `write_file` rejection was: "This tool call was blocked by
OpenAI because we couldn't determine the safety status of the request."
That is evidence of the rejected helper-preparation action, not proof of a
permanent account lock. Reconnection and successful read-only actions do not
approve that request. This source review does not override a safety decision or
authorize alternate execution of the rejected helper.

The owner has already authorized the feature and bounded maintenance. Do not ask
for another general authorization, change security settings, delete or edit the
recovered journal, or repeat the completed 3,357-record diagnostic. A permitted
deployment remains subject to the normal tool review and fresh operational gates.
If a concrete action is rejected, retain its exact action and reason and stop
that action; do not reroute it through another tool.

Pending live work: controller installation/continuation, frozen baseline,
additive migration, pinned-image activation, authenticated owner upload/correction
and cleanup, bounded backfill, independent OCR health and a subsequent natural
scheduled execution. Source tests alone do not close issue #182.
