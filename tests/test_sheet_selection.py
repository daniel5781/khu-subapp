"""시트 순서가 달라도 총거래표와 국산거래표를 구별하는 회귀 검사."""
from pathlib import Path
import sys
import unicodedata
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from iolib import preprocessing as P


class TransactionSheetSelectionTests(unittest.TestCase):
    def test_import_sheet_is_never_selected_as_domestic(self):
        sheets = ["A표_총거래표(생산자가격)", "A표_수입거래표(생산자가격)",
                  "A표_국산거래표(생산자가격)"]
        self.assertEqual(P._transaction_sheet_names(sheets), (sheets[0], sheets[2]))

    def test_reversed_order_and_unicode_spacing(self):
        domestic = unicodedata.normalize("NFD", "A표_ 국산 거래표 (생산자)")
        total = "A표_총거래표(생산자)"
        self.assertEqual(P._transaction_sheet_names([domestic, total]), (total, domestic))

    def test_missing_domestic_does_not_fall_back_to_import(self):
        with self.assertRaisesRegex(ValueError, "국산거래표.*없습니다"):
            P._transaction_sheet_names(["총거래표", "수입거래표"])

    def test_missing_total_does_not_fall_back_to_other_tab(self):
        with self.assertRaisesRegex(ValueError, "총거래표.*없습니다"):
            P._transaction_sheet_names(["Sheet1", "국산거래표"])

    def test_duplicate_named_tables_are_ambiguous(self):
        for sheets, label in [
            (["총거래표", "총거래표 복사", "국산거래표"], "총거래표"),
            (["총거래표", "국산거래표", "국산거래표 복사"], "국산거래표"),
        ]:
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, label + ".*여러 개"):
                P._transaction_sheet_names(sheets)

    def test_legacy_unnamed_workbook_keeps_order(self):
        self.assertEqual(P._transaction_sheet_names(["Sheet1", "Sheet2"]),
                         ("Sheet1", "Sheet2"))
        with self.assertRaisesRegex(ValueError, "두 개 이상"):
            P._transaction_sheet_names(["Sheet1"])

    def test_loader_reads_selected_sheets_then_uses_existing_cleanup(self):
        params = P.get_mode_params("Korea(2010~2020)")
        source = object()
        total, domestic, result = object(), object(), object()
        with patch.object(P.pd, "ExcelFile") as excel_file, \
                patch.object(P, "load_data", side_effect=[total, domestic]) as read, \
                patch.object(P, "_post_clean", return_value=result) as clean:
            excel_file.return_value.__enter__.return_value.sheet_names = [
                "국산거래표", "총거래표", "수입거래표"
            ]
            self.assertIs(P._load_two_sheet(source, params), result)
            self.assertEqual([c.args for c in read.call_args_list],
                             [(source, "총거래표"), (source, "국산거래표")])
            clean.assert_called_once_with(total, domestic, params)


class RealWorkbookSelectionTests(unittest.TestCase):
    def test_repository_2020_workbook_reads_domestic_not_import(self):
        path = next((p for p in REPO.glob("*.xlsx")
                     if "(2020실측)" in unicodedata.normalize("NFC", p.name)), None)
        if path is None:
            self.skipTest("2020 한국 표 fixture 없음")
        result = P.load_workbook(path, "Korea(2010~2020)")
        self.assertIn("총거래표", result.df.iloc[0, 0])
        self.assertIn("국산거래표", result.df_local.iloc[0, 0])
        self.assertEqual(result.mid_ID_idx, result.mid_ID_idx_local)
        domestic = pd.read_excel(path, sheet_name="A표_국산거래표(생산자가격)", header=None)
        row_end, col_end = result.mid_ID_idx_local
        np.testing.assert_array_equal(
            result.df_local.iloc[6:row_end, 2:col_end].to_numpy(float),
            domestic.iloc[6:row_end, 2:col_end].to_numpy(float),
        )

    def test_supplied_2024_workbook_matches_published_coefficients(self):
        path = next((p for p in (Path.home() / "Downloads").glob("*.xlsx")
                     if "2024??" in p.name and "생산자가격" in unicodedata.normalize("NFC", p.name)), None)
        if path is None:
            self.skipTest("사용자 2024 표가 없는 환경")
        result = P.load_workbook(path, "Korea(2010~2020)")
        self.assertIn("총거래표", result.df.iloc[0, 0])
        self.assertIn("국산거래표", result.df_local.iloc[0, 0])
        self.assertEqual(result.mid_ID_idx, (39, 35))
        self.assertEqual(result.mid_ID_idx_local, (39, 35))
        total = result.df.iloc[6:39, 2:35].to_numpy(float)
        domestic = result.df_local.iloc[6:39, 2:35].to_numpy(float)
        output = result.df.iloc[-1, 2:35].to_numpy(float)
        self.assertEqual(result.df.iloc[-1, 1], "총투입계")
        self.assertEqual(result.df.iloc[-2, 1], "부가가치계")
        for name, matrix in [("총투입계수(A)", total / output),
                             ("국산투입계수(Ad)", domestic / output),
                             ("생산유발계수", np.linalg.inv(np.eye(33) - domestic / output))]:
            with self.subTest(sheet=name):
                expected = pd.read_excel(path, sheet_name=name, header=None).iloc[6:39, 2:35].to_numpy(float)
                np.testing.assert_allclose(matrix, expected, atol=1e-12, rtol=1e-12)


if __name__ == "__main__":
    unittest.main()
