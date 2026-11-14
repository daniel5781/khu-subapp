from io import BytesIO
from pathlib import Path
import unittest
import os
from unittest.mock import patch
import numpy as np
import pandas as pd
from fixtures import workbook_table, loaded_tables
from iolib import preprocessing as p
from iolib import EditingSession
from iolib.loading import get_mid_ID_idx

REPO = Path(__file__).resolve().parents[1]


def excel_upload(sheets):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name, index=False, header=False)
    buffer.seek(0)
    return buffer


class WorkbookTests(unittest.TestCase):
    def setUp(self):
        self.data_dir = patch.dict(os.environ, {"KHU_SUBAPP_DATA_DIR": str(REPO)})
        self.data_dir.start()
        self.addCleanup(self.data_dir.stop)

    def test_legacy_korea_layout_keeps_numeric_contract(self):
        total, mid = workbook_table(first_idx=(5, 2))
        domestic = total.copy()
        total.loc[len(total)] = ["추가 행"] + [None] * (total.shape[1] - 1)
        loaded = p.load_workbook(
            excel_upload({"총거래표": total, "국산거래표": domestic}),
            "Korea(1990~2005)",
        )
        result = EditingSession.from_loaded(
            loaded, p.get_mode_params("Korea(1990~2005)")
        ).analyze()
        self.assertEqual(result.total.inverse.shape, (2, 2))
        self.assertEqual(loaded.mid_ID_idx, mid)

    def test_manual_mode_uses_custom_start_instead_of_integer(self):
        table, mid = workbook_table(first_idx=(3, 2))
        result = p.load_workbook(
            excel_upload({"총거래표": table, "국산거래표": table}),
            "Manual",
            first_idx=(3, 2),
        )
        self.assertEqual(result.mid_ID_idx, mid)
        self.assertEqual(p.get_mode_params("Manual").first_idx, (6, 2))

    def test_boundary_detection_handles_first_sector_with_zero_transactions(self):
        table, mid = workbook_table(np.array([[0.0, 0.0], [0.0, 20.0]]))
        self.assertEqual(get_mid_ID_idx(table, (6, 2)), mid)

    def test_japan_total_import_derives_domestic_and_total_domestic_does_not(self):
        total, mid = workbook_table()
        imp, _ = workbook_table(np.array([[2.0, 0.6], [0.4, 1.5]]))
        domestic = total.copy()
        domestic.iloc[6:8, 2:4] = total.iloc[6:8, 2:4].to_numpy(float) - imp.iloc[
            6:8, 2:4
        ].to_numpy(float)
        for sheets in (
            {"수입거래표": imp, "총거래표": total},
            {"국산거래표": domestic, "총거래표": total},
        ):
            with self.subTest(sheets=list(sheets)):
                result = p.load_workbook(excel_upload(sheets), "Japan(2000~2020)")
                np.testing.assert_allclose(
                    result.df_local.iloc[6:8, 2:4].to_numpy(float),
                    domestic.iloc[6:8, 2:4].to_numpy(float),
                )

    def test_domestic_sheet_does_not_require_value_added_rows(self):
        loaded = loaded_tables()
        from dataclasses import replace

        short = replace(loaded, df_local=loaded.df_local.iloc[:9])
        self.assertEqual(
            EditingSession.from_loaded(short, p.get_mode_params("Japan(2000~2020)"))
            .analyze()
            .domestic.inverse.shape,
            (2, 2),
        )

    def test_bundled_japan_workbooks_end_to_end(self):
        paths = [
            f
            for f in (REPO / "일본_산업연관표_연도별_자료").rglob("*.xlsx")
            if "한국어" in f.name and "대분류" in f.name and "수입거래표" in f.name
        ]
        self.assertEqual(len(paths), 5)
        for path in paths:
            with self.subTest(workbook=path.name):
                loaded = p.load_workbook(path, "Japan(2000~2020)")
                result = EditingSession.from_loaded(
                    loaded, p.get_mode_params("Japan(2000~2020)")
                ).analyze()
                self.assertTrue(np.isfinite(result.domestic.inverse).all())
                self.assertAlmostEqual(result.total.forward_linkage.mean(), 1)

    def test_us_all_bundled_years_both_classifications(self):
        for mode in ("US(Sector 2000~2024)", "US(Summary 2000~2024)"):
            years = p.available_us_years(mode)
            self.assertTrue(years)
            for year in years:
                with self.subTest(mode=mode, year=year):
                    loaded = p.load_workbook(
                        p.us_use_file_path(mode), mode, us_year=year
                    )
                    result = EditingSession.from_loaded(
                        loaded, p.get_mode_params(mode)
                    ).analyze()
                    n = 15 if "Sector" in mode else 71
                    self.assertEqual(result.total.inverse.shape, (n, n))
                    self.assertTrue(np.isfinite(result.domestic.inverse).all())
