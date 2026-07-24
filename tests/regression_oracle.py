"""백엔드 회귀 오라클 (동작 동일성 검증용).

실행:
    python tests/regression_oracle.py            # tests/golden.json 생성/갱신
    python tests/regression_oracle.py out.json   # 다른 경로로 저장
    python tests/regression_oracle.py --check     # tests/golden.json 과 비교, 다르면 exit 1

`iolib` 패키지(= 기존 functions.py)와 `preprocessing.py`의 순수 백엔드 함수
전체를 실제 한국 통합중분류 표로 한 번 돌려, 각 산출물의 안정적인 digest
(shape / sum / |sum| / mean)를 만든다. 코드 변경 후 `--check` 가 통과하면
백엔드 수치 동작이 보존된 것이다.

Streamlit 컨텍스트 없이 돌리므로 st.* 호출은 경고만 내고 무시된다.
"""
from __future__ import annotations

import io
import json
import sys
import warnings
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import functions as F          # noqa: E402  (리팩토링 후에도 shim 으로 동일 import)
import preprocessing as P      # noqa: E402

KOREA_XLSX = REPO / "(표)(2020실측)투입산출표_생산자가격_통합중분류.xlsx"


def digest(obj) -> dict:
    """DataFrame / ndarray / Series 를 안정적 요약값으로."""
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        arr = pd.to_numeric(np.asarray(obj).ravel(), errors="coerce")
    else:
        arr = np.asarray(obj, dtype=float).ravel()
    arr = np.asarray(arr, dtype=float)
    finite = arr[np.isfinite(arr)]
    return {
        "shape": list(np.shape(obj)),
        "n_finite": int(finite.size),
        "sum": round(float(finite.sum()), 4),
        "abs_sum": round(float(np.abs(finite).sum()), 4),
        "mean": round(float(finite.mean()), 6) if finite.size else None,
    }


