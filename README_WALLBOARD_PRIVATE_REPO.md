# PolitiTrack CHG90 wallboard and standalone private repository

## Display target

The dedicated wallboard is designed first for the Samsung CHG90 (`LC49HG90DMNXZA`) on the Mount-It! MI-12009 articulated wall arm beside the built-in desk.

- Native panel: 3,840 × 1,080, 32:9.
- Primary rotated canvas: 1,080 × 3,840 portrait.
- Approximate active display area after rotation: 336 mm wide × 1,196 mm tall.
- Landscape fallback: 3,840 × 1,080 when the arm is rotated back.

The portrait design uses the tall display as a persistent operations column rather than stretching a conventional desktop dashboard. It fits the full wallboard into one viewport with no page scrolling or horizontal overflow at 1,080 × 3,840. The native 32:9 fallback also fits into one viewport.

## Wallboard URL and behavior

After dashboard deployment, open:

```text
https://<github-user>.github.io/<repository>/wallboard.html
```

For the current legacy-named private repository `MyETF-Intelligence`, the default public Pages address is:

```text
https://maglothinm.github.io/MyETF-Intelligence/wallboard.html
```

The normal review dashboard has a **Wallboard** button. The wallboard provides:

- system state, source health, clock, data age, and refresh countdown at the top;
- large high-priority/watchlist metrics;
- the largest screen allocation for AI-ranked candidates;
- current price, calculated review band, transaction age, final/base score, owner, filer, and official-filing link;
- a compact Investor Edge line with modifier, confidence, observation count, relevant followable alpha, followable hit rate, sector alpha, and disclosure lag; unavailable observations use an em dash;
- open paper positions and paper P&L;
- newest official filings;
- latest Legislative, Executive, and AI runs;
- manual-review exceptions;
- a five-minute data refresh without reloading the page;
- full-screen control and screen wake-lock requests where supported;
- automatic portrait and 32:9 landscape arrangements.

The refresh interval can be changed, bounded from 60 to 1,800 seconds:

```text
wallboard.html?refresh=180
```

### Recommended display settings

- Operating-system resolution: native 3,840 × 1,080 before rotation.
- Orientation: Portrait for the primary wallboard position.
- Browser zoom: 100% initially.
- Full-screen or kiosk mode: enabled after the page loads.
- Keep the normal dashboard available for detailed filtering and document review; use the wallboard for persistent situational awareness.

## Why create a new repository rather than detach the fork in place

The recommended migration creates a new private, standalone repository and temporarily retains the existing public fork as a rollback source. The new repository keeps the complete Git commit history, branches, and tags, but GitHub reports `isFork=false`.

This is preferable to immediately using GitHub's irreversible **Leave fork network** operation because it provides a controlled cutover and preserves the working public system until the private replacement is validated.

## Private-repository migration

Apply, commit, and push this wallboard overlay in the current repository first. From a clean Codespaces working tree, run:

```bash
bash scripts/create_private_standalone_repo.sh MyETF-Intelligence
```

An alternate repository name can be supplied as the first argument.

The migration script:

1. records the source repository, remotes, secret names, and Actions variables under a private directory in the Codespace home folder;
2. downloads the newest unexpired Legislative, Executive, and AI state artifacts from the current repository;
3. creates a new private standalone repository;
4. pushes all branches and tags;
5. changes the current checkout's `origin` to the new private repository;
6. retains the old fork as the `public-fork` Git remote;
7. copies repository-level Actions variables where GitHub CLI exposes them;
8. disables the production workflows in the new repository until configuration is complete;
9. uploads exported state to a private one-time GitHub release;
10. dispatches **Import migrated MyETF state** in the new repository;
11. verifies that the new repository is private and is not a fork.

### State preservation

The import workflow reconstructs these durable artifacts in the new repository:

```text
legislative-tracker-state
executive-tracker-state
ai-analysis-state
```

That preserves the filing catalog, parsed transaction ledgers, manual-review queue, run history, AI analyses, and paper-portfolio state that exist in the latest artifacts.

If all three imported artifacts are green, do **not** create another silent baseline. Run Legislative and Executive manually with both input boxes unchecked so they restore the migrated state and create new repository-local caches.

If no source artifact was available, the migration script says so; in that case only, initialize Legislative and Executive once with silent-baseline checked and historical alerts unchecked.

## Secrets and variables after migration

GitHub does not reveal stored secret values after creation, so they cannot be copied by the script. Recreate the applicable secrets in the new repository:

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

Do not enable both old and new production workflows while they share the same Healthchecks URLs; otherwise one logical check receives pings from two repositories.

The script attempts to copy repository-level Actions variables. Confirm these in **Settings → Secrets and variables → Actions → Variables**:

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

The tracker workflows now calculate the GitHub Pages URL from the current repository automatically. Create a `DASHBOARD_URL` variable only when using a custom or authenticated dashboard address. `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are optional and should be recreated only when Gmail candidate alerts are wanted; Pushover and collector-alert behavior remain independent.

## Cutover sequence

1. Confirm **Import migrated MyETF state** is green in the private repository.
2. Recreate and verify all required secrets.
3. Confirm the copied Actions variables.
4. Disable the Legislative, Executive, AI, and dashboard workflows in the old public fork.
5. Enable those four workflows in the private repository.
6. Run Legislative and Executive manually with both boxes unchecked when migrated state exists.
7. Run the AI workflow with alerts suppressed for its private-repository acceptance run.
8. Run **Publish government trade dashboard**.
9. Confirm both Healthchecks checks and the optional AI check are receiving pings only from the private repository.
10. Leave the public fork intact but disabled for several successful scheduled cycles before archiving or deleting it.

The original Codespace remains associated with the public repository even after its Git remote changes. Once the private replacement is stable, create a new Codespace from the private repository.

## Repository privacy is not dashboard privacy

A private repository and a private GitHub Pages site are separate matters.

- GitHub Pages availability from a private personal repository depends on the GitHub plan.
- A Pages site published from a private repository is generally public unless organization-level Enterprise Cloud access control is used.
- The wallboard can expose AI rankings and paper-portfolio results, so repository privacy alone must not be treated as dashboard access control.

Practical choices are:

1. Keep the source repository private and knowingly publish the wallboard publicly through Pages.
2. Disable Pages and use private Actions artifacts only.
3. Deploy the static dashboard to an authenticated hosting service.
4. Add a private local wallboard service on the computer driving the monitor.

Select the dashboard access model deliberately before putting sensitive research or portfolio information on the display.

## Private migration release

The state migration release is private because the repository is private. Keep it until the new trackers, AI analyst, dashboard, and caches have all run successfully. It can then be deleted from the private repository's **Releases** page if a second durable backup is not wanted.
