"""Per-mode upload preprocessing for the I/O dashboard.

`app.py` selects a mode then calls `load_workbook(uploaded_file, mode)`. The
result is the same canonical bundle for every mode, so the backend math in
`functions.py` does not need to know which country / vintage produced it.

Adding a new mode = add an entry to MODES + _PARAMS and (if the upload layout
differs from the standard 2-sheet Korean BoK workbook) write a new private
loader and dispatch to it from `load_workbook`.

Upload contract for non-US modes: sheet 0 = Total Transactions Table
(생산자가격), sheet 1 = Import Transactions Table (생산자가격). Both come in
the BoK layout where labels are at the first `number_of_label` rows/cols and
the numeric block starts at `first_idx`.

US modes use BEA "Domestic Supply of Commodities by Industries" square
workbooks (`Supply_Sector_square.xlsx` / `Supply_Summary_square.xlsx`), one
year per sheet (1997~2024). Rows(상품)와 열(산업)이 같은 코드 집합을 갖도록
미리 정방으로 정리된 파일이며, `_build_bok_layout_supply` 가 이를 한국은행
레이아웃(first_idx=(6,2))으로 재구성해 이후 파이프라인이 한국 모드와 동일하게
동작한다. 공급표에는 수입표(sheet 1) 대응물이 없으므로 df_local 은 df 의
복사본을 쓴다.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from iolib import load_data, get_mid_ID_idx


@dataclass(frozen=True)
class ModeParams:
    first_idx: Any  # (row, col) tuple for upload modes; legacy `0` for Manual.
    subplus_edit: bool
    number_of_label: int


@dataclass(frozen=True)
class LoadResult:
    df: pd.DataFrame
    df_local: pd.DataFrame
    mid_ID_idx: Tuple[int, int]
    mid_ID_idx_local: Tuple[int, int]
    string_values: List[Tuple[Any, Any, str]]
    string_values_local: List[Tuple[Any, Any, str]]


# Order matches the radio displayed in app.py.
MODES: List[str] = [
    "Korea(2010~2020)",
    "Japan(2000~2020)",
    "Korea(1990~2005)",
    "Manual",
    "US(Supply Sector)",
    "US(Supply Summary)",
]

_PARAMS = {
    "Korea(2010~2020)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "Japan(2000~2020)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "Korea(1990~2005)": ModeParams(first_idx=(5, 2), subplus_edit=True,  number_of_label=2),
    "Manual":           ModeParams(first_idx=0,      subplus_edit=False, number_of_label=2),
    "US(Supply Sector)":  ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "US(Supply Summary)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
}


# US-only config — BEA Domestic Supply square workbooks (연도별 시트 1997~2024).
_US_CONFIG: Dict[str, Dict[str, Any]] = {
    "US(Supply Sector)": {
        "level": "Sector",       # 15개 대분류 산업
        "use_filename": "Supply_Sector_square.xlsx",
    },
    "US(Supply Summary)": {
        "level": "Summary",      # 71개 중분류 산업
        "use_filename": "Supply_Summary_square.xlsx",
    },
}

# Supply_*_square.xlsx 내부 고정 레이아웃 (0-index).
#   row 5 = 열 코드(col 2..), row 6 = ['IOCode','Name', 열 이름...],
#   row 7.. = 상품(commodity) 행 (col 0=코드, col 1=이름),
#   마지막 행 = 'Total industry supply' (col 0 은 빈칸).
_SUPPLY_CODES_ROW = 5
_SUPPLY_NAMES_ROW = 6
_SUPPLY_DATA_START = 7
# 산업 블록 오른쪽의 부속(공급 구성) 열 중 총공급(구매자가격) 열 코드.
_SUPPLY_TOTAL_COL = "T016"


def get_mode_params(mode: str) -> ModeParams:
    return _PARAMS[mode]


def get_us_config(mode: str) -> Dict[str, Any]:
    """Read-only view of `_US_CONFIG[mode]` for app.py UI hints (filename, level)."""
    return dict(_US_CONFIG.get(mode, {}))


def us_use_file_path(mode: str) -> Path | None:
    """Repo path to the BEA Use workbook for a US mode, or None. The file ships
    in the repo, so app.py can auto-load it when the user hasn't uploaded one."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return None
    return Path(__file__).resolve().parent / cfg["use_filename"]


def _find_string_values(df: pd.DataFrame, first_idx) -> List[Tuple[Any, Any, str]]:
    selected = df.iloc[first_idx[0]:, first_idx[1]:]
    out: List[Tuple[Any, Any, str]] = []
    for row_idx, row in selected.iterrows():
        for col_idx, value in row.items():
            if isinstance(value, str):
                out.append((row_idx, col_idx, value))
    return out


