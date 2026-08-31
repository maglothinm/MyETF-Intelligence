# PolitiTrack icon assets

These 22 image files are the unchanged contents of the owner-supplied
`PolitiTrack_Icon_Assets.zip` from the **Create PolitiTrack Icon** conversation.
No artwork was regenerated, cropped, resized or recompressed during integration.
`manifest.json` records each source file's size and SHA-256 digest, along with the
ZIP digest for provenance.

| Asset | Intended use |
| --- | --- |
| `polititrack-icon-original-1254.png` | Original-resolution, 1254 × 1254 RGBA source |
| `PolitiTrack.ico` | Windows application/shortcut icon; 16, 24, 32, 48, 64, 128 and 256px frames |
| `favicon.ico` | Browser icon; 16, 32 and 48px frames |
| `favicon-16x16.png`, `favicon-32x32.png` | Explicit PNG favicons |
| `apple-touch-icon.png` | 180px Apple touch icon |
| `android-chrome-192x192.png`, `android-chrome-512x512.png` | Web manifest icons; purpose `any` |
| `polititrack-header-*.png` | 40, 48, 64, 96 and 128px header variants |
| `polititrack-icon-*x*.png` | Additional supplied application/web sizes |

The Windows ICO is ready for future packaging or a Windows shortcut. This
repository currently has no Windows installer, executable packaging configuration,
or application icon reference to update.

The production dashboard's web copies live in `scripts/dashboard_assets/icons/`.
Both dashboard generation entry points use `scripts/dashboard_branding.py` to
copy them and `site.webmanifest` into generated output. Root, Wallboard and Filing
Vault retain their existing 35px desktop / 32px mobile header footprint; Wallboard
also retains its existing 54px mark on large portrait displays. The
standalone Investor Edge page receives favicon/manifest metadata without changing
its text-only heading. The manifest retains ordinary browser display behavior.

The retained React frontend has byte-identical web copies in its public directory
and keeps its existing header dimensions and layout. Its paths are independent
of the production Python-generated dashboard. For future updates, replace source
and served copies together, verify their hashes and generated URLs, then run the
existing dashboard checks and React build.
