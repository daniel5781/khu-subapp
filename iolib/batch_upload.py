"""엑셀/ZIP 일괄편집 파일 업로드 처리.

`from, to, to_name, alpha` 이전표 또는 `비율%(산업코드)` 연도별 표를 읽어
검증·미리보기 텍스트를 만든다. ZIP 내부 파일명이 cp437 로 깨져 들어오는
한글 파일명을 복구(`_fix_zip_name`)하고 원본 업로드 파일명과 매칭한다.
"""

import io
import re
import zipfile
import unicodedata
from decimal import Decimal

import pandas as pd

from .editing import _canon_code, validate_batch_edit


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _fix_zip_name(name: str) -> str:
    """
    zipfile이 cp437로 잘못 디코딩한 파일명을 복구 시도.
    1) cp437 bytes로 되돌린 뒤
    2) utf-8 / cp949 순으로 decode 시도
    """
    try:
        raw = name.encode("cp437")
    except Exception:
        return name

    for enc in ("utf-8", "cp949"):
        try:
            return raw.decode(enc)
        except Exception:
            pass

    # 최후: cp949로 깨지더라도 replace
    return raw.decode("cp949", errors="replace")


def _pick_excel_from_zip(z: zipfile.ZipFile, original_filename_no_ext: str):
    """ZIP 내부에서 원본 파일명 기반 매칭 -> 실패 시 첫 번째 엑셀 fallback"""

    infos = []
    for info in z.infolist():
        raw = info.filename
        fixed = _nfc(_fix_zip_name(raw)).replace("\\", "/")

        # __MACOSX 제거 + 엑셀만
        if fixed.startswith("__MACOSX") or "/__MACOSX/" in fixed:
            continue
        if not fixed.endswith((".xlsx", ".xls")):
            continue

        infos.append((info, fixed))

    # (표시용) clean name
    clean_names = []
    info_by_clean = {}
    for info, fixed in infos:
        base = fixed.split("/")[-1]
        clean_no_ext = base.rsplit(".", 1)[0]
        clean_names.append(clean_no_ext)
        info_by_clean[clean_no_ext] = info  # ✅ ZipInfo 저장

    # 1) 자동 매칭
    norm_orig = _nfc(original_filename_no_ext)
    for clean in clean_names:
        parts = [x for x in clean.split("_") if x]
        parts = [_nfc(x) for x in parts]
        if parts and all(part in norm_orig for part in parts):
            return clean, info_by_clean[clean], "matched"

    # 2) fallback: 첫 번째 엑셀
    if clean_names:
        clean = clean_names[0]
        return clean, info_by_clean[clean], "fallback_first"

    return None, None, "no_excel"


def _upload_bytes(alpha_file):
    """미리보기 재실행이 업로드 객체의 읽기 위치를 바꾸지 않도록 한다."""
    if hasattr(alpha_file, "getvalue"):
        return alpha_file.getvalue()
    position = alpha_file.tell()
    try:
        alpha_file.seek(0)
        return alpha_file.read()
    finally:
        alpha_file.seek(position)


def _read_batch_upload(alpha_file, original_filename_no_ext):
    filename = str(alpha_file.name)
    is_zip = filename.lower().endswith(".zip")
    meta = {
        "uploaded": filename,
        "kind": "zip" if is_zip else "excel",
        "matched_file": None,
        "match_mode": None,
    }
    contents = _upload_bytes(alpha_file)
    if is_zip:
        zip_bytes = io.BytesIO(contents)
        with zipfile.ZipFile(zip_bytes, "r") as z:
            matched_clean, matched_info, mode = _pick_excel_from_zip(
                z, original_filename_no_ext
            )
            if mode == "no_excel":
                raise ValueError("ZIP 내부에 엑셀 파일이 없습니다.")

            meta["matched_file"] = matched_clean
            meta["match_mode"] = mode

            with z.open(matched_info) as f:
                batch_df = pd.read_excel(f, dtype=str)
    else:
        meta["matched_file"] = filename
        meta["match_mode"] = "no_match_needed"
        batch_df = pd.read_excel(io.BytesIO(contents), dtype=str)
    return batch_df, meta


def _year_columns(batch_df):
    """항목 열 다음의 연속된 연도 열만 읽고 오른쪽 참고 계산은 제외한다."""
    if batch_df.empty and len(batch_df.columns) == 0:
        return {}
    heading = re.sub(r"\s+", "", _nfc(str(batch_df.columns[0])))
    if heading not in {"대분류/년도", "대분류/연도", "산업/년도", "산업/연도"}:
        return {}
    years = {}
    for column in batch_df.columns[1:]:
        label = str(column).strip()
        match = re.fullmatch(r"((?:19|20)\d{2})\s*년?", label)
        if not match:
            # pandas가 중복 헤더에 붙인 '.1'도 애매한 연도로 취급한다.
            if re.fullmatch(r"(?:19|20)\d{2}\s*년?\.\d+", label):
                raise ValueError(f"연도 열이 중복되어 있습니다: {label}")
            break
        year = int(match.group(1))
        if year in years:
            raise ValueError(f"연도 열이 중복되어 있습니다: {year}년")
        years[year] = column
    if not years:
        raise ValueError(
            "연도별 비율표의 두 번째 열부터 연도(예: 2024년)를 입력해 주세요."
        )
    return years


def inspect_batch_upload(alpha_file, original_filename_no_ext: str):
    """표준 이전표/연도별 비율표를 구분하고 선택 가능한 연도를 반환한다."""
    batch_df, meta = _read_batch_upload(alpha_file, original_filename_no_ext)
    years = _year_columns(batch_df)
    meta.update(format="year_ratio" if years else "standard", years=list(years))
    return meta


