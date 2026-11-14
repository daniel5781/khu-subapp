"""업로드 로딩 · 서브매트릭스 추출 · 중간수요 경계(mid_ID_idx) 탐지.

엑셀 업로드를 DataFrame 으로 읽고(`load_data`), 라벨을 포함한 부분행렬을
잘라내며(`get_submatrix_withlabel`), 중간거래 블록 X 와 최종수요/부가가치
영역의 경계 인덱스를 찾는다(`get_mid_ID_idx`).
"""

import pandas as pd
import unicodedata


def load_data(file, sheet):
    df = pd.read_excel(file, sheet_name=sheet, header=None, dtype=object)
    return df


def convert_df(df):
    return df.to_csv(header=False, index=False).encode("utf-8-sig")


def get_submatrix_withlabel(
    df, start_row, start_col, end_row, end_col, first_index_of_df, numberoflabel=2
):
    row_indexs = list(
        range(first_index_of_df[0] - numberoflabel, first_index_of_df[0])
    ) + list(range(start_row, end_row + 1))
    col_indexs = list(
        range(first_index_of_df[1] - numberoflabel, first_index_of_df[1])
    ) + list(range(start_col, end_col + 1))
    submatrix_withlabel = df.iloc[row_indexs, col_indexs]
    return submatrix_withlabel


def get_mid_ID_idx(df, first_idx):
    row, col = first_idx
    if row < 2 or col < 2 or row >= len(df) or col >= df.shape[1]:
        raise ValueError("숫자 시작 위치가 표의 범위를 벗어났습니다.")

    def normalized(value):
        return "".join(unicodedata.normalize("NFKC", str(value)).split()).lower()

    row_markers = {
        "중간투입계",
        "국산중간투입계",
        "내생부문계",
        "内生部門計",
        "intermediateinputs",
    }
    col_markers = {
        "중간수요계",
        "국산중간수요계",
        "내생부문계",
        "内生部門計",
        "intermediatedemand",
    }
    rows = [
        i for i in range(row, len(df)) if normalized(df.iat[i, col - 1]) in row_markers
    ]
    cols = [
        j
        for j in range(col, df.shape[1])
        if normalized(df.iat[row - 1, j]) in col_markers
    ]
    if len(rows) == len(cols) == 1:
        if rows[0] - row != cols[0] - col or rows[0] <= row:
            raise ValueError("중간거래 영역의 행·열 산업 수가 다릅니다.")
        return rows[0], cols[0]
    # 구형 이름 없는 표는 기존 누적합 경계 탐지를 유지한다.
    matrix_X = df.iloc[row:, col:].astype(float)
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

    if size <= 0 or row + size >= len(df) or col + size >= df.shape[1]:
        raise ValueError(
            "중간거래 합계 경계를 찾을 수 없습니다. 모드·숫자 시작 위치·원표 형식을 확인하세요."
        )
    return (row + size, col + size)
