"""배포 원자료의 목록과 파일/ZIP 읽기. 화면 프레임워크에 의존하지 않는다."""

import io
from pathlib import Path
import zipfile
from .config import get_data_dir

JAPAN_DATA_DIRNAME = "일본_산업연관표_연도별_자료"


def japan_files(folder: Path):
    root = folder.resolve()
    return [
        path
        for path in sorted(folder.rglob("*"))
        if path.is_file()
        and not path.name.startswith((".", "~$"))
        and path.resolve().is_relative_to(root)
    ]


def _japan_path(relative=""):
    root = (get_data_dir() / JAPAN_DATA_DIRNAME).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or any(
        part.startswith((".", "~$")) for part in Path(relative).parts
    ):
        raise ValueError("선택한 원자료 경로가 유효하지 않습니다.")
    return root, target


def japan_file_bytes(relative):
    _, target = _japan_path(relative)
    if not target.is_file():
        raise ValueError("선택한 원자료 파일을 찾을 수 없습니다.")
    return target.read_bytes()


def japan_zip_bytes(folder_name="전체"):
    root, target = _japan_path("" if folder_name == "전체" else folder_name)
    if not target.is_dir():
        raise ValueError("선택한 원자료 폴더를 찾을 수 없습니다.")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in japan_files(target):
            archive.write(path, path.relative_to(root.parent))
    return buffer.getvalue()


def japan_resource_options():
    root, _ = _japan_path()
    if not root.is_dir():
        return []
    options = [{"label": "일본 자료 전체 ZIP", "value": "zip:전체"}]
    options += [
        {"label": f"{path.name} ZIP", "value": f"zip:{path.name}"}
        for path in sorted(root.iterdir())
        if path.is_dir() and not path.name.startswith(".")
    ]
    options += [
        {"label": path.name, "value": "file:" + str(path.relative_to(root))}
        for path in japan_files(root)
    ]
    return options
