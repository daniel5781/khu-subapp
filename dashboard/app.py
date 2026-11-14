"""대시보드 구성요소의 실행 순서만 관리하는 진입점."""

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


def main():
    st.set_page_config(page_title="산업연관데이터 DashBoard", layout="wide")
    st.title("산업연관데이터 DashBoard")
    editor = render_upload()
    if editor is not None:
        render_editor(editor)
        editor = st.session_state["editor"]
        analysis = st.session_state.get("analysis")
        if analysis is not None:
            render_analysis(analysis, editor)
            try:
                render_network(analysis, editor)
            except (ValueError, ArithmeticError) as exc:
                st.session_state.pop("network_frames", None)
                st.session_state.pop("network_result", None)
                st.error(f"네트워크를 분석할 수 없습니다: {exc}")
    else:
        st.info("산업연관표를 업로드하거나 미국 모드의 연도를 선택하세요.")
    st.sidebar.header("다운로드")
    frames = collect_exports(
        editor, st.session_state.get("analysis"), st.session_state.get("network_frames")
    )
    with st.sidebar.expander("전체 결과 ZIP 다운로드"):
        if frames:
            download_multiple_csvs_as_zip(frames, "IO_analysis_all_results")
        else:
            st.write("아직 저장된 결과가 없습니다.")
    if frames:
        with st.sidebar.expander("개별 결과 다운로드"):
            for name, frame in frames.items():
                download_data(frame, name)
    render_japan_data_sidebar()
    with st.sidebar.expander("수정내역 보기"):
        st.text("\n\n".join(editor.logs) if editor else "")


if __name__ == "__main__":
    main()
