"""네트워크 추출(Method A/B)과 중심성·구조적 공백 지표 계산.

- `threshold_count`        : Method A. 임계값별 생존비율을 그려 최적 임계값 제안
                            (거리 최소화 + 고립 노드 방지 백트래킹).
- `extract_network_leontief` : Method B. Leontief 급수전개 수렴 시점의 네트워크.
- `calculate_network_centralities` : degree/betweenness/closeness/eigenvector/HITS
                            + Kim 구조적 공백 지표를 한 번에.
- `calculate_kim_metrics` / `calculate_standard_metrics` : 제약(constraint)·효율(efficiency).

`threshold_count` 와 `extract_network_leontief` 는 그래프를 직접 `st.pyplot` 으로
그리므로 Streamlit 컨텍스트 밖에서 호출하면 경고가 나지만 반환값은 동일하다.
"""
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import networkx as nx


def calculate_network_centralities(G_bn, df_label, use_weight=False):
    weight_arg = 'weight' if use_weight else None

    # Degree
    in_degree_bn = dict(G_bn.in_degree(weight=weight_arg))
    out_degree_bn = dict(G_bn.out_degree(weight=weight_arg))

    df_degree = df_label.iloc[2:, :2].copy()
    df_degree["in_degree"] = pd.Series(in_degree_bn).sort_index().values.reshape(-1, 1)
    df_degree["out_degree"] = pd.Series(out_degree_bn).sort_index().values.reshape(-1, 1)

    gd_in_mean = df_degree["in_degree"].mean()
    gd_in_std = df_degree["in_degree"].std()
    gd_out_mean = df_degree["out_degree"].mean()
    gd_out_std = df_degree["out_degree"].std()

    # Betweenness
    bc_bn = nx.betweenness_centrality(G_bn, normalized=False, endpoints=False, weight=weight_arg)
    num_n = len(G_bn)
    bc_bn = {node: value / (num_n * (num_n - 1)) for node, value in bc_bn.items()}

    df_bc = df_label.iloc[2:, :2].copy()
    df_bc["Betweenness Centrality"] = pd.Series(bc_bn).sort_index().values.reshape(-1, 1)

    bc_mean = df_bc["Betweenness Centrality"].mean()
    bc_std = df_bc["Betweenness Centrality"].std()

    # Closeness
    cci_bn = nx.closeness_centrality(G_bn, distance=weight_arg)
    cco_bn = nx.closeness_centrality(G_bn.reverse(), distance=weight_arg)

    df_cc = df_label.iloc[2:, :2].copy()
    df_cc["Indegree_Closeness Centrality"] = pd.Series(cci_bn).sort_index().values.reshape(-1, 1)
    df_cc["Outdegree_Closeness Centrality"] = pd.Series(cco_bn).sort_index().values.reshape(-1, 1)

    cc_in_mean = df_cc["Indegree_Closeness Centrality"].mean()
    cc_in_std = df_cc["Indegree_Closeness Centrality"].std()
    cc_out_mean = df_cc["Outdegree_Closeness Centrality"].mean()
    cc_out_std = df_cc["Outdegree_Closeness Centrality"].std()

    # Eigenvector
    evi_bn = nx.eigenvector_centrality(G_bn, max_iter=500, tol=1e-06, weight=weight_arg)
    evo_bn = nx.eigenvector_centrality(G_bn.reverse(), max_iter=500, tol=1e-06, weight=weight_arg)

    df_ev = df_label.iloc[2:, :2].copy()
    df_ev["Indegree_Eigenvector Centrality"] = pd.Series(evi_bn).sort_index().values.reshape(-1, 1)
    df_ev["Outdegree_Eigenvector Centrality"] = pd.Series(evo_bn).sort_index().values.reshape(-1, 1)

    ev_in_mean = df_ev["Indegree_Eigenvector Centrality"].mean()
    ev_in_std = df_ev["Indegree_Eigenvector Centrality"].std()
    ev_out_mean = df_ev["Outdegree_Eigenvector Centrality"].mean()
    ev_out_std = df_ev["Outdegree_Eigenvector Centrality"].std()

    # HITS (가중치 지원 안 함 → 그대로 사용)
    hubs, authorities = nx.hits(G_bn, max_iter=1000, tol=1e-08, normalized=True)

    df_hi = df_label.iloc[2:, :2].copy()
    df_hi["HITS Hubs"] = pd.Series(hubs).sort_index().values.reshape(-1, 1)
    df_hi["HITS Authorities"] = pd.Series(authorities).sort_index().values.reshape(-1, 1)

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
        df_degree, df_bc, df_cc, df_ev, df_hi, df_kim,  # df_kim 추가
        gd_in_mean, gd_in_std, gd_out_mean, gd_out_std,
        bc_mean, bc_std,
        cc_in_mean, cc_in_std, cc_out_mean, cc_out_std,
        ev_in_mean, ev_in_std, ev_out_mean, ev_out_std,
        hi_hub_mean, hi_hub_std, hi_ah_mean, hi_ah_std,
        kim_const_mean, kim_const_std, kim_eff_mean, kim_eff_std  # 통계치 4개 추가
    )


