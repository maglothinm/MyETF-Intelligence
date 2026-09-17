"""Deterministic OCR geometry tests plus an optional real-engine acceptance case."""
import hashlib
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
