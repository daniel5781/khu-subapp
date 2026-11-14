"""국가별 워크북 로딩. UI나 현재 작업 디렉터리에 의존하지 않는다."""

from dataclasses import replace
from typing import Any, List, Tuple
import unicodedata
import numpy as np
import pandas as pd
from .loading import load_data, get_mid_ID_idx
from .models import ModeParams, LoadResult
from .config import (
    MODES,
    _US_CONFIG,
    get_mode_params,
    get_us_config,
    us_use_file_path,
    us_local_file_path,
    get_data_dir,
)
from .us_workbooks import _build_bok_layout_use, _read_us_year_sheet


def _find_string_values(df: pd.DataFrame, first_idx) -> List[Tuple[Any, Any, str]]:
    selected = df.iloc[first_idx[0] :, first_idx[1] :]
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


def _post_clean(
    df: pd.DataFrame, df_local: pd.DataFrame, params: ModeParams
) -> LoadResult:
    fi = params.first_idx

    sv = _find_string_values(df, fi)
    sv_local = _find_string_values(df_local, fi)
    _replace_string_with_na(df, sv)
    _replace_string_with_na(df_local, sv_local)

    df = _slice_until_first_non_nan_row(df)
    df_local = _slice_until_first_non_nan_row(df_local)

    mid = get_mid_ID_idx(df, fi)
    mid_local = get_mid_ID_idx(df_local, fi)

    df.iloc[fi[0] :, fi[1] :] = df.iloc[fi[0] :, fi[1] :].apply(
        pd.to_numeric, errors="coerce"
    )
    df_local.iloc[fi[0] :, fi[1] :] = df_local.iloc[fi[0] :, fi[1] :].apply(
        pd.to_numeric, errors="coerce"
    )

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


def _transaction_sheet_names(sheet_names: List[str]) -> Tuple[str, str]:
    """총거래·국산거래 시트를 이름으로 찾고, 이름 없는 기존 양식만 순서를 쓴다."""
    normalized = {
        name: "".join(unicodedata.normalize("NFKC", name).split())
        for name in sheet_names
    }
    labels = ("총거래표", "국산거래표", "수입거래표")
    if any(label in name for name in normalized.values() for label in labels):
        selected = []
        for label in labels[:2]:
            matches = [
                name
                for name, normalized_name in normalized.items()
                if label in normalized_name
            ]
            if not matches:
                raise ValueError(
                    f"'{label}' 시트가 없습니다. 총거래표와 국산거래표가 모두 필요합니다. "
                    "수입거래표는 국산거래표 대신 사용할 수 없습니다."
                )
            if len(matches) != 1:
                raise ValueError(
                    f"'{label}' 시트가 여러 개입니다: {', '.join(matches)}"
                )
            selected.append(matches[0])
        if selected[0] == selected[1]:
            raise ValueError("총거래표와 국산거래표는 서로 다른 시트여야 합니다.")
        return selected[0], selected[1]

    if len(sheet_names) < 2:
        raise ValueError(
            "총거래표와 국산거래표에 해당하는 시트가 두 개 이상 필요합니다."
        )
    return sheet_names[0], sheet_names[1]


def _load_two_sheet(uploaded_file, params: ModeParams) -> LoadResult:
    """한국 표는 시트명으로 선택하고, 이름 없는 기존 두 시트 양식도 지원한다."""
    with pd.ExcelFile(uploaded_file) as workbook:
        total_sheet, domestic_sheet = _transaction_sheet_names(workbook.sheet_names)
    df = load_data(uploaded_file, total_sheet)
    df_local = load_data(uploaded_file, domestic_sheet)
    return _post_clean(df, df_local, params)


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
        return str(int(float(s))) if s.replace(".", "", 1).isdigit() else s

    codes_total = [_code(x) for x in df.iloc[fi[0] : mid[0], 0]]
    codes_imp = [_code(x) for x in dfl.iloc[fi[0] : midl[0], 0]]
    if codes_total != codes_imp:
        first_bad = next(
            i for i, (a, b) in enumerate(zip(codes_total, codes_imp)) if a != b
        )
        raise ValueError(
            f"총거래표와 수입거래표의 부문 코드 순서가 다릅니다 "
            f"(첫 불일치: 행 {fi[0] + first_bad}, "
            f"'{codes_total[first_bad]}' vs '{codes_imp[first_bad]}')."
        )

    columns_total = [_code(x) for x in df.iloc[fi[0] - 2, fi[1] : mid[1]]]
    columns_import = [_code(x) for x in dfl.iloc[fi[0] - 2, fi[1] : midl[1]]]
    if columns_total != columns_import:
        raise ValueError("총거래표와 수입거래표의 열 산업 코드 순서가 다릅니다.")

    total_X = (
        df.iloc[fi[0] : mid[0] + 1, fi[1] : mid[1] + 1]
        .apply(pd.to_numeric, errors="coerce")
        .to_numpy(dtype=float)
    )
    imp_X = (
        dfl.iloc[fi[0] : midl[0] + 1, fi[1] : midl[1] + 1]
        .apply(pd.to_numeric, errors="coerce")
        .to_numpy(dtype=float)
    )
    domestic = total_X - np.nan_to_num(imp_X)  # 수입표의 빈 셀은 수입 0 으로 간주

    dfl.iloc[fi[0] : midl[0] + 1, fi[1] : midl[1] + 1] = domestic

    old_title = dfl.iat[0, 0]
    prefix = (
        f"{old_title} → " if isinstance(old_title, str) and old_title.strip() else ""
    )
    dfl.iat[0, 0] = f"{prefix}국산거래표(총거래−수입, 로드 시 유도)"

    return LoadResult(
        df=df,
        df_local=dfl,
        mid_ID_idx=mid,
        mid_ID_idx_local=midl,
        string_values=result.string_values,
        string_values_local=result.string_values_local,
    )


