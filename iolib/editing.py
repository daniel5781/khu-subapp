"""부문(산업) 편집 연산과 그 재생(replay).

대시보드의 "DataFrame을 수정합니다" 단계에서 쓰는 연산들:
- `insert_row_and_col`  : 새 산업의 행+열 추가
- `transfer_to_new_sector` : 한 산업의 행/열 일부(alpha)를 다른 산업으로 이전
- `remove_zero_series`  : 전부 0 인 행과 짝 열 삭제
- `reduce_negative_values` : 음수를 절반으로 줄이고 차이를 마지막 행에 환원
- `apply_batch_edit`    : 엑셀 일괄 이전 적용
- `replay_edit_ops_on_df` : 위 연산 기록(edit_ops)을 다른 시트(국내표)에 그대로 재생

연산은 코드(문자열)와 수치를 한 DataFrame 에 섞어 쓰므로 새로 만드는 열은
반드시 object dtype 이어야 한다(`_nan_object_column`).
"""
from copy import deepcopy
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


def _nan_object_column(n: int, index) -> pd.Series:
    """NaN 으로 채운 object dtype 열. 코드/이름(문자열)과 0(숫자)을 같은 열에
    섞어 쓰므로 float 열로 만들면 pandas 3.0 이상에서 대입이 실패한다."""
    return pd.Series([np.nan] * n, index=index, dtype=object)


def _canon_code(x) -> str:
    """산업 코드 비교용 정규화: 11(int), 11.0(float), '11', ' 11 ', '11.0'
    → 모두 '11'. 엑셀이 숫자로만 된 코드를 int/float 로 읽어 와도 문자열
    입력(text_input, 배치 엑셀)과 항상 매칭되게 한다. NaN/None → ''."""
    if x is None:
        return ""
    if isinstance(x, float):
        if np.isnan(x):
            return ""
        if x == int(x):
            return str(int(x))
        return str(x)
    s = str(x).strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    return s


def insert_row_and_col(df, first_idx, mid_ID_idx, code, name, num_of_label):
    code = _canon_code(code)   # 숫자로 들어와도 '11' 같은 문자열로 저장
    df_editing = df.copy()
    df_editing.insert(loc=mid_ID_idx[1], column='a',
                      value=_nan_object_column(df_editing.shape[0], df_editing.index),
                      allow_duplicates=True)
    df_editing.iloc[first_idx[0]-num_of_label, mid_ID_idx[1]] = code
    df_editing.iloc[first_idx[0]-num_of_label+1, mid_ID_idx[1]] = name
    df_editing.iloc[first_idx[0]:, mid_ID_idx[1]] = 0
    df_editing.columns = range(df_editing.shape[1])
    df_editing = df_editing.T
    df_editing.insert(loc=mid_ID_idx[0], column='a',
                      value=_nan_object_column(df_editing.shape[0], df_editing.index),
                      allow_duplicates=True)
    df_editing.iloc[first_idx[1]-num_of_label, mid_ID_idx[0]] = code
    df_editing.iloc[first_idx[1]-num_of_label+1, mid_ID_idx[0]] = name
    df_editing.iloc[first_idx[1]:, mid_ID_idx[0]] = 0
    df_editing.columns = range(df_editing.shape[1])
    df_editing = df_editing.T
    df_inserted = df_editing.copy()
    mid_ID_idx = (mid_ID_idx[0]+1, mid_ID_idx[1]+1)
    msg = f'A new row and column (Code: {code}, Name: {name}) have been inserted.'

    return df_inserted, mid_ID_idx, msg


