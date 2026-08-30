# PolitiTrack CHG90 wallboard and private-repository operation

## Final topology

The canonical production repository is `maglothinm/PolitiTrack`. It is a private, standalone repository. The former private name `MyETF-Intelligence` is a historical alias, and the public `MyETF` fork is an archived legacy/rollback record whose Actions and Pages deployment must remain disabled.

Production data moves through one path:

1. `Legislative purchase tracker v2` and `Executive purchase tracker` restore and update their protected state artifacts.
2. `AI filing analyst and paper portfolio` restores those successful tracker artifacts plus `ai-analysis-state`.
3. `Publish government trade dashboard` restores the newest successful artifacts and deploys the generated static site.
4. GitHub Pages serves the review dashboard and wallboard.

Two actions sit outside that production path. [`Run Simulation`](.github/workflows/manual_test.yml) is a one-run Investor Edge acceptance check that publishes a short-lived dashboard artifact. [`Run $10K portfolio simulator`](.github/workflows/filing_simulation.yml) advances a separate persistent paper simulation with $10,000 starting capital and a $20,000 goal. Neither action updates a production cache, state artifact, paper portfolio, or Pages deployment.

## Display target

The dedicated wallboard is designed first for the Samsung CHG90 (`LC49HG90DMNXZA`) on the Mount-It! MI-12009 articulated wall arm beside the built-in desk.

- Native panel: 3,840 × 1,080, 32:9.
- Primary rotated canvas: 1,080 × 3,840 portrait.
- Approximate active display area after rotation: 336 mm wide × 1,196 mm tall.
- Landscape fallback: 3,840 × 1,080 when the arm is rotated back.

The portrait design treats the tall display as a persistent operations column rather than stretching a conventional desktop dashboard. Portrait and native 32:9 landscape layouts fit within one viewport.

## Production URLs

Review dashboard:

```text
https://maglothinm.github.io/PolitiTrack/
```

Wallboard:

```text
https://maglothinm.github.io/PolitiTrack/wallboard.html
```

The normal dashboard includes a **Wallboard** link. The wallboard provides:

- system state, source health, clock, data age, and refresh countdown;
- high-priority and watchlist metrics;
- AI-ranked candidates with final/base score, review band, filing link, and compact Investor Edge evidence;
- open paper positions and paper P&L;
- newest official filings;
- latest Legislative, Executive, and AI runs;
- manual-review exceptions;
- a five-minute data refresh without a full page reload;
- full-screen and screen wake-lock requests where supported;
- responsive portrait and 32:9 landscape arrangements.

The refresh interval can be changed from 60 to 1,800 seconds:

```text
https://maglothinm.github.io/PolitiTrack/wallboard.html?refresh=180
```

## Recommended display settings

- Set the operating-system resolution to the native 3,840 × 1,080 before rotation.
- Use Portrait for the primary wallboard position.
- Start at 100% browser zoom.
- Enter full-screen or kiosk mode only after the page has loaded and rendered correctly.
- Keep the normal dashboard available for filtering and source-document review.
- Verify that wake lock remains active after browser or display restarts.

## State continuity

The repository name changed without creating new production state. These compatibility identities remain authoritative:

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

Healthchecks URLs must be used by the canonical workflows only. The archived public repository must not ping the same checks.

## Deployment verification

After a code change or repository-settings change:

1. Confirm the latest Legislative and Executive runs restored their artifacts and succeeded without initialization.
2. Confirm the AI workflow restored all three production states and succeeded.
3. Run `Publish government trade dashboard`.
4. Open both production URLs and confirm current data, source links, Investor Edge, and paper positions.
5. Verify the five-minute refresh and both CHG90 orientations.
6. Confirm only the canonical repository is sending Healthchecks pings and alerts.
7. Record repository, branch, commit SHA, tests, workflow run URLs, and artifact identifiers in `docs/HANDOFF.md`.

Use `Run Simulation` for isolated Investor Edge acceptance. Use `Run $10K portfolio simulator` to advance the separate $10,000-to-$20,000 paper simulation history. Neither output is proof that production state or Pages deployment changed.

## Repository privacy is not dashboard privacy

Repository privacy and GitHub Pages visibility are separate controls. A Pages site generated from a private repository may still be publicly accessible, depending on the account and organization configuration. The wallboard exposes research rankings and paper-portfolio results, so validate the effective Pages access policy directly.

If public Pages is not acceptable, disable Pages and use private Actions artifacts or an authenticated hosting service. Do not treat a private source repository as dashboard authentication.
