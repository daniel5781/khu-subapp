from io import BytesIO
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from streamlit.testing.v1 import AppTest
from fixtures import loaded_tables
from test_workbooks import excel_upload
from dashboard.state import collect_exports, reset_source, invalidate_results
from iolib import EditingSession, get_mode_params

REPO = Path(__file__).resolve().parents[1]


class Upload(BytesIO):
    def __init__(self, data, name="2024.xlsx"):
        super().__init__(data)
        self.name = name


def button(app, label):
    return next(item for item in app.button if item.label == label)


class DashboardTests(unittest.TestCase):
    def setUp(self):
        from dashboard.upload import _load

        _load.clear()
        self.raw = loaded_tables()
        self.source = Upload(
            excel_upload(
                {"총거래표": self.raw.df, "국산거래표": self.raw.df_local}
            ).getvalue()
        )
        self.upload = patch(
            "streamlit.file_uploader",
            side_effect=lambda *args, **kw: (
                self.source if kw.get("key") == "source_file" else None
            ),
        )
        self.upload.start()
        self.addCleanup(self.upload.stop)
        # 원자료 ZIP 렌더링은 자체 다운로드 테스트가 담당한다.
        self.sidebar = patch("dashboard.app.render_japan_data_sidebar")
        self.sidebar.start()
        self.addCleanup(self.sidebar.stop)

    def app(self):
        return AppTest.from_file(str(REPO / "app.py"), default_timeout=60).run()

    def assert_healthy(self, app):
        self.assertEqual([item.message for item in app.exception], [])
        self.assertEqual([item.value for item in app.error], [])

    def test_no_upload_is_a_valid_start_state(self):
        self.source = None
        app = self.app()
        self.assert_healthy(app)
        self.assertGreater(len(app.info), 0)

    def test_forms_analysis_methods_and_edit_invalidation(self):
        app = self.app()
        self.assert_healthy(app)
        app.text_input(key="new_code").set_value("NEW")
        app.text_input(key="new_name").set_value("신규 산업")
        button(app, "산업 추가").click().run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state["editor"].mid, (9, 5))
        app.text_input(key="origin_code").set_value("S0")
        app.text_input(key="target_code").set_value("NEW")
        app.number_input(key="transfer_alpha").set_value(0.25)
        button(app, "값 옮기기").click().run()
        self.assert_healthy(app)
        app.button(key="analyze").click().run()
        self.assert_healthy(app)
        inverse = app.session_state["analysis"].total.inverse.copy()
        app.number_input(key="threshold_input").set_value(999.0)
        button(app, "설정 적용하기 (Apply)").click().run()
        self.assert_healthy(app)
        self.assertEqual(
            app.session_state["network_result"].weighted_graph.number_of_edges(), 0
        )
        np.testing.assert_array_equal(
            app.session_state["analysis"].total.inverse, inverse
        )
        app.radio(key="network_method").set_value(
            "Method B: Leontief 급수전개 (Series Expansion)"
        ).run()
        self.assert_healthy(app)
        self.assertIn("binary_hits", app.session_state["network_frames"])
        app.number_input(key="mb_epsilon").set_value(0.5).run()
        self.assert_healthy(app)
        app.text_input(key="new_code").set_value("OTHER")
        app.text_input(key="new_name").set_value("추가 산업")
        button(app, "산업 추가").click().run()
        self.assert_healthy(app)
        self.assertNotIn("analysis", app.session_state)
        self.assertNotIn("network_frames", app.session_state)

    def test_same_filename_new_contents_clears_edits(self):
        app = self.app()
        app.text_input(key="new_code").set_value("NEW")
        app.text_input(key="new_name").set_value("신규")
        button(app, "산업 추가").click().run()
        other = loaded_tables()
        other.df.iat[6, 2] = 19.0
        self.source = Upload(
            excel_upload(
                {"총거래표": other.df, "국산거래표": other.df_local}
            ).getvalue()
        )
        app.run()
        self.assert_healthy(app)
        self.assertEqual(app.session_state["editor"].operations, ())
        self.assertEqual(app.session_state["editor"].mid, (8, 4))

    def test_invalid_input_is_user_error_and_recovery_works(self):
        self.source = Upload(b"not an excel file")
        app = self.app()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.source = Upload(
            excel_upload(
                {"총거래표": self.raw.df, "국산거래표": self.raw.df_local}
            ).getvalue()
        )
        app.run()
        self.assert_healthy(app)
        app.text_input(key="origin_code").set_value("missing")
        app.text_input(key="target_code").set_value("S1")
        button(app, "값 옮기기").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["editor"].operations, ())


class ExportAndStateTests(unittest.TestCase):
    def test_exports_include_current_analysis_network_and_original_boundaries(self):
        editor = EditingSession.from_loaded(
            loaded_tables(), get_mode_params("Korea(2010~2020)")
        )
        original = editor.original.df.copy()
        editor = editor.apply({"type": "insert_sector", "code": "NEW", "name": "신규"})
        frames = collect_exports(editor, editor.analyze(), {"network_binary": original})
        self.assertEqual(frames["uploaded_matrix_X"].shape, (5, 5))
        self.assertEqual(frames["edited_matrix_X"].shape, (6, 6))
        self.assertIn("GDP", frames)
        self.assertIn("network_binary", frames)
        from iolib.exports import make_zip_bytes
        import zipfile

        with zipfile.ZipFile(BytesIO(make_zip_bytes(frames))) as archive:
            self.assertEqual(
                set(archive.namelist()), {f"{name}.csv" for name in frames}
            )
            self.assertTrue(archive.read("GDP.csv").startswith(b"\xef\xbb\xbf"))

    def test_invalidation_and_source_reset(self):
        state = {
            "source_signature": 1,
            "editor": "keep",
            "analysis": 1,
            "network_frames": 1,
            "threshold": 1,
        }
        self.assertFalse(reset_source(state, 1))
        invalidate_results(state)
        self.assertEqual(state, {"source_signature": 1, "editor": "keep"})
        self.assertTrue(reset_source(state, 2))
        self.assertEqual(state, {"source_signature": 2})
