"""Bounded source-document OCR with auditable, conservative House checkbox parsing.

Never executes PDF content, follows links, fetches URLs, or sends notifications.
OCR completion is distinct from structured-transaction acceptance. Callers own the
canonical write lock and retain evidence only after their snapshot commits.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "source-ocr-v2"
MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 30
MAX_PIXELS = 20_000_000
AMOUNTS = ["$1,001 - $15,000", "$15,001 - $50,000", "$50,001 - $100,000",
           "$100,001 - $250,000", "$250,001 - $500,000", "$500,001 - $1,000,000",
           "$1,000,001 - $5,000,000", "$5,000,001 - $25,000,000",
           "$25,000,001 - $50,000,000", "Over $50,000,000", "Over $1,000,000 (spouse or dependent child asset)"]
DATE = re.compile(r"(?<!\d)(\d{1,2}/\d{1,2}/\d{2,4})(?!\d)")


class OCRError(ValueError):
    """A safe diagnostic code; never includes document contents or tool stderr."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def inspect_document(data: bytes, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """Validate signature, encryption and decoded page/pixel bounds before OCR."""
    if not data or len(data) > MAX_BYTES:
        raise OCRError("document_byte_limit")
    if data.startswith(b"%PDF"):
        import pdfplumber
        try:
            with pdfplumber.open(io.BytesIO(data)) as pdf:
                if getattr(pdf.doc, "encryption", None) is not None:
                    raise OCRError("invalid_or_encrypted_pdf")
                count = len(pdf.pages)
                if not 0 < count <= max_pages:
                    raise OCRError("document_page_limit")
                import math
                if any(not math.isfinite(p.width * p.height) or min(p.width, p.height) <= 0 or p.width * p.height * (300 / 72) ** 2 > MAX_PIXELS for p in pdf.pages):
                    raise OCRError("document_pixel_limit")
                native = [p.extract_text() or "" for p in pdf.pages]
                if sum(map(len, native)) > 2_000_000:
                    raise OCRError("native_text_limit")
            return {"format": "pdf", "pages": count, "native_pages": native}
        except OCRError:
            raise
        except Exception:
            raise OCRError("invalid_or_encrypted_pdf") from None
    from PIL import Image, ImageOps
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG", "TIFF"}:
                raise OCRError("unsupported_image_format")
            count = getattr(image, "n_frames", 1)
            if not 0 < count <= max_pages:
                raise OCRError("document_page_limit")
            for page in range(count):
                image.seek(page)
                if image.width * image.height > MAX_PIXELS:
                    raise OCRError("document_pixel_limit")
                image.load()
            return {"format": image.format.lower(), "pages": count, "native_pages": [""] * count}
    except OCRError:
        raise
    except Exception:
        raise OCRError("invalid_image") from None


def read_tsv(text: str) -> list[dict[str, Any]]:
    words = []
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        if row.get("level") != "5" or not row.get("text", "").strip():
            continue
        try:
            word = {key: int(row[key]) for key in ("page_num", "left", "top", "width", "height")}
            word.update(text=row["text"].strip(), confidence=float(row["conf"]))
        except (ValueError, KeyError, TypeError):
            raise OCRError("invalid_ocr_coordinates") from None
        words.append(word)
        if len(words) > 100_000:
            raise OCRError("ocr_word_limit")
    return words


def _checkboxes(image) -> list[dict[str, Any]]:
    """Detect small enclosed square interiors, not glyphs mistaken for checkmarks."""
    import cv2
    import numpy as np
    gray = np.asarray(image.convert("L"))
    black = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)[1]
    contours, _ = cv2.findContours(black, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    scale = gray.shape[1] / 2544.0
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (38 * scale < w < 82 * scale and 38 * scale < h < 84 * scale and .75 < w / h < 1.3):
            continue
        if cv2.contourArea(contour) < w * h * .65:
            continue
        candidates.append((x, y, w, h))
    # Double-printed borders create nested contours: prefer the smallest actual
    # enclosed square. Center-distance suppression preserves neighboring boxes.
    kept = []
    for x, y, w, h in sorted(candidates, key=lambda box: box[2] * box[3]):
        cx, cy = x + w / 2, y + h / 2
        if any(abs(cx - item["cx"]) < min(w, item["w"]) * .48 and
               abs(cy - item["cy"]) < min(h, item["h"]) * .48 for item in kept):
            continue
        inside = black[y + int(h * .25):y + int(h * .8), x + int(w * .2):x + int(w * .8)]
        ink = float(np.mean(inside > 0)) if inside.size else 1.0
        kept.append({"x": x, "y": y, "w": w, "h": h, "cx": cx, "cy": cy,
                     "ink_fraction": round(ink, 4),
                     "state": "checked" if .20 <= ink <= .60 else "empty" if ink < .035 else "ambiguous"})
    return kept


def _date(value: str) -> str:
    match = DATE.search(value)
    if not match:
        raise OCRError("unreadable_date")
    raw = match.group(1)
    parsed = datetime.strptime(raw, "%m/%d/%Y" if len(raw.split("/")[-1]) == 4 else "%m/%d/%y")
    return parsed.date().isoformat()


def house_rows(images, words: list[dict[str, Any]]) -> dict[str, Any]:
    """Recognize only the validated House 4-type/11-amount checkbox form family.

    Unknown layouts/marks remain review-only. Preserve separate physical rows,
    including identical-looking transactions. Never copy printed-example owners.
    """
    rows, problems = [], []
    form_groups = 0
    all_text = " ".join(w["text"] for w in words).casefold()
    if "house of representatives" not in all_text or "transaction" not in all_text:
        return {"recognized": False, "rows": [], "problems": ["unsupported_form"]}
    for page, image in enumerate(images, 1):
        page_words = [w for w in words if w["page_num"] == page]
        boxes = [box for box in _checkboxes(image) if box["x"] > image.width * .25]
        clusters = []
        for box in sorted(boxes, key=lambda item: (item["cy"], item["cx"])):
            group = next((g for g in clusters if abs(g[0]["cy"] - box["cy"]) < box["h"] * .5), None)
            if group is None:
                clusters.append([box])
            else:
                group.append(box)
        populated = 0
        page_groups = 0
        for group in clusters:
            group.sort(key=lambda item: item["cx"])
            if len(group) != 15:
                continue
            types, amounts = group[:4], group[4:]
            # Dates must occupy the wide gap between the four transaction boxes
            # and eleven amount boxes; a 15-glyph text line is not a form row.
            if amounts[0]["cx"] - types[-1]["cx"] < types[0]["w"] * 4:
                continue
            form_groups += 1
            page_groups += 1
            cy = sum(b["cy"] for b in group) / len(group)
            band = max(b["h"] for b in group) * .70
            line = [w for w in page_words if abs(w["top"] + w["height"] / 2 - cy) < band]
            gap = [w for w in line if types[-1]["cx"] < w["left"] < amounts[0]["x"]]
            dates = sorted([w for w in gap if DATE.search(w["text"])], key=lambda w: w["left"])
            asset_words = sorted([w for w in line if image.width * .11 < w["left"] < types[0]["x"] - 8], key=lambda w: w["left"])
            asset = " ".join(w["text"] for w in asset_words)
            marks = [b for b in group if b["state"] != "empty"]
            if not dates and not asset and not marks:
                continue
            # A printed example has no 15 real checkboxes; defense in depth for
            # other editions that do. Do not use date/year alone to discard rows.
            if re.search(r"\b(ex[a-z]*m[pb][a-z]*|example)\b", asset, re.I):
                continue
            populated += 1
            issues = []
            selected_types = [i for i, b in enumerate(types) if b["state"] == "checked"]
            selected_amounts = [i for i, b in enumerate(amounts) if b["state"] == "checked"]
            if any(b["state"] == "ambiguous" for b in group) or len(selected_types) != 1 or len(selected_amounts) != 1:
                issues.append("ambiguous_checkboxes")
            if selected_amounts == [10]:
                issues.append("special_spouse_child_amount_requires_review")
            if len(dates) != 2 or any(w["confidence"] < 50 for w in dates):
                issues.append("unreadable_dates")
            if not asset or not asset_words or min(w["confidence"] for w in asset_words) < 50:
                issues.append("asset_text_needs_review")
            transaction_date = notification_date = ""
            if len(dates) == 2:
                try:
                    transaction_date, notification_date = [_date(w["text"]) for w in dates]
                    if transaction_date > notification_date:
                        issues.append("date_order_conflict")
                except (ValueError, OCRError):
                    issues.append("unreadable_dates")
            # Blank ownership must remain unknown, never infer Self or Joint.
            owner_words = [w for w in line if w["left"] < image.width * .11]
            if any(re.fullmatch(r"SP|DC|JT", w["text"], re.I) for w in owner_words):
                issues.append("ownership_needs_review")
            rows.append({"page": page, "row": populated, "asset": asset,
                         "owner": "", "ticker": "", "transaction_date": transaction_date,
                         "notification_date": notification_date,
                         "transaction_type": ["Purchase", "Sale", "Sale (Partial)", "Exchange"][selected_types[0]] if len(selected_types) == 1 else "",
                         "amount": AMOUNTS[selected_amounts[0]] if len(selected_amounts) == 1 else "",
                         "amount_column": chr(65 + selected_amounts[0]) if len(selected_amounts) == 1 else "",
                         "bbox": [max(0, int(image.width * .09)), int(cy - band), int(group[-1]["x"] + group[-1]["w"]), int(cy + band)],
                         "checkboxes": group, "issues": sorted(set(issues))})
        # OCR process/page coverage alone does not prove table coverage. An
        # unreadable/rotated/other-layout continuation cannot silently disappear.
        if not page_groups:
            problems.append("unvalidated_page_layout")
        # Any readable date pair below the table header not attached to a detected
        # row is evidence of incomplete segmentation, not an empty filing.
        for w in page_words:
            if not DATE.search(w["text"]) or not .40 < w["left"] / image.width < .56:
                continue
            if w["top"] < image.height * .35:
                continue
            if any(r["page"] == page and r["bbox"][1] <= w["top"] + w["height"] / 2 <= r["bbox"][3] for r in rows):
                continue
            neighbors = " ".join(v["text"] for v in page_words if abs(v["top"] - w["top"]) < 35)
            if "common stock" in neighbors.casefold() and ("corp" in neighbors.casefold()):
                continue  # recognized preprinted illustrative row, not a trade
            problems.append("unsegmented_date_row")
    if not rows:
        problems.append("no_validated_rows")
    return {"recognized": bool(form_groups), "rows": rows, "problems": sorted(set(problems))}


def extract(data: bytes, *, max_pages: int = MAX_PAGES, timeout: int = 120) -> dict[str, Any]:
    """One bounded Tesseract process for the complete document; no silent truncation."""
    try:
        from .source_ocr_limits import inspect_bounded, decoder_environment
    except ImportError:
        from source_ocr_limits import inspect_bounded, decoder_environment
    info = inspect_bounded(data, max_pages)
    from PIL import Image, ImageOps
    with tempfile.TemporaryDirectory(prefix="polititrack-ocr-") as temporary:
        root = Path(temporary)
        paths = []
        if info["format"] == "pdf":
            source = root / "source.pdf"
            source.write_bytes(data)
            try:
                subprocess.run(["pdftoppm", "-r", "300", "-png", "-gray", str(source), str(root / "page")],
                               check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=decoder_environment(), cwd=root)
            except (subprocess.SubprocessError, OSError):
                raise OCRError("pdf_render_failed") from None
            paths = sorted(root.glob("page-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
        else:
            with Image.open(io.BytesIO(data)) as source:
                for page in range(info["pages"]):
                    source.seek(page)
                    path = root / f"page-{page + 1}.png"
                    ImageOps.exif_transpose(source).convert("L").save(path)
                    paths.append(path)
        if len(paths) != info["pages"]:
            raise OCRError("incomplete_page_render")
        # No generated file or model result can inject a command; shell=False.
        (root / "pages.txt").write_text("\n".join(str(path) for path in paths), encoding="utf-8")
        try:
            subprocess.run(["tesseract", str(root / "pages.txt"), str(root / "result"), "-l", "eng", "--psm", "11", "txt", "tsv"],
                           check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=decoder_environment(), cwd=root)
        except (subprocess.SubprocessError, OSError):
            raise OCRError("ocr_engine_failed") from None
        if (root / "result.txt").stat().st_size > 8_000_000 or (root / "result.tsv").stat().st_size > 12_000_000:
            raise OCRError("ocr_output_limit")
        text = (root / "result.txt").read_text(encoding="utf-8")
        tsv = (root / "result.tsv").read_text(encoding="utf-8")
        if len(text) > 2_000_000 or len(tsv) > 12_000_000:
            raise OCRError("ocr_output_limit")
        page_ids = {int(row["page_num"]) for row in csv.DictReader(io.StringIO(tsv), delimiter="\t") if row.get("level") == "1"}
        if page_ids != set(range(1, info["pages"] + 1)):
            raise OCRError("incomplete_page_ocr")
        words = read_tsv(tsv)
        images = [Image.open(path) for path in paths]
        try:
            table = house_rows(images, words)
        finally:
            for image in images:
                image.close()
        return {"version": VERSION, "sha256": hashlib.sha256(data).hexdigest(),
                "format": info["format"], "page_count": info["pages"],
                "completed_pages": list(range(1, info["pages"] + 1)), "ocr_completed_at": now(),
                "native_pages": info["native_pages"], "ocr_text": text, "words": words,
                "house_table": table, "ocr_status": "complete" if words else "needs_review"}
