import unittest
import numpy as np
import pandas as pd
from fixtures import loaded_tables
from iolib import EditingSession, get_mode_params
from iolib.editing import validate_batch_edit


class EditingTests(unittest.TestCase):
    def editor(self):
        return EditingSession.from_loaded(
            loaded_tables(), get_mode_params("Korea(2010~2020)")
        )

    def test_insert_transfer_and_analysis_preserve_both_tables(self):
        editor = self.editor()
        edited = editor.apply(
            {"type": "insert_sector", "code": "NEW", "name": "새 산업"}
        )
        edited = edited.apply(
            {"type": "transfer", "from": "S0", "to": "NEW", "alpha": 0.3}
        )
        self.assertEqual(editor.mid, (8, 4))
        self.assertEqual(edited.mid, (9, 5))
        self.assertEqual(edited.mid_local, edited.mid)
        for before, after in (
            (editor.total, edited.total),
            (editor.domestic, edited.domestic),
        ):
            self.assertAlmostEqual(
                before.iloc[6:8, 2:4].to_numpy(float).sum(),
                after.iloc[6:9, 2:5].to_numpy(float).sum(),
            )
        first, second = edited.analyze(), edited.analyze()
        np.testing.assert_array_equal(first.total.inverse, second.total.inverse)

    def test_batch_self_transactions_match_pxp_transformation(self):
        editor = self.editor()
        records = [
            {"from": "S0", "to": "N1", "to_name": "신규1", "alpha": 0.2},
            {"from": "S0", "to": "N2", "to_name": "신규2", "alpha": 0.3},
        ]
        edited = editor.apply({"type": "batch_apply", "batch_records": records})
        p = np.array([[0.5, 0], [0, 1], [0.2, 0], [0.3, 0]])
        x = editor.total.iloc[6:8, 2:4].to_numpy(float)
        np.testing.assert_allclose(
            edited.total.iloc[6:10, 2:6].to_numpy(float), p @ x @ p.T
        )
        self.assertAlmostEqual(
            x.sum(), edited.total.iloc[6:10, 2:6].to_numpy(float).sum()
        )
        self.assertEqual(editor.names, {})

    def test_failed_edit_leaves_original_and_names_untouched(self):
        editor = self.editor()
        original = editor.total.copy()
        for op in [
            {"type": "insert_sector", "code": "S0", "name": "중복"},
            {"type": "transfer", "from": "S0", "to": "S0", "alpha": 0.1},
            {"type": "transfer", "from": "missing", "to": "S1", "alpha": 0.1},
            {
                "type": "batch_apply",
                "batch_records": [
                    {"from": "missing", "to": "NEW", "to_name": "신규", "alpha": 0.5}
                ],
            },
        ]:
            with self.subTest(op=op), self.assertRaises(ValueError):
                editor.apply(op)
            pd.testing.assert_frame_equal(editor.total, original)
            self.assertEqual(editor.names, {})

    def test_domestic_failure_is_atomic(self):
        editor = self.editor()
        editor.domestic.iloc[6, 0] = "BROKEN"
        original = editor.total.copy()
        with self.assertRaises(ValueError):
            editor.apply({"type": "transfer", "from": "S0", "to": "S1", "alpha": 0.5})
        pd.testing.assert_frame_equal(editor.total, original)
        self.assertEqual(editor.operations, ())

    def test_remove_zero_replays_identical_positions(self):
        editor = self.editor().apply(
            {"type": "insert_sector", "code": "ZERO", "name": "빈 산업"}
        )
        edited = editor.apply({"type": "remove_zero"})
        self.assertEqual(edited.mid, (8, 4))
        self.assertEqual(
            edited.total.iloc[6:8, 0].tolist(), edited.domestic.iloc[6:8, 0].tolist()
        )
        self.assertEqual(
            edited.operations[-1]["remove_positions"]["zero_row_indices"], [8]
        )

    def test_negative_reduction_includes_last_sector(self):
        editor = self.editor()
        editor.total.iloc[7, 3] = -4.0
        edited = editor.apply({"type": "reduce_negative"})
        self.assertEqual(edited.total.iloc[7, 3], -2.0)
        self.assertEqual(edited.mid, editor.mid)
        self.assertEqual(edited.total.iloc[-1, 3], 102.0)

    def test_batch_rejects_nonfinite_out_of_range_and_overallocated_ratios(self):
        for ratios in [[-1], [1.01], [float("nan")], [float("inf")], [0.6, 0.5]]:
            frame = pd.DataFrame(
                [
                    {"from": "S0", "to": f"N{i}", "to_name": f"신규{i}", "alpha": a}
                    for i, a in enumerate(ratios)
                ]
            )
            with self.subTest(ratios=ratios), self.assertRaises(ValueError):
                validate_batch_edit(frame)

    def test_batch_code_lookup_excludes_metadata(self):
        editor = self.editor()
        editor.total.iat[0, 0] = "S0"
        records = [{"from": "S0", "to": "NEW", "to_name": "신규", "alpha": 0.25}]
        result = editor.apply({"type": "batch_apply", "batch_records": records})
        self.assertEqual(result.mid, (9, 5))
        self.assertAlmostEqual(result.total.iloc[6:9, 2:5].to_numpy(float).sum(), 45.0)