def run() -> dict:
    out: dict = {}

    # ── 1) 업로드 로딩 (preprocessing) ────────────────────────────────
    with redirect_stdout(io.StringIO()):  # get_mid_ID_idx 디버그 print 흡수
        res = P.load_workbook(str(KOREA_XLSX), "Korea(2010~2020)")
    out["load.df"] = digest(res.df)
    out["load.df_local"] = digest(res.df_local)
    out["load.mid"] = list(res.mid_ID_idx)
    out["load.mid_local"] = list(res.mid_ID_idx_local)

    first_idx = (6, 2)
    nlbl = 2

    # 실제 앱처럼 전산출 0인 산업(행/열)을 먼저 제거해 (I-A) 가역성을 확보.
    df_nz, _msg, mid_nz, _pos = F.remove_zero_series(res.df, first_idx, res.mid_ID_idx)
    out["nonzero.df"] = digest(df_nz)
    out["nonzero.mid"] = list(mid_nz)

    # ── 2) 서브매트릭스 추출 ──────────────────────────────────────────
    X = F.get_submatrix_withlabel(df_nz, first_idx[0], first_idx[1],
                                  mid_nz[0], mid_nz[1],
                                  first_idx, numberoflabel=nlbl)
    out["submatrix.X"] = digest(X)

    df_for_leontief = X.iloc[:-1, :-1].copy()
    df_for_leontief.index = range(df_for_leontief.shape[0])
    df_for_leontief.columns = range(df_for_leontief.shape[1])

    norm = df_nz.iloc[df_nz.shape[0] - 1, first_idx[1]:mid_nz[1]]
    norm = pd.to_numeric(norm).replace(0, np.finfo(float).eps)

    # ── 3) 투입계수행렬 A (열 정규화) & 직접 역행렬 L ─────────────────
    A = df_for_leontief.apply(pd.to_numeric, errors="coerce").divide(norm, axis=1).to_numpy()
    L = np.linalg.inv(np.eye(A.shape[0]) - A)
    out["A"] = digest(A)
    out["L_direct"] = digest(L)

    # ── 4) Leontief (build_leontief_outputs) — without_label 은 L 블록 ─
    with_label, without_label = F.build_leontief_outputs(df_for_leontief, norm)
    out["leontief.with_label"] = digest(with_label)
    out["leontief.without_label"] = digest(without_label)
    Lblock = without_label  # 앱과 동일하게 네트워크 추출은 L 위에서 수행

    # ── 5) compute_leontief_inverse (급수 근사) & 분리 ────────────────
    N0 = F.compute_leontief_inverse(A, epsilon=0.05)
    Diagon, N = F.separate_diagonals(N0)
    out["series.N0"] = digest(N0)
    out["series.N"] = digest(N)
    out["series.Diagon"] = digest(Diagon)

    # ── 6) Method B (extract_network_leontief) — 입력은 L 블록 ────────
    with redirect_stdout(io.StringIO()):
        Bc, Q, _fig, info = F.extract_network_leontief(Lblock, epsilon=1e-4, delta=0.01, max_iter=100)
    out["methodB.Bc"] = digest(Bc)
    out["methodB.Q"] = digest(Q)
    out["methodB.info"] = {k: (round(v, 6) if isinstance(v, float) else v)
                           for k, v in info.items()
                           if k in ("final_t", "converged", "epsilon", "delta")}

    # ── 7) threshold_count (Method A 제안 임계값) — 입력은 L 블록 ─────
    with redirect_stdout(io.StringIO()):
        thr = F.threshold_count(Lblock)
    out["methodA.threshold"] = round(float(thr), 6)

    # ── 8) 이진/무방향 변환 ──────────────────────────────────────────
    bm = F.make_binary_matrix(Lblock.apply(pd.to_numeric, errors="coerce"), thr)
    _, bm = F.separate_diagonals(bm.to_numpy() if hasattr(bm, "to_numpy") else bm)
    out["binary"] = digest(bm)
    out["undirected"] = digest(F.create_undirected_network(bm))

    # ── 9) 중심성 (calculate_network_centralities) ───────────────────
    # 앱의 Method A 경로와 동일: threshold 로 튜닝된 이진행렬(고립 노드 없음) 위에
    # 가중 L 을 곱한 filtered 행렬에서 그래프를 만든다.
    import networkx as nx
    n = Lblock.shape[0]
    Lnum = Lblock.apply(pd.to_numeric, errors="coerce").to_numpy()
    filtered = Lnum * np.asarray(bm, dtype=float)
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    rows, cols = np.where(filtered != 0)
    weights = filtered[rows, cols]
    G.add_edges_from((int(j), int(i), {"weight": float(w)})
                     for i, j, w in zip(rows, cols, weights))
    cents = F.calculate_network_centralities(G, with_label, use_weight=False)
    for name, d in zip(("degree", "bc", "cc", "ev", "hi", "kim"), cents[:6]):
        out[f"cent.{name}"] = digest(d.iloc[:, 2:])

    # ── 10) Kim / 표준 구조적 공백 지표 ──────────────────────────────
    kc, ke = F.calculate_kim_metrics(G, weight=None)
    out["kim.constraint"] = digest(pd.Series(kc).sort_index())
    out["kim.efficiency"] = digest(pd.Series(ke).sort_index())

    # ── 11) 편집 연산 + 재생 (editing ops & replay) ──────────────────
    # 라벨 영역에 문자열 코드를 쓰므로 object dtype 으로 두고 검증(앱 동작과 동일).
    df_e = res.df.copy().astype(object)
    mid = res.mid_ID_idx
    code0 = str(df_e.iloc[first_idx[0], 0])
    code1 = str(df_e.iloc[first_idx[0] + 1, 0])

    df_e, mid, _ = F.insert_row_and_col(df_e, first_idx, mid, "ZZZ", "테스트산업", nlbl)
    out["edit.insert"] = digest(df_e)
    out["edit.insert.mid"] = list(mid)

    df_t, _ = F.transfer_to_new_sector(df_e, first_idx, code0, code1, 0.3)
    out["edit.transfer"] = digest(df_t)

    df_r, _, mid_r = F.reduce_negative_values(df_t, first_idx, (mid[0] - 1, mid[1] - 1))
    out["edit.reduce"] = digest(df_r)

    df_z, _, mid_z, pos = F.remove_zero_series(df_e, first_idx, mid)
    out["edit.remove_zero"] = digest(df_z)
    out["edit.remove_zero.mid"] = list(mid_z)

    ops = [
        {"type": "insert_sector", "code": "ZZZ", "name": "테스트산업"},
        {"type": "transfer", "from": code0, "to": code1, "alpha": 0.3},
    ]
    df_rep, mid_rep, _ids, _log = F.replay_edit_ops_on_df(
        res.df.copy(), res.mid_ID_idx, {}, ops,
        first_idx=first_idx, number_of_label=nlbl,
        insert_row_and_col_fn=F.insert_row_and_col,
        transfer_to_new_sector_fn=F.transfer_to_new_sector,
        remove_zero_series_fn=F.remove_zero_series,
        reduce_negative_values_fn=F.reduce_negative_values,
        batch_apply_fn=F.apply_batch_edit,
    )
    out["edit.replay"] = digest(df_rep)
    out["edit.replay.mid"] = list(mid_rep)

    # ── 12) make_col / make_table ────────────────────────────────────
    vec = np.arange(n, dtype=float)
    col = F.make_col("테스트", vec, "2")
    out["make_col"] = digest(col)
    out["make_table"] = digest(F.make_table(with_label, [col]))

    return out


def _check(golden_path: Path) -> int:
    if not golden_path.exists():
        print(f"[regression_oracle] golden 파일이 없습니다: {golden_path}\n"
              f"  먼저 `python tests/regression_oracle.py` 로 baseline 을 만드세요.")
        return 2
    golden = json.loads(golden_path.read_text())
    current = run()
    keys = set(golden) | set(current)
    bad = [(k, golden.get(k), current.get(k)) for k in sorted(keys)
           if golden.get(k) != current.get(k)]
    if not bad:
        print(f"✅ regression PASS — {len(golden)} digests 모두 일치")
        return 0
    print(f"❌ regression FAIL — {len(bad)} 개 불일치:")
    for k, g, c in bad[:20]:
        print(f"  {k}\n    golden : {g}\n    current: {c}")
    return 1


if __name__ == "__main__":
    golden_path = REPO / "tests" / "golden.json"
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        sys.exit(_check(golden_path))
    dst = Path(sys.argv[1]) if len(sys.argv) > 1 else golden_path
    result = run()
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[regression_oracle] wrote {len(result)} digests -> {dst}")
