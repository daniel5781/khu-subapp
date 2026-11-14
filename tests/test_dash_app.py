"""Dash의 실제 HTTP 콜백, 사용자 격리와 업로드→다운로드 흐름."""

import base64
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
import zipfile
import networkx as nx
import numpy as np
import pandas as pd
from plotly.utils import PlotlyJSONEncoder
from dash_app.app import create_app
from dash_app.models import Workspace
from dash_app.store import WorkspaceStore, StaleWorkspace, ExpiredWorkspace
from dash_app.uploads import Upload, decode_upload
from dash_app import services, views
from dash_app.tables import grid_payload
from fixtures import loaded_tables, workbook_table
from test_workbooks import excel_upload

REPO = Path(__file__).resolve().parents[1]
MODE = "Korea(2010~2020)"


def source_upload():
    raw = loaded_tables()
    return Upload(
        excel_upload({"총거래표": raw.df, "국산거래표": raw.df_local}).getvalue(),
        "2024.xlsx",
    )


def data_uri(data):
    return "data:application/octet-stream;base64," + base64.b64encode(data).decode()


def batch_upload(yearly=False):
    frame = (
        pd.DataFrame(
            {"대분류/년도": ["산업 0"], "2024년": ["25%(S0)"], "2023년": ["10%(S0)"]}
        )
        if yearly
        else pd.DataFrame(
            [{"from": "S0", "to": "NEW", "to_name": "신규 산업", "alpha": 0.25}]
        )
    )
    buffer = BytesIO()
    frame.to_excel(buffer, index=False)
    return Upload(buffer.getvalue(), "ratio.xlsx")


class DashClient:
    """브라우저와 같은 Dash POST 프로토콜로 콜백을 호출한다."""

    def __init__(self, app):
        self.app = app
        self.client = app.server.test_client()
        self.props = {}
        self.layout = self.client.get("/_dash-layout").get_json()
        self._collect(self.layout)
        self.callbacks = {
            value["callback"].__name__: (key, value)
            for key, value in app.callback_map.items()
        }

    def _collect(self, value):
        if isinstance(value, dict):
            props = value.get("props", {})
            if "id" in props:
                self.props[props["id"]] = dict(props)
            for child in value.values():
                self._collect(child)
        elif isinstance(value, list):
            for child in value:
                self._collect(child)

    def set(self, **values):
        for field, value in values.items():
            id, prop = field.rsplit(".", 1)
            self.props[id][prop] = value

    @property
    def pointer(self):
        return self.props["workspace"]["data"]

    def call(self, name, changed, **values):
        self.set(**values)
        key, meta = self.callbacks[name]
        output = meta["output"]
        serialize = lambda item: {
            "id": item.component_id,
            "property": item.component_property,
        }
        outputs = (
            [serialize(item) for item in output]
            if isinstance(output, list)
            else serialize(output)
        )
        payload = {"output": key, "outputs": outputs, "changedPropIds": [changed]}
        for target in ("inputs", "state"):
            payload[target] = [
                {**spec, "value": self.props[spec["id"]].get(spec["property"])}
                for spec in meta[target]
            ]
        response = self.client.post("/_dash-update-component", json=payload)
        if response.status_code == 204:
            return {}
        if response.status_code != 200:
            raise AssertionError(response.get_data(as_text=True))
        data = response.get_json()["response"]
        for id, props in data.items():
            self.props[id].update(props)
        return data


class DashHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(cache_dir=self.directory.name)
        self.addCleanup(self.app.workspace_store.close)
        self.ui = DashClient(self.app)

    def state(self):
        return self.app.workspace_store.read(self.ui.pointer)

    def load(self):
        self.ui.set(
            **{
                "source-upload.contents": data_uri(source_upload().getvalue()),
                "source-upload.filename": "2024.xlsx",
            }
        )
        self.ui.call("source_action", "load-source.n_clicks")
        self.assertIsNotNone(self.state().editor)

    def analyze(self):
        self.ui.call("edit_action", "run-analysis.n_clicks")
        self.assertIsNotNone(self.state().analysis)

    def render(self):
        result = self.ui.call("render_workspace", "workspace.data")
        self.ui.call("result_table", "result-table.value")
        self.ui.call("charts", "workspace.data")
        return result

    def test_start_assets_and_acyclic_callback_graph(self):
        for path in ("/", "/healthz", "/_dash-dependencies", "/assets/styles.css"):
            with self.ui.client.get(path) as response:
                self.assertEqual(response.status_code, 200, path)
        self.assertEqual(set(self.ui.pointer), {"token", "revision"})
        self.render()
        self.assertEqual(self.ui.props["editor-grid"]["rowData"], [])
        graph = nx.DiGraph()
        for callback in self.app.callback_map.values():
            outputs = callback["output"]
            if not isinstance(outputs, list):
                outputs = [outputs]
            for source in callback["inputs"]:
                for target in outputs:
                    graph.add_edge(f"{source['id']}.{source['property']}", str(target))
        self.assertTrue(nx.is_directed_acyclic_graph(graph))
        self.ui.call("navigate", "navigation.value", **{"navigation.value": "network"})
        self.assertEqual(self.ui.props["pane-network"]["style"], {"display": "block"})
        self.assertEqual(self.ui.props["pane-edit"]["style"], {"display": "none"})

    def test_upload_edit_analysis_methods_download_and_invalidation(self):
        self.load()
        original = self.state().editor.total.copy()
        self.ui.call(
            "edit_action",
            "insert-sector.n_clicks",
            **{"new-code.value": "NEW", "new-name.value": "신규 산업"},
        )
        self.assertEqual(self.state().editor.mid, (9, 5))
        self.ui.call(
            "edit_action",
            "transfer-sector.n_clicks",
            **{
                "from-code.value": "S0",
                "to-code.value": "NEW",
                "transfer-ratio.value": 0.25,
            },
        )
        self.assertEqual(len(self.state().editor.operations), 2)
        self.analyze()
        inverse = self.state().analysis.total.inverse.copy()
        self.render()
        self.assertGreater(len(self.ui.props["result-grid"]["rowData"]), 0)
        self.assertEqual(
            self.ui.props["threshold"]["value"], self.state().threshold.threshold
        )
        for name, frame in services.export_frames(self.state()).items():
            rows, columns = grid_payload(frame, name)
            self.assertEqual(
                len(columns),
                len(frame.columns) if isinstance(frame, pd.DataFrame) else 2,
            )
            json.dumps(rows, allow_nan=False)
        self.ui.call(
            "network_action", "run-network.n_clicks", **{"threshold.value": 999.0}
        )
        self.assertEqual(self.state().network.weighted_graph.number_of_edges(), 0)
        self.render()
        self.ui.call("centrality_table", "centrality-table.value")
        self.assertEqual(len(self.ui.props["centrality-grid"]["rowData"]), 3)
        self.ui.call(
            "network_action", "network-method.value", **{"network-method.value": "B"}
        )
        self.assertIsNone(self.state().network)
        self.ui.call("network_action", "run-network.n_clicks")
        self.assertIsNotNone(self.state().series)
        self.assertIn("binary_hits", self.state().network_frames)
        self.render()
        np.testing.assert_array_equal(self.state().analysis.total.inverse, inverse)
        self.ui.call("download", "download-zip.n_clicks")
        download = self.ui.props["file-download"]["data"]
        self.assertTrue(download["base64"])
        with zipfile.ZipFile(BytesIO(base64.b64decode(download["content"]))) as archive:
            self.assertIn("GDP.csv", archive.namelist())
            self.assertIn("binary_hits.csv", archive.namelist())
            self.assertTrue(archive.read("GDP.csv").startswith(b"\xef\xbb\xbf"))
        self.ui.call(
            "download", "download-csv.n_clicks", **{"export-table.value": "GDP"}
        )
        self.assertEqual(self.ui.props["file-download"]["data"]["filename"], "GDP.csv")
        self.ui.call(
            "edit_action",
            "insert-sector.n_clicks",
            **{"new-code.value": "NEXT", "new-name.value": "추가 산업"},
        )
        self.assertIsNone(self.state().analysis)
        self.assertIsNone(self.state().network)
        self.render()
        self.assertNotIn("GDP", services.export_frames(self.state()))
        self.assertEqual(
            services.export_frames(self.state())["edited_df"].shape[0],
            original.shape[0] + 2,
        )
        self.ui.call(
            "source_action",
            "source-upload.contents",
            **{"source-upload.contents": data_uri(b"changed")},
        )
        self.assertIsNone(self.state().editor)
        self.render()

    def test_invalid_input_preserves_state_and_users_are_isolated(self):
        self.load()
        before = self.ui.pointer.copy()
        self.ui.call(
            "edit_action",
            "transfer-sector.n_clicks",
            **{
                "from-code.value": "missing",
                "to-code.value": "S1",
                "transfer-ratio.value": 0.2,
            },
        )
        self.assertEqual(self.ui.pointer, before)
        self.assertIn(
            "error", self.ui.props["notice"]["children"]["props"]["className"]
        )
        second = DashClient(self.app)
        self.assertNotEqual(second.pointer["token"], self.ui.pointer["token"])
        self.assertIsNone(self.app.workspace_store.read(second.pointer).editor)
        self.ui.call("source_action", "reset-workspace.n_clicks")
        self.assertIsNone(self.state().editor)
        self.ui.call(
            "source_action",
            "load-source.n_clicks",
            **{"source-upload.contents": data_uri(b"bad workbook")},
        )
        self.assertIsNone(self.state().editor)
        self.assertIn(
            "error", self.ui.props["notice"]["children"]["props"]["className"]
        )
        self.load()

    def test_corrupted_excel_xml_is_a_user_error(self):
        buffer = BytesIO()
        with (
            zipfile.ZipFile(BytesIO(source_upload().getvalue())) as source,
            zipfile.ZipFile(buffer, "w") as target,
        ):
            for item in source.infolist():
                target.writestr(
                    item,
                    b"<broken"
                    if item.filename == "xl/workbook.xml"
                    else source.read(item),
                )
        self.ui.call(
            "source_action",
            "load-source.n_clicks",
            **{
                "source-upload.contents": data_uri(buffer.getvalue()),
                "source-upload.filename": "broken.xlsx",
            },
        )
        self.assertIsNone(self.state().editor)
        self.assertIn(
            "error", self.ui.props["notice"]["children"]["props"]["className"]
        )
        self.load()

    def test_batch_preview_and_apply_use_same_file_and_parameters(self):
        self.load()
        self.ui.call(
            "batch_action",
            "preview-batch.n_clicks",
            **{
                "batch-upload.contents": data_uri(batch_upload(True).getvalue()),
                "batch-upload.filename": "ratio.xlsx",
            },
        )
        self.assertEqual(len(self.state().batch.records), 1)
        self.render()
        self.assertEqual(self.ui.props["batch-year"]["value"], 2024)
        self.assertEqual(
            self.ui.props["batch-grid"]["columnDefs"][0]["headerName"], "from"
        )
        pointer = self.ui.pointer.copy()
        self.ui.call(
            "batch_action", "apply-batch.n_clicks", **{"batch-code.value": "OTHER"}
        )
        self.assertEqual(self.ui.pointer, pointer)
        self.ui.call(
            "batch_action", "apply-batch.n_clicks", **{"batch-code.value": "6000"}
        )
        self.assertIsNone(self.state().batch)
        self.assertEqual(len(self.state().editor.operations), 1)
        self.analyze()

    def test_mode_and_manual_controls(self):
        self.ui.call("mode_options", "mode.value", **{"mode.value": "Manual"})
        self.assertEqual(self.ui.props["manual-fields"]["style"], {"display": "grid"})
        table, mid = workbook_table(first_idx=(3, 2))
        self.ui.call(
            "source_action",
            "load-source.n_clicks",
            **{
                "manual-row.value": 4,
                "manual-col.value": 3,
                "source-upload.contents": data_uri(
                    excel_upload({"총거래표": table, "국산거래표": table}).getvalue()
                ),
                "source-upload.filename": "manual.xlsx",
            },
        )
        self.assertEqual(self.state().editor.mid, mid)
        self.analyze()
        self.ui.call(
            "search", "editor-search.value", **{"editor-search.value": "산업 0"}
        )
        self.assertEqual(
            self.ui.props["editor-grid"]["dashGridOptions"]["quickFilterText"], "산업 0"
        )

    def test_us_modes_use_available_year_and_shipped_workbooks(self):
        with patch.dict(os.environ, {"KHU_SUBAPP_DATA_DIR": str(REPO)}):
            for level, count in (("Summary", 71), ("Sector", 15)):
                mode = f"US({level} 2000~2024)"
                self.ui.call("mode_options", "mode.value", **{"mode.value": mode})
                self.assertIn(
                    self.ui.props["year"]["value"],
                    [o["value"] for o in self.ui.props["year"]["options"]],
                )
                self.ui.call("source_action", "load-source.n_clicks")
                self.assertEqual(self.state().editor.mid[0] - 6, count)
                self.analyze()
                self.render()
                self.assertEqual(
                    self.state().analysis.total.inverse.shape, (count, count)
                )

    def test_raw_download_and_inflight_request_invalidation(self):
        from iolib.resources import JAPAN_DATA_DIRNAME

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"KHU_SUBAPP_DATA_DIR": directory}),
        ):
            folder = Path(directory) / JAPAN_DATA_DIRNAME / "2024"
            folder.mkdir(parents=True)
            (folder / "sample.xlsx").write_bytes(source_upload().getvalue())
            self.ui.call(
                "download",
                "download-raw.n_clicks",
                **{"raw-resource.value": "zip:2024"},
            )
            data = self.ui.props["file-download"]["data"]
            with zipfile.ZipFile(BytesIO(base64.b64decode(data["content"]))) as archive:
                self.assertEqual(len(archive.namelist()), 1)
                self.assertTrue(archive.namelist()[0].endswith("/2024/sample.xlsx"))
            self.ui.call(
                "download",
                "download-raw.n_clicks",
                **{"raw-resource.value": "file:../outside.xlsx"},
            )
            self.assertIn(
                "error", self.ui.props["notice"]["children"]["props"]["className"]
            )
        # 아직 결과가 없는 계산 중에도 설정 변경은 기존 revision을 만료시킨다.
        pointer = self.ui.pointer.copy()
        self.ui.call("source_action", "mode.value", **{"mode.value": "Manual"})
        with self.assertRaises(StaleWorkspace):
            self.app.workspace_store.update(pointer, lambda state: state)
        pointer = self.ui.pointer.copy()
        self.ui.call("network_action", "epsilon.value", **{"epsilon.value": 0.1})
        with self.assertRaises(StaleWorkspace):
            self.app.workspace_store.update(pointer, lambda state: state)


