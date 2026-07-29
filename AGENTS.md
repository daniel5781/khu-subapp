# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Run / Develop

```bash
pip install -r requirements.txt
streamlit run app.py
```

The `.devcontainer/` is configured to auto-install requirements and launch `streamlit run app.py --server.enableCORS false --server.enableXsrfProtection false` on port 8501. There are no linters or build steps configured.

A backend regression test exists: `python tests/regression_oracle.py --check` runs the whole pure-backend pipeline on the real Korean workbook and compares 38 output digests against `tests/golden.json`. Run it after any change to `iolib/` or `preprocessing.py`; if it passes, numeric behavior is unchanged. Regenerate the baseline with `python tests/regression_oracle.py` (no args) only when a change is *intended* to alter results.

`new.py` is unrelated to the dashboard — it is a one-off Selenium scraper for musinsa snap profiles that dumps to `images/` and writes `output.csv`. Do not wire it into `app.py`.

## Architecture

The project is a Korean-language Streamlit dashboard ("산업연관데이터 DashBoard") for industrial input-output (I/O) analysis: ingesting an I/O table, allowing the user to edit sectors, computing the Leontief inverse and forward/backward linkages, and extracting / analyzing an industry network.

Where the code lives:

- `app.py` — the entire UI flow inside `main()`. Linear top-to-bottom: each stage gates the next via `st.session_state` keys (`df` → `df_editing` → `df_edited` → `df_for_leontief` → `threshold` / `res_method_b`). Stages render only when their predecessor key exists. The module-level `render_centrality_tabs(cents)` helper renders the 6 centrality sub-tabs and is reused at all four network blocks (tn/tbn/n/bn); it takes the raw tuple returned by `calculate_network_centralities`.
- `iolib/` — the backend package (all data manipulation, Leontief math, network extraction, centralities, batch-edit replay, download helpers). Split into `loading`, `batch_upload`, `editing`, `leontief`, `network`, `download`. `app.py` still does `from functions import *`; `functions.py` is now a thin shim that re-exports `iolib`, so any name in `iolib/__init__.py`'s `__all__` is callable in `app.py` without an explicit import. New code should `from iolib import ...` directly.
- `preprocessing.py` — per-mode upload parsing; imports `load_data, get_mid_ID_idx` from `iolib`.

### Mode → I/O table layout

The radio at the top of `main()` selects how the uploaded Excel is parsed:

| Mode | `first_idx` | `subplus_edit` | Notes |
|---|---|---|---|
| Korea (2010~2020) | (6, 2) | False | |
| Japan (2000~2020) | (6, 2) | False | |
| Korea (1990~2005) | (5, 2) | True | drops last row of `df` |
| Manual | 0 | False | |
| US(Summary 2000~2024) | (6, 2) | False | `미국_사용표_총거래/국산_한국레이아웃_2000_2024.xlsx`, n=71, year sheets 2000~2020 + 2023~2024; 총거래표 → `df`, 국산거래표 → `df_local`; Used→부가가치계, Other→기타투입 행; see CLAUDE.md |
| US(Sector 2000~2024) | (6, 2) | False | `..._대분류_2000_2024.xlsx`, n=15 (Summary를 15부문 집계); 그 외 위와 동일 |

`first_idx` = `(row, col)` where the numeric block starts. The two rows/cols immediately before it are labels (`number_of_label = 2`: code + name). `mid_ID_idx`, computed by `get_mid_ID_idx`, is the boundary between intermediate transactions and final-demand / value-added regions. Together they partition the table into four labeled sub-matrices: **X** (top-left intermediate), **R** (bottom-left value-added), **C** (top-right final demand), and the bottom-right is unused.

The uploader expects a **two-sheet** workbook: sheet 0 is the global table, sheet 1 is the local/domestic counterpart. Both are loaded into `df` / `df_local` and edits are applied to both in parallel.

### Editing pipeline (and why `edit_ops` exists)

User edits live in `st.session_state['df_editing']`. Each operation is appended to `st.session_state['edit_ops']` as a typed dict:

