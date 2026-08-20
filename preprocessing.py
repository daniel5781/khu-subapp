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

일본 모드는 로드 직후 `_derive_domestic_local` 이 시트 1(수입거래표)의
X 블록을 (총거래 − 수입) = 국산거래로 치환한다. 하류의 L_local
(부가가치유발계수 m_v = v·(I−A_d)⁻¹)은 국산투입계수 기준 역행렬을
기대하는데, 일본 정리본의 시트 1은 수입거래표이기 때문이다 — US 모드가
국산거래표를 df_local 로 넘기는 것과 동일한 계약으로 맞춘다.
(한국 모드는 기존 동작 유지 — 시트 1 을 그대로 df_local 로 사용.)

The US mode uses two BEA Use-table workbooks already arranged in the Korean
BoK layout (one year per sheet; 2000~2020, 2023, 2024; Summary level n=71):
`미국_사용표_총거래_한국레이아웃_2000_2024.xlsx` (총거래표, df) and
`미국_사용표_국산_한국레이아웃_2000_2024.xlsx` (국산거래표 = Use − 수입행렬,
df_local). `_build_bok_layout_use` 가 각 연도 시트를 캐노니컬 레이아웃
(first_idx=(6,2))으로 재구성해 이후 파이프라인이 한국 모드와 동일하게
동작한다. 마지막 행 = 총투입계(T018, A행렬 분모), 그 위가 부가가치계.
빌더 스크립트: 저장소 밖 `build_use_korean_layout.py`.
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
    "US(Summary 2000~2024)",
    "US(Sector 2000~2024)",
]

_PARAMS = {
    "Korea(2010~2020)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "Japan(2000~2020)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "Korea(1990~2005)": ModeParams(first_idx=(5, 2), subplus_edit=True,  number_of_label=2),
    "Manual":           ModeParams(first_idx=0,      subplus_edit=False, number_of_label=2),
    "US(Summary 2000~2024)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "US(Sector 2000~2024)":  ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
}


# US-only config — BEA Use 기반 한국레이아웃 워크북 (연도별 시트).
# 총거래표 → df, 국산거래표(Use − 수입행렬) → df_local.
_US_CONFIG: Dict[str, Dict[str, Any]] = {
    "US(Summary 2000~2024)": {
        "level": "Summary",      # 71개 중분류 산업
        "total_filename": "미국_사용표_총거래_한국레이아웃_2000_2024.xlsx",
        "local_filename": "미국_사용표_국산_한국레이아웃_2000_2024.xlsx",
    },
    "US(Sector 2000~2024)": {
        "level": "Sector",       # 15개 대분류 산업
        "total_filename": "미국_사용표_총거래_한국레이아웃_대분류_2000_2024.xlsx",
        "local_filename": "미국_사용표_국산_한국레이아웃_대분류_2000_2024.xlsx",
    },
}

# 미국_사용표_*_한국레이아웃 워크북 내부 고정 레이아웃 (0-index).
#   row 0 = ['IOCode', (빈칸), 산업코드..., 중간수요계, F코드..., 최종수요계, 총수요]
#   row 1 = ['Name',   (빈칸), 산업이름..., ...]
#   row 2.. = 상품(commodity) 행 (col 0=코드, col 1=이름)
#   상품 블록 뒤: 중간투입계(국산은 국산중간투입계/수입중간투입계) → 부가가치계
#   → 총산출(T018) 행. 그 아래 "(참고)" 부가가치 세부 블록은 무시한다.
_USE_CODES_ROW = 0
_USE_NAMES_ROW = 1
_USE_DATA_START = 2


def get_mode_params(mode: str) -> ModeParams:
    return _PARAMS[mode]


def get_us_config(mode: str) -> Dict[str, Any]:
    """Read-only view of `_US_CONFIG[mode]` for app.py UI hints (filename, level)."""
    return dict(_US_CONFIG.get(mode, {}))


