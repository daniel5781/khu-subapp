"""파일 비율을 입력표로 가져오거나 기존 다중 대상 일괄 편집을 실행한다."""

import streamlit as st
from iolib.batch_upload import (
    inspect_batch_upload,
    prepare_batch_preview,
    infer_input_year,
)
from iolib.allocations import sector_catalog
from .tables import show_table
from .workspace import ensure_draft, import_alpha, apply_operation


def render_batch(editor):
    uploaded = st.file_uploader(
        "비율표 Excel / ZIP 가져오기", type=["xlsx", "xls", "zip"], key="alpha_file"
    )
    st.caption(
        "기존 from·to·to_name·alpha 양식(α는 0~1)과 연도별 비율표를 모두 읽습니다."
    )
    if uploaded is None:
        return
    draft = ensure_draft(st.session_state)
    source_name = st.session_state.get("source_name", "")
    stem = source_name.rsplit(".", 1)[0]
    try:
        meta = inspect_batch_upload(uploaded, stem)
        selected_year = None
        if meta["format"] == "year_ratio":
            years = meta["years"]
            original_year = infer_input_year(editor.original.df, source_name)
            index = years.index(original_year) if original_year in years else None
            if st.session_state.get("ratio_year") not in years:
                st.session_state.pop("ratio_year", None)
            selected_year = st.selectbox(
                "적용할 비율 연도",
                years,
                index=index,
                key="ratio_year",
                placeholder="연도를 선택하세요",
            )
            if selected_year is None:
                return
            if original_year is not None and selected_year != original_year:
                st.warning(
                    f"원본은 {original_year}년이며, 선택한 비율은 {selected_year}년입니다."
                )
        frame, _, _, summaries = prepare_batch_preview(
            uploaded,
            stem,
            year=selected_year,
            target_code=draft.target_code,
            target_name=draft.target_name,
            source_codes=sector_catalog(draft.base)["code"].tolist(),
        )
        records = frame.to_dict("records")
        targets = frame[["to", "to_name"]].drop_duplicates()
        existing_codes = set(sector_catalog(draft.base)["code"])
        if len(targets) == 1 and targets.iloc[0]["to"] not in existing_codes:
            st.caption(
                f"{len(frame)}개 산업의 비율을 가져옵니다. 적용 전 입력표에서 수정할 수 있습니다."
            )
            if st.button("입력표로 가져오기", key="import_alpha"):
                import_alpha(st.session_state, records)
                st.rerun()
        else:
            st.info(
                "기존 산업 또는 여러 대상 산업으로 이동하는 파일입니다. 아래 내역을 확인하고 일괄 적용하세요."
            )
            preview = frame.rename(
                columns={"from": "출발 코드", "to": "대상 코드", "to_name": "대상 이름"}
            ).copy()
            preview["이동 비율 (%)"] = preview.pop("alpha") * 100
            show_table(preview, hide_index=True)
            for summary in summaries:
                st.caption(summary)
            identical = any(
                op.get("batch_records") == records
                for op in editor.operations
                if op["type"] == "batch_apply"
            )
            if identical:
                st.info(
                    "같은 편집이 이미 적용돼 있습니다. 수정하려면 먼저 실행 취소하세요."
                )
            if (
                st.button("파일 내용 일괄 적용", disabled=identical, key="apply_batch")
                and not identical
            ):
                apply_operation(
                    st.session_state,
                    {"type": "batch_apply", "batch_records": records},
                    "파일의 일괄 편집을 반영했습니다.",
                )
                st.rerun()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        st.error(f"비율표를 가져올 수 없습니다: {exc}")
