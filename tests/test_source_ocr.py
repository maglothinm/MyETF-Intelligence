"""Deterministic OCR geometry tests plus an optional real-engine acceptance case."""
import hashlib
import base64
import io
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

from scripts.source_ocr import (AMOUNTS, MAX_BYTES, OCRError, VERSION, extract,
                                house_rows, inspect_document, read_tsv)


def synthetic_form():
    """Public synthetic fixture, not the owner's uploaded document."""
    image = Image.new("L", (2544, 3300), 255)
    draw = ImageDraw.Draw(image)
    font_path = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"] if Path(p).is_file()), None)
    font = ImageFont.truetype(font_path, 27) if font_path else ImageFont.load_default(size=27)
    words = []
    def text(value, x, y, confidence=96):
        draw.text((x, y), value, font=font, fill=0)
        width = int(draw.textlength(value, font=font))
        words.append(dict(page_num=1,left=x,top=y,width=width,height=30,text=value,confidence=confidence))
    text("UNITED STATES HOUSE OF REPRESENTATIVES", 400, 700)
    text("Diana Harshbarger", 320, 850)
    text("AMOUNT OF TRANSACTION", 1500, 1450)
    text("Example Mega Corp Common Stock", 330, 1790)
    text("02/05/20", 1090, 1790)
    text("03/07/20", 1235, 1790)
    for row,y in enumerate([2100,2200]):
        text("School District Bond", 310, y+10)
        text("7/30/26", 1080, y+10)
        text("8/19/26", 1230, y+10)
        positions=[780,855,930,1005]+[1400+i*90 for i in range(11)]
        for col,x in enumerate(positions):
            draw.rectangle((x,y,x+56,y+56),outline=0,width=4)
            if col in {1,5}:
                draw.line([(x+12,y+29),(x+25,y+43),(x+47,y+12)],fill=0,width=7)
    return image,words


def test_checkboxes_keep_identical_physical_rows_and_ignore_printed_example():
    image, words = synthetic_form()
    parsed = house_rows([image], words)
    assert not parsed["problems"]
    assert len(parsed["rows"]) == 2
    assert [row["row"] for row in parsed["rows"]] == [1, 2]
    assert all(row["transaction_type"] == "Sale" and row["amount_column"] == "B" for row in parsed["rows"])
    assert all(row["owner"] == "" and row["ticker"] == "" for row in parsed["rows"])


def test_ambiguous_text_is_review_not_a_guessed_asset():
    image, words = synthetic_form()
    words[-3]["confidence"] = 3
    assert any(row["issues"] for row in house_rows([image], words)["rows"])


def test_native_house_header_is_not_enough_to_accept_checkbox_layout():
    image = Image.new("L",(2544,3300),255)
    _, words = synthetic_form()
    assert not house_rows([image], words)["recognized"]


def test_no_silent_page_limit_or_invalid_file_acceptance():
    with pytest.raises(OCRError):inspect_document(b"not a pdf")
    with pytest.raises(OCRError):inspect_document(b"%PDF" + b"x" * MAX_BYTES)
    image = Image.new("RGB",(100,100),"white")
    data=io.BytesIO(); image.save(data,format="TIFF",save_all=True,append_images=[image])
    with pytest.raises(OCRError,match="document_page_limit"):inspect_document(data.getvalue(),max_pages=1)
    assert inspect_document(data.getvalue())["pages"] == 2


def readable_encrypted_pdf():
    # Synthetic two-page AES-256 fixture: empty user password, nonempty owner
    # password. No real filing/upload, authoring dependency or secret is needed.
    return base64.b64decode((Path(__file__).parent / "fixtures/source-ocr/empty-password.pdf.b64").read_bytes())


def test_empty_password_pdf_keeps_native_text_and_inspection_bounds():
    import pdfplumber
    from scripts.source_ocr_limits import inspect_bounded
    data = readable_encrypted_pdf()
    with pdfplumber.open(io.BytesIO(data), password="") as pdf:
        assert pdf.doc.encryption is not None
    result = inspect_bounded(data)
    assert result["pages"] == 2
    assert result["native_pages"] == ["PUBLIC DISCLOSURE TEST PAGE 1", "PUBLIC DISCLOSURE TEST PAGE 2"]
    with pytest.raises(OCRError, match="document_page_limit"):
        inspect_bounded(data, max_pages=1)


