"""총거래·국산거래표에서 산업연관 지표를 만드는 공통 분석 서비스."""

from dataclasses import dataclass
import numpy as np
import pandas as pd
from .editing import _canon_code
from .loading import get_submatrix_withlabel
from .leontief import make_col, make_table, calculate_leontief, LeontiefResult


@dataclass(frozen=True)
class AnalysisResult:
    total: LeontiefResult
    domestic: LeontiefResult
    frames: dict[str, pd.DataFrame | pd.Series]
    statistics: dict[str, float]


def partition_table(df, first_idx, mid):
    """라벨 2행/2열과 합계 경계를 포함하는 X/R/C 블록을 반환한다."""
    row, col = first_idx
    end_row, end_col = mid
    if row < 2 or col < 2 or end_row <= row or end_col <= col:
        raise ValueError("산업 영역과 라벨 시작 위치를 확인하세요.")
    if end_row >= len(df) or end_col >= df.shape[1]:
        raise ValueError("산업 경계가 표의 범위를 벗어났습니다.")
    if end_row - row != end_col - col:
        raise ValueError("중간거래 영역의 산업 행·열 수가 다릅니다.")

    def block(sr, sc, er, ec):
        result = (
            get_submatrix_withlabel(df, sr, sc, er, ec, first_idx).copy().astype(object)
        )
        result.index = range(len(result))
        result.columns = range(result.shape[1])
        return result

    return {
        "matrix_X": block(row, col, end_row, end_col),
        "matrix_R": block(end_row + 1, col, len(df) - 1, end_col),
        "matrix_C": block(row, end_col + 1, end_row, df.shape[1] - 1),
    }


def labeled_matrix(template, values):
    result = template.copy().astype(object)
    if result.iloc[2:, 2:].shape != np.shape(values):
        raise ValueError("행렬과 라벨의 산업 수가 다릅니다.")
    result.iloc[2:, 2:] = np.asarray(values)
    return result


def _numeric(block):
    values = block.apply(pd.to_numeric, errors="raise").fillna(0).to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("표에 무한대가 포함돼 있습니다.")
    return values


def validate_sector_alignment(total, domestic, first_idx, mid, mid_local):
    row, col = first_idx
    n = mid[0] - row
    if (
        n <= 0
        or mid[1] - col != n
        or mid_local[0] - row != n
        or mid_local[1] - col != n
    ):
        raise ValueError(
            "총거래표와 국산거래표의 산업 수가 일치하는 정방행렬이어야 합니다."
        )
    expected = total.iloc[row : mid[0], col - 2].map(_canon_code).tolist()
    candidates = [
        total.iloc[row - 2, col : mid[1]].map(_canon_code).tolist(),
        domestic.iloc[row : mid_local[0], col - 2].map(_canon_code).tolist(),
        domestic.iloc[row - 2, col : mid_local[1]].map(_canon_code).tolist(),
    ]
    if (
        "" in expected
        or len(set(expected)) != n
        or any(codes != expected for codes in candidates)
    ):
        raise ValueError(
            "총거래표·국산거래표의 행/열 산업 코드가 없거나 중복되거나 순서가 다릅니다."
        )


def analyze_tables(total_df, domestic_df, *, first_idx, mid, mid_local):
    """계산·내보내기 결과를 함께 반환한다. 입력 DataFrame은 변경하지 않는다."""
    validate_sector_alignment(total_df, domestic_df, first_idx, mid, mid_local)
    if len(total_df) < mid[0] + 3:
        raise ValueError("총거래표에 부가가치계와 총투입계 행이 필요합니다.")
    blocks = partition_table(total_df, first_idx, mid)
    local_blocks = partition_table(domestic_df, first_idx, mid_local)
    template = blocks["matrix_X"].iloc[:-1, :-1].copy()
    local_template = local_blocks["matrix_X"].iloc[:-1, :-1].copy()
    row, col = first_idx
    output = pd.to_numeric(total_df.iloc[-1, col : mid[1]], errors="raise").astype(
        float
    )
    value_added = pd.to_numeric(total_df.iloc[-2, col : mid[1]], errors="raise").astype(
        float
    )
    if not np.isfinite(value_added).all():
        raise ValueError("부가가치계에 유효하지 않은 값이 있습니다.")
    total = calculate_leontief(_numeric(template.iloc[2:, 2:]), output)
    domestic = calculate_leontief(_numeric(local_template.iloc[2:, 2:]), output)
    # 기존 분석 규약: 총거래표의 총투입계로 국산표도 정규화한다.
    denominator = np.where(output.to_numpy() == 0, 1.0, output.to_numpy())
    v = value_added.to_numpy() / denominator
    final_headers = (
        blocks["matrix_C"]
        .iloc[1]
        .fillna("")
        .astype(str)
        .str.replace(" ", "", regex=False)
    )
    positions = np.flatnonzero(final_headers.to_numpy() == "최종수요계")
    if not len(positions):
        raise ValueError(
            "최종수요계 열을 찾을 수 없습니다. 표의 합계 열 이름을 확인하세요."
        )
    y = _numeric(blocks["matrix_C"].iloc[2:-1, [int(positions[0])]]).reshape(-1)
    gdp = v * (total.inverse @ y)
    multiplier = v @ domestic.inverse
    w = v[:, None] * total.inverse * y[None, :]
    g1, g2, g3 = w.sum(axis=1), w.sum(axis=0), w.diagonal()
    effects = {"g1": g1, "g2": g2, "g3": g3, "g123": g1 + g2 - g3}
    inverse_frame = labeled_matrix(template, total.inverse)
    r_template = blocks["matrix_R"].iloc[:-1, :-1].copy()
    r_frame = labeled_matrix(
        r_template, _numeric(r_template.iloc[2:, 2:]) / denominator
    )
    frames = {
        "edited_df": total_df.copy(),
        "edited_df_local": domestic_df.copy(),
        **{f"edited_{key}": value for key, value in blocks.items()},
        "투입계수행렬": labeled_matrix(template, total.coefficients),
        "국산투입계수행렬": labeled_matrix(local_template, domestic.coefficients),
        "leontief_inverse": inverse_frame,
        "국산_leontief_inverse": labeled_matrix(local_template, domestic.inverse),
        "normalization_denominator": output.copy(),
        "부가가치계벡터": value_added.copy(),
        "부가가치계수행렬": r_frame,
        "FL_BL": make_table(
            template,
            [
                make_col("FL", total.forward_linkage, "2"),
                make_col("BL", total.backward_linkage, "3"),
            ],
        ),
        "GDP": make_table(template, [make_col("GDP", gdp, "2")]),
        "부가가치유발효과": make_table(
            template, [make_col("부가가치유발효과", multiplier, "2")]
        ),
        "g_series": make_table(
            template,
            [
                make_col("g1+g2-g3" if name == "g123" else name, vec, str(i + 2))
                for i, (name, vec) in enumerate(effects.items())
            ],
        ),
    }
    statistics = {}
    for name, vec in {"GDP": gdp, "m_v": multiplier, **effects}.items():
        statistics[f"{name}_total"] = float(vec.sum())
        statistics[f"{name}_mean"] = float(vec.mean())
    return AnalysisResult(total, domestic, frames, statistics)