@st.cache_data()
def threshold_count(matrix):
    """
    [Integration Logic]
    1. Method 2 (Derivative): 변화율 안정화 지점 계산 (기존 유지)
    2. Method 2-1 (Distance): 원점 거리 최소화 지점 계산 (기존 유지 - 시작점 역할)
    3. Connectivity Check: Method 2-1 지점에서 고립 노드 발생 시, 사라질 때까지 Threshold 하향 조정 (신규 추가)
    """
    # -------------------------------------------------------------------------
    # 0. 데이터 준비
    # -------------------------------------------------------------------------
    if hasattr(matrix, 'to_numpy'):
        mat_data = matrix.to_numpy()
    else:
        mat_data = np.array(matrix)

    mat_data = mat_data.copy().astype(float)
    np.fill_diagonal(mat_data, 0)  # 대각 성분 제외

    N = mat_data.shape[0]
    total_elements = N**2 - N

    # x축 설정
    delta = 0.01
    max_val = np.max(mat_data)
    x_values = np.arange(0, max_val + delta, delta)

    # -------------------------------------------------------------------------
    # 1. 지표 계산: y(생존율) & w(변화율)
    # -------------------------------------------------------------------------
    # y: Survival Ratio
    y_list = []
    for x in x_values:
        count = (mat_data >= x).sum()
        ratio = count / total_elements
        y_list.append(ratio)
    y = np.array(y_list)

    # w: Slope Change Rate (Method 2)
    if len(y) > 1:
        z = (y[1:] - y[:-1]) / delta
    else:
        z = np.zeros(len(y))

    w_list = []
    w_x_values = []
    for i in range(1, len(z)):
        val_w = abs(z[i] - z[i-1]) / delta
        w_list.append(val_w)
        if i+1 < len(x_values):
            w_x_values.append(x_values[i+1])
    w = np.array(w_list)
    w_x_values = np.array(w_x_values)

    # Method 2: Stability Check (기존 로직 유지)
    epsilon = 0.01
    opt_idx_method2 = 0
    found_method2 = False

    for k in range(1, len(w)):
        if k > 3 and (w[k-1] - w[k]) <= epsilon:
            opt_idx_method2 = k + 2
            found_method2 = True
            break
    if not found_method2 and len(x_values) > 0:
        opt_idx_method2 = len(x_values) - 1

    threshold_method2 = x_values[opt_idx_method2] if len(x_values) > opt_idx_method2 else 0

    # -------------------------------------------------------------------------
    # 2. Method 2-1 (Distance Minimization) - [기준점]
    # -------------------------------------------------------------------------
    dist_sq = x_values**2 + y**2
    opt_idx_dist = np.argmin(dist_sq)

    threshold_dist = x_values[opt_idx_dist]
    min_y = y[opt_idx_dist] if len(y) > opt_idx_dist else 0

    # -------------------------------------------------------------------------
    # 3. [Logic Addition] Connectivity Backtracking
    # Method 2-1 지점(opt_idx_dist)에서 시작하여 0방향으로 스캔
    # -------------------------------------------------------------------------
    final_idx = opt_idx_dist
    adjusted = False

    # 현재 최적점(Distance Min)부터 0까지 역순 탐색
    for idx in range(opt_idx_dist, -1, -1):
        t = x_values[idx]

        # Binary Masking
        mask = (mat_data >= t)  # 1 if connected, else 0

        # 고립 노드 체크 (Undirected 관점: In-degree + Out-degree == 0 이면 고립)
        # mask 행렬에서 행의 합(Out) + 열의 합(In) 계산
        degrees = mask.sum(axis=1) + mask.sum(axis=0)

        if np.any(degrees == 0):
            # 고립 노드가 존재함 -> Threshold가 너무 높음 -> 계속 낮춤(Loop Continue)
            continue
        else:
            # 고립 노드 없음 (All Connected) -> 멈춤
            final_idx = idx
            if idx < opt_idx_dist:
                adjusted = True
            break

    final_threshold = x_values[final_idx]
    final_y = y[final_idx] if len(y) > final_idx else 0

    # -------------------------------------------------------------------------
    # 4. 시각화 (모든 지표 포함)
    # -------------------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(10, 7))

    # [왼쪽 축] y(x) Curve
    color1 = 'tab:blue'
    ax1.set_xlabel('Threshold (x)')
    ax1.set_ylabel('Survival Ratio (y)', color=color1, fontweight='bold')
    ax1.plot(x_values, y, color=color1, label='y: Survival Ratio', linewidth=2, alpha=0.7)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, alpha=0.3)

    # [오른쪽 축] w(t) Curve (기존 Method 2 시각화 유지)
    if len(w) > 0:
        ax2 = ax1.twinx()
        color2 = 'tab:orange'
        ax2.set_ylabel('Slope Change Rate (w)', color=color2, fontweight='bold')
        ax2.plot(w_x_values, w, color=color2, linestyle='--', alpha=0.5, label='w: Slope Stability')
        ax2.tick_params(axis='y', labelcolor=color2)

    # [Indicator 1] Method 2 (Stability) - 회색 수직선
    ax1.axvline(x=threshold_method2, color='gray', linestyle='-.', alpha=0.6,
                label=f'Method 2 (Stable): {threshold_method2:.4f}')

    # [Indicator 2] Method 2-1 (Distance Min) - 빨간 점 (원래의 수학적 최적점)
    ax1.plot(threshold_dist, min_y, 'ro', markersize=8, alpha=0.6,
             label=f'Method 2-1 (Dist Min): {threshold_dist:.4f}')

    # [Indicator 3] Final Decision (No Isolated) - 초록색 별/X (최종 결정)
    # 조정이 발생했다면 화살표와 함께 표시
    label_final = f'Final (No Isolated): {final_threshold:.4f}'

    if adjusted:
        # 조정된 경우: Method 2-1 -> Final 로 화살표 표시
        ax1.annotate('', xy=(final_threshold, final_y), xytext=(threshold_dist, min_y),
                     arrowprops=dict(arrowstyle="->", color='red', lw=2))
        ax1.plot(final_threshold, final_y, 'X', color='red', markersize=12, zorder=10, label=label_final)
    else:
        # 조정 안 된 경우: 빨간 점 위에 초록색 테두리 등을 씌워 강조
        ax1.plot(final_threshold, final_y, 'g*', markersize=14, zorder=10, label=label_final)

    # 범례 통합
    lines1, labels1 = ax1.get_legend_handles_labels()
    if len(w) > 0:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
    else:
        ax1.legend(loc='upper right')

    plt.title('Threshold Optimization: Distance Min + Connectivity Check')
    fig.tight_layout()
    st.pyplot(fig)

    # -------------------------------------------------------------------------
    # 5. 결과 반환 및 설명
    # -------------------------------------------------------------------------
    msg_adjustment = ""
    if adjusted:
        msg_adjustment = f"⚠️ 수학적 최적점(`{threshold_dist:.4f}`)에서 고립 노드가 발견되어, `{final_threshold:.4f}` 로 하향 조정했습니다."
    else:
        msg_adjustment = f"✅ 수학적 최적점(`{threshold_dist:.4f}`)이 고립 노드 없이 안정적입니다."

    st.markdown(f"""
    **최적 임계값 분석 결과**
    - **Stability Criterion:** `{threshold_method2:.4f}`
    - **Distance Min Criterion:** `{threshold_dist:.4f}` (Backtracking 시작점)
    - **Final Decision:** `{final_threshold:.4f}`

    {msg_adjustment}
    """)

    return final_threshold


