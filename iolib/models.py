"""업로드 모드와 정규화된 산업연관표의 공통 계약."""

from dataclasses import dataclass
from typing import Any, List, Tuple
import pandas as pd


@dataclass(frozen=True)
class ModeParams:
    first_idx: Tuple[int, int]  # 숫자 영역 시작 위치 (0부터).
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
