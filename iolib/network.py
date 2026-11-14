"""네트워크 추출. 순수 계산 결과와 진단 데이터를 반환하고 화면은 그리지 않는다.

기존 threshold_count / extract_network_leontief API는 유지한다.
신규 호출은 analyze_threshold / extract_series_network를 사용한다.
Method B의 수렴은 연결 개수의 안정화이며 행렬 급수 자체의 수렴과는 다르다.
"""

from dataclasses import dataclass
import numpy as np
import networkx as nx
from .validation import square_matrix
from .centrality import calculate_network_centralities as calculate_network_centralities
from .structural import (
    calculate_kim_metrics as calculate_kim_metrics,
    calculate_standard_metrics as calculate_standard_metrics,
)


@dataclass(frozen=True)
class ThresholdResult:
    threshold: float
    distance_threshold: float
    stability_threshold: float
    thresholds: np.ndarray
    survival: np.ndarray
    slope_thresholds: np.ndarray
    slope_changes: np.ndarray
    adjusted: bool
    isolated_nodes: tuple[int, ...]


@dataclass(frozen=True)
class SeriesResult:
    weighted: np.ndarray
    binary: np.ndarray
    info: dict


def analyze_threshold(matrix, step=0.01):
    """거리 최소화 후 고립 노드를 줄이도록 임계값을 낮춘다.

    실제 적용과 동일하게 값 > 임계값인 비대각 연결만 센다.
    원래 고립된 노드가 있으면 0까지 낮춘 뒤 그 노드 번호를 반환한다.
    """
    data = square_matrix(matrix)
    if not np.isfinite(step) or step <= 0:
        raise ValueError("임계값 간격은 양수여야 합니다.")
    np.fill_diagonal(data, 0)
    n = len(data)
    maximum = max(float(data.max()), 0.0)
    # 비정상적으로 큰 입력이 거대한 임계값 배열을 만들지 않도록 제한한다.
    if maximum / step > 100_000:
        raise ValueError(
            "임계값 후보가 너무 많습니다. step을 늘리거나 행렬을 확인하세요."
        )
    thresholds = np.arange(0, maximum + step, step)
    edges = np.sort(data[~np.eye(n, dtype=bool)])
    survival = (edges.size - np.searchsorted(edges, thresholds, side="right")) / max(
        n * (n - 1), 1
    )
    slopes = np.diff(survival) / step
    changes = np.abs(np.diff(slopes)) / step
    slope_thresholds = thresholds[2:]
    stable_index = len(thresholds) - 1
    for k in range(1, len(changes)):
        if k > 3 and changes[k - 1] - changes[k] <= 0.01:
            stable_index = k + 2
            break
    distance_index = int(np.argmin(thresholds**2 + survival**2))
    final_index = 0
    for index in range(distance_index, -1, -1):
        mask = data > thresholds[index]
        np.fill_diagonal(mask, False)
        if np.all(mask.any(axis=0) | mask.any(axis=1)):
            final_index = index
            break
    final_mask = data > thresholds[final_index]
    np.fill_diagonal(final_mask, False)
    isolated = tuple(
        int(i)
        for i in np.flatnonzero(~(final_mask.any(axis=0) | final_mask.any(axis=1)))
    )
    return ThresholdResult(
        float(thresholds[final_index]),
        float(thresholds[distance_index]),
        float(thresholds[stable_index]),
        thresholds,
        survival,
        slope_thresholds,
        changes,
        final_index < distance_index,
        isolated,
    )


def threshold_count(matrix):
    """기존 API: 제안 임계값만 반환한다. 화면 표시는 dashboard에서 담당한다."""
    return analyze_threshold(matrix).threshold


def extract_series_network(matrix, epsilon=1e-4, delta=0.01, max_iter=100):
    """Σ matrix^k의 연결 개수가 안정화되면 직전 단계의 행렬을 반환한다.

    수학적인 투입계수 급수에는 A를 전달한다. 기존 대시보드는 L을 전달하므로
    호환성을 위해 호출자가 입력 행렬을 선택할 수 있게 유지한다.
    """
    matrix = square_matrix(matrix)
    if not np.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon은 0보다 큰 유한한 값이어야 합니다.")
    if not np.isfinite(delta) or delta <= 0:
        raise ValueError("delta는 0보다 큰 유한한 값이어야 합니다.")
    if (
        isinstance(max_iter, bool)
        or not isinstance(max_iter, (int, np.integer))
        or max_iter < 1
    ):
        raise ValueError("max_iter는 1 이상의 정수여야 합니다.")
    n = len(matrix)
    total = np.zeros((n, n))
    power = np.eye(n)
    weighted_previous = np.zeros((n, n))
    binary_previous = np.zeros((n, n))
    previous_count = epsilon
    iterations, densities, ratios = [], [], []
    converged = False
    for iteration in range(1, max_iter + 1):
        with np.errstate(over="ignore", invalid="ignore"):
            power = power @ matrix
            total = total + power
        if not np.isfinite(total).all():
            raise ValueError(
                "급수 전개가 유한 범위를 벗어났습니다. 입력 행렬과 반복 횟수를 확인하세요."
            )
        weighted = total.copy()
        np.fill_diagonal(weighted, 0)
        weighted[weighted <= epsilon] = 0
        binary = (weighted > 0).astype(float)
        count = float(binary.sum())
        ratio = (
            (count - previous_count) / previous_count
            if previous_count
            else (0.0 if not count else float("inf"))
        )
        iterations.append(iteration)
        densities.append(count)
        ratios.append(ratio)
        if ratio < delta:
            converged = True
            break
        weighted_previous, binary_previous = weighted, binary
        previous_count = count
    if not converged:
        weighted_previous, binary_previous = weighted, binary
    return SeriesResult(
        weighted_previous,
        binary_previous,
        {
            "final_t": iteration,
            "converged": converged,
            "densities": densities,
            "ratios": ratios,
            "iterations": iterations,
            "last_ratio": ratios[-1],
            "last_density": densities[-1],
            "epsilon": epsilon,
            "delta": delta,
        },
    )


def extract_network_leontief(matrix, epsilon=1e-4, delta=0.01, max_iter=100):
    """호환 API: (가중행렬, 이진행렬, Figure, info). plots extra가 필요하다."""
    from .plots import plot_series

    result = extract_series_network(matrix, epsilon, delta, max_iter)
    return result.weighted, result.binary, plot_series(result.info), result.info


def graph_from_matrix(matrix, *, binary=False):
    """산업연관표의 열 j → 행 i 방향으로 생성하며 고립 노드도 보존한다."""
    matrix = square_matrix(matrix)
    graph = nx.DiGraph()
    graph.add_nodes_from(range(len(matrix)))
    rows, cols = np.where(matrix > 0)
    graph.add_edges_from(
        (int(j), int(i), {"weight": 1.0 if binary else float(matrix[i, j])})
        for i, j in zip(rows, cols)
        if i != j
    )
    return graph
