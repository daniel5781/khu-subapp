"""작은 해석 가능한 산업연관표. 사용자의 외부 파일에 의존하지 않는다."""

import numpy as np
import pandas as pd
from iolib.models import LoadResult


def workbook_table(x=None, first_idx=(6, 2)):
    x = (
        np.array([[20.0, 6.0], [4.0, 15.0]])
        if x is None
        else np.asarray(x, dtype=float)
    )
    n = len(x)
    row, col = first_idx
    mid = (row + n, col + n)
    frame = pd.DataFrame(
        np.nan, index=range(row + n + 3), columns=range(col + n + 3), dtype=object
    )
    frame.iloc[row:, col:] = 0.0
    frame.iat[0, 0] = "총거래표"
    frame.iat[1, 0] = "2024"
    codes = [f"S{i}" for i in range(n)]
    names = [f"산업 {i}" for i in range(n)]
    frame.iloc[row - 2, col : mid[1]] = codes
    frame.iloc[row - 1, col : mid[1]] = names
    frame.iloc[row : mid[0], col - 2] = codes
    frame.iloc[row : mid[0], col - 1] = names
    frame.iat[row - 1, mid[1]] = "중간수요계"
    frame.iat[row - 1, mid[1] + 1] = "최종수요계"
    frame.iat[row - 1, mid[1] + 2] = "총수요"
    frame.iat[mid[0], col - 1] = "중간투입계"
    frame.iat[mid[0] + 1, col - 1] = "부가가치계"
    frame.iat[mid[0] + 2, col - 1] = "총투입계"
    frame.iloc[row : mid[0], col : mid[1]] = x
    frame.iloc[row : mid[0], mid[1]] = x.sum(axis=1)
    frame.iloc[mid[0], col : mid[1]] = x.sum(axis=0)
    frame.iloc[row : mid[0], mid[1] + 1] = 100.0 - x.sum(axis=1)
    frame.iloc[row : mid[0], mid[1] + 2] = 100.0
    frame.iloc[-2, col : mid[1]] = 100.0 - x.sum(axis=0)
    frame.iloc[-1, col : mid[1]] = 100.0
    return frame, mid


def loaded_tables():
    total, mid = workbook_table()
    domestic, _ = workbook_table(np.array([[20.0, 6.0], [4.0, 15.0]]) * 0.8)
    domestic.iat[0, 0] = "국산거래표"
    return LoadResult(total, domestic, mid, mid, [], [])
