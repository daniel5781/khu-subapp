"""업로드 로딩 · 서브매트릭스 추출 · 중간수요 경계(mid_ID_idx) 탐지.

엑셀 업로드를 DataFrame 으로 읽고(`load_data`), 라벨을 포함한 부분행렬을
잘라내며(`get_submatrix_withlabel`), 중간거래 블록 X 와 최종수요/부가가치
영역의 경계 인덱스를 찾는다(`get_mid_ID_idx`).
"""
import numpy as np
import pandas as pd
import streamlit as st


@st.cache_data()
def load_data(file, sheet):
    df = pd.read_excel(file, sheet_name=sheet, header=None, dtype=object)
    return df


@st.cache_data
def convert_df(df):
    return df.to_csv(header=False, index=False).encode('utf-8-sig')


@st.cache_data()
def get_submatrix_withlabel(df, start_row, start_col, end_row, end_col, first_index_of_df, numberoflabel=2):
    row_indexs = list(range(first_index_of_df[0]-numberoflabel, first_index_of_df[0])) + list(range(start_row, end_row+1))
    col_indexs = list(range(first_index_of_df[1]-numberoflabel, first_index_of_df[1])) + list(range(start_col, end_col+1))
    submatrix_withlabel = df.iloc[row_indexs, col_indexs]
    return submatrix_withlabel


def get_mid_ID_idx(df, first_idx):
    matrix_X = df.iloc[first_idx[0]:, first_idx[1]:].astype(float)
    row_cnt, col_cnt, row_sum, col_sum = 0, 0, 0, 0
    for v in matrix_X.iloc[0]:
        if abs(row_sum - v) < 0.001:
            if v == 0:
                continue
            else:
                break
        row_cnt += 1
        row_sum += v
    for v in matrix_X.iloc[:, 0]:
        if abs(col_sum - v) < 0.001:
            if v == 0:
                continue
            else:
                break
        col_cnt += 1
        col_sum += v

    if row_cnt == col_cnt:
        size = row_cnt
    else:
        size = max(row_cnt, col_cnt)

    return (first_idx[0]+size, first_idx[1]+size)
