import subprocess
import sys
import unittest
import numpy as np
import pandas as pd
from fixtures import loaded_tables
from iolib import calculate_leontief, analyze_tables, EditingSession, get_mode_params


class AnalysisTests(unittest.TestCase):
    def test_exact_inverse_linkages_and_independent_index(self):
        x = np.array([[20.0, 6.0], [4.0, 15.0]])
        result = calculate_leontief(x, pd.Series([100.0, 90.0], index=["foo", "bar"]))
        expected = x / [100.0, 90.0]
        np.testing.assert_allclose(result.coefficients, expected)
        np.testing.assert_allclose(
            (np.eye(2) - expected) @ result.inverse, np.eye(2), atol=1e-14
        )
        self.assertAlmostEqual(result.forward_linkage.mean(), 1)
        self.assertAlmostEqual(result.backward_linkage.mean(), 1)

    def test_complete_pipeline_gdp_and_domestic_multiplier(self):
        loaded = loaded_tables()
        original = loaded.df.copy(deep=True)
        result = analyze_tables(
            loaded.df,
            loaded.df_local,
            first_idx=(6, 2),
            mid=loaded.mid_ID_idx,
            mid_local=loaded.mid_ID_idx_local,
        )
        a = np.array([[0.2, 0.06], [0.04, 0.15]])
        l = np.linalg.inv(np.eye(2) - a)
        ld = np.linalg.inv(np.eye(2) - a * 0.8)
        v = 1 - a.sum(axis=0)
        y = 100 - a.sum(axis=1) * 100
        np.testing.assert_allclose(
            result.frames["GDP"].iloc[1:, 2].to_numpy(float), v * (l @ y)
        )
        np.testing.assert_allclose(
            result.frames["부가가치유발효과"].iloc[1:, 2].to_numpy(float), v @ ld
        )
        self.assertAlmostEqual(
            result.statistics["g1_total"], result.statistics["GDP_total"]
        )
        self.assertAlmostEqual(
            result.statistics["g1_total"], result.statistics["g2_total"]
        )
        pd.testing.assert_frame_equal(loaded.df, original)

    def test_invalid_matrices_and_zero_output(self):
        for matrix, output in [
            (np.ones((2, 3)), [1, 1]),
            ([[np.nan]], [1]),
            ([[1]], [0]),
            ([[1]], [1]),
            ([[0]], [np.inf]),
        ]:
            with self.subTest(matrix=matrix), self.assertRaises(ValueError):
                calculate_leontief(matrix, output)
        np.testing.assert_array_equal(calculate_leontief([[0]], [0]).inverse, [[1]])

    def test_invalid_domestic_order_is_rejected(self):
        loaded = loaded_tables()
        loaded.df_local.iloc[6:8, 0] = ["S1", "S0"]
        with self.assertRaisesRegex(ValueError, "순서"):
            EditingSession.from_loaded(loaded, get_mode_params("Korea(2010~2020)"))

    def test_library_imports_without_ui_or_plot_dependencies(self):
        code = "import sys; sys.modules['streamlit']=None; sys.modules['matplotlib']=None; import iolib; from iolib import calculate_leontief; assert calculate_leontief([[0.2]],[1]).inverse[0,0] == 1.25"
        subprocess.run([sys.executable, "-c", code], check=True)
