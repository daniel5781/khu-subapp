"""백분율 변환, 재적용 없는 수정, 초안 보존과 편집 복원."""

from dataclasses import replace
from io import BytesIO
import unittest
import numpy as np
import pandas as pd
from fixtures import loaded_tables
from iolib import EditingSession, get_mode_params
from iolib.allocations import (
    sector_catalog,
    percentage_records,
    percentage_preview,
    percentages_from_records,
)
from dashboard import workspace as w
from dashboard.alpha import _xlsx


def editor():
    return EditingSession.from_loaded(
        loaded_tables(), get_mode_params("Korea(2010~2020)")
    )


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = sector_catalog(editor())

    def test_percentages_are_exact_and_preserve_leading_zero_codes(self):
        self.catalog.loc[0, "code"] = "0012"
        records = percentage_records(
            self.catalog, {"0012": 20.38, "S1": None}, "6000", "TMT"
        )
        self.assertEqual(
            records, [{"from": "0012", "to": "6000", "to_name": "TMT", "alpha": 0.2038}]
        )
        preview = percentage_preview(records, self.catalog)
        self.assertEqual(preview.iloc[0]["남는 비율 (%)"], 79.62)
        self.assertEqual(
            percentage_records(self.catalog, {"0012": 0, "S1": ""}, "6000", "TMT"), []
        )
        self.assertEqual(
            percentage_records(self.catalog, {"S1": 100}, "6000", "TMT")[0]["alpha"],
            1.0,
        )

    def test_invalid_plan_is_rejected_before_editing(self):
        for value in (-0.001, 100.001, float("nan"), float("inf"), "oops"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                percentage_records(self.catalog, {"S0": value}, "6000", "TMT")
        for values, code, name in [
            ({"missing": 20}, "6000", "TMT"),
            ({"S0": 20}, "S1", "existing"),
            ({"S0": 20}, "6000", ""),
            ({"S0": 20}, "", "TMT"),
        ]:
            with self.subTest(code=code, name=name), self.assertRaises(ValueError):
                percentage_records(self.catalog, values, code, name)

    def test_saved_excel_round_trips_into_percentage_draft(self):
        original = percentage_records(
            self.catalog, {"S0": 20.38, "S1": 50}, "NEW", "새 산업"
        )
        frame = pd.read_excel(BytesIO(_xlsx(original)), dtype={"from": str, "to": str})
        values, code, name = percentages_from_records(
            frame.to_dict("records"), self.catalog
        )
        self.assertEqual(values, {"S0": 20.38, "S1": 50.0})
        self.assertEqual(percentage_records(self.catalog, values, code, name), original)
        with self.assertRaisesRegex(ValueError, "하나의 대상"):
            percentages_from_records(
                original
                + [{"from": "S0", "to": "OTHER", "to_name": "다른 산업", "alpha": 0.1}],
                self.catalog,
            )


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.state = {"editor": editor()}
        w.ensure_draft(self.state)

    def percentages(self, **values):
        draft = self.state["alpha_draft"]
        self.state["alpha_draft"] = replace(
            draft, percentages={**draft.percentages, **values}
        )

    def test_removing_split_restores_baseline_and_is_undoable(self):
        base = self.state["editor"]
        self.percentages(S0=20)
        w.apply_alpha(self.state)
        split = self.state["editor"]
        self.assertTrue(w.remove_alpha_split(self.state))
        self.assertIs(self.state["editor"], base)
        self.assertFalse(self.state["alpha_draft"].dirty)
        self.assertIsNone(self.state["alpha_draft"].applied_percentages)
        w.undo(self.state)
        self.assertIs(self.state["editor"], split)
        self.assertEqual(self.state["alpha_draft"].percentages["S0"], 20)

    def test_apply_and_update_use_same_baseline_for_both_tables(self):
        base = self.state["editor"]
        self.percentages(S0=20, S1=40)
        self.assertTrue(w.apply_alpha(self.state))
        result = self.state["editor"]
        self.assertFalse(w.apply_alpha(self.state))
        self.assertIs(self.state["editor"], result)
        self.assertEqual(len(self.state["undo_stack"]), 1)
        self.percentages(S0=50, S1=10)
        w.calculate(self.state)
        self.assertIn("analysis", self.state)
        w.apply_alpha(self.state)
        result = self.state["editor"]
        self.assertNotIn("analysis", self.state)
        self.assertEqual(len(result.operations), 1)
        transform = np.array([[0.5, 0], [0, 0.9], [0.5, 0.1]])
        for old, new in ((base.total, result.total), (base.domestic, result.domestic)):
            np.testing.assert_allclose(
                new.iloc[6:9, 2:5].to_numpy(float),
                transform @ old.iloc[6:8, 2:4].to_numpy(float) @ transform.T,
            )
        self.assertTrue(w.undo(self.state))
        self.assertEqual(self.state["alpha_draft"].percentages, {"S0": 20, "S1": 40})
        self.assertTrue(w.redo(self.state))
        self.assertEqual(self.state["alpha_draft"].percentages, {"S0": 50, "S1": 10})
        pd.testing.assert_frame_equal(self.state["editor"].total, result.total)

    def test_invalid_update_retains_previous_edit_and_history(self):
        self.percentages(S0=20)
        w.apply_alpha(self.state)
        before = self.state["editor"]
        self.percentages(S0=101)
        with self.assertRaises(ValueError):
            w.apply_alpha(self.state)
        self.assertIs(before, self.state["editor"])
        self.assertEqual(len(self.state["undo_stack"]), 1)
        self.assertTrue(self.state["alpha_draft"].dirty)

    def test_search_uses_new_keys_and_never_reassigns_row_edits(self):
        catalog = sector_catalog(self.state["editor"])
        seed, key = w.grid_seed(self.state, catalog, "S0")
        self.state[key] = {"edited_rows": {0: {"percent": 20}}}
        w.capture_grid_changes(self.state, key, seed)
        seed2, key2 = w.grid_seed(self.state, catalog, "S1")
        self.assertNotEqual(key, key2)
        self.state[key2] = {"edited_rows": {0: {"percent": 30}}}
        w.capture_grid_changes(self.state, key2, seed2)
        w.capture_grid_changes(self.state, key, seed)  # stale callback must be ignored
        self.assertEqual(self.state["alpha_draft"].percentages, {"S0": 20, "S1": 30})
        all_rows, _ = w.grid_seed(self.state, catalog, "")
        self.assertEqual(all_rows["percent"].tolist(), [20, 30])
        # Clearing the grid's edit diff restores its baseline for that view.
        self.state[self.state["_alpha_grid_key"]] = {
            "edited_rows": {0: {"percent": None}}
        }
        w.capture_grid_changes(self.state, self.state["_alpha_grid_key"], all_rows)
        self.assertIsNone(self.state["alpha_draft"].percentages["S0"])

    def test_other_edits_reset_draft_and_can_be_undone_and_redone(self):
        self.percentages(S0=25)
        w.apply_alpha(self.state)
        split = self.state["editor"]
        w.apply_operation(
            self.state, {"type": "insert_sector", "code": "OTHER", "name": "추가"}
        )
        self.assertIsNone(self.state["alpha_draft"])
        w.undo(self.state)
        self.assertIs(self.state["editor"], split)
        self.assertEqual(self.state["alpha_draft"].percentages["S0"], 25)
        w.redo(self.state)
        self.assertEqual(self.state["editor"].mid, (10, 6))
        w.reset_edits(self.state)
        self.assertEqual(self.state["editor"].operations, ())
        w.undo(self.state)
        self.assertEqual(self.state["editor"].mid, (10, 6))
        w.undo(self.state)
        w.apply_operation(self.state, {"type": "reduce_negative"})
        self.assertEqual(self.state["redo_stack"], [])

    def test_history_is_bounded_and_import_is_only_a_draft(self):
        records = [{"from": "S0", "to": "NEW", "to_name": "신규", "alpha": 0.2038}]
        before = self.state["editor"]
        w.import_alpha(self.state, records)
        self.assertIs(self.state["editor"], before)
        self.assertEqual(self.state["alpha_draft"].percentages["S0"], 20.38)
        self.assertTrue(self.state["alpha_draft"].dirty)
        for i in range(w.HISTORY_LIMIT + 2):
            w.apply_operation(
                self.state,
                {"type": "insert_sector", "code": f"N{i}", "name": f"산업{i}"},
            )
        self.assertEqual(len(self.state["undo_stack"]), w.HISTORY_LIMIT)
