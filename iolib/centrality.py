"""방향성 네트워크 중심성. 입력 그래프의 노드는 표 행 순서의 0..n-1이다."""

import numpy as np
import pandas as pd
import networkx as nx
from .structural import calculate_kim_metrics


def _eigenvector_centrality_safe(G, weight=None, max_iter=500, tol=1e-06):
    """임계값 적용 후 그래프가 끊기거나 주기적 구조를 가지면 거듭제곱법이 수렴하지
    않을 수 있다(PowerIterationFailedConvergence). 그 경우 인접행렬의 최대(Perron)
    고유값에 대한 고유벡터를 직접 계산해 대체한다 — 수렴하는 그래프에서는 두 방식의
    결과가 동일하며, `eigenvector_centrality_numpy` 와 달리 비연결 그래프도 처리한다
    (AmbiguousSolution 없이 지배적 성분에 중심성이 집중된 해를 반환)."""
    if G.number_of_edges() == 0:
        return dict.fromkeys(G, 0.0)
    try:
        return nx.eigenvector_centrality(G, max_iter=max_iter, tol=tol, weight=weight)
    except nx.PowerIterationFailedConvergence:
        nodes = list(G)
        A = nx.to_numpy_array(G, nodelist=nodes, weight=weight)
        # nx.eigenvector_centrality 와 동일하게 in-edge 기준(A^T 의 고유벡터).
        # 비음행렬의 스펙트럼 반경은 실수 고유값이므로 실수부 최대가 Perron 고유값.
        eigvals, eigvecs = np.linalg.eig(A.T)
        v = np.abs(eigvecs[:, np.argmax(eigvals.real)].real)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        return dict(zip(nodes, v.tolist()))