def _replace_string_with_na(df: pd.DataFrame, locations) -> None:
    for row_idx, col_idx, _ in locations:
        df.iloc[row_idx, col_idx] = np.nan


def _slice_until_first_non_nan_row(df: pd.DataFrame) -> pd.DataFrame:
    last_valid = None
    for row_idx in reversed(range(df.shape[0])):
        if not df.iloc[row_idx].isna().all():
            last_valid = row_idx
            break
    if last_valid is None:
        return pd.DataFrame()
    return df.iloc[: last_valid + 1]


def _post_clean(df: pd.DataFrame, df_local: pd.DataFrame, params: ModeParams) -> LoadResult:
    fi = params.first_idx

    sv       = _find_string_values(df,       fi)
    sv_local = _find_string_values(df_local, fi)
    _replace_string_with_na(df,       sv)
    _replace_string_with_na(df_local, sv_local)

    df       = _slice_until_first_non_nan_row(df)
    df_local = _slice_until_first_non_nan_row(df_local)

    mid       = get_mid_ID_idx(df,       fi)
    mid_local = get_mid_ID_idx(df_local, fi)

    df.iloc[fi[0]:, fi[1]:]       = df.iloc[fi[0]:, fi[1]:].apply(pd.to_numeric, errors="coerce")
    df_local.iloc[fi[0]:, fi[1]:] = df_local.iloc[fi[0]:, fi[1]:].apply(pd.to_numeric, errors="coerce")

    if params.subplus_edit:
        df = df.iloc[:-1]

    return LoadResult(
        df=df,
        df_local=df_local,
        mid_ID_idx=mid,
        mid_ID_idx_local=mid_local,
        string_values=sv,
        string_values_local=sv_local,
    )


def _load_two_sheet(uploaded_file, params: ModeParams) -> LoadResult:
    """Loader for workbooks where sheet 0 = Total and sheet 1 = Import in the
    canonical Korean BoK layout (Korea / Japan / Manual)."""
    df       = load_data(uploaded_file, 0)
    df_local = load_data(uploaded_file, 1)
    return _post_clean(df, df_local, params)


# ---------------------------------------------------------------------------
# US (BEA Domestic Supply) loader — 상품 × 산업 정방 공급표
# ---------------------------------------------------------------------------
#
# Supply_*_square.xlsx 는 BEA "Domestic Supply of Commodities by Industries"
# 표에서 행(상품)과 열(산업)이 같은 코드 집합이 되도록 비교불능 행(Used/Other)
# 을 제거한 정방 파일이다. 이를 한국은행 레이아웃(first_idx=(6,2))으로 재구성해
# 이후 파이프라인(편집 → Leontief → 네트워크)이 한국 모드와 동일하게 돌아간다.
#
# Synthesized layout per sheet (n = 산업 수, k = 부속 공급구성 열 수):
#
#                col 0   col 1     cols 2..2+n-1   col 2+n    cols 2+n+1..2+n+k  col 2+n+k+1   col 2+n+k+2
#   row 0        title   ─        ─              ─          ─                 ─             ─
#   row 1        year    ─        ─              ─          ─                 ─             ─
#   row 2        note    ─        ─              ─          ─                 ─             ─
#   row 3        units   ─        ─              ─          ─                 ─             ─
#   row 4        ─       ─        industry codes  SUBTOTAL   T007..T016 코드    FINAL_DEMAND  TOTAL
#   row 5        ─       ─        industry names  중간수요계  (파일 원본 이름)    최종수요계     총산출
#   row 6..6+n-1 code    name     X_ij            Σ X row    파일 원본 값        T016-Σ X row  T016
#   row 6+n      ─       중간투입계  Σ X col        ─          ─                 ─             ─
#   row 6+n+1    ─       부가가치계  총공급-Σ X col  ─          ─                 ─             ─
#   row 6+n+2    ─       총투입계   총공급(파일 값)  ─          ─                 ─             ─
#
# `get_mid_ID_idx` walks the first data row, stopping at the SUBTOTAL cell,
# which lands `mid_ID_idx` at (6+n, 2+n). SUBTOTAL/중간투입계 는 파일의
# T007/Total 행을 그대로 쓰지 않고 X 블록에서 다시 계산한다 — 파일 값은 ±1
# 반올림 차이가 있어 경계 탐지(±0.001 허용)가 어긋날 수 있기 때문.
#
# ⚠️ 공급표 특성상 열합계(Σ X col) ≈ 총공급이라 부가가치계 ≈ 0 이고 투입계수
# 행렬의 열합이 1에 매우 가깝다. (I-A)⁻¹ 는 수치적으로 매우 불안정하므로 이
# 모드의 의미 있는 산출물은 네트워크 추출·중심성 분석 쪽이다.

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


