"""계산 경계에서 공유하는 입력 검증."""

import numpy as np


def square_matrix(matrix, name="행렬"):
    array = np.asarray(matrix, dtype=float)
    if array.ndim != 2 or array.shape[0] != array.shape[1] or not array.shape[0]:
        raise ValueError(f"{name}은 비어 있지 않은 정방행렬이어야 합니다.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name}에 NaN 또는 무한대가 포함돼 있습니다.")
    return array.copy()


def validate_ratio(value):
    try:
        ratio = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("이동 비율은 0과 1 사이의 숫자여야 합니다.") from exc
    if not np.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError("이동 비율은 0과 1 사이의 숫자여야 합니다.")
    return ratio
