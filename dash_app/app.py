"""독립 Dash 애플리케이션 팩토리."""

from pathlib import Path
import tempfile
from dash import Dash
from .callbacks import register_callbacks
from .layout import build_layout
from .store import WorkspaceStore


def create_app(*, cache_dir=None):
    store = WorkspaceStore(cache_dir or tempfile.mkdtemp(prefix="khu-dash-"))
    app = Dash(
        __name__,
        title="KHU · 산업연관 분석",
        update_title="계산 중…",
        assets_folder=str(Path(__file__).with_name("assets")),
    )
    app.server.config["MAX_CONTENT_LENGTH"] = 72 * 1024 * 1024
    app.layout = lambda: build_layout(store.create())
    app.workspace_store = store
    register_callbacks(app, store)

    @app.server.get("/healthz")
    def health():
        return {"status": "ok", "framework": "dash"}

    return app