def calculate_network_centralities(G_bn, df_label, use_weight=False):
    if set(G_bn) != set(range(len(df_label) - 2)):
        raise ValueError("그래프의 노드와 표의 산업 행 수/순서가 일치해야 합니다.")
    if not use_weight:
        # NetworkX HITS는 weight 인자가 없고 항상 'weight' 속성을 사용한다.
        G_bn = G_bn.copy()
        nx.set_edge_attributes(G_bn, 1.0, "weight")
    weight_arg = "weight" if use_weight else None

    # Degree
    in_degree_bn = dict(G_bn.in_degree(weight=weight_arg))
    out_degree_bn = dict(G_bn.out_degree(weight=weight_arg))

    df_degree = df_label.iloc[2:, :2].copy()
    df_degree["in_degree"] = pd.Series(in_degree_bn).sort_index().values.reshape(-1, 1)
    df_degree["out_degree"] = (
        pd.Series(out_degree_bn).sort_index().values.reshape(-1, 1)
    )

    gd_in_mean = df_degree["in_degree"].mean()
    gd_in_std = df_degree["in_degree"].std()
    gd_out_mean = df_degree["out_degree"].mean()
    gd_out_std = df_degree["out_degree"].std()

    # Betweenness
    bc_bn = nx.betweenness_centrality(
        G_bn, normalized=False, endpoints=False, weight=weight_arg
    )
    num_n = len(G_bn)
    bc_bn = {node: value / max(num_n * (num_n - 1), 1) for node, value in bc_bn.items()}

    df_bc = df_label.iloc[2:, :2].copy()
    df_bc["Betweenness Centrality"] = (
        pd.Series(bc_bn).sort_index().values.reshape(-1, 1)
    )

    bc_mean = df_bc["Betweenness Centrality"].mean()
    bc_std = df_bc["Betweenness Centrality"].std()

    # Closeness
    cci_bn = nx.closeness_centrality(G_bn, distance=weight_arg)
    cco_bn = nx.closeness_centrality(G_bn.reverse(), distance=weight_arg)

    df_cc = df_label.iloc[2:, :2].copy()
    df_cc["Indegree_Closeness Centrality"] = (
        pd.Series(cci_bn).sort_index().values.reshape(-1, 1)
    )
    df_cc["Outdegree_Closeness Centrality"] = (
        pd.Series(cco_bn).sort_index().values.reshape(-1, 1)
    )

    cc_in_mean = df_cc["Indegree_Closeness Centrality"].mean()
    cc_in_std = df_cc["Indegree_Closeness Centrality"].std()
    cc_out_mean = df_cc["Outdegree_Closeness Centrality"].mean()
    cc_out_std = df_cc["Outdegree_Closeness Centrality"].std()

    # Eigenvector
    evi_bn = _eigenvector_centrality_safe(G_bn, weight=weight_arg)
    evo_bn = _eigenvector_centrality_safe(G_bn.reverse(), weight=weight_arg)

    df_ev = df_label.iloc[2:, :2].copy()
    df_ev["Indegree_Eigenvector Centrality"] = (
        pd.Series(evi_bn).sort_index().values.reshape(-1, 1)
    )
    df_ev["Outdegree_Eigenvector Centrality"] = (
        pd.Series(evo_bn).sort_index().values.reshape(-1, 1)
    )

    ev_in_mean = df_ev["Indegree_Eigenvector Centrality"].mean()
    ev_in_std = df_ev["Indegree_Eigenvector Centrality"].std()
    ev_out_mean = df_ev["Outdegree_Eigenvector Centrality"].mean()
    ev_out_std = df_ev["Outdegree_Eigenvector Centrality"].std()

    # HITS (가중치 지원 안 함 → 그대로 사용)
    if G_bn.number_of_edges() == 0:
        hubs = authorities = dict.fromkeys(G_bn, 0.0)
    else:
        try:
            hubs, authorities = nx.hits(
                G_bn,
                max_iter=1000,
                tol=1e-08,
                normalized=True,
                nstart=dict.fromkeys(G_bn, 1.0),
            )
        except (nx.PowerIterationFailedConvergence, ValueError):
            nodes = list(G_bn)
            matrix = nx.to_numpy_array(G_bn, nodelist=nodes)
            left, _, right = np.linalg.svd(matrix)
            h, a = np.abs(left[:, 0]), np.abs(right[0, :])
            hubs = dict(zip(nodes, h / h.sum()))
            authorities = dict(zip(nodes, a / a.sum()))

    df_hi = df_label.iloc[2:, :2].copy()
    df_hi["HITS Hubs"] = pd.Series(hubs).sort_index().values.reshape(-1, 1)
    df_hi["HITS Authorities"] = (
        pd.Series(authorities).sort_index().values.reshape(-1, 1)
    )

    hi_hub_mean = df_hi["HITS Hubs"].mean()
    hi_hub_std = df_hi["HITS Hubs"].std()
    hi_ah_mean = df_hi["HITS Authorities"].mean()
    hi_ah_std = df_hi["HITS Authorities"].std()

    # Structural Hole Metrics (Constraint & Efficiency)
    constraints, efficiencies = calculate_kim_metrics(G_bn, weight=weight_arg)
    df_kim = df_label.iloc[2:, :2].copy()
    df_kim["Constraint"] = pd.Series(constraints).sort_index().values.reshape(-1, 1)
    df_kim["Efficiency"] = pd.Series(efficiencies).sort_index().values.reshape(-1, 1)

    # 평균(Mean) 및 표준편차(Std) 계산
    kim_const_mean = df_kim["Constraint"].mean()
    kim_const_std = df_kim["Constraint"].std()
    kim_eff_mean = df_kim["Efficiency"].mean()
    kim_eff_std = df_kim["Efficiency"].std()

    return (
        df_degree,
        df_bc,
        df_cc,
        df_ev,
        df_hi,
        df_kim,  # df_kim 추가
        gd_in_mean,
        gd_in_std,
        gd_out_mean,
        gd_out_std,
        bc_mean,
        bc_std,
        cc_in_mean,
        cc_in_std,
        cc_out_mean,
        cc_out_std,
        ev_in_mean,
        ev_in_std,
        ev_out_mean,
        ev_out_std,
        hi_hub_mean,
        hi_hub_std,
        hi_ah_mean,
        hi_ah_std,
        kim_const_mean,
        kim_const_std,
        kim_eff_mean,
        kim_eff_std,  # 통계치 4개 추가
    )
