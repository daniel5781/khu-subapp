"""설치된 대시보드 실행: khu-subapp --data-dir /path/to/data."""

import argparse
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="산업연관데이터 대시보드 실행")
    parser.add_argument(
        "--data-dir", type=Path, help="미국 워크북과 일본 자료가 있는 폴더"
    )
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    if args.data_dir:
        if not args.data_dir.is_dir():
            parser.error("--data-dir은 존재하는 폴더여야 합니다.")
        os.environ["KHU_SUBAPP_DATA_DIR"] = str(args.data_dir.resolve())
    if not 1 <= args.port <= 65535:
        parser.error("--port는 1~65535 사이여야 합니다.")
    try:
        from streamlit.web import cli
    except ImportError:
        parser.error(
            '대시보드 의존성이 필요합니다: pip install "khu-subapp[dashboard]"'
        )
    sys.argv = [
        "streamlit",
        "run",
        str(Path(__file__).with_name("app.py")),
        "--server.address",
        args.host,
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
    ]
    return cli.main()
