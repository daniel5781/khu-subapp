"""Streamlit 다운로드 버튼 헬퍼 (CSV 단건 · 다건 ZIP · 원자료 파일).

주의: `donwload_data` 는 오타지만 코드 전반에서 일관되게 쓰이므로 그대로 둔다
(고칠 거면 모든 호출부를 함께 바꿔야 한다).
"""
import io
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from .loading import convert_df

_REPO_ROOT = Path(__file__).resolve().parent.parent
JAPAN_DATA_DIRNAME = "일본_산업연관표_연도별_자료"


def donwload_data(df, file_name):
    csv = convert_df(df)
    button = st.download_button(label=f"{file_name} 다운로드", data=csv, file_name=file_name+".csv", mime='text/csv')
    return button


@st.cache_data
def make_zip_bytes(dfs: dict[str, pd.DataFrame]) -> bytes:
    """
    dfs: dict where keys are desired CSV filenames and values are DataFrames.
    반환값: ZIP 파일의 바이너리
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fname, df in dfs.items():
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            zf.writestr(f"{fname}.csv", csv_bytes)
    return buf.getvalue()


def download_multiple_csvs_as_zip(dfs: dict[str, pd.DataFrame], zip_name: str):
    zip_bytes = make_zip_bytes(dfs)
    return st.download_button(
        label=f"{zip_name} 다운로드",
        data=zip_bytes,
        file_name=f"{zip_name}.zip",
        mime="application/zip",
    )


def _japan_data_files(folder: Path) -> list[Path]:
    return [
        p for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.startswith((".", "~$"))
    ]


@st.cache_data
def _japan_zip_bytes(folder_name: str) -> bytes:
    """저장소의 일본 원자료 폴더(또는 '전체')를 ZIP 바이너리로 묶는다.

    파일들은 저장소에 정적으로 커밋돼 있으므로 폴더명만으로 캐시해도 안전하다.
    """
    data_dir = _REPO_ROOT / JAPAN_DATA_DIRNAME
    base = data_dir if folder_name == "전체" else data_dir / folder_name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in _japan_data_files(base):
            zf.write(p, p.relative_to(data_dir.parent))
    return buf.getvalue()


@st.cache_data
def _japan_file_bytes(rel_path: str) -> bytes:
    return (_REPO_ROOT / JAPAN_DATA_DIRNAME / rel_path).read_bytes()


def render_japan_data_sidebar():
    """사이드바에 일본 산업연관표 연도별 원자료 다운로드 섹션을 그린다.

    협업자가 앱에서 바로 원자료를 받을 수 있도록 저장소의
    `일본_산업연관표_연도별_자료/` 를 폴더별 ZIP + 개별 파일로 노출한다.
    """
    data_dir = _REPO_ROOT / JAPAN_DATA_DIRNAME
    with st.sidebar.expander("일본 산업연관표 연도별 자료"):
        if not data_dir.is_dir():
            st.write(f"저장소에 `{JAPAN_DATA_DIRNAME}` 폴더가 없습니다.")
            return
        folders = sorted(p.name for p in data_dir.iterdir() if p.is_dir())
        choice = st.selectbox(
            "폴더 선택", ["전체"] + folders, key="japan_data_folder"
        )
        target = data_dir if choice == "전체" else data_dir / choice
        files = _japan_data_files(target)
        zip_name = (
            JAPAN_DATA_DIRNAME if choice == "전체"
            else f"{JAPAN_DATA_DIRNAME}_{choice}"
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
