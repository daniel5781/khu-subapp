"""Streamlit 다운로드 버튼 헬퍼 (CSV 단건 · 다건 ZIP · 원자료 파일).

주의: `donwload_data` 는 오타지만 코드 전반에서 일관되게 쓰이므로 그대로 둔다
(고칠 거면 모든 호출부를 함께 바꿔야 한다).
"""

import pandas as pd
import streamlit as st

from iolib.loading import convert_df
from iolib.config import get_data_dir
from iolib.exports import make_zip_bytes

from iolib.resources import (
    JAPAN_DATA_DIRNAME,
    japan_files as _japan_data_files,
    japan_zip_bytes as _japan_zip_bytes,
    japan_file_bytes as _japan_file_bytes,
)


def download_data(df, file_name):
    csv = convert_df(df)
    button = st.download_button(
        label=f"{file_name} 다운로드",
        data=csv,
        file_name=file_name + ".csv",
        mime="text/csv",
    )
    return button


def download_multiple_csvs_as_zip(dfs: dict[str, pd.DataFrame], zip_name: str):
    zip_bytes = make_zip_bytes(dfs)
    return st.download_button(
        label=f"{zip_name} 다운로드",
        data=zip_bytes,
        file_name=f"{zip_name}.zip",
        mime="application/zip",
    )


def render_japan_data_sidebar():
    """사이드바에 일본 산업연관표 연도별 원자료 다운로드 섹션을 그린다.

    협업자가 앱에서 바로 원자료를 받을 수 있도록 저장소의
    `일본_산업연관표_연도별_자료/` 를 폴더별 ZIP + 개별 파일로 노출한다.
    """
    data_dir = get_data_dir() / JAPAN_DATA_DIRNAME
    with st.sidebar.expander("일본 산업연관표 연도별 자료"):
        if not data_dir.is_dir():
            st.write(f"저장소에 `{JAPAN_DATA_DIRNAME}` 폴더가 없습니다.")
            return
        folders = sorted(p.name for p in data_dir.iterdir() if p.is_dir())
        choice = st.selectbox("폴더 선택", ["전체"] + folders, key="japan_data_folder")
        target = data_dir if choice == "전체" else data_dir / choice
        files = _japan_data_files(target)
        zip_name = (
            JAPAN_DATA_DIRNAME if choice == "전체" else f"{JAPAN_DATA_DIRNAME}_{choice}"
        )
        st.download_button(
            label=f"{choice} ZIP 다운로드 ({len(files)}개 파일)",
            data=_japan_zip_bytes(choice),
            file_name=f"{zip_name}.zip",
            mime="application/zip",
            key="japan_data_zip",
        )
        if choice != "전체":
            st.caption("개별 파일")
            for p in files:
                rel = p.relative_to(data_dir)
                st.download_button(
                    label=p.name,
                    data=_japan_file_bytes(str(rel)),
                    file_name=p.name,
                    key=f"japan_data_file_{rel}",
                )
