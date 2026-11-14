"""두 추출 방식이 공유하는 그래프·중심성·다운로드 결과 조립."""

from dataclasses import dataclass
import numpy as np
from .analysis import labeled_matrix
from .centrality import calculate_network_centralities
from .network import graph_from_matrix
from .leontief import create_undirected_network

CENTRALITY_NAMES = (
    "degree",
    "betweenness",
    "closeness",
    "eigenvector",
    "hits",
    "structural_holes",
)


@dataclass(frozen=True)
class NetworkResult:
    weighted_graph: object
    binary_graph: object
    weighted_centralities: tuple
    binary_centralities: tuple
    frames: dict


def analyze_network(matrix, template):
    weighted = graph_from_matrix(matrix)
    binary = graph_from_matrix(matrix, binary=True)
    # 자기 연결은 어떤 경로에서도 지표나 내보내기에 포함하지 않는다.
    matrix = np.asarray(matrix, dtype=float).copy()
    np.fill_diagonal(matrix, 0)
    matrix[matrix < 0] = 0
    mask = (matrix > 0).astype(int)
    weighted_cents = calculate_network_centralities(weighted, template, True)
    binary_cents = calculate_network_centralities(binary, template, False)
    frames = {
        "network_weighted": labeled_matrix(template, matrix),
        "network_binary": labeled_matrix(template, mask),
        "network_undirected": labeled_matrix(template, create_undirected_network(mask)),
    }
    for kind, cents in (("weighted", weighted_cents), ("binary", binary_cents)):
        frames.update(
            {
                f"{kind}_{name}": frame
                for name, frame in zip(CENTRALITY_NAMES, cents[:6])
            }
        )
    return NetworkResult(weighted, binary, weighted_cents, binary_cents, frames)
