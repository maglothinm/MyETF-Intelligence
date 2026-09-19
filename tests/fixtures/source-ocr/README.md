# Synthetic readable encrypted PDF

`empty-password.pdf.b64` is a two-page synthetic PDF containing only
`PUBLIC DISCLOSURE TEST PAGE 1` / `2`, encrypted with AES-256, an empty user
password and a nonempty test-only owner password. It was generated with pypdf;
tests decode the fixed bytes without adding an authoring dependency to CI.

It verifies default public opening, native extraction, page bounds and real
Poppler/Tesseract processing. No downloaded filing or user-upload bytes are
included. The separate password-required fixture in `test_source_ocr.py` must
continue to fail closed.