def transfer_to_new_sector(df, first_idx, origin_code, target_code, ratio, code_label=2):
    df_editing = df.copy()
    # 코드 열이 int/float 로 읽혀 있어도 문자열 입력과 매칭되도록 정규화해 비교.
    codes = df_editing[first_idx[1]-code_label].map(_canon_code)
    target_idx = df_editing.index[codes == _canon_code(target_code)].tolist()
    if len(target_idx) == 1:
        target_idx = target_idx[0]
    else:
        msg = 'ERROR: target code is not unique.'
        return df_editing, msg
    origin_idx = df_editing.index[codes == _canon_code(origin_code)].tolist()
    if len(origin_idx) == 1:
        origin_idx = origin_idx[0]
    else:
        msg = 'ERROR: origin code is not unique.'
        return df_editing, msg
    df_editing.iloc[first_idx[0]:, first_idx[1]:] = df_editing.iloc[first_idx[0]:, first_idx[1]:].apply(pd.to_numeric, errors='coerce')
    origin_idx = (origin_idx, origin_idx-first_idx[0]+first_idx[1])
    target_idx = (target_idx, target_idx-first_idx[0]+first_idx[1])
    df_editing.iloc[target_idx[0], first_idx[1]:] += df_editing.iloc[origin_idx[0], first_idx[1]:] * ratio
    df_editing.iloc[origin_idx[0], first_idx[1]:] = df_editing.iloc[origin_idx[0], first_idx[1]:] * (1-ratio)
    df_editing.iloc[first_idx[0]:, target_idx[1]] += df_editing.iloc[first_idx[0]:, origin_idx[1]] * ratio
    df_editing.iloc[first_idx[0]:, origin_idx[1]] = df_editing.iloc[first_idx[0]:, origin_idx[1]] * (1-ratio)

    msg = f'{ratio*100}% of {origin_code} has been moved to {target_code}.'
    return df_editing, msg


def remove_zero_series(
    df: pd.DataFrame,
    first_idx: tuple[int, int],
    mid_ID_idx: tuple[int, int],
    remove_positions: dict | None = None,
):
    """
    - remove_positions가 None이면: 기존 로직대로 '0으로만 이뤄진 행'을 찾아 (대응되는 열)까지 삭제
    - remove_positions가 주어지면: 해당 위치만 삭제

    remove_positions / return_positions 형식(동일):
      {
        "zero_row_indices": [ ... ],   # df의 원본 index 기준 (drop에 바로 쓰는 값)
        "zero_col_indices": [ ... ],   # df의 원본 column index 기준 (drop에 바로 쓰는 값)
      }

    return:
      df_editing, msg, mid_ID_idx, removed_positions
    """

    df_editing = df.copy()

    # -------------------------
    # 1) 삭제 위치 결정
    # -------------------------
    if remove_positions is None:
        # 기존 로직: first_idx 이후 블록을 숫자로 보고, 행 전체가 0인 행 찾기
        df_test = df_editing.iloc[first_idx[0]:, first_idx[1]:].apply(pd.to_numeric, errors="coerce")

        zero_row_indices = df_test.index[(df_test == 0).all(axis=1)].tolist()
        zero_row_indices = [i for i in zero_row_indices if first_idx[0] <= i <= mid_ID_idx[0]]

        # 기존 로직: row index -> 대응되는 col index 매핑
        zero_col_indices = [i - first_idx[0] + first_idx[1] for i in zero_row_indices]

        removed_positions = {
            "zero_row_indices": zero_row_indices,
            "zero_col_indices": zero_col_indices,
        }

    else:
        # 주어진 삭제 위치 사용 (형식 동일)
        removed_positions = {
            "zero_row_indices": list(remove_positions.get("zero_row_indices", [])),
            "zero_col_indices": list(remove_positions.get("zero_col_indices", [])),
        }

    zero_row_indices = removed_positions["zero_row_indices"]
    zero_col_indices = removed_positions["zero_col_indices"]

    # -------------------------
    # 2) 삭제 수행
    # -------------------------
    if len(zero_row_indices) > 0:
        df_editing.drop(zero_row_indices, inplace=True)

    if len(zero_col_indices) > 0:
        df_editing.drop(zero_col_indices, inplace=True, axis=1)

    # index/columns 리셋(너 기존 코드 유지)
    df_editing.columns = range(df_editing.shape[1])
    df_editing.index = range(df_editing.shape[0])

    # -------------------------
    # 3) mid_ID_idx 업데이트 + msg
    # -------------------------
    count = len(zero_col_indices)  # 기존 로직: 삭제한 열 개수만큼 mid_ID_idx 줄임
    msg = f"{count}개의 행(열)이 삭제되었습니다."
    mid_ID_idx = (mid_ID_idx[0] - count, mid_ID_idx[1] - count)

    return df_editing, msg, mid_ID_idx, removed_positions


