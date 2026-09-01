# Bundled PDF.js renderer

Pinned Mozilla `pdfjs-dist` **6.3.289**, legacy minified build. Original upstream
bytes are copied without modification. `MANIFEST.json` records the npm tarball,
its verified SHA-512 integrity, SHA-256, upstream paths and every vendored file's
SHA-256. All applicable Apache, font, CMap, ICC and codec licenses are retained.

Sources:
- https://github.com/mozilla/pdf.js/releases/tag/v6.3.289
- https://mozilla.github.io/pdf.js/api/draft/module-pdfjsLib.html
- https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions

Only the library, matching worker, built-in CMaps, standard fonts, image-codec
WASM/fallbacks and ICC profile are bundled. No viewer application, scripting
sandbox, QuickJS, source maps, sample reports or PDF files are included. The
PolitiTrack helper supplies immutable bytes, not a remote PDF URL, and creates a
same-origin module worker explicitly. Its canvas-only rendering invokes no PDF
JavaScript or annotation actions, does not create interactive forms or links,
and disables XFA. PDF.js 6.3 removed the old `isEvalSupported` option and the core
does not evaluate PDF-provided JavaScript. The legacy polyfill bundle contains
a fixed `Function("return this")` fallback for discovering the global object;
supported browsers resolve `globalThis` before reaching it. CSP intentionally
blocks that fallback too. The helper passes `isEvalSupported:false` defensively
and never requires CSP `unsafe-eval`.
Image-codec WASM needs CSP `wasm-unsafe-eval`, which does not permit JavaScript eval.

The helper uses lazy pages, at most four retained canvases, at most 4 megapixels
per canvas, a 32 MiB document limit, a 300-page limit, and explicit cancellation
on close. PDF parser and decoded image allocations are not a hard process memory
sandbox. Large, unsupported or malformed files have an explicit download fallback.
Extracted text is a separate plain-text preview and never replaces the original.

Mozilla's current legacy-build FAQ lists Safari 18+ as mostly supported and
Chrome 125+ as supported. Bundling does not establish physical iPhone acceptance.
No CDN or upstream connection is needed during viewing. Serve the complete
directory beneath `vendor/pdfjs/` alongside the generated Vault page with correct `.mjs` and `.wasm` MIME types.
