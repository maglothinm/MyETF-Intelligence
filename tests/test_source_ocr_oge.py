"""TEST-only numbered OGE tables; no provider or production calls."""
import unittest
from scripts.source_ocr_oge import OGETableError, parse_verified_oge

HEADER = "# DESCRIPTION TYPE DATE NOTIFICATION AMOUNT\nRECEIVED OVER\n30 DAYS AGO\n"
INTRO = "Periodic Transaction Report (OGE Form 278-T)\nExample Official\nTransactions"
BODY = ("1 Example Company (TEST) Purchase 07/30/2026 No $1,001 - $15,000\n"
        "2 Example Company (TEST) Purchase 07/30/2026 No $1,001 - $15,000\n")
NATIVE = [INTRO, HEADER + BODY + "Endnotes\nSummary of Contents"]
OPTICAL = INTRO + "\f" + HEADER.replace(" ", "\n") + BODY.replace(" ", "\n") + "Endnotes\n"


class TestOGERows(unittest.TestCase):
    def test_cells_and_wrapped_headers_agree_without_collapsing_identical_rows(self):
        rows = parse_verified_oge(NATIVE, OPTICAL)
        self.assertEqual([row["row"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["asset"], "Example Company (TEST)")
        self.assertEqual(rows[0]["transaction_date"], "2026-07-30")
        self.assertEqual(rows[0]["notification_date"], "")
        self.assertEqual(rows[0]["owner"], "")
        self.assertFalse(rows[0]["notification_over_30_days"])

    def test_multiple_pages_and_repeated_headers(self):
        native = [INTRO, HEADER + BODY.splitlines()[0] + "\nExample Official - Page 2",
                  HEADER + BODY.splitlines()[1] + "\nEndnotes"]
        self.assertEqual([r["page"] for r in parse_verified_oge(native, "\f".join(native))], [2, 3])

    def test_asset_disagreement_rejects_whole_document(self):
        with self.assertRaisesRegex(OGETableError, "native_ocr_disagreement"):
            parse_verified_oge(NATIVE, OPTICAL.replace("Example\nCompany", "Different\nCompany"))

    def test_missing_row_rejects_whole_document(self):
        bad = [INTRO, HEADER + BODY.replace("1 Example", "3 Example")]
        with self.assertRaisesRegex(OGETableError, "row_sequence"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_asset_tail_after_amount_is_ambiguous(self):
        bad = [INTRO, HEADER + BODY.replace("$15,000", "$15,000\nClass A", 1)]
        with self.assertRaisesRegex(OGETableError, "rows_needs_review"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_bad_date_rejects(self):
        bad = [s.replace("07/30/2026", "02/30/2026") for s in NATIVE]
        with self.assertRaisesRegex(OGETableError, "date_needs_review"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_bad_amount_rejects(self):
        bad = [s.replace("$15,000", "$15,999") for s in NATIVE]
        with self.assertRaisesRegex(OGETableError, "amount_needs_review"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_second_page_without_header_is_not_silently_lost(self):
        bad = [INTRO, HEADER + BODY.splitlines()[0], BODY.splitlines()[1]]
        with self.assertRaisesRegex(OGETableError, "header_missing"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_table_after_endnotes_rejects(self):
        bad = NATIVE + [HEADER + "3 Example Company Sale 07/30/2026 No $1,001 - $15,000"]
        with self.assertRaisesRegex(OGETableError, "boundary_needs_review"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_missing_optical_page_rejects(self):
        with self.assertRaisesRegex(OGETableError, "page_coverage_disagreement"):
            parse_verified_oge(NATIVE, INTRO)

    def test_nominee_form_is_not_a_periodic_transaction_report(self):
        bad = [s.replace("278-T", "278e") for s in NATIVE]
        with self.assertRaisesRegex(OGETableError, "unsupported_form"):
            parse_verified_oge(bad, "\f".join(bad))

    def test_notification_is_boolean_not_invented_date(self):
        native = [s.replace("No $", "Yes $") for s in NATIVE]
        rows = parse_verified_oge(native, "\f".join(native))
        self.assertTrue(rows[0]["notification_over_30_days"])
        self.assertEqual(rows[0]["notification_date"], "")


if __name__ == "__main__":
    unittest.main()

