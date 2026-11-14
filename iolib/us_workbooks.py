"""BEA Use 워크북을 한국은행 공통 레이아웃으로 변환한다."""

from typing import Dict
import numpy as np
import pandas as pd
from .config import _USE_CODES_ROW, _USE_NAMES_ROW, _USE_DATA_START


def _to_float_or_zero(x) -> float:
    if x is None:
        return 0.0
    try:
        if isinstance(x, float) and np.isnan(x):
            return 0.0
    except TypeError:
        pass
    try:
        return float(x)
    except (ValueError, TypeError):
        return 0.0


def _build_bok_layout_use(raw: pd.DataFrame, *, kind: str, year: int) -> pd.DataFrame:
    """미국_사용표_*_한국레이아웃 워크북의 연도 시트 하나를 캐노니컬 레이아웃으로
    재구성한다. kind: 'total'(총거래표) 또는 'local'(국산거래표).
    See module-level diagram for the output shape."""
    if str(raw.iat[_USE_CODES_ROW, 0]).strip() != "IOCode":
        raise ValueError(
            f"미국 사용표 한국레이아웃 파일 형식이 아닙니다 (셀 [{_USE_CODES_ROW}, 0] 이 "
            f"'IOCode' 가 아님). `미국_사용표_총거래_한국레이아웃_2000_2024.xlsx` "
            f"형식의 파일을 업로드하세요."
        )

    local = kind == "local"
    mid_col_label = "국산중간수요계" if local else "중간수요계"
    fin_col_label = "국산최종수요계" if local else "최종수요계"
    tot_col_label = "국산총수요" if local else "총수요"
    mid_row_label = "국산중간투입계" if local else "중간투입계"

    col_codes = [str(c).strip() for c in raw.iloc[_USE_CODES_ROW, 2:].tolist()]
    col_names = [str(c) for c in raw.iloc[_USE_NAMES_ROW, 2:].tolist()]
    col_pos = {c: 2 + j for j, c in enumerate(col_codes)}
    name_for = {c: col_names[j] for j, c in enumerate(col_codes)}
    for required in (mid_col_label, fin_col_label, tot_col_label):
        if required not in col_pos:
            raise ValueError(
                f"`{required}` 열을 찾지 못했습니다 — "
                f"{'국산거래표' if local else '총거래표'} 한국레이아웃 파일이 맞는지 확인하세요."
            )

    n = col_codes.index(mid_col_label)
    industry_codes = col_codes[:n]
    f_codes = col_codes[n + 1 : col_codes.index(fin_col_label)]
    k = len(f_codes)

    # 행 스캔: 상품 블록 → 총계 행들(라벨은 col 0). "(참고)" 블록은 무시.
    row_pos: Dict[str, int] = {}
    total_rows: Dict[str, int] = {}
    for r in range(_USE_DATA_START, raw.shape[0]):
        code = raw.iat[r, 0]
        if code is None or (isinstance(code, float) and np.isnan(code)):
            continue
        code = str(code).strip()
        if code.startswith("(참고)"):
            break
        if code in (mid_row_label, "수입중간투입계", "부가가치계") or code.startswith(
            ("총산출", "기타투입")
        ):
            total_rows[code.split("(")[0]] = r
        else:
            row_pos[code] = r

    if [c for c in industry_codes if c in row_pos] != industry_codes or len(
        row_pos
    ) != n:
        raise ValueError(
            "행(상품)과 열(산업) 코드가 일치하지 않습니다 — 한국레이아웃 파일이 맞는지 확인하세요."
        )
    if "총산출" not in total_rows or "부가가치계" not in total_rows:
        raise ValueError(
            "총산출(T018)/부가가치계 행을 찾지 못했습니다 — 한국레이아웃 파일이 맞는지 확인하세요."
        )
    if local and "수입중간투입계" not in total_rows:
        raise ValueError(
            "수입중간투입계 행을 찾지 못했습니다 — 국산거래표 파일이 맞는지 확인하세요."
        )

    X = np.zeros((n, n), dtype=float)
    for i, ri in enumerate(industry_codes):
        for j, ci in enumerate(industry_codes):
            X[i, j] = _to_float_or_zero(raw.iat[row_pos[ri], col_pos[ci]])

    F = np.zeros((n, k), dtype=float)
    for i, ri in enumerate(industry_codes):
        for j, fc in enumerate(f_codes):
            F[i, j] = _to_float_or_zero(raw.iat[row_pos[ri], col_pos[fc]])

    t018 = np.array(
        [
            _to_float_or_zero(raw.iat[total_rows["총산출"], col_pos[c]])
            for c in industry_codes
        ]
    )
    imp = None
    if local:
        imp = np.array(
            [
                _to_float_or_zero(raw.iat[total_rows["수입중간투입계"], col_pos[c]])
                for c in industry_codes
            ]
        )
    # 기타투입(Other, 비교불능수입 등) — 부가가치계에 넣지 않고 별도 행으로 보존.
    # (구형 파일에는 이 행이 없을 수 있으므로 없으면 0 취급 — 그 경우 부가가치계가 흡수)
    has_other = "기타투입" in total_rows
    other = (
        np.array(
            [
                _to_float_or_zero(raw.iat[total_rows["기타투입"], col_pos[c]])
                for c in industry_codes
            ]
        )
        if has_other
        else np.zeros(n)
    )

    # 경계 탐지(±0.001)가 확실히 통과하도록 파생 합계는 X/F 에서 재계산.
    row_subtotals = X.sum(axis=1)
    col_subtotals = X.sum(axis=0)
    fd = F.sum(axis=1)
    va = t018 - col_subtotals - other - (imp if local else 0)

    # Compose canonical layout.
    n_rows = 6 + n + (4 if local else 3) + (1 if has_other else 0)
    n_cols = 2 + n + 1 + k + 2
    out = pd.DataFrame(np.nan, index=range(n_rows), columns=range(n_cols), dtype=object)

    out.iat[0, 0] = f"BEA Use — {'국산거래표' if local else '총거래표'} Summary {year}"
    out.iat[1, 0] = str(year)
    out.iat[2, 0] = (
        "Use of commodities by industries, domestic (Use − import matrix)"
        if local
        else "Use of commodities by industries (total, basic prices)"
    )
    out.iat[3, 0] = "Unit: Millions of USD"

    for j, code in enumerate(industry_codes):
        out.iat[4, 2 + j] = code
        out.iat[5, 2 + j] = name_for.get(code, code)
    out.iat[4, 2 + n] = "SUBTOTAL"
    out.iat[5, 2 + n] = mid_col_label
    for j, code in enumerate(f_codes):
        out.iat[4, 2 + n + 1 + j] = code
        out.iat[5, 2 + n + 1 + j] = name_for.get(code, code)
    out.iat[4, 2 + n + 1 + k] = "FINAL_DEMAND"
    out.iat[5, 2 + n + 1 + k] = fin_col_label
    out.iat[4, 2 + n + 1 + k + 1] = "TOTAL"
    out.iat[5, 2 + n + 1 + k + 1] = tot_col_label

    for i, code in enumerate(industry_codes):
        r = 6 + i
        out.iat[r, 0] = code
        out.iat[r, 1] = name_for.get(code, code)
        for j in range(n):
            out.iat[r, 2 + j] = X[i, j]
        out.iat[r, 2 + n] = row_subtotals[i]
        for j in range(k):
            out.iat[r, 2 + n + 1 + j] = F[i, j]
        out.iat[r, 2 + n + 1 + k] = fd[i]
        out.iat[r, 2 + n + 1 + k + 1] = row_subtotals[i] + fd[i]

    r = 6 + n
    out.iat[r, 1] = mid_row_label
    for j in range(n):
        out.iat[r, 2 + j] = col_subtotals[j]
    if local:
        r += 1
        out.iat[r, 1] = "수입중간투입계"
        for j in range(n):
            out.iat[r, 2 + j] = imp[j]
    if has_other:
        r += 1
        out.iat[r, 1] = "기타투입(Other)"
        for j in range(n):
            out.iat[r, 2 + j] = other[j]
    r += 1
    out.iat[r, 1] = "부가가치계"
    for j in range(n):
        out.iat[r, 2 + j] = va[j]
    r += 1
    out.iat[r, 1] = "총투입계"
    for j in range(n):
        out.iat[r, 2 + j] = t018[j]

    return out


def _read_us_year_sheet(
    source, year: int, expected_filename: str, table_kor: str
) -> pd.DataFrame:
    expected_sheet = str(year)
    try:
        xl = pd.ExcelFile(source)
    except Exception as e:
        raise ValueError(
            f"{table_kor} 파일을 열 수 없습니다: {e}. "
            f"`{expected_filename}` 형식의 파일이어야 합니다."
        )
    with xl:
        if expected_sheet not in xl.sheet_names:
            sample = ", ".join(xl.sheet_names[:8])
            if len(xl.sheet_names) > 8:
                sample += f", ... (총 {len(xl.sheet_names)}개 시트)"
            raise ValueError(
                f"{table_kor} 파일에 '{expected_sheet}' 시트가 없습니다. "
                f"발견된 시트: {sample}.\n"
                f"`{expected_filename}` (연도별 시트 워크북) 형식이어야 합니다."
            )
        return pd.read_excel(xl, sheet_name=expected_sheet, header=None, dtype=object)
