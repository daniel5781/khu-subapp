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
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from functions import load_data, get_mid_ID_idx


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
    "US(BEA Summary)",
    "US(BEA Detail)",
]

_PARAMS = {
    "Korea(2010~2020)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "Japan(2000~2020)": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "Korea(1990~2005)": ModeParams(first_idx=(5, 2), subplus_edit=True,  number_of_label=2),
    "Manual":           ModeParams(first_idx=0,      subplus_edit=False, number_of_label=2),
    "US(BEA Summary)":  ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "US(BEA Detail)":   ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
}


# Where (codes, names, data) live in each BEA xlsx flavor (0-indexed row positions).
# Canonical layout (after _normalize_bea_xlsx) is title=0, codes=1, names=2, data=3+,
# which is what _square_industry_codes and _build_bok_layout expect.
@dataclass(frozen=True)
class HeaderLayout:
    title_row: int
    codes_row: int
    names_row: int
    data_start: int

# SUMMARY-level files written by `bea_io_download.py`'s `write_matrix_to_sheet`
# (codes above names, no extra header rows) — already canonical, no normalization.
_LAYOUT_SUMMARY_USE = HeaderLayout(0, 1, 2, 3)
# BEA's Import Matrix multi-year & single-year files — 5 header rows then codes/names.
_LAYOUT_SUMMARY_IMPORT = HeaderLayout(0, 5, 6, 7)
# BEA's official DETAIL files (Use/Make/Import) — names ABOVE codes (rows 4 vs 5).
_LAYOUT_DETAIL = HeaderLayout(0, 5, 4, 6)


# US-only config. `import_files` is a priority list — the first file in repo whose
# sheet contains the requested year wins. Single-year fallbacks may use {year}.
_US_CONFIG: Dict[str, Dict[str, Any]] = {
    "US(BEA Summary)": {
        "level": "Summary",
        "use_filename": "bea_use_table_all_years_summary.xlsx",
        "use_layout": _LAYOUT_SUMMARY_USE,
        "import_files": [
            "bea_import_matrices_before_redefinitions_SUM_1997-2023.xlsx",
            "bea_import_matrices_after_redefinitions_SUM_1997-2023.xlsx",
            "bea_import_matrix_summary_{year}.xlsx",   # single-year fallback (e.g. 2024)
        ],
        "import_layout": _LAYOUT_SUMMARY_IMPORT,
    },
    "US(BEA Detail)": {
        "level": "Detail",
        "use_filename": "IOUse_Before_Redefinitions_PRO_DET.xlsx",
        "use_layout": _LAYOUT_DETAIL,
        "import_files": [
            # BEA's "ImportMatrices_Before_Redefinitions_DET_2017.xlsx" actually
            # contains 2007/2012/2017 sheets — the most-recent file is the only
            # one needed at DETAIL level.
            "ImportMatrices_Before_Redefinitions_DET_2017.xlsx",
            "ImportMatrices_After_Redefinitions_DET_2017.xlsx",
        ],
        "import_layout": _LAYOUT_DETAIL,
    },
}


def get_mode_params(mode: str) -> ModeParams:
    return _PARAMS[mode]


def get_us_config(mode: str) -> Dict[str, Any]:
    """Read-only view of `_US_CONFIG[mode]` for app.py UI hints (filename, level)."""
    return dict(_US_CONFIG.get(mode, {}))


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
# US (BEA) loader — industry × industry square shortcut
# ---------------------------------------------------------------------------
#
# BEA publishes Use Tables (Total) and Import Matrices in commodity × industry
# (rectangular) form, which the dashboard's `(I − A)^-1` math can't handle.
# The user picked the "industry-technology diagonalization" shortcut: keep only
# the rows/cols whose codes appear on both axes (the natural square subset),
# and pack the result into the Korean BoK layout (first_idx=(6,2)) so the rest
# of the pipeline runs unchanged.
#
# Synthesized layout per loaded sheet:
#
#                col 0   col 1    cols 2..2+n-1   col 2+n     col 2+n+1     col 2+n+2
#   row 0        title  ─       ─              ─           ─             ─
#   row 1        year   ─       ─              ─           ─             ─
#   row 2        note   ─       ─              ─           ─             ─
#   row 3        units  ─       ─              ─           ─             ─
#   row 4        ─      ─       industry codes   SUBTOTAL    FINAL_DEMAND  TOTAL
#   row 5        ─      ─       industry names  중간수요계  최종수요계   총산출
#   row 6..6+n-1 code   name    X_ij           Σ X row     Σ FD row      Σ X row + FD
#   row 6+n      ─      중간투입계  Σ X col      ─           ─             ─
#   row 6+n+1    ─      부가가치계  VA per col   ─           ─             ─
#   row 6+n+2    ─      총투입계   total_out_per_col ─       ─             ─
#
# `get_mid_ID_idx` walks the first data row, stopping at the SUBTOTAL cell,
# which lands `mid_ID_idx` at (6+n, 2+n). Downstream slicing then picks up the
# 최종수요계 column (matched by Korean label string in `app.py`).

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


