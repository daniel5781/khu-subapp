"""레온티에프·GDP·부가가치·연쇄효과 표시."""

import numpy as np
import streamlit as st
from .tables import show_table
from .charts import scatter


def render_analysis(result, editor):
    st.header("Leontief 과정 matrices")
    items = [
        ("edited_df", "edited_df"),
        ("normalization denominator", "normalization_denominator"),
        ("투입계수행렬", "투입계수행렬"),
        ("leontief inverse", "leontief_inverse"),
        ("FL-BL", "FL_BL"),
        ("g_series", "g_series"),
        ("GDP", "GDP"),
        ("부가가치유발효과(국내)", "부가가치유발효과"),
        ("부가가치계수행렬", "부가가치계수행렬"),
        ("부가가치계벡터", "부가가치계벡터"),
    ]
    for tab, (label, name) in zip(st.tabs([item[0] for item in items]), items):
        with tab:
            show_table(result.frames[name])
            metrics = (
                ["g1", "g2", "g3", "g123"]
                if name == "g_series"
                else (
                    ["GDP"]
                    if name == "GDP"
                    else (["m_v"] if name == "부가가치유발효과" else [])
                )
            )
            for metric in metrics:
                st.write(
                    f"{metric}: 합계 {result.statistics[metric + '_total']:,.6f} / 평균 {result.statistics[metric + '_mean']:,.6f}"
                )
    with st.expander("수정된 X / R / C / 국산거래표"):
        for name in (
            "edited_matrix_X",
            "edited_matrix_R",
            "edited_matrix_C",
            "edited_df_local",
            "국산_leontief_inverse",
        ):
            st.write(name)
            show_table(result.frames[name])
    with st.expander("레온티에프 역행렬 정합성 검증"):
        st.write(
            f"FL 평균이 1인지: {np.isclose(result.total.forward_linkage.mean(), 1)}"
        )
        st.write(
            f"BL 평균이 1인지: {np.isclose(result.total.backward_linkage.mean(), 1)}"
        )
        inverse = result.total.inverse
        positions = np.argwhere((inverse < -0.1) | (inverse > 2))
        diagonal = np.flatnonzero(np.diag(inverse) < 1)
        if positions.size:
            st.write(f"참고 범위 [-0.1, 2] 밖의 값: {len(positions)}개")
            show_table(
                [
                    {"행": int(i) + 2, "열": int(j) + 2, "값": inverse[i, j]}
                    for i, j in positions[:200]
                ]
            )
        if len(diagonal):
            st.write(f"대각 원소가 1 미만인 산업: {len(diagonal)}개")
        st.caption("참고 범위는 진단용이며 모든 산업연관표의 유효성 조건은 아닙니다.")
    names = list(
        dict.fromkeys(name for values in editor.names.values() for name in values)
    )
    selected = st.multiselect("FL-BL 강조할 산업", names, default=names)
    frame = result.frames["FL_BL"].iloc[1:].rename(columns={"2": "FL", "3": "BL"})
    scatter(frame, "FL", "BL", "FL-BL Plot", "fl_bl", selected, reference=1.0)
