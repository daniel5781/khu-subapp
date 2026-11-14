"""수동/일괄 편집 화면. 모든 변경은 EditingSession에서 두 표에 함께 적용한다."""

import streamlit as st
from .tables import show_table
from iolib.batch_upload import (
    inspect_batch_upload,
    prepare_batch_preview,
    infer_input_year,
)
from .state import invalidate_results


def _apply(operation):
    try:
        next_editor = st.session_state["editor"].apply(operation)
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        st.error(f"편집을 적용할 수 없습니다: {exc}")
        return
    st.session_state["editor"] = next_editor
    invalidate_results(st.session_state)
    st.rerun()


def _batch_identity(records):
    return tuple(
        sorted(
            (str(row["from"]), str(row["to"]), float(row["alpha"])) for row in records
        )
    )


def render_batch(editor):
    uploaded = st.file_uploader(
        "Alpha 값 엑셀/ZIP 파일 업로드", type=["xlsx", "xls", "zip"], key="alpha_file"
    )
    st.caption("from, to, to_name, alpha 열 또는 연도별 비율%(산업코드) 표를 올리세요.")
    if uploaded is None:
        return
    source_name = st.session_state.get("source_name", "")
    stem = source_name.rsplit(".", 1)[0]
    try:
        meta = inspect_batch_upload(uploaded, stem)
        selected_year, target_code, target_name = None, "6000", "TMT"
        is_year_ratio = meta["format"] == "year_ratio"
        if is_year_ratio:
            years = meta["years"]
            original_year = infer_input_year(editor.original.df, source_name)
            index = years.index(original_year) if original_year in years else None
            selected_year = st.selectbox(
                "적용할 비율 연도",
                years,
                index=index,
                key="ratio_year",
                placeholder="연도를 선택하세요",
            )
            left, right = st.columns(2)
            target_code = left.text_input(
                "분리할 산업 코드", "6000", key="ratio_target"
            )
            target_name = right.text_input("분리할 산업 이름", "TMT", key="ratio_name")
            if selected_year is None:
                return
            if original_year is not None and selected_year != original_year:
                st.warning(
                    f"원본은 {original_year}년이며, 선택한 비율은 {selected_year}년입니다."
                )
        codes = editor.total.iloc[
            editor.params.first_idx[0] : editor.mid[0], editor.params.first_idx[1] - 2
        ].tolist()
        frame, _, lines, summaries = prepare_batch_preview(
            uploaded,
            stem,
            year=selected_year,
            target_code=target_code,
            target_name=target_name,
            source_codes=codes,
        )
        st.markdown("##### 일괄 적용 내역 요약")
        show_table(frame, hide_index=True)
        for summary in summaries:
            st.write(summary)
        records = frame.to_dict("records")
        already = is_year_ratio and any(
            op["type"] == "batch_apply"
            and _batch_identity(op["batch_records"]) == _batch_identity(records)
            for op in editor.operations
        )
        if already:
            st.success(
                "이 비율은 이미 적용했습니다. ‘전체 적용’을 누르면 계산 결과를 볼 수 있습니다."
            )
        if st.button("일괄 적용", disabled=already, key="apply_batch"):
            _apply({"type": "batch_apply", "batch_records": records})
    except (ValueError, KeyError, TypeError, OSError) as exc:
        st.error(f"미리보기 준비 중 오류: {exc}")


def render_editor(editor):
    st.header("1. DataFrame을 수정합니다")
    render_batch(editor)
    st.markdown("#### 수동 입력")
    with st.form("insert_sector", border=False):
        left, right = st.columns(2)
        code = left.text_input("새로 삽입할 산업의 code를 입력하세요", key="new_code")
        name = right.text_input("새로 삽입할 산업의 이름을 입력하세요", key="new_name")
        if st.form_submit_button("산업 추가"):
            _apply({"type": "insert_sector", "code": code, "name": name})
    with st.form("transfer", border=False):
        left, middle, right = st.columns(3)
        origin = left.text_input("from", key="origin_code")
        target = middle.text_input("to", key="target_code")
        ratio = right.number_input(
            "alpha value (0.000 to 1.000)",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.001,
            format="%.3f",
            key="transfer_alpha",
        )
        if st.form_submit_button("값 옮기기"):
            _apply({"type": "transfer", "from": origin, "to": target, "alpha": ratio})
    left, middle, right = st.columns(3)
    if left.button("0인 행(열) 삭제"):
        _apply({"type": "remove_zero"})
    if middle.button("음수 값 절반으로 나누기"):
        _apply({"type": "reduce_negative"})
    if right.button("전체 적용", type="primary", key="analyze"):
        try:
            with st.spinner("레온티에프 역행렬과 산업별 지표를 계산하고 있습니다."):
                result = editor.analyze()
            invalidate_results(st.session_state)
            st.session_state["analysis"] = result
        except (ValueError, TypeError, IndexError) as exc:
            invalidate_results(st.session_state)
            st.error(f"분석할 수 없습니다: {exc}")
    count = sum(op["type"] == "reduce_negative" for op in editor.operations)
    st.caption(
        f"음수 나누기 {count}번 적용 · 총거래표와 국산거래표에 같은 편집이 반영됩니다."
    )
    show_table(editor.total)