def _normalize_bea_xlsx(df: pd.DataFrame, layout: HeaderLayout) -> pd.DataFrame:
    """Reformat any BEA xlsx into the canonical layout used by the rest of this
    module: row 0 = title, row 1 = column codes, row 2 = column names, row 3+
    = data with row codes in col 0 and row descriptions in col 1.

    This handles the difference between BEA's SUMMARY-level files (codes above
    names) and DETAIL files (names above codes), and the extra header rows in
    Import Matrix workbooks."""
    title = df.iloc[[layout.title_row]].reset_index(drop=True)
    codes = df.iloc[[layout.codes_row]].reset_index(drop=True)
    names = df.iloc[[layout.names_row]].reset_index(drop=True)
    data = df.iloc[layout.data_start:].reset_index(drop=True)
    return pd.concat([title, codes, names, data], ignore_index=True)


# Row-code candidates — first match wins.
# SUMMARY/SECTOR uses 4-char codes; DETAIL uses 6-char (T018 → T008, etc.).
_TOTAL_OUTPUT_ROW_CANDIDATES = ("T018", "T008")
_TOTAL_VA_ROW_CANDIDATES = ("VAPRO", "VABAS", "T006")
# Components for explicit VA fallback (when no single total row exists).
_VA_PLUS_CODES = ("V001", "V003", "V00100", "V00300", "T00OTOP", "T00TOP", "V00200")
_VA_MINUS_CODES = ("T00OSUB", "T00SUB")


def _square_industry_codes(use_df: pd.DataFrame, imp_df: pd.DataFrame) -> List[str]:
    """Codes that appear as both a row header (commodity) and a column header
    (industry) in BOTH workbooks. Order is taken from the Use file's column
    order so the resulting block is industry-by-industry from the Use POV."""
    use_cols = [str(c) for c in use_df.iloc[1, 2:].tolist()]
    use_rows = {str(c) for c in use_df.iloc[3:, 0].tolist()}
    imp_cols = {str(c) for c in imp_df.iloc[1, 2:].tolist()}
    imp_rows = {str(c) for c in imp_df.iloc[3:, 0].tolist()}
    return [c for c in use_cols if c and c in use_rows and c in imp_cols and c in imp_rows]