def _resolve_source_code(code, source_codes):
    if source_codes is None:
        return code
    codes = [_canon_code(value) for value in source_codes]
    exact = [value for value in codes if value == code]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"원본 표에 산업코드 {code}가 중복되어 있습니다.")
    # 숫자 코드의 자릿수만 다른 경우에 한해 실제 표의 코드를 보존한다.
    candidates = (
        [
            value
            for value in codes
            if value.isascii() and value.isdigit() and int(value) == int(code)
        ]
        if code.isascii() and code.isdigit()
        else []
    )
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise ValueError(
            f"산업코드 {code}에 대응하는 원본 코드가 여러 개입니다: {', '.join(candidates)}"
        )
    raise ValueError(
        f"원본 표에서 산업코드 {code}를 찾을 수 없습니다. 적용 연도와 분류를 확인해 주세요."
    )


def _convert_year_ratios(batch_df, years, year, target_code, target_name, source_codes):
    if year not in years:
        available = ", ".join(str(value) for value in years)
        raise ValueError(
            f"비율표의 적용 연도를 선택해 주세요. 사용 가능한 연도: {available}"
        )
    target_code = _canon_code(target_code)
    target_name = "" if target_name is None else str(target_name).strip()
    if not target_code or not target_name:
        raise ValueError("추가할 산업의 코드와 이름을 입력해 주세요.")
    codes = None if source_codes is None else list(source_codes)
    records = []
    seen = set()
    for row_number, (_, row) in enumerate(batch_df.iterrows(), start=2):
        value = row[years[year]]
        if pd.isna(value) or not str(value).strip():
            continue
        match = re.fullmatch(
            r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*%\s*\(\s*([^()]+?)\s*\)\s*",
            str(value),
        )
        if not match:
            raise ValueError(
                f"{year}년 {row_number}행의 비율 형식이 잘못되었습니다: {value}. 예: 20.380%(C09)"
            )
        alpha = float(Decimal(match.group(1)) / 100)
        if not 0 <= alpha <= 1:
            raise ValueError(
                f"{year}년 {row_number}행의 비율은 0% 이상 100% 이하여야 합니다: {value}"
            )
        code = _resolve_source_code(_canon_code(match.group(2)), codes)
        if code in seen:
            raise ValueError(f"{year}년의 산업코드 {code}가 두 번 입력되어 있습니다.")
        if code == target_code:
            raise ValueError(f"이전할 산업코드와 추가할 산업코드가 같습니다: {code}")
        seen.add(code)
        records.append(
            {"from": code, "to": target_code, "to_name": target_name, "alpha": alpha}
        )
    if not records:
        raise ValueError(f"{year}년에 적용할 비율이 없습니다.")
    return pd.DataFrame(records, columns=["from", "to", "to_name", "alpha"])


def prepare_batch_preview(
    alpha_file,
    original_filename_no_ext: str,
    *,
    year=None,
    target_code="6000",
    target_name="TMT",
    source_codes=None,
):
    """표준 이전표 또는 선택 연도의 비율표를 일괄 적용 내역으로 변환한다.

    연도별 비율표의 빈 셀은 이전 대상이 아니다. 값이 있는 셀의 형식이나
    원본 코드가 잘못된 경우에는 일부만 적용하지 않고 미리보기부터 중단한다.
    return: (batch_df, meta, preview_lines, summary_lines)
    """
    batch_df, meta = _read_batch_upload(alpha_file, original_filename_no_ext)
    years = _year_columns(batch_df)
    meta.update(
        format="year_ratio" if years else "standard",
        years=list(years),
        year=year if years else None,
    )
    if years:
        batch_df = _convert_year_ratios(
            batch_df, years, year, target_code, target_name, source_codes
        )

    # --- 검증/정리 ---
    needed_cols = {"from", "to", "to_name", "alpha"}
    if not needed_cols.issubset(batch_df.columns):
        raise ValueError(f"엑셀 파일에 다음 컬럼이 포함되어야 합니다: {needed_cols}")

    df = batch_df.copy()
    # 숫자로만 된 코드가 11 / 11.0 / '11.0' 으로 읽혀도 '11' 로 통일
    df["from"] = df["from"].map(_canon_code)
    df["to"] = df["to"].map(_canon_code)
    df["to_name"] = df["to_name"].astype(str)
    df["to_name"] = df["to_name"].replace("nan", "").fillna("")
    df["alpha"] = pd.to_numeric(df["alpha"], errors="coerce")

    df = validate_batch_edit(df)

    # --- 2단계: 텍스트 미리보기 생성 ---
    preview_lines = []
    for _, r in df.iterrows():
        nm = r["to_name"] if r["to_name"] else "-"
        preview_lines.append(
            f"{r['from']} -> {r['to']}({nm}) : {float(r['alpha']) * 100:.4f}%"
        )

    # from별 합/잔여
    summary_lines = []
    grouped = df.groupby("from")["alpha"].sum()
    for origin_code, total_alpha in grouped.items():
        remaining = 1.0 - float(total_alpha)
        summary_lines.append(
            f"[from={origin_code}] 이동합={float(total_alpha) * 100:.4f}%, 잔여={remaining * 100:.4f}%"
        )

    return df, meta, preview_lines, summary_lines


def infer_input_year(df, source_name=""):
    for row in (1, 0):
        if len(df) > row:
            text = " ".join(str(v) for v in df.iloc[row, :2].dropna())
            years = set(re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", text))
            if len(years) == 1:
                return int(years.pop())
    years = set(re.findall(r"(?<!\d)((?:19|20)\d{2})(?!\d)", source_name))
    return int(years.pop()) if len(years) == 1 else None