def _build_bok_layout_supply(raw: pd.DataFrame, *, level: str, year: int) -> pd.DataFrame:
    """BEA Domestic Supply square 시트 하나를 한국은행 레이아웃으로 재구성한다.
    See module-level diagram for the output shape."""
    if str(raw.iat[_SUPPLY_NAMES_ROW, 0]).strip() != "IOCode":
        raise ValueError(
            f"Supply square 파일 형식이 아닙니다 (셀 [{_SUPPLY_NAMES_ROW}, 0] 이 'IOCode' 가 아님). "
            f"`Supply_Sector_square.xlsx` 또는 `Supply_Summary_square.xlsx` 를 업로드하세요."
        )

    col_codes = [str(c).strip() for c in raw.iloc[_SUPPLY_CODES_ROW, 2:].tolist()]
    col_names = [str(c) for c in raw.iloc[_SUPPLY_NAMES_ROW, 2:].tolist()]
    col_pos = {c: 2 + j for j, c in enumerate(col_codes)}
    name_for = {c: col_names[j] for j, c in enumerate(col_codes)}
    if _SUPPLY_TOTAL_COL not in col_pos:
        raise ValueError(f"총공급 열 `{_SUPPLY_TOTAL_COL}` 을 찾지 못했습니다 — Supply square 파일이 맞는지 확인하세요.")

    # 상품(행) 블록: col 0 에 코드가 있는 행들. 마지막 'Total industry supply'
    # 행은 이름으로 식별해 제외한다 (Sector 파일은 코드 없음, Summary 는 'T017').
    row_pos: Dict[str, int] = {}
    total_supply_row_idx = None
    for r in range(_SUPPLY_DATA_START, raw.shape[0]):
        if "total industry supply" in str(raw.iat[r, 1]).lower():
            total_supply_row_idx = r
            continue
        code = raw.iat[r, 0]
        if code is None or (isinstance(code, float) and np.isnan(code)):
            continue
        row_pos[str(code).strip()] = r
    if total_supply_row_idx is None:
        raise ValueError("'Total industry supply' 행을 찾지 못했습니다 — Supply square 파일이 맞는지 확인하세요.")

    industry_codes = [c for c in col_codes if c in row_pos]
    n = len(industry_codes)
    if n < 2:
        raise ValueError(
            f"행(상품)과 열(산업)이 공유하는 코드가 {n}개뿐입니다 — 정방 정렬에 실패했습니다."
        )

    X = np.zeros((n, n), dtype=float)
    for i, ri in enumerate(industry_codes):
        for j, ci in enumerate(industry_codes):
            X[i, j] = _to_float_or_zero(raw.iat[row_pos[ri], col_pos[ci]])

    # 부속(공급 구성) 열: 산업이 아닌 열 전부 (T007, MCIF, ..., T016) —
    # 파일 원본 값·이름 그대로 C 블록에 보존한다.
    extra_codes = [c for c in col_codes if c not in row_pos and c and c.lower() != "nan"]
    k = len(extra_codes)

    t016 = np.array([
        _to_float_or_zero(raw.iat[row_pos[c], col_pos[_SUPPLY_TOTAL_COL]]) for c in industry_codes
    ])
    total_supply = np.array([
        _to_float_or_zero(raw.iat[total_supply_row_idx, col_pos[c]]) for c in industry_codes
    ])

    row_subtotals = X.sum(axis=1)
    col_subtotals = X.sum(axis=0)
    fd = t016 - row_subtotals          # 총공급(구매자가격) − 산업공급계
    va = total_supply - col_subtotals  # ≈ 0 (반올림 잔차) — 공급표엔 부가가치 행이 없음

    # Compose canonical layout.
    n_rows = 6 + n + 3
    n_cols = 2 + n + 1 + k + 2
    out = pd.DataFrame(np.nan, index=range(n_rows), columns=range(n_cols), dtype=object)

    out.iat[0, 0] = f"BEA Domestic Supply — {level} {year}"
    out.iat[1, 0] = str(year)
    out.iat[2, 0] = "Domestic supply of commodities by industries (square)"
    out.iat[3, 0] = "Unit: Millions of USD"

    for j, code in enumerate(industry_codes):
        out.iat[4, 2 + j] = code
        out.iat[5, 2 + j] = name_for.get(code, code)
    out.iat[4, 2 + n] = "SUBTOTAL"
    out.iat[5, 2 + n] = "중간수요계"
    for j, code in enumerate(extra_codes):
        out.iat[4, 2 + n + 1 + j] = code
        out.iat[5, 2 + n + 1 + j] = name_for.get(code, code)
    out.iat[4, 2 + n + 1 + k] = "FINAL_DEMAND"
    out.iat[5, 2 + n + 1 + k] = "최종수요계"
    out.iat[4, 2 + n + 1 + k + 1] = "TOTAL"
    out.iat[5, 2 + n + 1 + k + 1] = "총산출"

    for i, code in enumerate(industry_codes):
        r = 6 + i
        out.iat[r, 0] = code
        out.iat[r, 1] = name_for.get(code, code)
        for j in range(n):
            out.iat[r, 2 + j] = X[i, j]
        out.iat[r, 2 + n] = row_subtotals[i]
        for j, ec in enumerate(extra_codes):
            out.iat[r, 2 + n + 1 + j] = _to_float_or_zero(raw.iat[row_pos[code], col_pos[ec]])
        out.iat[r, 2 + n + 1 + k] = fd[i]
        out.iat[r, 2 + n + 1 + k + 1] = t016[i]

    sub_r = 6 + n
    out.iat[sub_r, 1] = "중간투입계"
    for j in range(n):
        out.iat[sub_r, 2 + j] = col_subtotals[j]

    va_r = 6 + n + 1
    out.iat[va_r, 1] = "부가가치계"
    for j in range(n):
        out.iat[va_r, 2 + j] = va[j]

    tot_r = 6 + n + 2
    out.iat[tot_r, 1] = "총투입계"
    for j in range(n):
        out.iat[tot_r, 2 + j] = total_supply[j]

    return out