def reduce_negative_values(df, first_idx, mid_ID_idx):
    # 데이터프레임 복사
    df_editing = df.copy()

    # first_idx에서 mid_ID_idx까지의 범위 슬라이싱
    df_test = df_editing.iloc[first_idx[0]:mid_ID_idx[0], first_idx[1]:mid_ID_idx[1]].apply(pd.to_numeric, errors='coerce')

    # 음수 값이 있는 위치 추적 및 줄인 값 계산
    reduced_values_per_column = {}

    def reduce_and_track(value, col_index):
        if value < 0:
            # 줄일 값 저장 (음수 값의 절반)
            reduced_value = value / 2
            if col_index not in reduced_values_per_column:
                reduced_values_per_column[col_index] = 0
            reduced_values_per_column[col_index] += value - reduced_value  # 원래 값 - 절반으로 줄인 값
            return reduced_value
        return value

    # 음수인 값만 1/2로 줄이면서 추적
    for col_idx in range(df_test.shape[1]):
        df_test.iloc[:, col_idx] = df_test.iloc[:, col_idx].apply(lambda x: reduce_and_track(x, col_idx))

    # 수정된 값을 원본 데이터프레임에 다시 반영 (first_idx에서 mid_ID_idx까지의 부분)
    df_editing.iloc[first_idx[0]:mid_ID_idx[0], first_idx[1]:mid_ID_idx[1]] = df_test

    # 마지막 행에 줄인 값만큼 더하기
    last_row_index = df_editing.shape[0] - 1
    for col_idx, total_reduced in reduced_values_per_column.items():
        df_editing.iloc[last_row_index, first_idx[1] + col_idx] -= total_reduced

    msg = "음수 값들을 절반으로 줄이고, 줄인 값을 마지막 행에 더했습니다."

    # 중간 인덱스 값은 그대로 반환 (mid_ID_idx는 행과 열 인덱스이므로 이 경우 변경되지 않음)
    return df_editing, msg, mid_ID_idx