@pytest.mark.skipif(not all(shutil.which(name) for name in ("tesseract", "pdftoppm")), reason="real OCR tools unavailable")
def test_empty_password_pdf_reaches_real_render_and_ocr():
    data = readable_encrypted_pdf()
    result = extract(data, timeout=60)
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["completed_pages"] == [1, 2]
    assert all(f"TEST PAGE {number}" in result["ocr_text"] for number in [1, 2])
    assert len(result["native_pages"]) == 2


@pytest.mark.skipif(not shutil.which("tesseract"), reason="real OCR engine is not installed")
def test_real_ocr_process_reads_synthetic_source(tmp_path):
    image,_=synthetic_form()
    data=io.BytesIO();image.save(data,format="PNG")
    result=extract(data.getvalue(),timeout=60)
    assert result["version"] == VERSION
    assert result["sha256"] == hashlib.sha256(data.getvalue()).hexdigest()
    assert result["completed_pages"] == [1]
    assert "Harshbarger" in result["ocr_text"]
    assert len(result["house_table"]["rows"]) == 2
    assert all(row["amount"] == AMOUNTS[1] for row in result["house_table"]["rows"])


@pytest.mark.skipif(not shutil.which("tesseract"), reason="real OCR engine is not installed")
def test_real_multipage_ocr_keeps_physical_numbers_across_no_text_page():
    image = Image.new("L", (1000, 400), 255)
    font_path = next((p for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"] if Path(p).is_file()), None)
    font = ImageFont.truetype(font_path, 40) if font_path else ImageFont.load_default(size=40)
    first, last = image.copy(), image.copy()
    ImageDraw.Draw(first).text((40, 100), "FIRST SOURCE PAGE", font=font, fill=0)
    ImageDraw.Draw(last).text((40, 100), "THIRD SOURCE PAGE", font=font, fill=0)
    data = io.BytesIO()
    first.save(data, format="TIFF", save_all=True, append_images=[image, last])
    result = extract(data.getvalue(), timeout=60)
    assert result["completed_pages"] == [1, 2, 3]
    assert result["empty_ocr_pages"] == [2]
    assert result["ocr_status"] == "needs_review"
    assert {word["page_num"] for word in result["words"] if word["text"] == "THIRD"} == {3}
    assert {word["page_num"] for word in result["words"] if word["text"] == "FIRST"} == {1}


TSV_HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"


@pytest.mark.parametrize("bad_output", ["missing", "malformed", "wrong_page", "missing_header", "duplicate_header", "failed"])
def test_page_completion_rejects_missing_malformed_or_failed_output(tmp_path, monkeypatch, bad_output):
    from scripts import source_ocr
    def engine(command, **kwargs):
        if bad_output == "failed":
            raise source_ocr.subprocess.CalledProcessError(1, command)
        if bad_output == "missing":
            return
        output = Path(command[2])
        output.with_suffix(".txt").write_text("", encoding="utf-8")
        header = "1\t1\t0\t0\t0\t0\t0\t0\t100\t100\t-1\t\n"
        content = {"malformed": "wrong\theader\n", "wrong_page": TSV_HEADER + header.replace("1\t1", "1\t2", 1),
                   "missing_header": TSV_HEADER + header.replace("1\t1", "5\t1", 1),
                   "duplicate_header": TSV_HEADER + header + header}[bad_output]
        output.with_suffix(".tsv").write_text(content, encoding="utf-8")
    monkeypatch.setattr(source_ocr.subprocess, "run", engine)
    with pytest.raises(OCRError, match="incomplete_page_ocr|ocr_engine_failed"):
        source_ocr._ocr_pages([tmp_path / "page.png"], tmp_path, 30, {})


def test_no_text_completion_has_one_document_deadline_and_cumulative_output_bound(tmp_path, monkeypatch):
    from scripts import source_ocr
    calls = []
    clock = iter([0, 1, 6])
    monkeypatch.setattr(source_ocr.time, "monotonic", lambda: next(clock))
    def engine(command, **kwargs):
        calls.append(kwargs["timeout"])
        output = Path(command[2])
        output.with_suffix(".txt").write_text("", encoding="utf-8")
        output.with_suffix(".tsv").write_text(TSV_HEADER, encoding="utf-8")
    monkeypatch.setattr(source_ocr.subprocess, "run", engine)
    assert source_ocr._ocr_pages([tmp_path / "1.png", tmp_path / "2.png"], tmp_path, 10, {}) == ("\f", [], [1, 2])
    assert calls == [9, 4]
    clock = iter([0, 11])
    with pytest.raises(OCRError, match="ocr_engine_failed"):
        source_ocr._ocr_pages([tmp_path / "1.png"], tmp_path, 10, {})
    assert len(calls) == 2


def test_page_output_limits_apply_across_document_not_per_page(tmp_path, monkeypatch):
    from scripts import source_ocr
    def engine(command, **kwargs):
        output = Path(command[2])
        output.with_suffix(".txt").write_text(" " * 4_000_001, encoding="utf-8")
        output.with_suffix(".tsv").write_text(TSV_HEADER, encoding="utf-8")
    monkeypatch.setattr(source_ocr.subprocess, "run", engine)
    with pytest.raises(OCRError, match="ocr_output_limit"):
        source_ocr._ocr_pages([tmp_path / "1.png", tmp_path / "2.png"], tmp_path, 30, {})


def test_unrecognized_continuation_cannot_silently_drop_a_page():
    image, words = synthetic_form()
    # A rotated or otherwise unsupported continuation remains non-importable,
    # even when a different page yields good-looking transaction rows.
    rotated = image.rotate(90, expand=True)
    result = house_rows([image, rotated], words)
    assert result["recognized"] and result["rows"]
    assert "unvalidated_page_layout" in result["problems"]


def test_bounded_probe_rejects_malformed_pdf_and_times_out_without_secrets(monkeypatch):
    import subprocess
    from scripts.source_ocr_limits import inspect_bounded
    with pytest.raises(OCRError): inspect_bounded(b"%PDF-not-valid")
    seen = {}
    def timeout(*args, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(args[0], 15)
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "private-password")
    monkeypatch.setenv("DATABASE_URL", "private-database")
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(OCRError, match="inspection_limit"): inspect_bounded(b"%PDF-test")
    assert "GMAIL_APP_PASSWORD" not in seen["env"] and "DATABASE_URL" not in seen["env"]
    assert not seen.get("shell", False)


def test_valid_encrypted_pdf_is_rejected_by_bounded_probe():
    import base64
    from scripts.source_ocr_limits import inspect_bounded
    # Synthetic one-page AES-256 fixture generated for this regression only.
    # No optional PDF-authoring dependency is needed in CI.
    data = base64.b64decode(
        "JVBERi0xLjMKJcK1wrYKCjEgMCBvYmoKPDwvRjEgMiAwIFI+PgplbmRvYmoKCjIgMCBvYmoKPDwvVHlwZS9Gb250L1N1YnR5cGUv"
        "VHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhL0VuY29kaW5nL1dpbkFuc2lFbmNvZGluZy9OYW1lL0YxPj4KZW5kb2JqCgozIDAgb2Jq"
        "Cjw8L1R5cGUvUGFnZS9Db250ZW50cyA3IDAgUi9NZWRpYUJveFswIDAgNTk1LjI3NTYgODQxLjg4OThdL1BhcmVudCA2IDAgUi9S"
        "ZXNvdXJjZXM8PC9Gb250IDEgMCBSL1Byb2NTZXRbL1BERi9UZXh0L0ltYWdlQi9JbWFnZUMvSW1hZ2VJXT4+L1JvdGF0ZSAwL1Ry"
        "YW5zPDw+Pj4+CmVuZG9iagoKNCAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZU1vZGUvVXNlTm9uZS9QYWdlcyA2IDAgUj4+CmVu"
        "ZG9iagoKNSAwIG9iago8PC9BdXRob3I8RkM3QzRDMEQ4REZEQzFCRDY4M0Y2OEFGNzUxNzU2NkNFNEY5NzIzN0M1OTFCRUI2NkVB"
        "QTc2MDRDQUVFNkM4NT4vQ3JlYXRpb25EYXRlPDE1QzFCNjc1QzM0NTgyNkY2N0Y2REU3QzM3MTUxMUE2QjMxMEY5MDhEMDEyQzk2"
        "RTUwNUQzMDUxOTAyNTQ2MDI0OTA5OTc2NTZFNUY5QUMwQTA2RDczQjg0MkM1NzAyMT4vQ3JlYXRvcjw0QTkyMjA3NUJCRjIwOUEw"
        "NzY0Qzk5RTBBMjZERUFERjc0Nzk0QzM4RjRDQkZBNzIwRUE5ODgzNTk2QTNGOTY5Pi9LZXl3b3Jkczw+L01vZERhdGU8QUIxQjdE"
        "NTBFQTc3RjAxOEY0N0I1Q0E5N0NBMzRENzA5MjJDM0E3MzgxMjYzMDBFNkVGMkM1Mjk0MDIzOEY4NDM4RkYxNDQ5M0UxRkE5QUY1"
        "QjM3MkZFMTg2QzBEMUJBPi9Qcm9kdWNlcjxFNkE5NUY2NDY5Njg3MUJGREZFMjg5Q0EyQzVENDREMEFDOUI1QjQ3RUM0RkRFRDM5"
        "RDdCMjcyMjQ4RTdCMjg0MEVGQTVDQzJFQjg0RjY1N0IyMzdEM0M2Q0QwRkNFRDQ4NTVFMzkwNzY4MDIyNTZGNzhGMURDOEZGQkYx"
        "QjVFQj4vU3ViamVjdDw0OUE4RjgzNEVDN0I2ODlGRDZGQzIyNTFCODVFNzk5OUVGOUJFM0I1Q0RGOTBBRkVEMTVEN0VBNkEyMTRE"
        "MjBCPi9UaXRsZTxDM0E0MUI2MENCODQ0RURGMTY2NkNCNzFDNzhCMzc4MjAwOUI1QkY0NzJEODFERDc2MThDQ0I3N0FEQ0M4OTcz"
        "Pi9UcmFwcGVkL0ZhbHNlPj4KZW5kb2JqCgo2IDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzMgMCBSXT4+CmVuZG9i"
        "agoKNyAwIG9iago8PC9GaWx0ZXJbL0FTQ0lJODVEZWNvZGUvRmxhdGVEZWNvZGVdL0xlbmd0aCAxNDQ+PgpzdHJlYW0K4ks6p/t3"
        "PsiA3cZ4n+loZesAy+tiW652o2YyHEX2TRSqlFoGYq4BauNFl8Ncj1FmLvTugpgQhyllvfMi/xmw3NM1hvgao0dv9mVshIlkFdiE"
        "PHMoTUiffJsSZn9ecubJiNh51zKsWLY0cP0nnY4ZiMkAhvIGdpxOKbG4jOhtI33JmjkEwdA7S9af+OLjy5MICmVuZHN0cmVhbQpl"
        "bmRvYmoKCnhyZWYKMCA4CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDAxNiAwMDAwMCBuIAowMDAwMDAwMDQ2IDAwMDAwIG4g"
        "CjAwMDAwMDAxNDMgMDAwMDAgbiAKMDAwMDAwMDMxOCAwMDAwMCBuIAowMDAwMDAwMzgxIDAwMDAwIG4gCjAwMDAwMDEwNzYgMDAw"
        "MDAgbiAKMDAwMDAwMTEyOCAwMDAwMCBuIAoKdHJhaWxlcgo8PC9TaXplIDgvSW5mbyA1IDAgUi9Sb290IDQgMCBSL0lEWzw4MkND"
        "MDlFMTExRjQ2QkVDMEE4MDEyODgzRjE2NDA2OT48MTY0OEYyNTlGOEZBRDFGNjYyM0MzMDAzMzM2NDUyQUU+XS9FbmNyeXB0PDwv"
        "RmlsdGVyL1N0YW5kYXJkL1IgNi9WIDUvTGVuZ3RoIDI1Ni9QIC00L0VuY3J5cHRNZXRhZGF0YSB0cnVlL1N0bUYvU3RkQ0YvU3Ry"
        "Ri9TdGRDRi9DRjw8L1N0ZENGPDwvQXV0aEV2ZW50L0RvY09wZW4vQ0ZNL0FFU1YzL0xlbmd0aCAzMj4+Pj4vTzw0NTc1NDAwRTY4"
        "OTI2OUQ3OTAyMjZDMUFCMzA3MjIyNzIxMTgzOENFMTNCMkFEMzAyOEUxRUM4MjJEMTFCNEJBRjJCNkIzMzE5MkI2OEYxRjQyQzND"
        "QkUxQkEwOTE1QzY+L1U8NzUzN0QwRkQ4RTIwQTVENzQyMjREQjBFODY1NjExQzhFMDE4QjI5OTEyOTQ0M0ZGMjg0NDNCN0MzQjg4"
        "ODZDMkMzRUIxNjIxMDg4MkNFQUFBQzY0NDU1MzQwNTc2MjMyPi9PRTxDRTEwRkMxMzQ3RDcyQzI3QTgwNUI0N0Q2OTVDMUNGNDlF"
        "MEYwQkY3MTkxQUJGQjUzMzgxQjMxNDdBRTk4MTY1Pi9VRTw3OUUwNTAxMTVFN0U5RUQ3Q0JDMUU4RkRBNTk4NTA0QUNEMUQ1OTM2"
        "N0FCOUZFQzY3QzZCMEE0RjE4MkEzQTUyPi9QZXJtczxGRjFGMDEzQzZFRUI4NkJGQTYyRDFDRTUzMEQzMUIzNT4+Pj4+CnN0YXJ0"
        "eHJlZgoxMzU3CiUlRU9GCg=="
)
    with pytest.raises(OCRError, match="invalid_or_encrypted_pdf"):
        inspect_bounded(data)


def test_decoder_environment_drops_application_credentials(monkeypatch):
    from scripts.source_ocr_limits import decoder_environment
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "/private/credential")
    monkeypatch.setenv("DATABASE_URL", "secret-database")
    monkeypatch.setenv("OPENAI_API_KEY", "secret-model")
    monkeypatch.setenv("HTTPS_PROXY", "secret-proxy")
    monkeypatch.setenv("TESSDATA_PREFIX", "/usr/share/tesseract-ocr")
    env = decoder_environment()
    assert env["TESSDATA_PREFIX"] == "/usr/share/tesseract-ocr"
    assert not set(env) & {"GOOGLE_APPLICATION_CREDENTIALS", "DATABASE_URL", "OPENAI_API_KEY", "HTTPS_PROXY"}


# Manual page-count exemption: keep every automatic resource policy intact.
def multipage_source(count, format="PDF"):
    image = Image.new("RGB", (240, 96), "white")
    ImageDraw.Draw(image).text((15, 25), "MANUAL SOURCE TEST", fill="black", font=ImageFont.load_default(size=20))
    stream = io.BytesIO()
    image.save(stream, format=format, save_all=True, append_images=[image] * (count - 1))
    image.close()
    return stream.getvalue()


@pytest.mark.parametrize("count", [31, 37, 51, 75])
@pytest.mark.parametrize("format", ["PDF", "TIFF"])
def test_manual_admission_has_no_page_count_cap_but_automatic_stays_30(count, format):
    from scripts.source_ocr import MAX_PAGES
    from scripts.source_ocr_limits import inspect_bounded
    data = multipage_source(count, format)
    assert MAX_PAGES == 30
    with pytest.raises(OCRError, match="document_page_limit"):
        inspect_bounded(data)
    info = inspect_bounded(data, max_pages=None)
    assert info["pages"] == count and len(info["native_pages"]) == count


@pytest.mark.parametrize("limit", [0, -1, False, True, "manual-upload", 31])
def test_probe_does_not_treat_invalid_limits_as_owner_exemption(limit):
    from scripts.source_ocr_limits import inspect_bounded
    with pytest.raises(OCRError, match="document_page_limit"):
        inspect_bounded(b"%PDF-invalid", max_pages=limit)


def test_manual_mode_retains_invalid_file_and_byte_limits():
    from scripts.source_ocr_limits import inspect_bounded
    with pytest.raises(OCRError, match="document_byte_limit"):
        inspect_bounded(b"%PDF" + b"x" * MAX_BYTES, max_pages=None)
    with pytest.raises(OCRError, match="invalid_or_encrypted_pdf"):
        inspect_bounded(b"%PDF-not-valid", max_pages=None)


def test_manual_ocr_watchdog_is_per_page_without_changing_automatic_deadline(tmp_path, monkeypatch):
    from scripts import source_ocr
    calls = []
    # The second page starts after the automatic 10-second total deadline.
    clock = iter([0, 0, 1, 15, 16])
    monkeypatch.setattr(source_ocr.time, "monotonic", lambda: next(clock))
    def engine(command, **kwargs):
        calls.append(kwargs["timeout"])
        output = Path(command[2])
        output.with_suffix(".txt").write_text("", encoding="utf-8")
        output.with_suffix(".tsv").write_text(TSV_HEADER, encoding="utf-8")
    monkeypatch.setattr(source_ocr.subprocess, "run", engine)
    assert source_ocr._ocr_pages([tmp_path / "1.png", tmp_path / "2.png"], tmp_path, 10, {}, per_page_deadline=True) == ("\f", [], [1, 2])
    assert calls == [9, 9]


@pytest.mark.skipif(not all(shutil.which(name) for name in ("tesseract", "pdftoppm")), reason="real OCR tools unavailable")
def test_real_manual_pdf_processes_all_37_pages_without_truncation():
    result = extract(multipage_source(37), max_pages=None, timeout=30)
    assert result["page_count"] == 37
    assert result["completed_pages"] == list(range(1, 38))
    assert len(result["native_pages"]) == 37
    assert {word["page_num"] for word in result["words"]} == set(range(1, 38))
