"""설치 후 khu-dash 또는 python -m dash_app으로 실행한다."""

import argparse
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description="KHU 산업연관 분석 · Dash 버전")
    parser.add_argument("--data-dir", type=Path, help="미국·일본 원자료 폴더")
    parser.add_argument("--cache-dir", type=Path, help="사용자별 임시 작업 저장 폴더")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8050)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port는 1~65535 사이여야 합니다.")
    if args.data_dir:
        if not args.data_dir.is_dir():
            parser.error("--data-dir은 존재하는 폴더여야 합니다.")
        os.environ["KHU_SUBAPP_DATA_DIR"] = str(args.data_dir.resolve())
    try:
        from waitress import serve
        from .app import create_app
    except ImportError:
        parser.error('Dash 의존성이 필요합니다: pip install "khu-subapp[dash]"')
    temporary = (
        tempfile.TemporaryDirectory(prefix="khu-dash-")
        if args.cache_dir is None
        else None
    )
    app = create_app(cache_dir=args.cache_dir or temporary.name)
    print(f"KHU Dash: http://{args.host}:{args.port}", flush=True)
    try:
        serve(
            app.server,
            host=args.host,
            port=args.port,
            threads=4,
            max_request_body_size=72 * 1024 * 1024,
        )
    finally:
        app.workspace_store.close()
        if temporary:
            temporary.cleanup()