def available_us_years(mode: str) -> List[int]:
    """저장소 루트의 총거래/국산 워크북이 공통으로 가진 연도 시트 목록."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return []
    years = None
    for key in ("total_filename", "local_filename"):
        p = get_data_dir() / cfg[key]
        if not p.exists():
            return []
        try:
            with pd.ExcelFile(p) as workbook:
                s = {int(x) for x in workbook.sheet_names if x.isdigit()}
        except Exception:
            return []
        years = s if years is None else (years & s)
    return sorted(years or [])


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

    raw_total = _read_us_year_sheet(
        uploaded_file, year, cfg["total_filename"], "총거래표"
    )
    raw_local = _read_us_year_sheet(
        str(local_p), year, cfg["local_filename"], "국산거래표"
    )

    df = _build_bok_layout_use(raw_total, kind="total", year=year)
    df_local = _build_bok_layout_use(raw_local, kind="local", year=year)
    return _post_clean(df, df_local, params)


def load_workbook(
    uploaded_file,
    mode: str,
    *,
    us_year: int | None = None,
    first_idx: tuple[int, int] | None = None,
) -> LoadResult:
    """Public entry point. `app.py` should call only this function.

    For `US(...)` modes the caller must pass `us_year` (use `available_us_years(mode)`
    to populate the selector)."""
    params = get_mode_params(mode)
    if first_idx is not None:
        if mode != "Manual" or len(first_idx) != 2 or min(first_idx) < 2:
            raise ValueError("수동 모드의 숫자 시작 위치는 라벨 2행/2열 뒤여야 합니다.")
        params = replace(params, first_idx=tuple(first_idx))
    if mode.startswith("US"):
        if us_year is None:
            raise ValueError(
                f"`{mode}` 모드는 연도 선택이 필요합니다. "
                f"app.py 가 us_year 키워드를 넘겨야 합니다."
            )
        return _load_us(uploaded_file, mode, params, year=int(us_year))
    if mode.startswith("Japan"):
        return _load_japan(uploaded_file, params)
    result = _load_two_sheet(uploaded_file, params)
    return result


def _load_japan(source, params):
    """총거래+수입 표만 차감하며 이미 국산인 표는 그대로 사용한다."""
    with pd.ExcelFile(source) as workbook:
        names = workbook.sheet_names
    normalized = {
        name: "".join(unicodedata.normalize("NFKC", name).split()) for name in names
    }

    def select(label):
        matches = [name for name, text in normalized.items() if label in text]
        if len(matches) > 1:
            raise ValueError(f"'{label}' 시트가 여러 개입니다: {matches}")
        return matches[0] if matches else None

    total, domestic, imports = (
        select(label) for label in ("총거래표", "국산거래표", "수입거래표")
    )
    if total or domestic or imports:
        if not total or not (domestic or imports):
            raise ValueError(
                "일본 표에는 총거래표와 국산거래표 또는 수입거래표가 필요합니다."
            )
        second, derive = (domestic, False) if domestic else (imports, True)
    else:
        if len(names) < 2:
            raise ValueError(
                "총거래표와 수입거래표에 해당하는 시트가 두 개 이상 필요합니다."
            )
        total, second, derive = names[0], names[1], True
    result = _post_clean(load_data(source, total), load_data(source, second), params)
    return _derive_domestic_local(result, params) if derive else result


__all__ = [
    "MODES",
    "ModeParams",
    "LoadResult",
    "get_mode_params",
    "get_us_config",
    "us_use_file_path",
    "us_local_file_path",
    "available_us_years",
    "load_workbook",
]