class DashServiceTests(unittest.TestCase):
    def load(self):
        return services.load_source(Workspace(), mode=MODE, source=source_upload())

    def test_repeated_analysis_and_failed_operation_are_atomic(self):
        original = self.load()
        with self.assertRaises(ValueError):
            services.edit(
                original, {"type": "transfer", "from": "S0", "to": "S1", "alpha": 2}
            )
        self.assertEqual(original.editor.operations, ())
        analyzed = services.analyze(original)
        again = services.analyze(analyzed)
        np.testing.assert_array_equal(
            analyzed.analysis.total.inverse, again.analysis.total.inverse
        )
        state = services.extract_network(
            analyzed, method="B", epsilon=1e-4, delta=0.01, max_iter=100
        )
        figures = views.chart_view(state, [], "binary")
        self.assertEqual(len(figures), 7)
        json.dumps(figures, cls=PlotlyJSONEncoder)
        with self.assertRaises(ValueError):
            services.extract_network(analyzed, method="A", threshold=float("nan"))
        with self.assertRaises(ValueError):
            services.extract_network(analyzed, method="B", max_iter=1.5)

    def test_batch_duplicate_year_and_changed_payload_are_rejected(self):
        yearly = batch_upload(True)
        state = services.prepare_batch(self.load(), yearly)
        state = services.apply_batch(state, yearly, year=2024)
        state = services.prepare_batch(state, yearly, year=2024)
        with self.assertRaisesRegex(ValueError, "이미 적용"):
            services.apply_batch(state, yearly, year=2024)
        standard_upload = batch_upload()
        standard = services.prepare_batch(self.load(), standard_upload)
        applied = services.apply_batch(standard, standard_upload)
        self.assertEqual(applied.editor.mid, (9, 5))
        with self.assertRaises(ValueError):
            services.apply_batch(standard, batch_upload(True))

    def test_upload_validation_and_numeric_grid(self):
        self.assertIsNone(decode_upload(None, None))
        for contents, filename in [
            ("bad", "a.xlsx"),
            (data_uri(b"a"), "a.exe"),
            ("data:base64,invalid%%", "a.xlsx"),
            (data_uri(b""), "a.xlsx"),
        ]:
            with self.assertRaises(ValueError):
                decode_upload(contents, filename)
        with patch("dash_app.uploads.MAX_UPLOAD_BYTES", 2):
            with self.assertRaises(ValueError):
                decode_upload(data_uri(b"123"), "a.xlsx")
        frame = pd.DataFrame(
            {"a": [np.nan, np.inf, np.int64(3)], "b": [None, "산업", pd.NA]}
        )
        rows, columns = grid_payload(frame)
        json.dumps(rows, allow_nan=False)
        self.assertEqual(columns[0]["headerName"], "a")
        rows, columns = grid_payload(pd.Series([1.0, 2.0]))
        self.assertEqual([c["headerName"] for c in columns], ["산업 위치", "값"])

    def test_import_and_app_creation_do_not_need_streamlit_or_matplotlib(self):
        script = "import sys,tempfile; sys.modules['streamlit']=None; sys.modules['matplotlib']=None; from dash_app.app import create_app\nwith tempfile.TemporaryDirectory() as d:\n app=create_app(cache_dir=d); assert app.server.test_client().get('/_dash-layout').status_code==200; app.workspace_store.close()"
        subprocess.run(
            [sys.executable, "-c", script], cwd=REPO, check=True, capture_output=True
        )


