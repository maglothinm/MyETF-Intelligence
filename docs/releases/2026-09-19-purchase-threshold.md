# Purchase threshold implementation and production readiness — #197

## Implementation

PR #199 implements the configurable per-purchase gain-threshold flag in the
canonical repository, ID 1349678672. The default is 8%, explicitly provisional.
A prior crossing survives a retracement, later outage, restart and a new
purchase. A negative requires complete stated coverage; uncertain execution
price/time, purchase-day ordering and extended hours are not inferred.
The feature is descriptive, not an independent buy gate or forecast.

Source preparation run 35458400175 applied a SHA-256-verified patch and removed
its temporary transport. Feature source 9286d66098b59271f7660263cafdc3acaf9db9a7
was followed by e99b9ebb08db4ec4a3f721cdd0249147abb91ac5 to include opportunity
modules in PostgreSQL-backed Runtime v2 CI. All existing workflow tests and
read-only permissions remain; no production workflow is introduced.

Local focused verification passed 165 Python tests. JavaScript syntax and
diff checks passed. Missing local Flask/Werkzeug packages prevented treating
broader local execution as a full pass. Current Opportunity matrix, Runtime
safety, Investor Edge and Source Upload/OCR CI provide canonical acceptance;
exact final-head runs and merge evidence are linked in PR #199.

## Actual provider readiness — September 19, 2026, 17:35:42 UTC

A bounded read-only Cloud Shell check used the credentials already configured
on `polititrack-ai`; keys and secret values were neither printed nor changed.
The test requested SPY only and did not create a signal or paper transaction.

- Finnhub credentials were accessible. Its quote endpoint returned a positive
  quote with timestamp 1789761600. This closed-market test does not verify
  realtime latency, feed delay, or a current-session running-high entitlement.
- Alpha Vantage credentials were accessible. The required
  `TIME_SERIES_DAILY_ADJUSTED`, `outputsize=full` request returned **zero daily
  bars and a premium-access notice**, not usable split/history coverage.
  No rate-limit notice or API error field was observed.
- No provider capability file was manufactured, no credential or subscription
  changed, and no production feature mode, image, schedule or state changed.

Current Opportunity remains **off**. Enabling live while this required source
cannot return history would produce data-limited results, not the requested
functioning feature. Its activation also needs verified security mappings,
provider capability and recipient records, and coordinated shadow/live checks.
The owner has already approved deployment; another merge/activation approval
is not the blocker. An entitled configured history source is required first.

## Release coordination

At this check, the separate Executive-only recovery journal under
`ocr-executive-recovery-77aadf541b03` reported `complete` and
`schedules_restored: true`. Its later ordinary OCR continuation is a separate
release. Do not treat this as threshold deployment or all-OCR acceptance;
refresh the canonical handoff, live resource specifications, active release
lock and newest snapshot heads before any further production operation.

Issue #197 remains open until live acceptance. Preserve all closed journals,
existing snapshots, alerts, paper positions, accounts and review history.
Deployment must use the existing owner and cannot reset or rewind state.

PR: https://github.com/maglothinm/MyETF-Intelligence/pull/199
Issue: https://github.com/maglothinm/MyETF-Intelligence/issues/197
