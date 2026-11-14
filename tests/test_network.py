import unittest
from unittest.mock import patch
import numpy as np
from fixtures import workbook_table
from iolib.network import analyze_threshold, extract_series_network, graph_from_matrix
from iolib.network_analysis import analyze_network
from iolib.centrality import calculate_network_centralities


class NetworkTests(unittest.TestCase):
    def template(self, n):
        table, mid = workbook_table(np.zeros((n, n)))
        return table.iloc[4 : mid[0], : mid[1]].reset_index(drop=True)

    def test_threshold_survival_excludes_diagonal_zero_edges_and_equality(self):
        result = analyze_threshold([[1, 0.01], [0.01, 1]])
        self.assertEqual(result.threshold, 0)
        np.testing.assert_array_equal(result.survival, [1, 0])
        self.assertEqual(result.isolated_nodes, ())
        self.assertTrue(np.all(result.survival <= 1))

    def test_zero_and_single_sector_networks(self):
        for n in (1, 3):
            with self.subTest(n=n):
                matrix = np.zeros((n, n))
                threshold = analyze_threshold(matrix)
                self.assertEqual(len(threshold.isolated_nodes), n)
                result = analyze_network(matrix, self.template(n))
                self.assertEqual(len(result.binary_graph), n)
                self.assertEqual(result.binary_graph.number_of_edges(), 0)
                self.assertTrue(
                    np.isfinite(
                        result.binary_centralities[4].iloc[:, 2:].to_numpy(float)
                    ).all()
                )
                np.testing.assert_array_equal(
                    result.binary_centralities[4].iloc[:, 2:].to_numpy(float), 0
                )

    def test_graph_orientation_and_nonmutation(self):
        matrix = np.array([[1, 2], [3, 1.0]])
        before = matrix.copy()
        result = analyze_network(matrix, self.template(2))
        self.assertEqual(result.weighted_graph[1][0]["weight"], 2)
        self.assertEqual(result.weighted_graph[0][1]["weight"], 3)
        self.assertEqual(result.binary_graph[0][1]["weight"], 1)
        np.testing.assert_array_equal(matrix, before)
        np.testing.assert_array_equal(
            np.diag(result.frames["network_weighted"].iloc[2:, 2:].to_numpy(float)), 0
        )

    def test_binary_hits_ignores_original_edge_weights(self):
        matrix = np.array([[0, 1, 4], [7, 0, 1], [1, 9, 0.0]])
        graph = graph_from_matrix(matrix)
        binary = graph_from_matrix(matrix, binary=True)
        actual = calculate_network_centralities(graph, self.template(3), False)[4]
        expected = calculate_network_centralities(binary, self.template(3), False)[4]
        np.testing.assert_allclose(
            actual.iloc[:, 2:].to_numpy(float), expected.iloc[:, 2:].to_numpy(float)
        )
        self.assertEqual(graph[1][2]["weight"], 9)

    def test_degenerate_hits_are_finite_nonnegative_normalized_singular_vectors(self):
        graph = graph_from_matrix([[0.0, 1.0], [1.0, 0.0]])
        for bad in (
            ({0: float("inf"), 1: float("-inf")}, {0: float("nan"), 1: 0.0}),
            ({0: 1e16, 1: -1e16}, {0: -1e16, 1: 1e16}),
        ):
            with (
                self.subTest(bad=bad),
                patch("iolib.centrality.nx.hits", return_value=bad),
            ):
                scores = (
                    calculate_network_centralities(graph, self.template(2), False)[4]
                    .iloc[:, 2:]
                    .to_numpy(float)
                )
                self.assertTrue(np.isfinite(scores).all())
                self.assertTrue((scores >= 0).all())
                np.testing.assert_allclose(scores.sum(axis=0), 1.0)
                # 두 산업의 상호 연결은 h = A a, a = Aᵀ h를 만족한다.
                np.testing.assert_allclose(scores[:, 0], scores[::-1, 1])
        scores = (
            calculate_network_centralities(graph, self.template(2), False)[4]
            .iloc[:, 2:]
            .to_numpy(float)
        )
        self.assertTrue(np.isfinite(scores).all())
        self.assertTrue((scores >= -1e-12).all())

    def test_series_returns_previous_step_at_structural_convergence(self):
        matrix = np.array([[0.2, 0.1], [0.3, 0.2]])
        result = extract_series_network(matrix)
        expected = matrix.copy()
        np.fill_diagonal(expected, 0)
        self.assertEqual(result.info["final_t"], 2)
        self.assertTrue(result.info["converged"])
        np.testing.assert_allclose(result.weighted, expected)
        one = extract_series_network(matrix, max_iter=1)
        self.assertFalse(one.info["converged"])
        np.testing.assert_allclose(one.weighted, expected)

    def test_invalid_extraction_parameters_raise(self):
        for kwargs in (
            {"epsilon": 0},
            {"epsilon": float("nan")},
            {"delta": 0},
            {"max_iter": 0},
            {"max_iter": 1.5},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                extract_series_network(np.eye(2), **kwargs)
        for matrix in ([[float("inf")]], np.ones((2, 3)), np.empty((0, 0))):
            with self.assertRaises(ValueError):
                analyze_threshold(matrix)