def us_use_file_path(mode: str) -> Path | None:
    """Repo path to the US 총거래표 workbook, or None. The file ships in the
    repo, so app.py can auto-load it when the user hasn't uploaded one.
    (업로드가 있으면 업로드본이 총거래표를 대체하고, 국산거래표는 항상
    `us_local_file_path` 의 저장소 파일을 쓴다.)"""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return None
    return Path(__file__).resolve().parent / cfg["total_filename"]


def us_local_file_path(mode: str) -> Path | None:
    """Repo path to the US 국산거래표 workbook, or None."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return None
    return Path(__file__).resolve().parent / cfg["local_filename"]


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


# 시트 1 이 수입거래표인 모드 중 국산거래표(총거래 − 수입) 변환을 적용할 모드.
# 일본만 적용 — 한국 모드는 기존 동작(시트 1 을 그대로 df_local 로) 유지 결정,
# Manual 은 레이아웃을 알 수 없으므로 제외.
_DERIVE_DOMESTIC_MODES = {"Japan(2000~2020)"}


def _derive_domestic_local(result: LoadResult, params: ModeParams) -> LoadResult:
    """시트 1(수입거래표)의 X 블록을 국산거래(총거래 − 수입)로 치환한다.

    치환 범위는 내생부문계 행·열(mid 위치)까지 — 합계는 선형이라 부분합도
    그대로 정합한다. df_local 의 최종수요/본원투입 영역은 하류(m_v 의
    L_local)에서 쓰지 않으므로 그대로 둔다. 두 시트의 부문 코드가 위치까지
    일치하는지 검증한 뒤 위치 기반으로 차감한다.
    """
    fi = params.first_idx
    df, dfl = result.df, result.df_local.copy()
    mid, midl = result.mid_ID_idx, result.mid_ID_idx_local

    n_rows, n_cols = mid[0] - fi[0], mid[1] - fi[1]
    if (midl[0] - fi[0], midl[1] - fi[1]) != (n_rows, n_cols):
        raise ValueError(
            f"총거래표 X 블록({n_rows}×{n_cols})과 수입거래표 X 블록"
            f"({midl[0] - fi[0]}×{midl[1] - fi[1]})의 크기가 다릅니다 — "
            f"두 시트의 부문 구성이 같은 워크북인지 확인하세요."
        )

    def _code(x):
        s = str(x).strip()
        return str(int(s)) if s.replace(".", "", 1).isdigit() else s

    codes_total = [_code(x) for x in df.iloc[fi[0]:mid[0], 0]]
    codes_imp   = [_code(x) for x in dfl.iloc[fi[0]:midl[0], 0]]
    if codes_total != codes_imp:
        first_bad = next(i for i, (a, b) in enumerate(zip(codes_total, codes_imp)) if a != b)
        raise ValueError(
            f"총거래표와 수입거래표의 부문 코드 순서가 다릅니다 "
            f"(첫 불일치: 행 {fi[0] + first_bad}, "
            f"'{codes_total[first_bad]}' vs '{codes_imp[first_bad]}')."
        )

    total_X = (df.iloc[fi[0]:mid[0] + 1, fi[1]:mid[1] + 1]
               .apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float))
    imp_X = (dfl.iloc[fi[0]:midl[0] + 1, fi[1]:midl[1] + 1]
             .apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float))
    domestic = total_X - np.nan_to_num(imp_X)  # 수입표의 빈 셀은 수입 0 으로 간주

    dfl.iloc[fi[0]:midl[0] + 1, fi[1]:midl[1] + 1] = domestic

    old_title = dfl.iat[0, 0]
    prefix = f"{old_title} → " if isinstance(old_title, str) and old_title.strip() else ""
    dfl.iat[0, 0] = f"{prefix}국산거래표(총거래−수입, 로드 시 유도)"

    return LoadResult(
        df=df,
        df_local=dfl,
        mid_ID_idx=mid,
        mid_ID_idx_local=midl,
        string_values=result.string_values,
        string_values_local=result.string_values_local,
    )


# ---------------------------------------------------------------------------
# US (BEA Use) loader — 한국레이아웃 워크북 2종 (총거래표 / 국산거래표)
# ---------------------------------------------------------------------------
#
# 두 워크북은 BEA SUT Use표(기초가격, Summary 71개 산업)를 이미 한국은행
# 형식으로 정렬한 것이다 (총거래 = Use 그대로, 국산 = Use − 수입행렬).
# `_build_bok_layout_use` 가 연도 시트 하나를 캐노니컬 레이아웃으로 재구성해
# 이후 파이프라인(편집 → Leontief → 네트워크)이 한국 모드와 동일하게 돌아간다.
#
# Synthesized layout per sheet (n = 산업 수 71, k = 최종수요 F열 수 19):
#
#                col 0   col 1       cols 2..2+n-1   col 2+n    cols 2+n+1..2+n+k  col 2+n+k+1   col 2+n+k+2
#   row 0        title   ─          ─              ─          ─                 ─             ─
#   row 1        year    ─          ─              ─          ─                 ─             ─
#   row 2        note    ─          ─              ─          ─                 ─             ─
#   row 3        units   ─          ─              ─          ─                 ─             ─
#   row 4        ─       ─          industry codes  SUBTOTAL   F010..F10N 코드    FINAL_DEMAND  TOTAL
#   row 5        ─       ─          industry names  중간수요계  (파일 원본 이름)    최종수요계     총수요
#   row 6..6+n-1 code    name       X_ij            Σ X row    파일 원본 값        Σ F row       Σ X + Σ F
#   row 6+n      ─       중간투입계    Σ X col        ─          ─                 ─             ─
#  (row 6+n+1    ─       수입중간투입계 파일 값 — 국산거래표에만 있음)
#  (그 다음 행    ─       기타투입(Other) 파일 값 — 비교불능수입 등, 부가가치 아님)
#   끝-2         ─       부가가치계    T018 − 위 행들 (= VABAS + Used)
#   끝-1         ─       총투입계     T018(파일 값)   ─          ─                 ─             ─
#
# `get_mid_ID_idx` walks the first data row, stopping at the SUBTOTAL cell,
# which lands `mid_ID_idx` at (6+n, 2+n). SUBTOTAL/중간투입계 는 X 블록에서
# 다시 계산한다 (경계 탐지 ±0.001 허용 안에 확실히 들어가도록).
#
# app.py 의 분모 규약: 마지막 행 = 총투입계(T018) → A 행렬 분모,
# 마지막에서 두 번째 행 = 부가가치계 → v 벡터. 두 워크북 모두 T018 이
# 분모이므로 국산 레온티에프 = (I − X_국산/T018)⁻¹ 가 된다 (표준 국산투입계수).

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
    f_codes = col_codes[n + 1: col_codes.index(fin_col_label)]
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
        if (code in (mid_row_label, "수입중간투입계", "부가가치계")
                or code.startswith(("총산출", "기타투입"))):
            total_rows[code.split("(")[0]] = r
        else:
            row_pos[code] = r

    if [c for c in industry_codes if c in row_pos] != industry_codes or len(row_pos) != n:
        raise ValueError("행(상품)과 열(산업) 코드가 일치하지 않습니다 — 한국레이아웃 파일이 맞는지 확인하세요.")
    if "총산출" not in total_rows or "부가가치계" not in total_rows:
        raise ValueError("총산출(T018)/부가가치계 행을 찾지 못했습니다 — 한국레이아웃 파일이 맞는지 확인하세요.")
    if local and "수입중간투입계" not in total_rows:
        raise ValueError("수입중간투입계 행을 찾지 못했습니다 — 국산거래표 파일이 맞는지 확인하세요.")

    X = np.zeros((n, n), dtype=float)
    for i, ri in enumerate(industry_codes):
        for j, ci in enumerate(industry_codes):
            X[i, j] = _to_float_or_zero(raw.iat[row_pos[ri], col_pos[ci]])

    F = np.zeros((n, k), dtype=float)
    for i, ri in enumerate(industry_codes):
        for j, fc in enumerate(f_codes):
            F[i, j] = _to_float_or_zero(raw.iat[row_pos[ri], col_pos[fc]])

    t018 = np.array([
        _to_float_or_zero(raw.iat[total_rows["총산출"], col_pos[c]]) for c in industry_codes
    ])
    imp = None
    if local:
        imp = np.array([
            _to_float_or_zero(raw.iat[total_rows["수입중간투입계"], col_pos[c]]) for c in industry_codes
        ])
    # 기타투입(Other, 비교불능수입 등) — 부가가치계에 넣지 않고 별도 행으로 보존.
    # (구형 파일에는 이 행이 없을 수 있으므로 없으면 0 취급 — 그 경우 부가가치계가 흡수)
    has_other = "기타투입" in total_rows
    other = (np.array([
        _to_float_or_zero(raw.iat[total_rows["기타투입"], col_pos[c]]) for c in industry_codes
    ]) if has_other else np.zeros(n))

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
    out.iat[2, 0] = ("Use of commodities by industries, domestic (Use − import matrix)"
                     if local else "Use of commodities by industries (total, basic prices)")
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


def available_us_years(mode: str) -> List[int]:
    """저장소 루트의 총거래/국산 워크북이 공통으로 가진 연도 시트 목록."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return []
    years = None
    for key in ("total_filename", "local_filename"):
        p = Path(__file__).resolve().parent / cfg[key]
        if not p.exists():
            return []
        try:
            s = {int(x) for x in pd.ExcelFile(p).sheet_names if x.isdigit()}
        except Exception:
            return []
        years = s if years is None else (years & s)
    return sorted(years or [])


