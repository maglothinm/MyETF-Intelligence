# Approved icon integration — 2026-08-31

Repository **1349678672**, `maglothinm/MyETF-Intelligence`, default `main`.
Work record: [issue #4](https://github.com/maglothinm/MyETF-Intelligence/issues/4).
Source commit: `aa8201a7b3b95c575adf069f39688e1ac811f0c6`, branch
`codex/polititrack-icon-assets`, based on `ecc031dad297f6878e086dbe0b62861cbb4a6441`.
Review: [PR #18](https://github.com/maglothinm/MyETF-Intelligence/pull/18).

## Scope and source integrity

All 22 images supplied in `PolitiTrack_Icon_Assets.zip` are preserved unchanged
in `assets/branding/polititrack/`. The ZIP SHA-256 is
`0fbc21472cce75ee3d1f47040683dfe8e4a1b1044cd892f12e75c599b40cf65a`.
Its per-file source manifest, original 1254x1254 PNG and Windows ICO are committed.
The ICO contains 16, 24, 32, 48, 64, 128 and 256px frames; browser ICO frames are
16, 32 and 48px. No Windows packaging configuration exists to update.

Both Python dashboard entry points stage 11 byte-identical web images plus the
manifest. All 30 favicon/touch/manifest links resolve in the full and independently
generated standalone output, including repository-subpath URL resolution.
The retained React frontend uses the same approved images, preserves its 50px
header and manifest display/theme settings, and corrects the obsolete install name.
No workflow, protected state, collector, score, alert, simulation, credential,
schedule, Vault runtime or hosting setting changes.

## Local verification

- **524 Python tests passed**, no failures/skips, in **258.80 seconds**. Includes
  existing nested dashboard/DOM checks. Declared dependencies and test output were
  isolated outside the checkout. Windows ACL access required a reviewed escalated
  test run; no ACL or source/test guard was changed.
- **1 retained React App test passed** with an explicit relative test glob to
  accommodate this Windows checkout path. Dependency lockfile is unchanged.
- React **production build passed** with the `/MyETF-Intelligence/` hosted prefix.
  All 11 emitted icon files match their approved source bytes; emitted HTML,
  manifest, header paths, decorative alt text and 50px dimensions passed checks.
  Existing warnings are in unchanged `Politician.jsx`, `StockChart.jsx`,
  `StocksTable.jsx`, `Title.jsx` and legacy dependencies/bundle sizing.
- Source ZIP/file hashes, PNG dimensions, ICO frames, generated-copy hashes and
  all icon links passed. Both full-site and standalone generation succeeded.
- Diff checks and independent icon/copy-path review passed. The existing large
  portrait Wallboard image-size hint was included after review.
- Browser warning/error logs were empty. This is rendered preview acceptance,
  not physical-device, native touch/keyboard or Windows installation acceptance.

The new image loads and these rectangles exactly match pre-change templates:

| Surface / viewport | Icon size | Header height | Horizontal overflow |
| --- | --- | --- | --- |
| Root, 1440x900 | 35x35 | 86.5px | None |
| Root, 390x900 | 32x32 | 137.45px | None |
| Root, 320x900 | 32x32 | 187.45px | None |
| Filing Vault, 1440x900 | 35x35 | 84px | None |
| Filing Vault, 390x844 | 32x32 | 84px | None |
| Wallboard, 1440x900 | 35x35 | 47.5px | None |
| Wallboard, 1440x2560 | 54x54 | 86.25px | None |

Root brand/sidebar rectangles also match exactly. Standalone Investor Edge keeps
its text-only heading and receives only favicon/manifest metadata.

## Pre-release continuity evidence

The read-only preflight examined 180 runs and 198 global artifacts. Exact
successful attempts/jobs, upload windows, expiry, ancestry and producer high-water
marks passed. Pages run `33409174140` / 1 consumed these exact protected inputs:

| Input | Artifact | Run / attempt | Job | ZIP SHA-256 |
| --- | --- | --- | --- | --- |
| Legislative | 9764350004 | 33408974583 / 1 | 99543508327 | `666303ed7c1dc88d2404a9048b45a75276f927ef0c595713e981d393bc8cc228` |
| Executive | 9760298853 | 33398375467 / 1 | 99508337018 | `e4c95a6829fef8c431bb7f574d6cda9af585f887157d6b2bd8dcefeccb18a4e0` |
| AI | 9764387095 | 33409079174 / 1 | 99543844689 | `4ce53ab46300fd53999c8c23539197a2bb916fed1f6c1101adb34c7c6713cc86` |
| Simulator | 9734790733 | 33320677882 / 1 | 99281977011 | `1daa01b253894ea07007bdfbf59bdcf5cb2afe568e9d6feff1774488b294dc59` |

Five ZIP exports passed independent SHA-256 and CRC checks at **16:53:43 UTC**.
Every member was hashed: 7 Legislative, 4 Executive, 45 AI and 2 simulator files;
simulator history retains 2 rows. Rollback Pages artifact `9764416987` contains
239 nested files; ZIP digest
`3e9c1245ddae60854c2158275fcb7629b9b77763ffd881946ae9d7c29fd1e226`.
Evidence ZIPs/member inventories remain outside Git in the task workspace's
`icon-release-evidence/`, never as production restore inputs. Rollback means a
reviewed source revert through Pages using current valid state, not old state.

## Release status

PR #18 merged source `aa8201a7b3b95c575adf069f39688e1ac811f0c6` as
`6bd76843e604941efef757aab434699feb1944f1`; both trees are
`c2300379c6347fdf2b652f86c7a25d2886f554f7`.
Exact-head PR CI `33416929114` / 1, job `99569712096`, passed **441 Python tests**,
**6 DOM cases** and Linux **VERIFICATION PASSED** at 16:58:15 UTC.
Main [CI `33417300859`](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33417300859)
/ 1, job `99570923703`, passed on exact merge `6bd76843`: **441 Python tests**
in 20.70 seconds, **6 DOM cases**, and Linux **VERIFICATION PASSED**.
Automatic [Pages `33417300834`](https://github.com/maglothinm/MyETF-Intelligence/actions/runs/33417300834)
/ 1 succeeded on that same merge, build job `99570924086`, deploy job
`99571098216`, completed **17:02:40 UTC**. The existing push trigger was used;
no manual writer or simulation was dispatched.

The sole uploaded artifact is `github-pages` **9767514649**, **4,400,016 bytes**,
SHA-256 `73b3cf8fee7b1a82ba96d3e3e797c60eea288a958e8721d71a088b5b77d80ded`.
Its upload window is 17:02:03–17:02:04 UTC; expiry is 2026-09-01 17:02:03 UTC.
Publisher logs consumed the exact four input artifact/run/attempt IDs in the
pre-release table. A fresh 183-run readback at **17:10:00 UTC** found no later
producer runs or later reruns;
the selected artifacts remain from their same successful first attempts.

The [live site](https://maglothinm.github.io/MyETF-Intelligence/) passed
**251/251 byte comparisons** at **17:06:47 UTC**: 250 served content files plus
the root URL,
all matching the verified Pages archive. The `.nojekyll` control file is
retained separately in the 251-file archive inventory. Exactly 12 files were
added (11 icons plus the manifest), none removed; 229 prior files are unchanged.
The 12 source assets match the tested and merged tree exactly. Other output
changes are the expected icon HTML/CSS (including shared Investor Edge CSS) and
three generated JSON files with only build SHA, timestamps and computed ages.

The final **17:12:12 UTC** continuity audit freshly re-exported and downloaded all
four protected/simulator ZIPs. Each ZIP digest matches preflight and current
GitHub metadata, and every member hash matches preflight: 7 Legislative,
4 Executive, 45 AI and
2 simulator files; simulator history remains 2 rows. Authoritative producer jobs,
exact successful first attempts, ancestry and high-water marks passed. Neither
CI run uploaded artifacts; the Pages run uploaded only `github-pages`.
Machine-readable evidence: `postflight-pages-byte-audit.json`,
`postflight-provenance-audit.json` and `postflight-continuity-audit.json` in the
external evidence directory. No protected record or state inventory changed.

Live desktop 1440x900 and mobile 390x844 browser checks loaded the new artwork,
correct favicon/manifest URLs, unchanged 35px/32px icon and 86.5px/137.45px header
dimensions, and no horizontal overflow or warning/error logs. Screenshots and
machine-readable byte evidence remain in the external task evidence directory.
This confirms deployed icon delivery and rendered layout preservation; it does
not claim physical-device or Windows installation acceptance.

Existing physical-device, obsolete queue, cutover, historical simulator and
private Vault/runtime gates remain separate.
