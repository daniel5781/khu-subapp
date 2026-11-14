"""백분율 입력을 기본으로 제공하고 개별 편집·정리는 별도로 모은다."""

import streamlit as st
from iolib.allocations import sector_catalog
from .alpha import render_alpha
from .tables import show_table
from .workspace import apply_operation, calculate, ensure_draft


def _apply(operation):
    try:
        apply_operation(
            st.session_state,
            operation,
            "편집을 반영했습니다. 경제지표를 다시 계산하세요.",
        )
        st.rerun()
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        st.error(f"편집을 적용할 수 없습니다: {exc}")


def render_editor(editor):
    render_alpha(editor)
    with st.expander("기타 편집 · 산업 추가 / 기존 산업 간 이동 / 값 정리"):
        st.caption(
            "새 산업으로 분리할 때는 위 입력표가 산업을 자동으로 추가합니다. 아래 도구는 별도 편집이 필요할 때 사용하세요."
        )
        with st.form("insert_sector", border=False):
            left, right = st.columns(2)
            code = left.text_input("추가할 산업 코드", key="new_code")
            name = right.text_input("추가할 산업 이름", key="new_name")
            if st.form_submit_button("산업 추가"):
                _apply({"type": "insert_sector", "code": code, "name": name})
        catalog = sector_catalog(editor)
        codes = catalog["code"].tolist()
        names = dict(zip(codes, catalog["name"]))
        for key in ("origin_code", "target_code"):
            if st.session_state.get(key) not in codes:
                st.session_state.pop(key, None)
        with st.form("transfer", border=False):
            left, middle, right = st.columns(3)
            origin = left.selectbox(
                "출발 산업",
                codes,
                index=None,
                format_func=lambda c: f"{names[c]} ({c})",
                key="origin_code",
                placeholder="이름·코드로 검색",
            )
            target = middle.selectbox(
                "대상 산업",
                codes,
                index=None,
                format_func=lambda c: f"{names[c]} ({c})",
                key="target_code",
                placeholder="이름·코드로 검색",
            )
            percent = right.number_input(
                "이동 비율 (%)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.1,
                format="%.3f",
                key="transfer_percent",
            )
            if st.form_submit_button("선택한 산업 간 이동"):
                if not origin or not target or percent == 0:
                    st.warning("출발·대상 산업을 선택하고 0%보다 큰 비율을 입력하세요.")
                else:
                    _apply(
                        {
                            "type": "transfer",
                            "from": origin,
                            "to": target,
                            "alpha": percent / 100,
                        }
                    )
        left, right = st.columns(2)
        if left.button("0인 행·열 삭제"):
            _apply({"type": "remove_zero"})
        if right.button("음수 값 절반으로 줄이기"):
            _apply({"type": "reduce_negative"})
        st.caption(
            "위 도구로 편집하면 새 비율 입력 작업이 시작됩니다. 이전 편집은 실행 취소로 복원할 수 있습니다."
        )
    draft = ensure_draft(st.session_state)
    st.divider()
    if st.button(
        "현재 편집표로 경제지표 계산",
        key="analyze",
        disabled=draft.dirty,
        help="미반영 비율이 있으면 위의 ‘비율 적용 및 경제지표 계산’을 사용하세요.",
    ):
        try:
            with st.spinner("레온티에프 역행렬과 경제지표를 계산하고 있습니다."):
                calculate(st.session_state)
            st.rerun()
        except (ValueError, TypeError, IndexError, ArithmeticError) as exc:
            st.error(f"분석할 수 없습니다: {exc}")
    with st.expander("현재 편집표 보기"):
        show_table(editor.total, width="stretch")
