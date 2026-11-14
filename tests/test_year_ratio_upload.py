"""연도별 비율표의 해석·코드 대응과 기존 업로드 형식의 회귀 검사."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import zipfile

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iolib.batch_upload import inspect_batch_upload, prepare_batch_preview


class Upload(io.BytesIO):
    def __init__(self, contents=b"mock workbook", name="비율표.xlsx"):
        super().__init__(contents)
        self.name = name


def ratios():
    # 2024 숫자 헤더는 본표 밖의 참고 계산 열이다.
    return pd.DataFrame([
        ["전기 및 전자기기", "8.203%(12)", None, None, None],
        ["컴퓨터, 전자 및 광학기기", None, "20.380%(C09)", None, "999%(무시)"],
        ["정보통신 및 방송 서비스", "100%(20)", "95.320%(J)", None, "잘못된 참고값"],
    ], columns=["대분류/년도", "1990년", "2024년", "Unnamed: 3", 2024])


class YearRatioUploadTests(unittest.TestCase):
    def preview(self, frame=None, **kwargs):
        with patch("iolib.batch_upload.pd.read_excel", return_value=ratios() if frame is None else frame):
            return prepare_batch_preview(Upload(), "2024_대분류", **kwargs)

    def test_inspection_excludes_reference_columns(self):
        with patch("iolib.batch_upload.pd.read_excel", return_value=ratios()):
            meta = inspect_batch_upload(Upload(), "2024_대분류")
        self.assertEqual(meta["format"], "year_ratio")
        self.assertEqual(meta["years"], [1990, 2024])

    def test_percentages_become_batch_operations(self):
        frame, meta, preview, summary = self.preview(year=2024, source_codes=["C09", "J"])
        self.assertEqual(frame["from"].tolist(), ["C09", "J"])
        self.assertEqual(frame["to"].tolist(), ["6000", "6000"])
        self.assertEqual(frame["to_name"].tolist(), ["TMT", "TMT"])
        self.assertAlmostEqual(frame.iloc[0]["alpha"], 0.2038)
        self.assertAlmostEqual(frame.iloc[1]["alpha"], 0.9532)
        self.assertEqual(meta["year"], 2024)
        self.assertIn("20.3800%", preview[0])
        self.assertIn("잔여=79.6200%", summary[0])

    def test_numeric_padding_uses_actual_source_codes(self):
        frame, *_ = self.preview(year=1990, source_codes=["0012", "0020"])
        self.assertEqual(frame["from"].tolist(), ["0012", "0020"])

    def test_exact_code_takes_precedence_over_numeric_alias(self):
        frame, *_ = self.preview(year=1990, source_codes=["12", "0012", "20"])
        self.assertEqual(frame["from"].tolist(), ["12", "20"])

    def test_missing_or_ambiguous_sources_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "찾을 수 없습니다"):
            self.preview(year=2024, source_codes=["C09"])
        with self.assertRaisesRegex(ValueError, "여러 개"):
            self.preview(year=1990, source_codes=["012", "0012", "20"])
        with self.assertRaisesRegex(ValueError, "중복"):
            self.preview(year=1990, source_codes=["12", "12", "20"])

    def test_invalid_cells_are_not_silently_skipped(self):
        for value, message in [("20.380(C09)", "형식"), ("101%(C09)", "100%"), ("-1%(C09)", "0%")]:
            with self.subTest(value=value):
                frame = ratios()
                frame.loc[1, "2024년"] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.preview(frame, year=2024)

    def test_duplicate_sources_are_rejected_after_resolution(self):
        frame = ratios()
        frame.loc[2, "2024년"] = "10%(C09)"
        with self.assertRaisesRegex(ValueError, "두 번"):
            self.preview(frame, year=2024)

    def test_year_must_exist_and_have_entries(self):
        for year in [None, 2023]:
            with self.subTest(year=year), self.assertRaisesRegex(ValueError, "사용 가능한 연도"):
                self.preview(year=year)
        frame = ratios()
        frame["2024년"] = None
        with self.assertRaisesRegex(ValueError, "적용할 비율이 없습니다"):
            self.preview(frame, year=2024)

    def test_zero_and_full_percentages_are_valid(self):
        frame = ratios()
        frame.loc[1, "2024년"] = "0%(C09)"
        frame.loc[2, "2024년"] = "100%(J)"
        result, *_ = self.preview(frame, year=2024)
        self.assertEqual(result["alpha"].tolist(), [0.0, 1.0])

    def test_target_must_be_named_and_distinct(self):
        with self.assertRaisesRegex(ValueError, "코드와 이름"):
            self.preview(year=2024, target_name="")
        with self.assertRaisesRegex(ValueError, "같습니다"):
            self.preview(year=2024, target_code="C09")

    def test_standard_format_is_unchanged(self):
        source = pd.DataFrame({"from": ["11.0"], "to": ["6000"], "to_name": ["TMT"], "alpha": ["0.2038"]})
        result, meta, *_ = self.preview(source)
        self.assertEqual(meta["format"], "standard")
        self.assertEqual(result.to_dict("records"), [{"from": "11", "to": "6000", "to_name": "TMT", "alpha": 0.2038}])

    def test_zip_matching_and_repeated_reads_preserve_cursor(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as zip_file:
            zip_file.writestr("__MACOSX/ignored.xlsx", b"ignored")
            zip_file.writestr("2024_대분류.xlsx", b"mock workbook")
        upload = Upload(archive.getvalue(), "ratios.zip")
        upload.seek(7)
        with patch("iolib.batch_upload.pd.read_excel", return_value=ratios()):
            first = inspect_batch_upload(upload, "2024_대분류")
            result, second, *_ = prepare_batch_preview(upload, "2024_대분류", year=2024)
        self.assertEqual(first["match_mode"], "matched")
        self.assertEqual(second["matched_file"], "2024_대분류")
        self.assertEqual(upload.tell(), 7)
        self.assertEqual(len(result), 2)

    def test_plain_file_handle_cursor_is_preserved(self):
        class FileLike:
            name = "비율표.xlsx"
            def __init__(self):
                self.data = io.BytesIO(b"mock workbook")
            def tell(self): return self.data.tell()
            def seek(self, *args): return self.data.seek(*args)
            def read(self): return self.data.read()
        upload = FileLike()
        upload.seek(4)
        with patch("iolib.batch_upload.pd.read_excel", return_value=ratios()):
            inspect_batch_upload(upload, "2024_대분류")
            prepare_batch_preview(upload, "2024_대분류", year=2024)
        self.assertEqual(upload.tell(), 4)


if __name__ == "__main__":
    unittest.main()