def available_us_years(mode: str) -> List[int]:
    """저장소 루트의 Supply square 워크북에 들어 있는 연도 시트 목록."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return []
    use_p = Path(__file__).resolve().parent / cfg["use_filename"]
    if not use_p.exists():
        return []
    try:
        return sorted(int(s) for s in pd.ExcelFile(use_p).sheet_names if s.isdigit())
    except Exception:
        return []


def _load_us(uploaded_file, mode: str, params: ModeParams, *, year: int) -> LoadResult:
    """US Supply loader. 업로드(또는 저장소 자동 로드)된 Supply square 워크북에서
    `year` 시트를 읽어 한국은행 레이아웃으로 재구성한다. 공급표에는 수입표
    (sheet 1) 대응물이 없으므로 df_local 은 같은 표의 복사본을 쓴다."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        raise NotImplementedError(f"US mode {mode!r} not configured.")
    level = cfg["level"]
    expected_use_filename = cfg["use_filename"]

    expected_sheet = str(year)
    try:
        xl = pd.ExcelFile(uploaded_file)
    except Exception as e:
        raise ValueError(
            f"업로드한 파일을 열 수 없습니다: {e}. "
            f"`{mode}` 모드에서는 `{expected_use_filename}` 을 업로드하세요."
        )
    if expected_sheet not in xl.sheet_names:
        sample = ", ".join(xl.sheet_names[:8])
        if len(xl.sheet_names) > 8:
            sample += f", ... (총 {len(xl.sheet_names)}개 시트)"
        raise ValueError(
            f"업로드한 파일에 '{expected_sheet}' 시트가 없습니다. "
            f"발견된 시트: {sample}.\n"
            f"`{mode}` 모드에서는 `{expected_use_filename}` 파일을 업로드해야 합니다 "
            f"(BEA Domestic Supply 연도별 정방 워크북)."
        )

    raw = xl.parse(sheet_name=expected_sheet, header=None, dtype=object)
    supply_canonical = _build_bok_layout_supply(raw, level=level, year=year)
    supply_local = supply_canonical.copy(deep=True)
    return _post_clean(supply_canonical, supply_local, params)


def load_workbook(uploaded_file, mode: str, *, us_year: int | None = None) -> LoadResult:
    """Public entry point. `app.py` should call only this function.

    For `US(...)` modes the caller must pass `us_year` (use `available_us_years(mode)`
    to populate the selector)."""
    params = get_mode_params(mode)
    if mode.startswith("US"):
        if us_year is None:
            raise ValueError(
                f"`{mode}` 모드는 연도 선택이 필요합니다. "
                f"app.py 가 us_year 키워드를 넘겨야 합니다."
            )
        return _load_us(uploaded_file, mode, params, year=int(us_year))
    return _load_two_sheet(uploaded_file, params)