@st.cache_data
def extract_network_leontief(matrix, epsilon=1e-4, delta=0.01, max_iter=100):
    """
    Leontief Inverse의 급수 전개(Series Expansion)를 활용한 네트워크 추출 알고리즘.

    Parameters
    ----------
    matrix : array-like
        인접 행렬 A (투입계수행렬).
    epsilon : float
        정밀도 조절 변수. B^t 원소 중 이 값 이하인 것을 0으로 제거.
    delta : float
        수렴 기준. Change Ratio r이 이 값 미만이면 반복 중단.
    max_iter : int
        최대 반복 횟수.

    Returns
    -------
    N : ndarray
        B_c^{t-1} — Weighted Directed Network (수렴 직전 단계).
    N0 : ndarray
        Q^{t-1} — Unweighted (Binary) Directed Network.
    fig : matplotlib.figure.Figure
        수렴 과정 그래프 (Dual Axis: Density / Change Ratio).
    info : dict
        수렴 관련 정보 (final_t, converged, densities, ratios 등).
    """
    # -------------------------------------------------------------------------
    # 0. 데이터 준비
    # -------------------------------------------------------------------------
    if hasattr(matrix, 'to_numpy'):
        A = matrix.to_numpy().copy().astype(float)
    else:
        A = np.array(matrix, dtype=float).copy()

    n = A.shape[0]

    # -------------------------------------------------------------------------
    # 1. 초기화
    # -------------------------------------------------------------------------
    B_prev = np.zeros((n, n))       # B^0 = 0 행렬
    r = 1.0                         # 초기 변화율
    theta_prev = epsilon            # θ^0 = epsilon (0으로 나누기 방지)

    # 이전 단계 결과 저장 (t-1 반환용)
    Bc_prev = np.zeros((n, n))      # B_c^{t-1}
    Q_prev = np.zeros((n, n))       # Q^{t-1}

    # 시각화용 리스트
    t_list = []
    density_list = []
    ratio_list = []

    A_power = np.eye(n)             # A^0 = I (거듭제곱 누적용)
    final_t = 0
    converged = False

    # -------------------------------------------------------------------------
    # 2. 반복문 (Do while r >= delta)
    # -------------------------------------------------------------------------
    for t in range(1, max_iter + 1):
        # --- Step 1: Partial Sum 계산 ---
        # A^t = A^{t-1} * A
        A_power = A_power @ A
        B_t = B_prev + A_power      # B^t = B^{t-1} + A^t

        # --- Step 2: Cut-off Matrix (B_c^t) 생성 ---
        Bc_t = B_t.copy()
        np.fill_diagonal(Bc_t, 0)                  # 대각 성분 제거
        Bc_t[Bc_t <= epsilon] = 0                   # epsilon 이하 값 제거

        # --- Step 3: Binary Matrix (Q^t) 생성 ---
        Q_t = (Bc_t > 0).astype(float)

        # --- Step 4: Density (θ^t) 계산 ---
        theta_t = float(Q_t.sum())                  # 유효 연결의 총 개수

        # --- Step 5: Ratio (r) 업데이트 ---
        r = (theta_t - theta_prev) / theta_prev

        # 기록 저장
        t_list.append(t)
        density_list.append(theta_t)
        ratio_list.append(r)

        # --- 수렴 판정 ---
        if r < delta:
            # r < δ 이면 **이전 단계(t-1)**의 결과를 반환
            converged = True
            final_t = t
            break

        # 다음 반복을 위해 현재값을 이전값으로 저장
        Bc_prev = Bc_t.copy()
        Q_prev = Q_t.copy()
        B_prev = B_t.copy()
        theta_prev = theta_t
        final_t = t

    # 수렴하지 못하고 max_iter에 도달한 경우: 마지막 결과 사용
    if not converged:
        Bc_prev = Bc_t.copy()
        Q_prev = Q_t.copy()

    # -------------------------------------------------------------------------
    # 3. 시각화 (Dual Axis: Density vs Change Ratio)
    # -------------------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # [왼쪽 축] Density (θ^t)
    color1 = 'tab:blue'
    ax1.set_xlabel('Iteration (t)', fontsize=12)
    ax1.set_ylabel('Density (θ)', color=color1, fontweight='bold', fontsize=12)
    ax1.plot(t_list, density_list, color=color1, marker='s', label='Density (θ)',
             linewidth=2, markersize=6)
    ax1.tick_params(axis='y', labelcolor=color1)
    ax1.grid(True, alpha=0.3)

    # [오른쪽 축] Change Ratio (r)
    ax2 = ax1.twinx()
    color2 = 'tab:red'
    ax2.set_ylabel('Change Ratio (r)', color=color2, fontweight='bold', fontsize=12)
    ax2.plot(t_list, ratio_list, color=color2, marker='o', linestyle='--',
             label='Change Ratio (r)', linewidth=2, markersize=6, alpha=0.8)
    ax2.tick_params(axis='y', labelcolor=color2)

    # δ 기준선
    ax2.axhline(y=delta, color='gray', linestyle='-.', linewidth=1.5,
                label=f'δ = {delta}')

    # 범례 합치기
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)

    status_label = "Converged" if converged else "Max Iter"
    plt.title(f'Leontief Series Expansion Convergence (Stopped at t={final_t}, {status_label})',
              fontsize=13)
    fig.tight_layout()

    # -------------------------------------------------------------------------
    # 4. 결과 정보
    # -------------------------------------------------------------------------
    info = {
        'final_t': final_t,
        'converged': converged,
        'densities': density_list,
        'ratios': ratio_list,
        'iterations': t_list,
        'last_ratio': ratio_list[-1] if ratio_list else 0.0,
        'last_density': density_list[-1] if density_list else 0.0,
        'epsilon': epsilon,
        'delta': delta,
    }

    # N = B_c^{t-1}, N0 = Q^{t-1}
    return Bc_prev, Q_prev, fig, info


def calculate_kim_metrics(G, weight='weight'):
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
    node_max_volumes = {}   # 분모: Max connection strength

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

                R_ij += (rho_iq * tau_jq)
            sum_Rij += R_ij

        # Kim's Efficiency Formula: epsilon = T_i / N_i where T_i = N_i - sum(R_ij)
        Ti = Ni - sum_Rij
        efficiencies[i] = Ti / Ni if Ni > 0 else 0.0

    return constraints, efficiencies


def calculate_standard_metrics(G_directed, weight='weight'):
    """Burt 표준 방식 (Efficiency = Effective Size / Out-Degree)"""
    std_constraints = nx.constraint(G_directed, weight=weight)
    effective_sizes = nx.effective_size(G_directed, weight=weight)

    std_efficiencies = {}
    for n, eff_size in effective_sizes.items():
        degree = G_directed.out_degree(n)  # Standard Burt uses Out-degree for ego network size
        if degree > 0:
            std_efficiencies[n] = eff_size / degree
        else:
            std_efficiencies[n] = 0.0

    return std_constraints, std_efficiencies
