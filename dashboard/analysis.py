"""경제지표 요약, 산업 선택, 필요한 결과만 표시하는 화면."""

import numpy as np
import streamlit as st
from iolib.allocations import sector_catalog
from .tables import show_table
from .charts import scatter
from .labels import result_label


def render_analysis(result, editor):
    st.subheader("경제지표")
    left, right = st.columns(2)
    left.metric("GDP 유발액 합계", f"{result.statistics['GDP_total']:,.2f}")
    right.metric(
        "국내 부가가치 유발계수 합계", f"{result.statistics['m_v_total']:,.4f}"
    )
    st.caption(
        "금액 단위는 원자료와 같습니다. 비율을 수정했다면 산업 편집 화면에서 다시 적용·계산하세요."
    )
    catalog = sector_catalog(editor)
    codes = catalog["code"].tolist()
    names = dict(zip(codes, catalog["name"]))
    if any(code not in names for code in st.session_state.get("highlight_codes", [])):
        st.session_state.pop("highlight_codes", None)
    selected = st.multiselect(
        "차트에서 강조할 산업",
        codes,
        format_func=lambda c: f"{names[c]} ({c})",
        default=[c for c in editor.names if c in names],
        key="highlight_codes",
        placeholder="모든 산업에서 이름·코드로 검색할 수 있습니다",
    )
    frame = result.frames["FL_BL"].iloc[1:].rename(columns={"2": "FL", "3": "BL"})
    scatter(
        frame,
        "FL",
        "BL",
        "FL-BL Plot",
        "fl_bl",
        [names[c] for c in selected],
        reference=1.0,
    )
    primary = ["FL_BL", "GDP", "부가가치유발효과", "g_series"]
    options = primary + [name for name in result.frames if name not in primary]
    name = st.selectbox(
        "확인할 지표·행렬", options, format_func=result_label, key="economic_result"
    )
    st.caption(result_label(name))
    show_table(result.frames[name], width="stretch")
    metrics = (
        ["g1", "g2", "g3", "g123"]
        if name == "g_series"
        else ["GDP"]
        if name == "GDP"
        else ["m_v"]
        if name == "부가가치유발효과"
        else []
    )
    for metric in metrics:
        st.write(
            f"{metric}: 합계 {result.statistics[metric + '_total']:,.6f} / 평균 {result.statistics[metric + '_mean']:,.6f}"
        )
    with st.expander("역행렬과 연쇄효과 계산 점검"):
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
