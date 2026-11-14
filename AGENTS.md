# Repository guidance

## Run and verify

```bash
python -m pip install -e '.[dashboard,dev]'
streamlit run app.py
ruff check .
python -m unittest discover -s tests -v
python tests/regression_oracle.py --check
python -m build
```

Run the 38-digest oracle after changes to `iolib/` or preprocessing. Do not regenerate
`tests/golden.json` to hide a regression; change it only for an intended numerical
change with an independent test. New numerical behavior also needs exact-value or
invariant tests, since aggregate digests alone do not detect every error.

## Architecture and dependencies

- `app.py` delegates to `dashboard.app.main`; do not put computation there.
- `dashboard/` owns Streamlit, widget forms, caching, state invalidation, charts and downloads.
- `iolib/` is the reusable library. Importing it must not import Streamlit or matplotlib.
- `iolib.preprocessing` owns loading; `config` owns mode/data paths; `us_workbooks` owns BEA conversion.
- `iolib.session.EditingSession` applies operations atomically to total and domestic tables.
- `iolib.leontief` owns matrix normalization/inversion; `analysis` owns economic indicators.
- `iolib.network` extracts matrices; `centrality` and `structural` compute metrics;
  `network_analysis` assembles their shared output.
- `iolib.exports` serializes CSV/ZIP. `plots` imports matplotlib only when explicitly requested.
- Root `functions.py` and `preprocessing.py`, and `iolib.download` retain old public imports.
  New code imports explicit names from the owning module. Private monkeypatches should
  target the owning module, not a compatibility shim.
- `pyproject.toml` defines dependencies, extras, CLI and package discovery. Raw Excel
  datasets are external to wheels. Resolve them with `KHU_SUBAPP_DATA_DIR`, never cwd.
- `new.py` is an unrelated Selenium scraper; do not connect it to the dashboard.

## Data contracts

`first_idx` is a `(row, col)` pair, with code/name labels in the preceding two rows/columns.
`mid` points to the intermediate subtotal row/column, excluded from the industry block.
Mixed label/value DataFrames and inserted columns use object dtype, including on pandas 3.
UI text and industry labels are Korean. Preserve country-specific financial conventions.

Korea selects total/domestic sheets by their Korean names, never using imports as domestic.
Legacy unnamed Korean sheets retain total/domestic order. Japan uses named domestic as-is;
only total/import inputs are subtracted, after row and column code alignment checks.
Legacy unnamed Japan sheets retain total/import order. Domestic tables may lack primary
input rows; their X block suffices because the denominator comes from the total table.
Manual mode accepts the same layout with configurable numeric start coordinates.

US Summary (71) and Sector (15) use the shipped BEA Use total/domestic pairs and common
available year sheets. A total upload replaces only the total workbook. Used is folded into
value-added; Other remains a separate primary-input row. T018 is the common denominator.

## Editing and analysis

Use `EditingSession.apply` for new UI edits. Validate before mutation and retain the old
session if either table fails. Dimension changes update both boundaries. Zero removal
must replay identical positions in both tables. Add new operations to the replay engine
and session/UI, with tests. Batch splitting is row then updated column (`P X P^T`).
The negative reduction function uses an exclusive `mid`; the session must not subtract 1.

Source changes reset editor and results. Edit changes invalidate all derived results.
`analyze()` does not replay edits. Exports use the original boundaries for original data,
and an explicit current result registry; do not collect parent locals from a nested function.

A = X / total output, L = (I - A)^-1, FL/BL normalized row/column sums.
GDP = diag(v) L y; m_v = v L_domestic. Do not duplicate these formulas in the UI.
Method A consistently uses strict `>` and excludes diagonal/zero edges. Method B's legacy
UI input is L, and its convergence is edge-count stabilization, not matrix-series convergence.
Changing to A in the UI would be a separate analytical decision. Graph orientation remains
column j → row i. Weighted shortest paths retain the legacy weight-as-distance convention.
Binary HITS must remove original weights; handle isolated/single-node networks safely.

## Tests and compatibility

Tests use deterministic small workbooks plus repository datasets and Streamlit AppTest.
The optional user Downloads fixture may skip in CI; required repository fixtures must run
in repository checkouts. Never add external files, environment secrets, or generated raw
outputs to package artifacts. `dist/`, virtualenvs and build metadata are ignored by Git.
