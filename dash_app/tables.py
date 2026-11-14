"""혼합형 산업연관표를 검색 가능한 AG Grid 데이터로 변환한다."""

import math
import numpy as np
import pandas as pd

METRIC_TABLES = {"FL_BL", "GDP", "부가가치유발효과", "g_series"}
RAW_TABLES = {
    "uploaded_df",
    "uploaded_df_local",
    "edited_df",
    "edited_df_local",
    "editor",
}


def scalar(value):
    if value is None or value is pd.NA:
        return None
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, float, int, bool)):
        return value
    return None if pd.isna(value) else str(value)


def grid_payload(frame, name=""):
    if frame is None:
        return [], []
    if isinstance(frame, pd.Series):
        frame = frame.rename("값").to_frame().reset_index(names="산업 위치")
    data = frame.copy()
    if name in METRIC_TABLES:
        headers = [str(value) for value in data.iloc[0]]
        data = data.iloc[1:]
        headers[:2] = ["산업 코드", "산업 이름"]
    elif (
        name not in RAW_TABLES
        and len(data) >= 2
        and all(isinstance(c, int) for c in data.columns)
    ):
        headers = ["산업 코드", "산업 이름"] + [str(v) for v in data.iloc[1, 2:]]
        data = data.iloc[2:]
    else:
        headers = [str(column) for column in data.columns]
        if name not in RAW_TABLES and list(data.columns[:2]) == [0, 1]:
            headers[:2] = ["산업 코드", "산업 이름"]
    fields = [f"c{index}" for index in range(len(headers))]
    columns = [
        {
            "field": field,
            "headerName": title,
            "pinned": "left" if i < 2 else None,
            "minWidth": 120 if i else 95,
            "cellDataType": False,
        }
        for i, (field, title) in enumerate(zip(fields, headers))
    ]
    rows = [
        dict(zip(fields, map(scalar, row)))
        for row in data.itertuples(index=False, name=None)
    ]
    return rows, columns
