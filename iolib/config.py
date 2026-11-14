"""모드 설정과 외부 데이터 위치. 설치 위치와 실행 디렉터리를 분리한다."""

import os
from pathlib import Path
from typing import Any, Dict, List
from .models import ModeParams


def get_data_dir() -> Path:
    """환경 변수로 데이터 폴더를 지정하거나 소스 저장소 루트를 사용한다."""
    configured = os.environ.get("KHU_SUBAPP_DATA_DIR")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else Path(__file__).resolve().parents[1]
    )


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
    "Korea(2010~2020)": ModeParams(
        first_idx=(6, 2), subplus_edit=False, number_of_label=2
    ),
    "Japan(2000~2020)": ModeParams(
        first_idx=(6, 2), subplus_edit=False, number_of_label=2
    ),
    "Korea(1990~2005)": ModeParams(
        first_idx=(5, 2), subplus_edit=True, number_of_label=2
    ),
    "Manual": ModeParams(first_idx=(6, 2), subplus_edit=False, number_of_label=2),
    "US(Summary 2000~2024)": ModeParams(
        first_idx=(6, 2), subplus_edit=False, number_of_label=2
    ),
    "US(Sector 2000~2024)": ModeParams(
        first_idx=(6, 2), subplus_edit=False, number_of_label=2
    ),
}


# US-only config — BEA Use 기반 한국레이아웃 워크북 (연도별 시트).
# 총거래표 → df, 국산거래표(Use − 수입행렬) → df_local.
_US_CONFIG: Dict[str, Dict[str, Any]] = {
    "US(Summary 2000~2024)": {
        "level": "Summary",  # 71개 중분류 산업
        "total_filename": "미국_사용표_총거래_한국레이아웃_2000_2024.xlsx",
        "local_filename": "미국_사용표_국산_한국레이아웃_2000_2024.xlsx",
    },
    "US(Sector 2000~2024)": {
        "level": "Sector",  # 15개 대분류 산업
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
    try:
        return _PARAMS[mode]
    except KeyError as exc:
        raise ValueError(f"지원하지 않는 모드입니다: {mode}") from exc


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
    return get_data_dir() / cfg["total_filename"]


def us_local_file_path(mode: str) -> Path | None:
    """Repo path to the US 국산거래표 workbook, or None."""
    cfg = _US_CONFIG.get(mode)
    if cfg is None:
        return None
    return get_data_dir() / cfg["local_filename"]
