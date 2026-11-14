# Project guidance

Read [AGENTS.md](AGENTS.md) for the current architecture, execution commands, data contracts,
editing rules and regression checks. [README.md](README.md) documents the public API and UI.

The former monolithic app and root preprocessing implementation have been replaced by
`dashboard/` and `iolib/`. `app.py`, `functions.py`, and `preprocessing.py` are compatibility
entrypoints. Do not restore old wildcard imports or import-time module reloads.

Preserve BEA Use conventions: Summary 71 / Sector 15; total and domestic workbooks;
Used included in value-added; Other as separate primary input; T018 normalization.
The BEA download/build scripts remain independent of the app. The unrelated `new.py`
Selenium script must not be wired into the dashboard.
