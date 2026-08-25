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
