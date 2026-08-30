# PolitiTrack CHG90 wallboard and private-repository operation

## Approved topology and current cutover state

The canonical production identity is repository ID `1349678672`, currently named
`maglothinm/MyETF-Intelligence`. GitHub currently reports it public; the approved
settings cutover is to make the intended privacy correction and rename that same
repository in place to `maglothinm/PolitiTrack`. Public `MyETF` is a code-frozen
legacy/rollback record, but its Actions/Pages settings and archive flag still need
authenticated verification.

Production data moves through one path:

1. `Legislative purchase tracker v2` and `Executive purchase tracker` restore and update their protected state artifacts.
2. `AI filing analyst and paper portfolio` restores those successful tracker artifacts plus `ai-analysis-state`.
3. `Publish government trade dashboard` restores the newest successful artifacts and deploys the generated static site.
4. GitHub Pages serves the review dashboard and wallboard.

Two actions sit outside that production path. [`Run Simulation`](.github/workflows/manual_test.yml) is a one-run Investor Edge acceptance check that publishes a short-lived dashboard artifact. [`Run $10K portfolio simulator`](.github/workflows/filing_simulation.yml) appends an isolated historical replay result with $10,000 starting capital and a $20,000 goal to `simulation-state`. Retaining independent replay results is not a persistent portfolio ledger. Neither action updates a production state artifact, paper portfolio, or Pages deployment.

## Display target

The dedicated wallboard is designed first for the Samsung CHG90 (`LC49HG90DMNXZA`) on the Mount-It! MI-12009 articulated wall arm beside the built-in desk.

- Native panel: 3,840 × 1,080, 32:9.
- Primary rotated canvas: 1,080 × 3,840 portrait.
- Approximate active display area after rotation: 336 mm wide × 1,196 mm tall.
- Landscape fallback: 3,840 × 1,080 when the arm is rotated back.

The portrait design treats the tall display as a passive operations column rather
than stretching a conventional desktop dashboard. CSS targets a single viewport
at portrait and native 32:9 dimensions. Physical CHG90 acceptance remains
unverified; an emulated viewport is not proof of hardware/browser behavior.

## Production URLs

Review dashboard:

```text
https://maglothinm.github.io/MyETF-Intelligence/
```

Wallboard:

```text
https://maglothinm.github.io/MyETF-Intelligence/wallboard.html
```

The normal dashboard includes a **Wallboard** link. The wallboard provides:

- a deterministic Situation Brief, retained branch health, clock, data age, and refresh countdown;
- qualifying High Priority/Watchlist totals and the top qualifying signals only;
- compact signal cards with filing/evidence links, delayed-price timestamps, and Investor Edge confidence/history context;
- the open paper-position count, with individual valuations available on the full dashboard;
- the latest **SIMULATED — SINGLE-RUN REPLAY** value and actual change, without an equity curve or persistent-performance claim;
- newest official filings;
- latest Legislative, Executive, and AI runs;
- manual-review exceptions;
- access/request-required inventory shown separately as informational;
- browser-local sound armed/muted state, with sound off by default;
- a five-minute data refresh without a full page reload;
- full-screen and screen wake-lock requests where supported;
- responsive portrait and 32:9 landscape arrangements.

The refresh interval can be changed from 60 to 1,800 seconds:

```text
https://maglothinm.github.io/MyETF-Intelligence/wallboard.html?refresh=180
```

The wallboard reads the same compact `data/dashboard-insights.json` as Overview.
It does not fetch the complete filing/review ledgers or call any external alert
provider. Missing run evidence is **Unknown**; an old timestamp alone does not
establish an overdue incident when expected cadence is unavailable. Refresh
failure keeps existing content visible and marks it potentially stale.

The source assets are `scripts/dashboard_assets/wallboard.html`,
`wallboard.css`, and `wallboard.js`, with shared display and notification code
assembled by `scripts/build_trade_dashboard.py`. Edit these generator-owned
sources, never the deployed output. Root, Wallboard, and Investor Edge URLs are
preserved. Actions links remain secondary and only open GitHub Actions.

## Sound, touch, and browser-local history

The wallboard and main dashboard share bounded browser-local notification state
on the same origin. First load establishes a silent baseline; unchanged refresh,
reload, or visibility changes do not replay prior events. Configure category
mute, quiet hours, volume, and sound mode in the main Notification Center. Arming
audio requires a user gesture in the current page; reopening a page does not
automatically arm sound. The wallboard control reports its current state.

Sound requires an open, active page and browser support. It is never the only
failure indicator, and ordinary filings remain silent. Local sound and
acknowledgement do not change Gmail, Pushover, or Healthchecks. The browser never
pings a Healthchecks URL. Fullscreen and wake lock also depend on browser support
and permissions; essential monitoring information does not require hover.

