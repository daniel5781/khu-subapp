"""추출 방식 선택과 공통 네트워크 결과 표시."""

import numpy as np
import streamlit as st
from .tables import show_table
from iolib.network import analyze_threshold, extract_series_network
from iolib.network_analysis import analyze_network
from iolib.analysis import labeled_matrix
from iolib.plots import plot_threshold, plot_series
from .charts import render_centralities, render_graph

cached_threshold = st.cache_data(show_spinner=False)(analyze_threshold)
cached_series = st.cache_data(show_spinner=False)(extract_series_network)
cached_network = st.cache_data(show_spinner=False)(analyze_network)


def _clear_network():
    for key in ("threshold", "network_result", "network_frames", "network_signature"):
        st.session_state.pop(key, None)


def render_network(analysis, editor):
    st.header("2. 네트워크 추출")
    matrix = analysis.total.inverse
    threshold_result = cached_threshold(matrix)
    with st.expander("Method A 분석 결과 (Threshold Optimization)"):
        st.pyplot(plot_threshold(threshold_result))
        st.write(f"제안 임계값: {threshold_result.threshold:.4f}")
        if threshold_result.isolated_nodes:
            st.warning(
                f"원자료에서 이미 고립된 산업 {len(threshold_result.isolated_nodes)}개가 있습니다."
            )
    method = st.radio(
        "분석 모드 선택",
        [
            "Method A: 최적 임계값 (Threshold Optimization)",
            "Method B: Leontief 급수전개 (Series Expansion)",
        ],
        key="network_method",
        on_change=_clear_network,
    )
    final = None
    extra_frames = {}
    if method.startswith("Method A"):
        with st.form("threshold_form", border=False):
            threshold = st.number_input(
                "임계값 (Threshold)",
                min_value=0.0,
                value=float(threshold_result.threshold),
                step=0.001,
                format="%.6f",
                key="threshold_input",
            )
            apply = st.form_submit_button("설정 적용하기 (Apply)", type="primary")
        if apply:
            _clear_network()
            st.session_state["threshold"] = float(threshold)
        if "threshold" in st.session_state:
            final = matrix.copy()
            final[final <= st.session_state["threshold"]] = 0
            np.fill_diagonal(final, 0)
            mask = (final > 0).astype(int)
            template = analysis.frames["leontief_inverse"]
            extra_frames = {
                "filtered_transactions": labeled_matrix(
                    template,
                    editor.total.iloc[
                        editor.params.first_idx[0] : editor.mid[0],
                        editor.params.first_idx[1] : editor.mid[1],
                    ].to_numpy(float)
                    * mask,
                ),
                "filtered_coefficients": labeled_matrix(
                    template, analysis.total.coefficients * mask
                ),
            }
    else:
        st.caption(
            "기존 분석 규약대로 L의 거듭제곱 누적합을 사용합니다. 수렴 표시는 연결 개수의 안정화를 뜻합니다."
        )
        left, middle, right = st.columns(3)
        epsilon = left.number_input(
            "ε (epsilon)",
            min_value=1e-12,
            value=1e-4,
            step=1e-5,
            format="%.6f",
            key="mb_epsilon",
        )
        delta = middle.number_input(
            "δ (delta)",
            min_value=1e-12,
            value=0.01,
            step=0.001,
            format="%.4f",
            key="mb_delta",
        )
        max_iter = right.number_input(
            "Max Iterations",
            min_value=1,
            max_value=500,
            value=100,
            step=1,
            key="mb_max_iter",
        )
        series = cached_series(matrix, epsilon, delta, int(max_iter))
        st.pyplot(plot_series(series.info))
        st.write(
            f"반복 {series.info['final_t']}회 · {'연결 개수 안정화' if series.info['converged'] else '최대 반복 도달'} · 연결 수 {series.info['last_density']:.0f}"
        )
        final = series.weighted
    if final is None:
        return
    result = cached_network(final, analysis.frames["leontief_inverse"])
    st.session_state["network_result"] = result
    st.session_state["network_frames"] = {**result.frames, **extra_frames}
    highlights = [name for values in editor.names.values() for name in values]
    weighted, binary, undirected = st.tabs(
        [
            "가중치 네트워크(Weighted)",
            "이진 네트워크(Binary)",
            "무방향 이진 네트워크(UN)",
        ]
    )
    with weighted:
        show_table(result.frames["network_weighted"])
        render_centralities(result.weighted_centralities, "weighted", highlights)
    with binary:
        show_table(result.frames["network_binary"])
        render_graph(result.binary_graph, analysis.frames["leontief_inverse"])
        render_centralities(result.binary_centralities, "binary", highlights)
    with undirected:
        show_table(result.frames["network_undirected"])