def apply_batch_edit(
    *,
    batch_df: pd.DataFrame,
    df_curr: pd.DataFrame,
    first_idx: tuple,
    number_of_label: int,
    mid_ID_idx: tuple,
    ids_simbol: dict,
    insert_row_and_col_fn,
):
    """
    Inputs
    ------
    batch_df : columns = ['from','to','alpha','to_name']
    df_curr  : 현재 df_editing
    first_idx, number_of_label : 기존 그대로
    mid_ID_idx : 현재 mid index
    ids_simbol : 코드->이름 리스트 dict (공유/갱신)
    insert_row_and_col_fn : 기존 함수 주입

    Returns
    -------
    df_out, mid_out, ids_out, log_text
    """

    df_curr = df_curr.copy()
    code_col_idx = first_idx[1] - number_of_label

    log_lines = []

    # -------------------------
    # 1) to/to_name 기반 자동 산업 추가
    # -------------------------
    targets = batch_df[["to", "to_name"]].drop_duplicates()

    for _, t in targets.iterrows():
        new_code = _canon_code(t["to"])
        new_name = str(t["to_name"]) if str(t["to_name"]) not in ["nan", "None"] else ""

        exists = (df_curr.iloc[:, code_col_idx].map(_canon_code) == new_code).any()
        if exists:
            if new_code not in ids_simbol:
                ids_simbol[new_code] = []
            if new_name and (new_name not in ids_simbol[new_code]):
                ids_simbol[new_code].append(new_name)
            continue

        result = insert_row_and_col_fn(
            df_curr,
            first_idx,
            mid_ID_idx,
            new_code,
            new_name if new_name else f"NEW_{new_code}",
            number_of_label,
        )

        df_curr, mid_ID_idx = result[0], result[1]
        # 원본 코드의 data_editing_log += result[2]
        log_lines.append(str(result[2]).strip())

        if new_code not in ids_simbol:
            ids_simbol[new_code] = []
        if new_name:
            ids_simbol[new_code].append(new_name)

    # -------------------------
    # 2) from 기준 분배 이동
    # -------------------------
    grouped = batch_df.groupby("from")
    # 1단계의 insert 가 끝난 뒤라 행 구성이 고정 — 코드 열을 한 번만 정규화.
    codes_series = df_curr.iloc[:, code_col_idx].map(_canon_code)

    for origin_code, group in grouped:
        origin_indices = df_curr.index[codes_series == _canon_code(origin_code)].tolist()
        if len(origin_indices) != 1:
            log_lines.append(f"Error: Origin Code '{origin_code}' 유일하지 않거나 없음. 스킵")
            continue

        origin_row_idx = origin_indices[0]
        origin_col_idx = origin_row_idx - first_idx[0] + first_idx[1]

        # snapshot
        origin_row_data = df_curr.iloc[origin_row_idx, first_idx[1]:].copy()
        origin_col_data = df_curr.iloc[first_idx[0]:, origin_col_idx].copy()

        total_alpha = float(group["alpha"].sum())

        for _, r in group.iterrows():
            target_code = r["to"]
            ratio = float(r["alpha"])

            target_indices = df_curr.index[codes_series == _canon_code(target_code)].tolist()
            if len(target_indices) != 1:
                log_lines.append(
                    f"Error: Target Code '{target_code}' 유일하지 않거나 없음. ({origin_code}->{target_code} 스킵)"
                )
                continue

            target_row_idx = target_indices[0]
            target_col_idx = target_row_idx - first_idx[0] + first_idx[1]

            df_curr.iloc[target_row_idx, first_idx[1]:] += origin_row_data * ratio
            df_curr.iloc[first_idx[0]:, target_col_idx] += origin_col_data * ratio

            log_lines.append(f"[Batch] {origin_code} -> {target_code}: {ratio*100:.2f}% 이동")

        remaining_ratio = 1.0 - total_alpha
        if abs(remaining_ratio) < 1e-9:
            remaining_ratio = 0.0

        df_curr.iloc[origin_row_idx, first_idx[1]:] = origin_row_data * remaining_ratio
        df_curr.iloc[first_idx[0]:, origin_col_idx] = origin_col_data * remaining_ratio
        log_lines.append(f"[Batch Info] {origin_code} 잔여: {remaining_ratio*100:.4f}%")

    log_text = "\n".join([x for x in log_lines if x])

    return df_curr, mid_ID_idx, ids_simbol, log_text