**Methodology & Risk** keeps the full disclosure accessible without a dominant
banner. SIMULATED, PAPER TRADING, delayed/cached-price, and insufficient-history
labels remain at their point of use. Tooltips support keyboard and tap dismissal.

## Recommended display settings

- Set the operating-system resolution to the native 3,840 × 1,080 before rotation.
- Use Portrait for the primary wallboard position.
- Start at 100% browser zoom.
- Enter full-screen or kiosk mode only after the page has loaded and rendered correctly.
- Keep the normal dashboard available for filtering and source-document review.
- Verify that wake lock remains active after browser or display restarts.

## State continuity

The presentation redesign does not rename the repository or create new production
state. These compatibility identities remain authoritative:

```text
legislative-tracker-state
executive-tracker-state
ai-analysis-state
.trade-tracker/
```

The collector workflows hard-code state initialization and historical-alert bootstrapping off and do not expose either control for manual runs. If a restore step cannot find the expected artifact, the run fails closed. Recovery requires a separately approved procedure that identifies and verifies the known-good state; do not create a replacement baseline.

Only successful collectors and the successful AI analyst may publish their corresponding production state. The dashboard reads state but does not write it. Simulations may write only simulation-named artifacts.

## Secrets and variables

Applicable production secrets include:

```text
PUSHOVER_API_TOKEN
PUSHOVER_USER_KEY
LEGISLATIVE_HEALTHCHECKS_PING_URL
EXECUTIVE_HEALTHCHECKS_PING_URL
OPENAI_API_KEY
FINNHUB_API_KEY
ALPHAVANTAGE_API_KEY
AI_HEALTHCHECKS_PING_URL
GMAIL_ADDRESS
GMAIL_APP_PASSWORD
```

Confirm the applicable Actions variables:

```text
DISCLOSURE_TERMS_ACKNOWLEDGED=true
AI_ANALYSIS_ENABLED=true
OPENAI_MODEL=gpt-5.6-terra
OPENAI_REASONING_EFFORT=medium
AI_WEB_SEARCH_ENABLED=true
AI_FETCH_DOCUMENT_TEXT=true
AI_MAX_ANALYSES_PER_RUN=20
AI_REQUIRE_PUSHOVER=false
INVESTOR_EDGE_ENABLED=true
SEC_USER_AGENT=PolitiTrack research contact <monitored-email-address>
```

The workflows calculate the repository Pages URL automatically. Create `DASHBOARD_URL` only for a deliberate custom or authenticated address. Gmail delivery is optional and requires both `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`; it remains independent of Pushover and collector alerts.

Healthchecks URLs must be used by the canonical workflows only. The legacy public
repository must not ping the same checks.

## Deployment verification

After a code change or repository-settings change:

1. Verify the latest eligible Legislative and Executive producer attempts and artifacts without initialization.
2. Verify the eligible AI artifact and retained run evidence. Read existing runs; do not dispatch analysis to populate the UI.
3. Preserve the previous Pages artifact, then use `Publish government trade dashboard` for deployment.
4. Open the root, Wallboard, and Investor Edge URLs; confirm the tested build SHA, counts, links, and unchanged protected-state evidence.
5. Verify the five-minute refresh and both CHG90 orientations.
6. Confirm only the canonical repository is sending Healthchecks pings and alerts.
7. Record repository, branch, commit SHA, tests, workflow run URLs, and artifact identifiers in `docs/HANDOFF.md`.

Use `Run Simulation` only when an isolated Investor Edge acceptance run is
separately intended. The $10K simulator adds an independent historical replay;
neither action is required to release the UI or proves a production deployment.

The responsive acceptance matrix includes 1440 × 900, 1280 × 720, 768 × 1024,
430 × 932, 390 × 844, 1080 × 1920, 1080 × 3840, and 3840 × 1080. Check for page
overflow, clipping, obscured focus, touch targets, refresh preservation, and sound
deduplication. Actual Chrome desktop, current iPhone Safari, and physical CHG90
validation have **not yet been completed** for this redesign; record those
results explicitly before claiming device acceptance.

## Repository privacy is not dashboard privacy

Repository privacy and GitHub Pages visibility are separate controls. The verified
pre-rename Pages site is currently public. A Pages site generated from a private
repository may also remain publicly accessible, depending on the account and
organization configuration. The wallboard exposes research rankings and
paper-portfolio results, so validate the effective Pages access policy directly.

If public Pages is not acceptable, disable Pages and use private Actions artifacts or an authenticated hosting service. Do not treat a private source repository as dashboard authentication.
