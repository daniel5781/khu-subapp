"""Dash 업로드 메시지를 검증하고 파일 객체로 변환한다."""

import base64
import binascii
from io import BytesIO
from pathlib import PurePath

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class Upload(BytesIO):
    def __init__(self, data, name):
        super().__init__(data)
        self.name = name


def decode_upload(contents, filename, *, batch=False):
    if contents is None:
        return None
    if not isinstance(filename, str) or not filename:
        raise ValueError("업로드 파일 이름이 없습니다.")
    suffix = PurePath(filename).suffix.lower()
    allowed = {".xls", ".xlsx", ".zip"} if batch else {".xls", ".xlsx"}
    if suffix not in allowed:
        raise ValueError("Excel 또는 일괄 편집용 ZIP 파일을 선택하세요.")
    if not isinstance(contents, str) or "," not in contents:
        raise ValueError("올바른 업로드 데이터가 아닙니다.")
    header, encoded = contents.split(",", 1)
    if ";base64" not in header or len(encoded) > (MAX_UPLOAD_BYTES + 2) // 3 * 4:
        raise ValueError("파일 형식이 올바르지 않거나 50MB 업로드 한도를 초과했습니다.")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(
            "업로드 데이터를 해석할 수 없습니다. 파일을 다시 선택하세요."
        ) from exc
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("비어 있거나 50MB를 초과한 파일입니다.")
    return Upload(data, PurePath(filename).name)
