"""Dash 이벤트 어댑터. 편집·계산은 services, 저장은 WorkspaceStore에 위임한다."""

from pathlib import PurePath
from zipfile import BadZipFile
from openpyxl.utils.exceptions import InvalidFileException
from xlrd.biffh import XLRDError
from dash import Input, Output, State, ctx, dcc, no_update
from dash.exceptions import PreventUpdate
from iolib.preprocessing import available_us_years
from iolib.exports import make_zip_bytes
from iolib.loading import convert_df
from iolib.resources import (
    japan_resource_options,
    japan_file_bytes,
    japan_zip_bytes,
    JAPAN_DATA_DIRNAME,
)
from . import services, views
from .models import Workspace
from .store import ExpiredWorkspace, StaleWorkspace
from .tables import grid_payload
from .uploads import decode_upload

USER_ERRORS = (
    ValueError,
    TypeError,
    KeyError,
    OSError,
    BadZipFile,
    ArithmeticError,
    SyntaxError,
    InvalidFileException,
    XLRDError,
)


def register_callbacks(app, store):
    def commit(pointer, transform, success):
        try:
            updated = store.update(pointer, transform)
            return updated, views.message(success, "success")
        except StaleWorkspace as exc:
            return store.latest(pointer), views.message(str(exc))
        except USER_ERRORS as exc:
            return no_update, views.message(str(exc), "error")

    def read(pointer):
        try:
            return store.read(pointer)
        except ExpiredWorkspace:
            return Workspace()

    @app.callback(
        Output("year", "options"),
        Output("year", "value"),
        Output("year", "disabled"),
        Output("manual-fields", "style"),
        Input("mode", "value"),
    )
    def mode_options(mode):
        years = available_us_years(mode) if mode and mode.startswith("US") else []
        return (
            [{"label": str(y), "value": y} for y in years],
            years[-1] if years else None,
            not bool(years),
            {"display": "grid" if mode == "Manual" else "none"},
        )

    @app.callback(
        Output("source-file-label", "children"),
        Output("batch-file-label", "children"),
        Input("source-upload", "filename"),
        Input("batch-upload", "filename"),
    )
    def filenames(source, batch):
        return source or "선택된 파일 없음", batch or "선택된 파일 없음"

    @app.callback(
        Output("source-upload", "contents"),
        Output("source-upload", "filename"),
        Input("clear-upload", "n_clicks"),
        prevent_initial_call=True,
    )
    def clear_upload(_):
        return None, None

    @app.callback(
        *[
            Output(f"pane-{name}", "style")
            for name in ("edit", "economic", "network", "export")
        ],
        Input("navigation", "value"),
    )
    def navigate(active):
        return [
            {"display": "block" if active == name else "none"}
            for name in ("edit", "economic", "network", "export")
        ]

    @app.callback(
        Output("workspace", "data", allow_duplicate=True),
        Output("notice", "children", allow_duplicate=True),
        Input("mode", "value"),
        Input("year", "value"),
        Input("manual-row", "value"),
        Input("manual-col", "value"),
        Input("source-upload", "contents"),
        Input("load-source", "n_clicks"),
        Input("reset-workspace", "n_clicks"),
        State("source-upload", "filename"),
        State("workspace", "data"),
        prevent_initial_call=True,
    )
    def source_action(mode, year, row, col, contents, _load, _reset, filename, pointer):
        trigger = ctx.triggered_id
        if trigger != "load-source":
            return commit(
                pointer,
                lambda s: Workspace(revision=s.revision),
                "원자료 설정이 변경됐습니다. 데이터를 불러오세요.",
            )

        def load(state):
            first_idx = None
            if mode == "Manual":
                if any(
                    v is None or isinstance(v, bool) or int(v) != v for v in (row, col)
                ):
                    raise ValueError("숫자 시작 행·열에 정수를 입력하세요.")
                first_idx = (int(row) - 1, int(col) - 1)
            return services.load_source(
                state,
                mode=mode,
                year=year,
                first_idx=first_idx,
                source=decode_upload(contents, filename),
            )

        return commit(pointer, load, "원자료를 불러왔습니다.")

    @app.callback(
        Output("workspace", "data", allow_duplicate=True),
        Output("notice", "children", allow_duplicate=True),
        Output("threshold", "value"),
        *[
            Input(id, "n_clicks")
            for id in (
                "insert-sector",
                "transfer-sector",
                "remove-zero",
                "reduce-negative",
                "run-analysis",
            )
        ],
        *[
            State(id, "value")
            for id in ("new-code", "new-name", "from-code", "to-code", "transfer-ratio")
        ],
        State("workspace", "data"),
        prevent_initial_call=True,
    )
    def edit_action(
        _insert,
        _transfer,
        _zero,
        _negative,
        _analyze,
        code,
        name,
        from_code,
        to_code,
        ratio,
        pointer,
    ):
        trigger = ctx.triggered_id
        if trigger == "run-analysis":
            updated, notice = commit(
                pointer,
                services.analyze,
                "경제지표를 계산했습니다. 경제지표·네트워크 탭에서 확인하세요.",
            )
            state = read(updated) if updated is not no_update else None
            return (
                updated,
                notice,
                state.threshold.threshold if state and state.threshold else no_update,
            )
        operations = {
            "insert-sector": {
                "type": "insert_sector",
                "code": code or "",
                "name": name or "",
            },
            "transfer-sector": {
                "type": "transfer",
                "from": from_code or "",
                "to": to_code or "",
                "alpha": ratio,
            },
            "remove-zero": {"type": "remove_zero"},
            "reduce-negative": {"type": "reduce_negative"},
        }
        updated, notice = commit(
            pointer,
            lambda s: services.edit(s, operations[trigger]),
            "편집을 적용했습니다. 경제지표를 다시 계산하세요.",
        )
        return updated, notice, no_update

    @app.callback(
        Output("workspace", "data", allow_duplicate=True),
        Output("notice", "children", allow_duplicate=True),
        Input("preview-batch", "n_clicks"),
        Input("apply-batch", "n_clicks"),
        State("batch-upload", "contents"),
        State("batch-upload", "filename"),
        State("batch-year", "value"),
        State("batch-code", "value"),
        State("batch-name", "value"),
        State("workspace", "data"),
        prevent_initial_call=True,
    )
    def batch_action(_preview, _apply, contents, filename, year, code, name, pointer):
        applying = ctx.triggered_id == "apply-batch"

        def apply(state):
            upload = decode_upload(contents, filename, batch=True)
            function = services.apply_batch if applying else services.prepare_batch
            return function(
                state, upload, year=year, target_code=code, target_name=name
            )

        return commit(
            pointer,
            apply,
            "일괄 편집을 적용했습니다."
            if applying
            else "미리보기를 확인하세요. 연도 목록이 나타나면 선택 후 다시 생성하세요.",
        )

    @app.callback(
        Output("workspace", "data", allow_duplicate=True),
        Output("notice", "children", allow_duplicate=True),
        Input("run-network", "n_clicks"),
        *[
            Input(id, "value")
            for id in ("network-method", "threshold", "epsilon", "delta", "max-iter")
        ],
        State("workspace", "data"),
        prevent_initial_call=True,
    )
    def network_action(_run, method, threshold, epsilon, delta, max_iter, pointer):
        if ctx.triggered_id != "run-network":
            state = read(pointer)
            if state.network_settings == (method, threshold, epsilon, delta, max_iter):
                raise PreventUpdate
            updated, notice = commit(
                pointer,
                services.clear_network,
                "네트워크 설정이 변경됐습니다. 다시 추출하세요.",
            )
            return updated, notice if state.network is not None else no_update
        return commit(
            pointer,
            lambda s: services.extract_network(
                s,
                method=method,
                threshold=threshold,
                epsilon=epsilon,
                delta=delta,
                max_iter=max_iter,
            ),
            "네트워크와 중심성을 계산했습니다.",
        )

    @app.callback(
        *[
            Output(id, prop)
            for id, prop in [
                ("source-summary", "children"),
                ("metrics", "children"),
                ("editor-grid", "rowData"),
                ("editor-grid", "columnDefs"),
                ("result-table", "options"),
                ("result-table", "value"),
                ("export-table", "options"),
                ("export-table", "value"),
                ("edit-log", "children"),
                ("highlight", "options"),
                ("highlight", "value"),
                ("batch-grid", "rowData"),
                ("batch-grid", "columnDefs"),
                ("batch-summary", "children"),
                ("batch-year", "options"),
                ("batch-year", "value"),
                ("analysis-summary", "children"),
                ("network-summary", "children"),
            ]
        ],
        Input("workspace", "data"),
        *[
            State(id, "value")
            for id in ("result-table", "export-table", "highlight", "batch-year")
        ],
    )
    def render_workspace(pointer, result_name, export_name, highlights, batch_year):
        return views.workspace_view(
            read(pointer), result_name, export_name, highlights, batch_year
        )

    @app.callback(
        Output("result-grid", "rowData"),
        Output("result-grid", "columnDefs"),
        Input("result-table", "value"),
        Input("workspace", "data"),
    )
    def result_table(name, pointer):
        return grid_payload(services.export_frames(read(pointer)).get(name), name)

    @app.callback(
        Output("centrality-grid", "rowData"),
        Output("centrality-grid", "columnDefs"),
        Input("centrality-table", "value"),
        Input("network-kind", "value"),
        Input("workspace", "data"),
    )
    def centrality_table(name, kind, pointer):
        key = f"{kind}_{name}"
        return grid_payload(read(pointer).network_frames.get(key), key)

    @app.callback(
        Output("editor-grid", "dashGridOptions"),
        Output("result-grid", "dashGridOptions"),
        Input("editor-search", "value"),
        Input("result-search", "value"),
    )
    def search(editor_text, result_text):
        return [
            {
                "theme": "legacy",
                "pagination": True,
                "paginationPageSize": 25,
                "paginationPageSizeSelector": [25, 50, 100],
                "rowHeight": 34,
                "quickFilterText": text or "",
            }
            for text in (editor_text, result_text)
        ]

    @app.callback(
        *[
            Output(id, "figure")
            for id in (
                "fl-bl",
                "gdp-chart",
                "threshold-chart",
                "series-chart",
                "network-chart",
                "hits-chart",
                "holes-chart",
            )
        ],
        Input("workspace", "data"),
        Input("highlight", "value"),
        Input("network-kind", "value"),
        Input("navigation", "value"),
    )
    def charts(pointer, highlights, kind, _navigation):
        return views.chart_view(read(pointer), highlights, kind)

    @app.callback(
        Output("file-download", "data"),
        Output("notice", "children", allow_duplicate=True),
        Input("download-zip", "n_clicks"),
        Input("download-csv", "n_clicks"),
        Input("download-raw", "n_clicks"),
        State("export-table", "value"),
        State("raw-resource", "value"),
        State("workspace", "data"),
        prevent_initial_call=True,
    )
    def download(_zip, _csv, _raw, name, resource, pointer):
        try:
            trigger = ctx.triggered_id
            if trigger == "download-raw":
                if resource not in {item["value"] for item in japan_resource_options()}:
                    raise ValueError("제공된 원자료를 선택하세요.")
                kind, path = resource.split(":", 1)
                data = (
                    japan_zip_bytes(path) if kind == "zip" else japan_file_bytes(path)
                )
                filename = (
                    f"{JAPAN_DATA_DIRNAME}_{path}.zip"
                    if kind == "zip"
                    else PurePath(path).name
                )
            else:
                frames = services.export_frames(store.read(pointer))
                if not frames:
                    raise ValueError(
                        "다운로드할 자료가 없습니다. 원자료를 먼저 불러오세요."
                    )
                if trigger == "download-zip":
                    data, filename = make_zip_bytes(frames), "khu-analysis.zip"
                else:
                    if name not in frames:
                        raise ValueError("다운로드할 결과를 선택하세요.")
                    data, filename = convert_df(frames[name]), f"{name}.csv"
            return dcc.send_bytes(data, filename), views.message(
                "다운로드 파일을 준비했습니다.", "success"
            )
        except USER_ERRORS as exc:
            return no_update, views.message(str(exc), "error")