def _build_bok_layout(
    bea_df: pd.DataFrame,
    industry_codes: List[str],
    *,
    title: str,
    year: int,
    has_va: bool,
    total_out_override: Dict[str, float] | None = None,
) -> pd.DataFrame:
    """Repack a BEA-format DataFrame (first_idx=(3, 2)) into the Korean BoK
    layout (first_idx=(6, 2)) restricted to the industry × industry square
    block. See module-level diagram for the output shape.

    total_out_override : industry_code → industry_output map. When provided,
        used as the BoK 총투입계 row instead of T018. The Import workbook MUST
        use Use 표's T018 here, because BoK normalizes Aᵐ by the same industry
        output as A; using Import 표's own column sum would normalize by total
        imports per industry, which inflates Aᵐ and explodes (I − Aᵈ)⁻¹.
    """
    n = len(industry_codes)
    use_col_codes = [str(c) for c in bea_df.iloc[1, 2:].tolist()]
    use_row_codes = [str(c) for c in bea_df.iloc[3:, 0].tolist()]
    use_col_names = [str(c) for c in bea_df.iloc[2, 2:].tolist()]

    col_pos = {c: 2 + i for i, c in enumerate(use_col_codes)}
    row_pos = {c: 3 + i for i, c in enumerate(use_row_codes)}
    name_for = {c: use_col_names[i] for i, c in enumerate(use_col_codes)}
    industry_set = set(industry_codes)
    code_to_pos = {c: i for i, c in enumerate(industry_codes)}

    # X block (n × n) — industry × industry
    X = np.zeros((n, n), dtype=float)
    for i, ri in enumerate(industry_codes):
        for j, ci in enumerate(industry_codes):
            X[i, j] = _to_float_or_zero(bea_df.iat[row_pos[ri], col_pos[ci]])

    # Final-demand sum per row: cells in cols whose code is neither industry nor T-total.
    fd_sum = np.zeros(n, dtype=float)
    for i, ri in enumerate(industry_codes):
        r_idx = row_pos[ri]
        for j, cc in enumerate(use_col_codes):
            if cc in industry_set or cc.startswith('T'):
                continue
            fd_sum[i] += _to_float_or_zero(bea_df.iat[r_idx, 2 + j])

    # VA per col (Use file only — Import has no VA rows).
    # Single-total row preferred (VAPRO/VABAS at SUMMARY, T006 at DETAIL); otherwise
    # explicit sum V001+V003+(T00OTOP-T00OSUB)+(T00TOP-T00SUB) — DETAIL uses 6-char
    # variants V00100/V00300/V00200.
    # NOTE: T018/T008 are industry total output, NOT VA components — never summed.
    va_per_col = np.zeros(n, dtype=float)
    if has_va:
        va_total_code = next((c for c in _TOTAL_VA_ROW_CANDIDATES if c in row_pos), None)
        if va_total_code is not None:
            r = row_pos[va_total_code]
            for ci in industry_codes:
                va_per_col[code_to_pos[ci]] = _to_float_or_zero(bea_df.iat[r, col_pos[ci]])
        else:
            for ci in industry_codes:
                cidx = col_pos[ci]
                acc = 0.0
                for code in _VA_PLUS_CODES:
                    if code in row_pos:
                        acc += _to_float_or_zero(bea_df.iat[row_pos[code], cidx])
                for code in _VA_MINUS_CODES:
                    if code in row_pos:
                        acc -= _to_float_or_zero(bea_df.iat[row_pos[code], cidx])
                va_per_col[code_to_pos[ci]] = acc

    # Total output per col (= 총투입계 = industry output): T018 (SUMMARY/SECTOR) or
    # T008 (DETAIL). For Import the caller must pass total_out_override (= Use's
    # T018/T008) so BoK Aᵐ is normalized by the same industry output as A.
    total_out = np.zeros(n, dtype=float)
    if total_out_override is not None:
        for ci in industry_codes:
            total_out[code_to_pos[ci]] = float(total_out_override.get(ci, 0.0))
    else:
        out_code = next((c for c in _TOTAL_OUTPUT_ROW_CANDIDATES if c in row_pos), None)
        if out_code is not None:
            r = row_pos[out_code]
            for ci in industry_codes:
                total_out[code_to_pos[ci]] = _to_float_or_zero(bea_df.iat[r, col_pos[ci]])
        else:
            for j_x in range(n):
                total_out[j_x] = X[:, j_x].sum() + va_per_col[j_x]

    # Compose canonical layout.
    n_rows = 6 + n + 3
    n_cols = 2 + n + 3
    out = pd.DataFrame(np.nan, index=range(n_rows), columns=range(n_cols), dtype=object)

    out.iat[0, 0] = title
    out.iat[1, 0] = str(year)
    out.iat[2, 0] = 'Producer Prices'
    out.iat[3, 0] = 'Unit: Millions of USD'

    for j, code in enumerate(industry_codes):
        out.iat[4, 2 + j] = code
        out.iat[5, 2 + j] = name_for.get(code, code)
    out.iat[4, 2 + n]     = 'SUBTOTAL'
    out.iat[5, 2 + n]     = '중간수요계'
    out.iat[4, 2 + n + 1] = 'FINAL_DEMAND'
    out.iat[5, 2 + n + 1] = '최종수요계'
    out.iat[4, 2 + n + 2] = 'TOTAL'
    out.iat[5, 2 + n + 2] = '총산출'

    row_subtotals = X.sum(axis=1)
    col_subtotals = X.sum(axis=0)
    for i, code in enumerate(industry_codes):
        r = 6 + i
        out.iat[r, 0] = code
        out.iat[r, 1] = name_for.get(code, code)
        for j in range(n):
            out.iat[r, 2 + j] = X[i, j]
        out.iat[r, 2 + n]     = row_subtotals[i]
        out.iat[r, 2 + n + 1] = fd_sum[i]
        out.iat[r, 2 + n + 2] = row_subtotals[i] + fd_sum[i]

    sub_r = 6 + n
    out.iat[sub_r, 1] = '중간투입계'
    for j in range(n):
        out.iat[sub_r, 2 + j] = col_subtotals[j]

    va_r = 6 + n + 1
    out.iat[va_r, 1] = '부가가치계'
    for j in range(n):
        out.iat[va_r, 2 + j] = va_per_col[j]

    tot_r = 6 + n + 2
    out.iat[tot_r, 1] = '총투입계'
    for j in range(n):
        out.iat[tot_r, 2 + j] = total_out[j]

    return out