- `insert_sector` — `insert_row_and_col(...)` adds a new code/name row+column.
- `transfer` — `transfer_to_new_sector(...)` moves `alpha` fraction of one sector's row+column into another's.
- `remove_zero` — `remove_zero_series(...)` drops all-zero rows and their paired columns; the *positions* are saved in the op so replay deletes the same indices.
- `reduce_negative` — `reduce_negative_values(...)` halves negatives and pushes the delta into the last row.
- `batch_apply` — applies an uploaded Excel/ZIP of `from, to, to_name, alpha` rows via `apply_batch_edit(...)`. ZIP uploads are fuzzy-matched against the original filename (see `_pick_excel_from_zip`) with cp437→utf-8/cp949 filename repair for Korean names.

When the user clicks "전체 적용", `replay_edit_ops_on_df(...)` replays the same `edit_ops` against `df_editing_local` so the local sheet stays consistent. **Any new editing operation must be added in three places: the button in `app.py`, an entry pushed into `edit_ops`, and a corresponding branch in `replay_edit_ops_on_df`.** `mid_ID_idx` must also be updated by every op that changes the matrix dimensions, or downstream slicing breaks.

### Leontief & metrics block

After "전체 적용", the app computes:

1. **Input-coefficient matrix A** = `X / normalization_denominator` (column-normalized).
2. **Leontief inverse L** = `(I − A)^-1` via `np.linalg.inv`. `build_leontief_outputs` does this for the local sheet; the global sheet is computed inline in `app.py`.
3. **FL / BL** — row sums and column sums of L, each divided by their mean (so 1.0 = average).
4. **GDP / value-added effects** — `g = V·L·y`, `m_v = v·L_local`, and W = V·L·diag(y), from which `g1 = W·1`, `g2 = 1·W`, `g3 = diag(W)`.

A self-check warns if mean of row/col sums of L is not ≈ 1 or if any L entry falls outside [-0.1, 2] / any diagonal < 1.

### Network extraction (Section 2)

Two mutually-exclusive paths produce `final_network_matrix`:

- **Method A** — `threshold_count(...)` plots survival ratio vs threshold, finds the distance-minimization optimum, then **back-tracks down** until no node is isolated. The user can override the suggested threshold and click Apply.
- **Method B** — `extract_network_leontief(...)` iterates partial sums `B^t = Σ A^k`, zeroes diagonals + entries ≤ ε, and stops when the change ratio of nonzero count drops below δ. Returns `B_c^{t-1}` (weighted) and `Q^{t-1}` (binary).

Switching methods clears `threshold` / `threshold_cal` via the `on_change` callback so stale results don't render.

From the chosen matrix the app builds `G_n` (weighted DiGraph) and `G_bn` (binary DiGraph), then `calculate_network_centralities(...)` returns degree / betweenness / closeness / eigenvector / HITS, and Kim-style structural-hole metrics (`calculate_kim_metrics`: Burt's constraint plus a redundancy-based efficiency that differs from `calculate_standard_metrics`). Each centrality dataframe and the matrices are individually downloadable from the sidebar; `_gather_all_dataframes()` at the end bundles every cached result into a single ZIP.

### Things that bite

- `donwload_data` (in `iolib/download.py`) and `download_multiple_csvs_as_zip` — `donwload` is misspelled but consistent across the codebase; do not "fix" without grepping all call sites.
- `@st.cache_data` is applied to `load_data`, `convert_df`, `get_submatrix_withlabel` (`iolib/loading.py`), `make_zip_bytes` (`iolib/download.py`), `threshold_count`, and `extract_network_leontief` (`iolib/network.py`). Changing their signatures or returning mutable objects that callers mutate will produce stale results.
- Edit operations mix string codes/names and numbers in one DataFrame, so any **newly created column must be object dtype** — pandas ≥ 3.0 raises `TypeError` when a string is written into a float column. `insert_row_and_col` uses `_nan_object_column` for exactly this reason; keep that pattern for any new editing op.
- All UI strings, comments, and dataframe column labels are Korean — preserve them when editing.
- The table contains string headers inside the numeric region; `find_string_values` + `replace_string_with_na` + `slice_until_first_non_nan_row` (defined inline in `main`) clean these on upload before `pd.to_numeric`.
- `ids_simbol` is `{code: [name, ...]}` and is shared between global and local replays unless `copy_ids=True` is passed to `replay_edit_ops_on_df`.