class WorkspaceStoreTests(unittest.TestCase):
    def test_stale_parallel_updates_commit_only_once_and_failures_roll_back(self):
        with tempfile.TemporaryDirectory() as directory:
            first = WorkspaceStore(directory)
            second = WorkspaceStore(directory)
            self.addCleanup(first.close)
            self.addCleanup(second.close)
            pointer = first.create()
            barrier = Barrier(2)

            def transform(state):
                barrier.wait(timeout=5)
                return replace(state, source_name="updated")

            def update(store):
                try:
                    return store.update(pointer, transform)
                except StaleWorkspace:
                    return None

            with ThreadPoolExecutor(2) as pool:
                results = list(pool.map(update, [first, second]))
            self.assertEqual(sum(result is not None for result in results), 1)
            self.assertEqual(first.read(pointer).revision, 1)
            with self.assertRaises(StaleWorkspace):
                first.update(pointer, lambda state: state)
            latest = first.latest(pointer)

            def fail(state):
                raise ValueError("bad input")

            with self.assertRaises(ValueError):
                first.update(latest, fail)
            self.assertEqual(first.latest(pointer), latest)
            with self.assertRaises(ExpiredWorkspace):
                first.read({"token": "../invalid"})
            first.cache.delete(first._key(pointer["token"]))
            with self.assertRaises(ExpiredWorkspace):
                second.read(pointer)
