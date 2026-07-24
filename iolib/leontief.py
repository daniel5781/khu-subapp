"""Leontief 역행렬 계산과 행렬 전처리·표 생성 헬퍼.

- `build_leontief_outputs` : 투입계수행렬 A 정규화 → L=(I-A)^-1 → FL/BL 부착
- `compute_leontief_inverse` : L 을 무한급수 I+A+A^2+... 로 근사
- `separate_diagonals` / `threshold_network` / `create_binary_network` /
  `create_undirected_network` / `make_binary_matrix` / `filter_matrix`
  : 네트워크 행렬 전처리
- `make_col` / `make_table` : 지표 열·표 조립
"""
import numpy as np
import pandas as pd


def make_binary_matrix(matrix, threshold):
    # 임계값 이하의 원소들을 0으로 설정
    binary_matrix = matrix.apply(lambda x: np.where(x > threshold, 1, 0))
    return binary_matrix


def filter_matrix(matrix, threshold):
    # 임계값 이하의 원소들을 0으로 설정
    filtered_matrix = matrix.where(matrix > threshold, 0)
    return filtered_matrix


def compute_leontief_inverse(A, epsilon=0.05, max_iter=100):
    """
    Leontief 역행렬을 무한급수(I + A + A^2 + ...)로 근사 계산하는 함수.
    수렴 조건: 누적합의 상대변화가 epsilon 이하가 될 때까지 반복.

    Parameters:
        A (ndarray): 투입계수행렬.
        epsilon (float): 수렴 판정 기준 (예: 0.05 = 5%).
        max_iter (int): 최대 반복 횟수 (무한급수의 수렴이 안 될 경우 대비).

    Returns:
        M (ndarray): I + A + A^2 + ... + A^r (r번째 항까지 계산한 근사 Leontief 역행렬).
    """
    n = A.shape[0]
    I = np.eye(n)           # n x n 항등행렬 생성
    M = I.copy()            # 초기 누적합: M(0) = I
    s_prev = np.sum(M)      # 초기 전체합 (s(0))
    k = 1                   # 거듭제곱 차수 초기화

    while k < max_iter:
        # A^k 계산 (행렬의 거듭제곱)
        A_power = np.linalg.matrix_power(A, k)

        # 누적합 업데이트: M(k) = M(k-1) + A^k
        M_new = M + A_power

        # 새로운 전체합 계산
        s_new = np.sum(M_new)

        # 상대 변화량 계산: (s(k) - s(k-1)) / s(k-1)
        ratio_change = (s_new - s_prev) / s_prev if s_prev != 0 else 0

        # 수렴 판정: 상대 변화가 epsilon 이하이면 종료
        if ratio_change <= epsilon:
            M = M_new
            break

        # 업데이트 후 다음 반복 진행
        M = M_new
        s_prev = s_new
        k += 1

    return M


def separate_diagonals(N0):
    """
    입력 행렬 N0에서 대각원소와 비대각원소(네트워크 base)를 분리.

    Parameters:
        N0 (ndarray): Leontief 역행렬 근사 (I + A + A^2 + ...).

    Returns:
        Diagon (ndarray): N0에서 대각원소만 남기고 나머지를 0으로 만든 행렬.
        N (ndarray): N0에서 대각원소를 모두 0으로 만든 네트워크 행렬.
    """
    # np.diag: 대각 성분 추출, np.diagflat: 대각 행렬로 재구성
    Diagon = np.diag(np.diag(N0))
    N = N0 - Diagon
    return Diagon, N


def threshold_network(N, delta):
    """
    네트워크 행렬 N에서 임계치 delta보다 작은 값들을 0으로 대체.

    Parameters:
        N (ndarray): 원본 네트워크 행렬.
        delta (float): 임계치 값.

    Returns:
        N_thresholded (ndarray): thresholding 적용된 네트워크 행렬.
    """
    N_thresholded = N.copy()
    N_thresholded[N_thresholded < delta] = 0
    return N_thresholded


def create_binary_network(N):
    """
    가중치 네트워크 행렬 N를 이진(0-1) 네트워크로 변환 (양수면 1, 아니면 0).

    Parameters:
        N (ndarray): 가중치 네트워크 행렬.

    Returns:
        BN (ndarray): 이진화된 네트워크 (방향성 유지).
    """
    BN = (N > 0).astype(int)
    return BN


def create_undirected_network(BN):
    """
    방향성이 있는 이진 네트워크 BN를 무방향 네트워크로 변환.
    두 노드 간 어느 한쪽이라도 연결되어 있으면, 무방향 연결로 처리.

    Parameters:
        BN (ndarray): 이진화된 방향성 네트워크.

    Returns:
        UN (ndarray): 무방향(대칭) 이진 네트워크.
    """
    UN = ((BN + BN.T) > 0).astype(int)
    return UN


