"""단일 새 산업으로 분리하는 백분율 입력표와 적용 전 미리보기."""

from dataclasses import replace
from io import BytesIO
import pandas as pd
import streamlit as st
from iolib.allocations import sector_catalog, percentage_preview
from .batch import render_batch
from .tables import show_table
from .workspace import (
    ensure_draft,
    grid_seed,
    capture_grid_changes,
    invalidate_grid,
    rebuild_alpha_widgets,
    apply_alpha,
    calculate,
    remove_alpha_split,
)


def _capture(key, seed):
    capture_grid_changes(st.session_state, key, seed)


def _xlsx(records):
    buffer = BytesIO()
    pd.DataFrame(records, columns=["from", "to", "to_name", "alpha"]).to_excel(
        buffer, index=False
    )
    return buffer.getvalue()


def render_alpha(editor):
    state = st.session_state
    draft = ensure_draft(state)
    catalog = sector_catalog(draft.base)
    st.subheader("여러 산업에서 새 산업으로 분리")
    st.caption(
        "새 산업을 정하고 각 산업의 이동 비율을 입력하세요. 20%를 옮기려면 20을 입력합니다. α=0.2와 같습니다."
    )
    left, right = st.columns([1, 2])
    code = left.text_input(
        "새 산업 코드",
        value=draft.target_code,
        key="alpha_target_code",
        help="기존 표에 없는 고유한 코드입니다.",
    )
    name = right.text_input(
        "새 산업 이름", value=draft.target_name, key="alpha_target_name"
    )
    draft = replace(draft, target_code=code, target_name=name)
    state["alpha_draft"] = draft
    if draft.applied_percentages is not None:
        st.info(
            "현재 분리 설정을 수정하고 있습니다. 비율을 바꿔 다시 적용하면 분리 전 표에서 재계산합니다."
        )
    with st.expander("Excel / ZIP에서 비율 가져오기"):
        render_batch(editor)
    search = st.text_input(
        "산업 찾기", key="alpha_search", placeholder="산업 이름 또는 코드로 검색"
    )
    seed, key = grid_seed(state, catalog, search)
    st.caption(
        f"전체 {len(catalog)}개 중 {len(seed)}개 산업 표시 · 검색으로 숨겨진 산업의 입력값도 유지되고 함께 적용됩니다."
    )
    if len(seed):
        edited = st.data_editor(
            seed,
            key=key,
            on_change=_capture,
            args=(key, seed),
            hide_index=True,
            num_rows="fixed",
            width="stretch",
            height=min(460, 38 * (len(seed) + 1) + 12),
            disabled=["code", "name"],
            column_config={
                "code": st.column_config.TextColumn("산업 코드", width="small"),
                "name": st.column_config.TextColumn("산업 이름", width="large"),
                "percent": st.column_config.NumberColumn(
                    "이동 비율 (%)",
                    min_value=0.0,
                    max_value=100.0,
                    format="plain",
                    help="0~100을 입력하세요. 빈칸과 0은 이동하지 않습니다. Excel의 여러 셀을 붙여넣을 수 있습니다.",
                ),
            },
        )
        values = dict(state["alpha_draft"].percentages)
        # 이름/코드는 편집할 수 없다. 기준 행의 코드로만 입력값을 연결한다.
        for index, value in enumerate(edited["percent"]):
            values[seed.iloc[index]["code"]] = None if pd.isna(value) else value
        state["alpha_draft"] = replace(state["alpha_draft"], percentages=values)
    else:
        st.info("검색 결과가 없습니다. 검색어를 바꿔보세요.")
    with st.expander("여러 산업에 같은 비율 입력 / 입력값 지우기"):
        fill = st.number_input(
            "표시 중인 산업에 입력할 비율 (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=0.1,
            key="alpha_fill_percent",
        )
        left, right = st.columns(2)
        if left.button(
            "표시 중인 산업에 채우기", key="alpha_fill", disabled=seed.empty
        ):
            draft = state["alpha_draft"]
            state["alpha_draft"] = replace(
                draft,
                percentages={**draft.percentages, **dict.fromkeys(seed["code"], fill)},
            )
            invalidate_grid(state)
            st.rerun()
        if right.button("입력 비율 모두 지우기", key="alpha_clear"):
            draft = state["alpha_draft"]
            state["alpha_draft"] = replace(
                draft, percentages=dict.fromkeys(catalog["code"], 0.0)
            )
            invalidate_grid(state)
            st.rerun()
    draft = state["alpha_draft"]
    records, valid = [], True
    try:
        records = draft.records()
    except ValueError as exc:
        valid = False
        st.error(str(exc))
    if records:
        st.markdown(
            f"**적용 전 확인 · {len(records)}개 산업 → {draft.target_name} ({draft.target_code})**"
        )
        show_table(
            percentage_preview(records, catalog), hide_index=True, width="stretch"
        )
        if not draft.dirty:
            st.success("입력한 비율이 이미 편집표에 반영돼 있습니다.")
        else:
            st.caption(
                "아래 버튼을 눌러야 편집표에 반영됩니다. 총거래표와 국산거래표에 함께 적용합니다."
            )
    elif valid:
        if draft.applied_percentages is not None:
            st.info(
                "입력 비율을 모두 지웠습니다. 기존 분리는 아직 유지됩니다. 분리를 없애려면 아래 ‘현재 분리 해제’를 사용하세요."
            )
        else:
            st.caption(
                "이동할 산업의 비율을 입력하면 미리보기가 표시됩니다. 아직 편집표는 바뀌지 않았습니다."
            )
    left, right = st.columns(2)
    apply_and_analyze = left.button(
        "비율 적용 및 경제지표 계산",
        type="primary",
        key="alpha_apply_analyze",
        disabled=not (valid and records),
    )
    apply_only = right.button(
        "편집표에만 적용",
        key="alpha_apply",
        disabled=not (valid and records and draft.dirty),
    )
    if apply_only or apply_and_analyze:
        applied = False
        try:
            with st.spinner("산업별 비율을 반영하고 있습니다."):
                applied = apply_alpha(state)
                if apply_and_analyze:
                    calculate(state)
            st.rerun()
        except (ValueError, TypeError, KeyError, IndexError, ArithmeticError) as exc:
            prefix = (
                "비율은 편집표에 반영했지만 경제지표를 계산하지 못했습니다"
                if applied
                else "적용·계산을 마치지 못했습니다"
            )
            state["workspace_notice"] = ("error", f"{prefix}: {exc}")
            st.rerun()
    with st.expander("비율표 저장 · 분리 해제 · 다른 산업 분리"):
        if st.button(
            "현재 분리 해제",
            key="alpha_remove_split",
            disabled=draft.applied_percentages is None,
        ):
            remove_alpha_split(state)
            st.rerun()
        template = records or [
            {"from": c, "to": code, "to_name": name, "alpha": 0.0}
            for c in catalog["code"]
        ]
        st.download_button(
            "비율표 Excel 저장",
            _xlsx(template),
            "sector_alpha.xlsx",
            key="alpha_download",
            disabled=not valid,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption(
            "파일은 다시 가져올 수 있는 기존 표준 양식입니다. alpha 열에는 20%=0.2처럼 0~1 값이 저장됩니다."
        )
        if st.button(
            "다른 새 산업 분리 시작",
            key="alpha_new_plan",
            disabled=draft.applied_percentages is None,
        ):
            state["alpha_draft"] = None
            rebuild_alpha_widgets(state)
            state["workspace_notice"] = (
                "info",
                "현재 편집표를 기준으로 새 분리 작업을 시작합니다.",
            )
            st.rerun()