def _resolve_import_source(mode: str, year: int) -> Tuple[Path, str] | Tuple[None, None]:
    """Return (path, sheet_name) for BEA Import Matrix data for a given year.
    Tries _US_CONFIG[mode]['import_files'] in order. Multi-year workbooks have
    a year-named sheet; the single-year fallback file uses sheet 'Table'."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return None, None
    repo = Path(__file__).resolve().parent
    for fn_template in cfg["import_files"]:
        fn = fn_template.format(year=year)
        path = repo / fn
        if not path.exists():
            continue
        try:
            sheet_names = pd.ExcelFile(path).sheet_names
        except Exception:
            continue
        if str(year) in sheet_names:
            return path, str(year)
        if "Table" in sheet_names:
            return path, "Table"
    return None, None


def available_us_years(mode: str) -> List[int]:
    """Years for which both Use (uploaded) and Import (in repo) data exist."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return []
    repo = Path(__file__).resolve().parent
    use_p = repo / cfg["use_filename"]
    if not use_p.exists():
        return []
    try:
        use_years = {int(s) for s in pd.ExcelFile(use_p).sheet_names if s.isdigit()}
    except Exception:
        return []
    return sorted(y for y in use_years if _resolve_import_source(mode, y)[0] is not None)


def _load_us(uploaded_file, mode: str, params: ModeParams, *, year: int) -> LoadResult:
    """US loader. Reads the Total Use sheet for `year` from the uploaded BEA
    workbook, locates a matching BEA Import Matrix in the repo, restricts both
    to the shared industry × industry block, and repacks them into the Korean
    BoK layout."""
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
            f"`{mode}` 모드에서는 저장소 루트의 `{expected_use_filename}` 파일을 "
            f"업로드해야 합니다 (BEA Use Table 연도별 워크북). "
            f"Import 파일은 코드가 자동으로 읽습니다."
        )

    import_path, import_sheet = _resolve_import_source(mode, year)
    if import_path is None:
        candidates = ", ".join(cfg["import_files"]).format(year=year)
        raise FileNotFoundError(
            f"BEA Import Matrix 파일을 찾을 수 없습니다 (연도={year}). "
            f"다음 중 하나를 저장소 루트에 두세요: {candidates}"
        )

    # Both files get normalized to canonical first_idx=(3, 2) layout — DETAIL
    # files have names ABOVE codes which the rest of the pipeline can't read.
    use_raw = pd.read_excel(uploaded_file, sheet_name=expected_sheet, header=None, dtype=object)
    imp_raw = pd.read_excel(str(import_path), sheet_name=import_sheet, header=None, dtype=object)
    use_df = _normalize_bea_xlsx(use_raw, cfg["use_layout"])
    imp_df = _normalize_bea_xlsx(imp_raw, cfg["import_layout"])

    industry_codes = _square_industry_codes(use_df, imp_df)
    if len(industry_codes) < 2:
        raise ValueError(
            f"BEA Use[{year}] and Import[{year}] only share {len(industry_codes)} "
            f"industry code(s) — alignment failed. Check that the uploaded file is "
            f"`{expected_use_filename}` and that {import_path.name} contains data for {year}."
        )

    # Industry total output row in Use (T018 SUMMARY / T008 DETAIL) — reused as
    # the denominator for the Import workbook so BoK Aᵐ shares the same x̂.
    use_row_codes = [str(c) for c in use_df.iloc[3:, 0].tolist()]
    use_col_codes = [str(c) for c in use_df.iloc[1, 2:].tolist()]
    industry_output: Dict[str, float] = {}
    out_code = next((c for c in _TOTAL_OUTPUT_ROW_CANDIDATES if c in use_row_codes), None)
    if out_code is not None:
        out_row = 3 + use_row_codes.index(out_code)
        for j, cc in enumerate(use_col_codes):
            if cc in industry_codes:
                industry_output[cc] = _to_float_or_zero(use_df.iat[out_row, 2 + j])

    use_canonical = _build_bok_layout(
        use_df, industry_codes,
        title=f'BEA Use Table — {level} {year}', year=year, has_va=True,
        total_out_override=industry_output,
    )
    imp_canonical = _build_bok_layout(
        imp_df, industry_codes,
        title=f'BEA Import Matrix — {level} {year}', year=year, has_va=False,
        total_out_override=industry_output,
    )

    return _post_clean(use_canonical, imp_canonical, params)


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