def build_leontief_outputs(
    df_for_leontief: pd.DataFrame,
    normalization_denominator_replaced,
):
    """
      1) df_for_leontief_with_label  (라벨 포함 + 레온티에프 역행렬 L만, FL/BL 없음)
      2) df_for_leontief_without_label (라벨 제거 + L만)
      3) fl_bl (번호/부문명칭 + FL + BL)
    """

    # 1) with/without 준비 (너 코드 동일)
    df_with_label = df_for_leontief.copy()
    df_without_label = df_with_label.iloc[2:, 2:].copy()

    # 2) A(tmp) 만들기: 숫자 변환 + 열 정규화 (너 코드 동일)
    tmp = df_without_label.copy()
    tmp = tmp.apply(pd.to_numeric, errors="coerce")
    tmp = tmp.divide(normalization_denominator_replaced, axis=1)

    # A를 with_label에 반영 (너 코드 동일)
    df_with_label.iloc[2:, 2:] = tmp

    # 3) 레온티에프 역행렬 L=(I-A)^-1 (너 코드 동일)
    unit_matrix = np.eye(tmp.shape[0])
    subtracted_matrix = unit_matrix - tmp
    leontief = np.linalg.inv(subtracted_matrix.values)
    leontief = pd.DataFrame(leontief)

    # 4) (N+1)x(N+1)로 확장해서 FL/BL 계산 + 평균 정규화 (너 코드 동일)
    leontief_rows, leontief_cols = leontief.shape
    leontief_with_sums = np.zeros((leontief_rows + 1, leontief_cols + 1))
    leontief_with_sums[:-1, :-1] = leontief.values
    leontief_with_sums[-1, :-1] = leontief.sum(axis=0).values  # BL 원자료(열합)
    leontief_with_sums[:-1, -1] = leontief.sum(axis=1).values  # FL 원자료(행합)

    last_row_mean = leontief_with_sums[-1, :-1].mean()
    leontief_with_sums[-1, :-1] /= last_row_mean

    last_col_mean = leontief_with_sums[:-1, -1].mean()
    leontief_with_sums[:-1, -1] /= last_col_mean

    new_df = pd.DataFrame(leontief_with_sums)

    # 5) current_df 확장 후, (2,2)부터 new_df 삽입 (너 코드 동일)
    current_df = df_with_label
    existing_rows = current_df.shape[0] - 2
    existing_cols = current_df.shape[1] - 2

    current_df = current_df.reindex(
        index=range(existing_rows + 3),
        columns=range(existing_cols + 3)
    )

    current_df.iloc[2:2 + new_df.shape[0], 2:2 + new_df.shape[1]] = new_df.values
    current_df.iloc[1, -1] = "FL"
    current_df.iloc[-1, 1] = "BL"

    # 6) fl_bl 추출 (너 코드의 iloc 위치 그대로)
    ids_col = current_df.iloc[1:-1, :2]
    fl_data = current_df.iloc[1:-1, -1]
    bl_data = current_df.iloc[-1, 1:-1]

    fl_data = fl_data.to_frame(name="2")
    bl_data = bl_data.to_frame(name="3")

    ids_col = ids_col.reset_index(drop=True)
    fl_data = fl_data.reset_index(drop=True)
    bl_data = bl_data.reset_index(drop=True)

    fl_bl = pd.concat([ids_col, fl_data, bl_data], axis=1)

    # 7) 최종 with_label에서는 FL/BL 제거 (너 코드 동일)
    df_for_leontief_with_label = current_df.iloc[:-1, :-1].copy()

    # 8) 최종 without_label 갱신 (너 코드 동일)
    df_for_leontief_without_label = df_for_leontief_with_label.iloc[2:, 2:].copy()

    return df_for_leontief_with_label, df_for_leontief_without_label


# 지표 열 만드는 함수
def make_col(title: str, vec_1d: np.ndarray, colname: str) -> pd.DataFrame:
    vec_1d = np.asarray(vec_1d, dtype=float).reshape(-1)
    return pd.concat(
        [
            pd.DataFrame([title], columns=[colname]),
            pd.Series(vec_1d).to_frame(name=colname)
        ],
        axis=0
    ).reset_index(drop=True)


# 지표 테이블 만드는 함수
def make_table(base_df, cols: list[pd.DataFrame]) -> pd.DataFrame:
    ids_col = base_df.iloc[1:, :2].reset_index(drop=True)
    return pd.concat([ids_col] + cols, axis=1)
