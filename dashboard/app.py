"""단계별 화면과 공통 작업 상태를 조립하는 Streamlit 진입점."""

from pathlib import Path
import streamlit as st
from dashboard.upload import render_upload
from dashboard.editing import render_editor
from dashboard.analysis import render_analysis
from dashboard.network import render_network
from dashboard.downloads import (
    download_data,
    download_multiple_csvs_as_zip,
    render_japan_data_sidebar,
)
from dashboard.state import collect_exports
from dashboard.labels import result_label
from dashboard.workspace import (
    prepare_widgets,
    invalidate_grid,
    undo,
    redo,
    reset_edits,
)

VIEWS = ["산업 편집", "경제지표", "네트워크", "내보내기"]


def render_toolbar(editor):
    left, middle, right = st.columns(3)
    left.metric("현재 산업 수", editor.mid[0] - editor.params.first_idx[0])
    middle.metric("반영된 편집", len(editor.operations))
    right.metric(
        "경제지표", "계산 완료" if "analysis" in st.session_state else "계산 전"
    )
    left, middle, right = st.columns(3)
    if left.button(
        "실행 취소",
        key="undo_edit",
        disabled=not st.session_state.get("undo_stack"),
        width="stretch",
    ):
        undo(st.session_state)
        st.rerun()
    if middle.button(
        "다시 실행",
        key="redo_edit",
        disabled=not st.session_state.get("redo_stack"),
        width="stretch",
    ):
        redo(st.session_state)
        st.rerun()
    if right.button(
        "원본으로 되돌리기",
        key="reset_edits",
        disabled=not editor.operations,
        width="stretch",
    ):
        reset_edits(st.session_state)
        st.rerun()


def render_exports(editor):
    frames = collect_exports(
        editor, st.session_state.get("analysis"), st.session_state.get("network_frames")
    )
    st.subheader("결과 저장")
    st.caption(
        "현재 원본·편집본·계산 결과를 내려받습니다. 경제지표와 네트워크는 마지막으로 계산한 결과만 포함됩니다."
    )
    download_multiple_csvs_as_zip(frames, "IO_analysis_all_results")
    if st.session_state.get("export_choice") not in frames:
        st.session_state.pop("export_choice", None)
    name = st.selectbox(
        "개별 결과 선택", list(frames), format_func=result_label, key="export_choice"
    )
    if name:
        download_data(frames[name], name)
    with st.expander("편집 이력", expanded=True):
        st.text(
            "\n\n".join(editor.logs) if editor.logs else "아직 반영한 편집이 없습니다."
        )
    render_japan_data_sidebar()


def main():
    st.set_page_config(page_title="산업연관 분석", layout="wide")
    with st.sidebar:
        st.header("원자료 선택")
        editor = render_upload()
        st.caption("원자료를 바꾸면 편집과 계산 결과가 초기화됩니다.")
    prepare_widgets(st.session_state)
    # 비활성 화면에서 위젯이 정리되더라도 네트워크 설정은 보존한다.
    for key in (
        "network_method",
        "threshold_input",
        "mb_epsilon",
        "mb_delta",
        "mb_max_iter",
        "new_code",
        "new_name",
        "origin_code",
        "target_code",
        "transfer_percent",
        "alpha_fill_percent",
    ):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    st.title("산업연관 분석")
    st.caption("원자료 선택 → 산업별 비율 입력 → 적용 및 계산")
    if editor is None:
        st.info(
            "왼쪽에서 산업연관표를 업로드하세요. 미국 자료는 분류와 연도를 선택하면 바로 시작할 수 있습니다."
        )
        return
    st.caption(
        f"{st.session_state.get('mode', '')} · {Path(st.session_state.get('source_name', '')).name}"
    )
    render_toolbar(editor)
    if notice := st.session_state.pop("workspace_notice", None):
        getattr(st, notice[0])(notice[1])
    if next_view := st.session_state.pop("_next_view", None):
        st.session_state["workspace_view"] = next_view
    view = st.radio(
        "작업 화면",
        VIEWS,
        horizontal=True,
        key="workspace_view",
        label_visibility="collapsed",
    )
    analysis = st.session_state.get("analysis")
    if view == "산업 편집":
        render_editor(editor)
        return
    # 비활성 화면의 위젯 정리 후에도 입력 초안으로 다시 표를 구성할 수 있게 한다.
    invalidate_grid(st.session_state)
    draft = st.session_state.get("alpha_draft")
    if draft and draft.dirty:
        st.info(
            "아직 적용하지 않은 비율 입력이 있습니다. 현재 결과에는 포함되지 않았습니다."
        )
    if view == "내보내기":
        render_exports(editor)
    elif analysis is None:
        st.info(
            "산업 편집 화면에서 ‘비율 적용 및 경제지표 계산’ 또는 ‘현재 편집표로 경제지표 계산’을 실행하세요."
        )
    elif view == "경제지표":
        render_analysis(analysis, editor)
    else:
        try:
            render_network(analysis, editor)
        except (ValueError, ArithmeticError) as exc:
            st.session_state.pop("network_frames", None)
            st.session_state.pop("network_result", None)
            st.error(f"네트워크를 분석할 수 없습니다: {exc}")


if __name__ == "__main__":
    main()