def replay_edit_ops_on_df(
    df_base: pd.DataFrame,
    mid_ID_idx_base: Tuple[int, int],
    ids_simbol_base: Dict[str, List[str]],
    ops: List[Dict[str, Any]],
    *,
    first_idx: Tuple[int, int],
    number_of_label: int,
    insert_row_and_col_fn,
    transfer_to_new_sector_fn,
    remove_zero_series_fn,
    reduce_negative_values_fn,
    batch_apply_fn=None,          # apply_batch_edit 같은 함수 주입
    copy_ids: bool = False,       # ids_simbol 공유 싫으면 True
    return_log: bool = True,      # 디버깅/기록용 로그 반환
):
    """
    ops를 순서대로 df_base에 다시 적용하여 df/mid/ids를 갱신해서 반환.
    - st.session_state 의존 없음
    - batch_apply는 batch_apply_fn이 주어졌을 때만 실행 가능

    Returns
    -------
    (df, mid, ids) or (df, mid, ids, log_text)  (return_log=True일 때)
    """

    df = df_base.copy()
    mid = mid_ID_idx_base
    ids = deepcopy(ids_simbol_base) if copy_ids else ids_simbol_base

    log_lines: List[str] = []

    for i, op in enumerate(ops, start=1):
        if "type" not in op:
            raise KeyError(f"[op #{i}] missing key: 'type'")

        t = op["type"]

        # -------------------------
        # 1) 산업 추가 (insert_row_and_col)
        # -------------------------
        if t == "insert_sector":
            for k in ("code", "name"):
                if k not in op:
                    raise KeyError(f"[op #{i} insert_sector] missing key: '{k}'")

            result = insert_row_and_col_fn(
                df,
                first_idx,
                mid,
                op["code"],
                op["name"],
                number_of_label,
            )
            df, mid = result[0], result[1]

            # result[2] = 로그 문자열 (너 코드 기준)
            if len(result) >= 3 and result[2]:
                log_lines.append(str(result[2]).strip())

            # ids 반영
            c = str(op["code"])
            n = str(op["name"])
            if c not in ids:
                ids[c] = []
            if n and n not in ids[c]:
                ids[c].append(n)

        # -------------------------
        # 2) 값 옮기기 (transfer_to_new_sector)
        # -------------------------
        elif t == "transfer":
            for k in ("from", "to", "alpha"):
                if k not in op:
                    raise KeyError(f"[op #{i} transfer] missing key: '{k}'")

            result = transfer_to_new_sector_fn(
                df,
                first_idx,
                op["from"],
                op["to"],
                float(op["alpha"]),
            )
            df = result[0]

            # result[1]이 로그라면 누적(너 함수가 그렇게 주면)
            if return_log and len(result) >= 2 and result[1]:
                log_lines.append(str(result[1]).strip())

        # -------------------------
        # 3) 0인 행/열 삭제 (remove_zero_series)
        # -------------------------
        elif t == "remove_zero":
            result = remove_zero_series_fn(df, first_idx, mid, remove_positions=op.get("remove_positions"))
            df, mid = result[0], result[2]

            if return_log and len(result) >= 2 and result[1]:
                log_lines.append(str(result[1]).strip())

        # -------------------------
        # 4) 음수 절반 (reduce_negative_values)
        # -------------------------
        elif t == "reduce_negative":
            # 네 기존 코드처럼 mid를 -1 해서 넘길지 여부
            use_minus_one = bool(op.get("use_minus_one_mid", True))
            mid_use = (mid[0] - 1, mid[1] - 1) if use_minus_one else mid

            result = reduce_negative_values_fn(df, first_idx, mid_use)
            df = result[0]

            if return_log and len(result) >= 2 and result[1]:
                log_lines.append(str(result[1]).strip())

        # -------------------------
        # 5) 배치 적용 (apply_batch_edit로 재실행)
        # -------------------------
        elif t == "batch_apply":
            if "batch_records" not in op:
                raise KeyError(f"[op #{i} batch_apply] missing key: 'batch_records'")
            if batch_apply_fn is None:
                raise ValueError(
                    "[batch_apply] batch_apply_fn이 필요합니다. "
                    "예: replay_edit_ops_on_df(..., batch_apply_fn=apply_batch_edit)"
                )

            batch_df = pd.DataFrame(op["batch_records"])

            df, mid, ids, batch_log = batch_apply_fn(
                batch_df=batch_df,
                df_curr=df,
                first_idx=first_idx,
                number_of_label=number_of_label,
                mid_ID_idx=mid,
                ids_simbol=ids,
                insert_row_and_col_fn=insert_row_and_col_fn,
            )

            if return_log and batch_log:
                log_lines.append(str(batch_log).strip())

        else:
            raise ValueError(f"[op #{i}] Unknown op type: {t}")

    if return_log:
        log_text = "\n".join([x for x in log_lines if x])
        return df, mid, ids, log_text

    return df, mid, ids
