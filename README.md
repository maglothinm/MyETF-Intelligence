# MyETF government trade tracker — fast-track overlay

This bundle installs a narrow, operational monitoring layer into the public `maglothinm/MyETF` repository. It does **not** attempt to revive the older PostgreSQL/dbt/React dashboard before data collection works.

The overlay:

- polls official House and Senate Periodic Transaction Report sources;
- discovers OGE Form 278-T listings for covered Executive-branch officials;
- records newly disclosed **purchases** in durable JSONL ledgers and CSV snapshots;
- sends Pushover alerts for equity-like purchases and for filings that require manual review or a Form 201 request;
- retains state across GitHub Actions runs using both cache and durable artifacts;
- fails visibly on missing state, source-schema changes, empty sources, parser failures, or required-notification failures;
- includes 23 offline tests plus an installer and end-to-end smoke verification.

## Package contents

- `repo-files/` — files copied into the MyETF repository.
- `apply.sh` — idempotent installer.
- `verify.sh` — offline verification and clean-repository smoke test.
- `VERIFICATION.txt` — generated verification record.

## Install

```bash
unzip MyETF-government-trade-tracker-fast-track.zip
cd MyETF-government-trade-tracker-fast-track
./verify.sh
./apply.sh /path/to/MyETF
cd /path/to/MyETF
git diff --check
git status --short
```

Then follow `README_GOVERNMENT_TRADES.md` in the repository. GitHub authentication is required only to commit and push the installed files.

## Scope boundary

“Fast” means rapid detection **after an official disclosure becomes public**. It does not eliminate the statutory filing delay: covered transactions may be disclosed weeks after the trade.

Executive-branch coverage is necessarily partial. OGE centrally reviews only a subset of public filers; many reports are held by employing agencies, and some OGE listings require a Form 201 request. The overlay records those request-required listings instead of claiming that it downloaded unavailable records.

## Legal-use boundary

House, Senate, and OGE disclosure systems display statutory use restrictions. The workflows will not run until the repository variable `DISCLOSURE_TERMS_ACKNOWLEDGED` is explicitly set to `true`. Review those restrictions and the intended use before activation, especially before any commercial, automated-investment, or redistribution use.

<!-- MYETF-GOVERNMENT-TRADE-TRACKER:START -->

## Government financial-disclosure collectors

The fail-closed House, Senate, and OGE collectors, durable state, official-filing links, failure semantics, and disclosure-use restrictions are documented in [`README_GOVERNMENT_TRADES.md`](README_GOVERNMENT_TRADES.md).

<!-- MYETF-GOVERNMENT-TRADE-TRACKER:END -->

<!-- MYETF-REPORTING-DASHBOARD:START -->

## Searchable filing-review dashboard

The repository publishes a filing inventory, complete parsed transaction ledger, manual-review queue, tracker health, AI analyses, and paper portfolio. GitHub Actions calculates the Pages URL from the current repository; see [`README_REPORTING_DASHBOARD.md`](README_REPORTING_DASHBOARD.md).

<!-- MYETF-REPORTING-DASHBOARD:END -->

<!-- MYETF-AI-FILING-ANALYST:START -->

## AI filing analyst and paper portfolio

New parsed equity purchases can be enriched with market and SEC evidence, analyzed through a strict OpenAI JSON schema, deterministically scored, and evaluated in a paper-only portfolio. The implementation has no brokerage or order-submission path. See [`README_AI_FILING_ANALYST.md`](README_AI_FILING_ANALYST.md).

<!-- MYETF-AI-FILING-ANALYST:END -->

<!-- MYETF-CHG90-WALLBOARD:START -->

## CHG90 portrait and super-ultrawide wallboard

The dashboard includes `wallboard.html`, optimized for the Samsung CHG90 at 1,080 × 3,840 portrait and 3,840 × 1,080 landscape. The private standalone-repository migration preserves current state artifacts and retains the old fork as a rollback remote. See [`README_WALLBOARD_PRIVATE_REPO.md`](README_WALLBOARD_PRIVATE_REPO.md).

<!-- MYETF-CHG90-WALLBOARD:END -->