def _read_us_year_sheet(source, year: int, expected_filename: str, table_kor: str) -> pd.DataFrame:
    expected_sheet = str(year)
    try:
        xl = pd.ExcelFile(source)
    except Exception as e:
        raise ValueError(
            f"{table_kor} 파일을 열 수 없습니다: {e}. "
            f"`{expected_filename}` 형식의 파일이어야 합니다."
        )
    if expected_sheet not in xl.sheet_names:
        sample = ", ".join(xl.sheet_names[:8])
        if len(xl.sheet_names) > 8:
            sample += f", ... (총 {len(xl.sheet_names)}개 시트)"
        raise ValueError(
            f"{table_kor} 파일에 '{expected_sheet}' 시트가 없습니다. "
            f"발견된 시트: {sample}.\n"
            f"`{expected_filename}` (연도별 시트 워크북) 형식이어야 합니다."
        )
    return xl.parse(sheet_name=expected_sheet, header=None, dtype=object)


def _load_us(uploaded_file, mode: str, params: ModeParams, *, year: int) -> LoadResult:
    """US Use loader. 총거래표(업로드본이 있으면 그것, 없으면 저장소 파일)와
    국산거래표(항상 저장소 파일)에서 `year` 시트를 읽어 캐노니컬 레이아웃으로
    재구성한다. df = 총거래표, df_local = 국산거래표."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        raise NotImplementedError(f"US mode {mode!r} not configured.")

    local_p = us_local_file_path(mode)
    if local_p is None or not local_p.exists():
        raise ValueError(
            f"국산거래표 `{cfg['local_filename']}` 를 저장소 루트에서 찾지 못했습니다."
        )

    raw_total = _read_us_year_sheet(uploaded_file, year, cfg["total_filename"], "총거래표")
    raw_local = _read_us_year_sheet(str(local_p), year, cfg["local_filename"], "국산거래표")

    df = _build_bok_layout_use(raw_total, kind="total", year=year)
    df_local = _build_bok_layout_use(raw_local, kind="local", year=year)
    return _post_clean(df, df_local, params)


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
    result = _load_two_sheet(uploaded_file, params)
    if mode in _DERIVE_DOMESTIC_MODES:
        result = _derive_domestic_local(result, params)
    return result
