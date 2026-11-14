"""구조적 공백: Kim 효율과 Burt 지표."""

import networkx as nx


def calculate_kim_metrics(G, weight="weight"):
    """
    Kim (2021) 방식의 Constraint와 Efficiency를 계산하여 딕셔너리로 반환
    Return: (constraints_dict, efficiencies_dict)
    """
    # 1. Constraint (Burt's constraint)
    # 가중치가 있으면 생산유발계수 등을 반영
    constraints = nx.constraint(G, weight=weight)

    # 2. Efficiency (Kim's redundancy-based)
    efficiencies = {}
    nodes = list(G.nodes())

    # 효율성 계산을 위한 사전 계산 (속도 최적화)
    # 양방향 거래량(volume) 계산 헬퍼
    def get_vol(u, v):
        if not G.has_edge(u, v):
            return 0.0
        return G[u][v].get(weight, 1.0) if weight else 1.0

    def get_bi_vol(u, v):
        return get_vol(u, v) + get_vol(v, u)

    node_total_volumes = {}  # 분모: (In + Out sum)
    node_max_volumes = {}  # 분모: Max connection strength

    for n in nodes:
        # Total Volume (In + Out)
        vol_in = G.in_degree(n, weight=weight)
        vol_out = G.out_degree(n, weight=weight)
        node_total_volumes[n] = vol_in + vol_out

        # Max Volume with any partner
        partners = set(G.predecessors(n)) | set(G.successors(n))
        max_vol = 0.0
        for p in partners:
            vol = get_bi_vol(n, p)
            if vol > max_vol:
                max_vol = vol
        node_max_volumes[n] = max_vol

    # 개별 노드 효율성 계산
    for i in nodes:
        partners_i = list(set(G.predecessors(i)) | set(G.successors(i)))
        Ni = len(partners_i)

        if Ni == 0:
            efficiencies[i] = 0.0
            continue

        sum_Rij = 0.0
        for j in partners_i:
            # j와 i를 제외한 제3자(q) 탐색 (Redundancy check)
            potential_qs = [q for q in partners_i if q != j and q != i]

            R_ij = 0.0
            for q in potential_qs:
                # rho_iq: i의 전체 거래 중 q와의 비중
                vol_iq = get_bi_vol(i, q)
                denom_i = node_total_volumes.get(i, 0)
                rho_iq = vol_iq / denom_i if denom_i > 1e-9 else 0.0

                # tau_jq: j의 최대 거래 대비 q와의 강도
                vol_jq = get_bi_vol(j, q)
                max_vol_j = node_max_volumes.get(j, 0)
                tau_jq = vol_jq / max_vol_j if max_vol_j > 1e-9 else 0.0

                R_ij += rho_iq * tau_jq
            sum_Rij += R_ij

        # Kim's Efficiency Formula: epsilon = T_i / N_i where T_i = N_i - sum(R_ij)
        Ti = Ni - sum_Rij
        efficiencies[i] = Ti / Ni if Ni > 0 else 0.0

    return constraints, efficiencies


def calculate_standard_metrics(G_directed, weight="weight"):
    """Burt 표준 방식 (Efficiency = Effective Size / Out-Degree)"""
    std_constraints = nx.constraint(G_directed, weight=weight)
    effective_sizes = nx.effective_size(G_directed, weight=weight)

    std_efficiencies = {}
    for n, eff_size in effective_sizes.items():
        degree = G_directed.out_degree(
            n
        )  # Standard Burt uses Out-degree for ego network size
        if degree > 0:
            std_efficiencies[n] = eff_size / degree
        else:
            std_efficiencies[n] = 0.0

    return std_constraints, std_efficiencies
