"""산업별 비율 입력, 검색·화면 이동·수정·복원을 실제 Streamlit 실행으로 검증한다."""

from copy import deepcopy
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
from fixtures import loaded_tables
from test_workbooks import excel_upload
from test_dashboard import Upload

REPO = Path(__file__).resolve().parents[1]


def send_grid(app, edits=None):
    """AppTest의 data_editor 입력은 브라우저처럼 요청마다 edit state로 전달한다."""
    key = app.session_state["_alpha_grid_key"]
    seed = app.session_state["_alpha_grid_seed"]
    values = {**app.session_state["alpha_draft"].percentages, **(edits or {})}
    changes = {
        i: {"percent": values.get(code, 0.0)} for i, code in enumerate(seed["code"])
    }
    app.session_state[key] = {
        "edited_rows": changes,
        "added_rows": [],
        "deleted_rows": [],
    }
    if edits is not None:
        # 실제 브라우저도 셀 편집 요청으로 먼저 다시 그린 뒤 활성 버튼을 누른다.
        app.run()
        return send_grid(app)
    return app


class StreamlitAlphaTests(unittest.TestCase):
    def setUp(self):
        from dashboard.upload import _load

        _load.clear()
        raw = loaded_tables()
        self.source = Upload(
            excel_upload({"총거래표": raw.df, "국산거래표": raw.df_local}).getvalue()
        )
        self.ratio = None
        uploader = patch(
            "streamlit.file_uploader",
            side_effect=lambda *a, **k: (
                self.source if k.get("key") == "source_file" else self.ratio
            ),
        )
        uploader.start()
        self.addCleanup(uploader.stop)
        resources = patch("dashboard.app.render_japan_data_sidebar")
        resources.start()
        self.addCleanup(resources.stop)

    def app(self):
        return AppTest.from_file(str(REPO / "app.py"), default_timeout=60).run()

    def healthy(self, app):
        self.assertEqual([e.message for e in app.exception], [])
        self.assertEqual([e.value for e in app.error], [])

    def test_percent_grid_apply_analysis_and_noncompounding_update(self):
        app = self.app()
        self.healthy(app)
        base = app.session_state["editor"]
        send_grid(app, {"S0": 20.38, "S1": 50}).button(
            key="alpha_apply_analyze"
        ).click().run()
        self.healthy(app)
        self.assertEqual(app.radio(key="workspace_view").value, "경제지표")
        self.assertEqual(
            app.session_state["editor"].operations[0]["batch_records"][0]["alpha"],
            0.2038,
        )
        self.assertIn("analysis", app.session_state)
        app.radio(key="workspace_view").set_value("산업 편집").run()
        self.assertEqual(
            app.session_state["alpha_draft"].percentages, {"S0": 20.38, "S1": 50.0}
        )
        self.assertTrue(app.button(key="alpha_apply").disabled)
        send_grid(app, {"S0": 40}).button(key="alpha_apply").click().run()
        self.healthy(app)
        result = app.session_state["editor"]
        self.assertEqual(len(result.operations), 1)
        self.assertEqual(result.mid, (9, 5))
        transform = np.array([[0.6, 0], [0, 0.5], [0.4, 0.5]])
        np.testing.assert_allclose(
            result.total.iloc[6:9, 2:5].to_numpy(float),
            transform @ base.total.iloc[6:8, 2:4].to_numpy(float) @ transform.T,
        )
        self.assertNotIn("analysis", app.session_state)
        app.button(key="undo_edit").click().run()
        self.healthy(app)
        self.assertEqual(app.session_state["alpha_draft"].percentages["S0"], 20.38)
        app.button(key="redo_edit").click().run()
        self.healthy(app)
        self.assertEqual(app.session_state["alpha_draft"].percentages["S0"], 40.0)

    def test_search_and_navigation_preserve_all_industries(self):
        app = self.app()
        send_grid(app, {"S0": 20, "S1": 30}).run()
        self.healthy(app)
        first_key = app.session_state["_alpha_grid_key"]
        send_grid(app).text_input(key="alpha_search").set_value("S1").run()
        self.assertNotEqual(first_key, app.session_state["_alpha_grid_key"])
        self.assertEqual(app.session_state["_alpha_grid_seed"]["code"].tolist(), ["S1"])
        send_grid(app, {"S1": 40}).run()
        self.assertEqual(
            app.session_state["alpha_draft"].percentages, {"S0": 20.0, "S1": 40.0}
        )
        app.radio(key="workspace_view").set_value("경제지표").run()
        self.assertTrue(app.info)
        app.radio(key="workspace_view").set_value("산업 편집").run()
        self.healthy(app)
        self.assertEqual(
            app.session_state["alpha_draft"].percentages, {"S0": 20.0, "S1": 40.0}
        )
        send_grid(app).text_input(key="alpha_search").set_value("no matches").run()
        self.assertEqual(len(app.session_state["_alpha_grid_seed"]), 0)
        app.button(key="alpha_apply").click().run()
        self.healthy(app)
        self.assertEqual(
            len(app.session_state["editor"].operations[0]["batch_records"]), 2
        )

    def test_bulk_fill_clear_and_invalid_input_are_reviewable(self):
        app = self.app()
        app.text_input(key="alpha_search").set_value("S0").run()
        app.number_input(key="alpha_fill_percent").set_value(25.0)
        app.button(key="alpha_fill").click().run()
        self.healthy(app)
        self.assertEqual(
            app.session_state["alpha_draft"].percentages, {"S0": 25.0, "S1": 0.0}
        )
        self.assertEqual(app.session_state["editor"].operations, ())
        send_grid(app, {"S0": 101}).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.error)
        self.assertTrue(app.button(key="alpha_apply").disabled)
        send_grid(app).button(key="alpha_clear").click().run()
        self.healthy(app)
        self.assertTrue(app.button(key="alpha_apply").disabled)
        send_grid(app, {"S0": 25}).text_input(key="alpha_target_code").set_value(
            "S1"
        ).run()
        self.assertTrue(app.error)
        self.assertEqual(app.session_state["editor"].operations, ())
        send_grid(app).text_input(key="alpha_target_code").set_value("NEW").run()
        self.healthy(app)
        send_grid(app).text_input(key="alpha_target_name").set_value("새 산업").run()
        send_grid(app).button(key="alpha_apply").click().run()
        self.healthy(app)
        self.assertIn("NEW", app.session_state["editor"].total.iloc[6:9, 0].tolist())

    def test_import_file_can_be_reviewed_and_edited_before_apply(self):
        buffer = BytesIO()
        pd.DataFrame(
            {"대분류/년도": ["산업 0", "산업 1"], "2024년": ["20.380%(S0)", "50%(S1)"]}
        ).to_excel(buffer, index=False)
        self.ratio = Upload(buffer.getvalue(), "ratios.xlsx")
        app = self.app()
        self.healthy(app)
        app.button(key="import_alpha").click().run()
        self.healthy(app)
        self.assertEqual(app.session_state["editor"].operations, ())
        self.assertEqual(
            app.session_state["alpha_draft"].percentages, {"S0": 20.38, "S1": 50.0}
        )
        send_grid(app, {"S1": 25}).button(key="alpha_apply").click().run()
        self.healthy(app)
        self.assertEqual(
            app.session_state["editor"].operations[0]["batch_records"][1]["alpha"], 0.25
        )
        app.button(key="reset_edits").click().run()
        self.healthy(app)
        self.assertEqual(app.session_state["editor"].operations, ())
        app.button(key="undo_edit").click().run()
        self.healthy(app)
        self.assertEqual(app.session_state["editor"].mid, (9, 5))

    def test_same_filename_new_source_clears_draft_and_history(self):
        app = self.app()
        send_grid(app, {"S0": 25}).button(key="alpha_apply").click().run()
        self.assertTrue(app.session_state["undo_stack"])
        old = deepcopy(app.session_state["editor"].original)
        old.df.iat[6, 2] = 19.0
        self.source = Upload(
            excel_upload({"총거래표": old.df, "국산거래표": old.df_local}).getvalue()
        )
        app.run()
        self.healthy(app)
        self.assertEqual(app.session_state["editor"].operations, ())
        self.assertTrue(app.button(key="undo_edit").disabled)
        self.assertEqual(
            app.session_state["alpha_draft"].percentages, {"S0": 0.0, "S1": 0.0}
        )
        self.assertIsNone(app.session_state["alpha_draft"].applied_percentages)

    def test_file_transfer_to_existing_sector_remains_available(self):
        buffer = BytesIO()
        pd.DataFrame(
            [{"from": "S0", "to": "S1", "to_name": "산업 1", "alpha": 0.25}]
        ).to_excel(buffer, index=False)
        self.ratio = Upload(buffer.getvalue(), "existing.xlsx")
        app = self.app()
        base = app.session_state["editor"]
        app.button(key="apply_batch").click().run()
        self.healthy(app)
        changed = app.session_state["editor"]
        self.assertEqual(changed.mid, base.mid)
        transform = np.array([[0.75, 0], [0.25, 1]])
        np.testing.assert_allclose(
            changed.total.iloc[6:8, 2:4].to_numpy(float),
            transform @ base.total.iloc[6:8, 2:4].to_numpy(float) @ transform.T,
        )
        # Streamlit 1.52 AppTest는 expander 안의 rerun 직후 이전 노드도 남긴다.
        # 브라우저의 완료된 화면에 해당하는 다음 실행에서 버튼 상태를 검사한다.
        app.run()
        self.assertTrue(app.button(key="apply_batch").disabled)
