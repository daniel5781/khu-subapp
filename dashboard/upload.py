"""모드·파일 선택과 업로드 오류 표시."""

from dataclasses import replace
from io import BytesIO
import streamlit as st
from iolib import preprocessing
from iolib.session import EditingSession
from .state import reset_source, source_revision


@st.cache_data(show_spinner=False)
def _load(content, mode, year, first_idx, revision):
    source = BytesIO(content) if isinstance(content, bytes) else content
    return preprocessing.load_workbook(source, mode, us_year=year, first_idx=first_idx)


def render_upload():
    mode = st.radio("모드 선택", preprocessing.MODES, key="mode")
    params = preprocessing.get_mode_params(mode)
    manual_start = None
    if mode == "Manual":
        st.caption(
            "코드·이름 라벨 2행/2열, 중간수요·중간투입 합계, 마지막 두 행은 부가가치계·총투입계인 표를 사용하세요."
        )
        left, right = st.columns(2)
        row = left.number_input("숫자 시작 행 (1부터)", min_value=3, value=7, step=1)
        col = right.number_input("숫자 시작 열 (1부터)", min_value=3, value=3, step=1)
        manual_start = (int(row) - 1, int(col) - 1)
        params = replace(params, first_idx=manual_start)
    year = None
    if mode.startswith("US"):
        years = preprocessing.available_us_years(mode)
        if years:
            year = st.selectbox("연도 선택", years, index=len(years) - 1, key="us_year")
        else:
            st.error("미국 총거래·국산거래 워크북을 데이터 폴더에서 찾지 못했습니다.")
    uploaded = st.file_uploader(
        "여기에 파일을 드래그하거나 클릭하여 업로드하세요.",
        type=["xls", "xlsx"],
        key="source_file",
    )
    source = uploaded
    if source is None and mode.startswith("US") and year is not None:
        source = preprocessing.us_use_file_path(mode)
        st.info(f"저장소의 {source.name} ({year}년)과 국산거래표를 사용합니다.")
    source_name = getattr(source, "name", "")
    domestic_revision = (
        source_revision(preprocessing.us_local_file_path(mode))
        if mode.startswith("US") and year
        else None
    )
    signature = (
        mode,
        year,
        manual_start,
        source_name,
        source_revision(source),
        domestic_revision,
    )
    reset_source(st.session_state, signature)
    if source is None or (mode.startswith("US") and year is None):
        return None
    if "editor" not in st.session_state:
        try:
            content = source.getvalue() if hasattr(source, "getvalue") else str(source)
            with st.spinner("산업연관표를 읽고 있습니다."):
                loaded = _load(content, mode, year, manual_start, signature)
                st.session_state["editor"] = EditingSession.from_loaded(loaded, params)
        except (ValueError, TypeError, IndexError, KeyError, OSError) as exc:
            st.error(f"파일을 읽을 수 없습니다: {exc}")
            return None
    st.session_state["source_name"] = source_name
    return st.session_state["editor"]
