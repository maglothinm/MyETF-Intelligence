# OCR heartbeat publication correction — September 18, 2026

Issue #182 remains open. This corrects the concrete live acceptance failure from the reviewed PR #185 controller continuation; it does not certify a new runtime deployment.

## Observed defect

The migration, read-only image smoke, two Legislative runs, two Executive runs, AI and Dashboard all succeeded on source `9402f6c9866e919c789845de96f4334058600cee`. Final independent audit `polititrack-admin-ht9mq` failed with `published_ocr_health_disagrees`. The live Operations page showed OCR `Unknown / Invalid Evidence` and an unavailable heartbeat despite retained complete-stage processing evidence.

`build_site()` applies `public_payload()` before calculating dashboard insights. Its generic private-key filter removes any key containing `heartbeat`, including the public `runtime_mode_evidence.source_ocr.heartbeat_at` timestamp. Tests that called `build_insights()` directly bypassed that projection and missed the defect. The prior code now reproduces the exact missing `heartbeat_at` through full site generation.

## Correction and verification

The projection sends only the exact `runtime_mode_evidence.source_ocr` envelope through the existing bounded `safe_metrics()` validator. This preserves validated stage timestamps and counts, removes unknown document/configuration fields, and reduces malformed metrics to an enabled/invalid marker. Generic heartbeat/healthcheck credentials remain excluded everywhere else. No collector, account, state, schedule, notification or OCR row-interpretation behavior changes.

Five regression cases cover generated healthy/degraded OCR outcomes, retained heartbeat evidence, malformed timestamps, private document/heartbeat URL exclusion, source immutability and idempotent public projection. Local verification: **207 passed, 1 skipped** across OCR health, dashboard insights, actual dashboard generation and collector freshness. The skipped case requires the isolated PostgreSQL CI service; no local database result is claimed. Canonical CI and subsequent deployment must be recorded separately.

## Operational boundary

The controller preserved the failed acceptance and ran recovery-preservation audit `polititrack-admin-424v8` successfully before disabling OCR and restoring schedules. The first recovery's web-update wait encountered a Cloud Shell authentication error; the same saved recovery was resumed under an authorized session, without resubmitting producer jobs or deleting evidence.

See [controller takeover](2026-09-18-ocr-controller-takeover.md) and [active handoff](../HANDOFF.md) for the latest recovery state. Preserve both the original recovered journal and its successor. A corrected runtime image and a fresh reviewed release are required; never edit either closed journal to force a retry. Authenticated upload/correction/cleanup, document-specific review and post-restoration scheduled execution remain independent acceptance gates.
