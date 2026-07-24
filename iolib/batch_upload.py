"""엑셀/ZIP 일괄편집 파일 업로드 처리.

`from, to, to_name, alpha` 컬럼을 가진 엑셀(또는 그것을 담은 ZIP)을 읽어
검증·미리보기 텍스트를 만든다. ZIP 내부 파일명이 cp437 로 깨져 들어오는
한글 파일명을 복구(`_fix_zip_name`)하고 원본 업로드 파일명과 매칭한다.
"""
import io
import zipfile
import unicodedata

import pandas as pd

from .editing import _canon_code


def _nfc(s: str) -> str:
    return unicodedata.normalize('NFC', s)


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
        info_by_clean[clean_no_ext] = info   # ✅ ZipInfo 저장

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


def prepare_batch_preview(alpha_file, original_filename_no_ext: str):
    """
    1) ZIP이면 매칭 후 batch_df 로드 / 엑셀이면 바로 로드
    2) 텍스트 미리보기 라인 생성
    return: (batch_df, meta, preview_lines, summary_lines)
    """
    meta = {
        "uploaded": alpha_file.name,
        "kind": "zip" if alpha_file.name.endswith(".zip") else "excel",
        "matched_file": None,
        "match_mode": None
    }

    # --- 1단계: 파일 확보 (업로드 즉시 실행) ---
    if alpha_file.name.endswith(".zip"):
        zip_bytes = io.BytesIO(alpha_file.getvalue())
        with zipfile.ZipFile(zip_bytes, 'r') as z:
            matched_clean, matched_info, mode = _pick_excel_from_zip(z, original_filename_no_ext)
            if mode == "no_excel":
                raise ValueError("ZIP 내부에 엑셀 파일이 없습니다.")

            meta["matched_file"] = matched_clean
            meta["match_mode"] = mode

            # ✅ 문자열 경로가 아니라 ZipInfo로 open
            with z.open(matched_info) as f:
                batch_df = pd.read_excel(
                f,
                dtype=str  # <─ 전체를 문자열로 받음 (숫자로 오인 금지)
            )

    else:
        meta["matched_file"] = alpha_file.name
        meta["match_mode"] = "no_match_needed"
        batch_df = pd.read_excel(
            alpha_file,
            dtype=str  # <─ 여기서도 동일
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

    # alpha가 NaN인 행 제거
    df = df.dropna(subset=["alpha"])

    # --- 2단계: 텍스트 미리보기 생성 ---
    preview_lines = []
    for _, r in df.iterrows():
        nm = r["to_name"] if r["to_name"] else "-"
        preview_lines.append(f"{r['from']} -> {r['to']}({nm}) : {float(r['alpha'])*100:.4f}%")

    # from별 합/잔여
    summary_lines = []
    grouped = df.groupby("from")["alpha"].sum()
    for origin_code, total_alpha in grouped.items():
        remaining = 1.0 - float(total_alpha)
        summary_lines.append(
            f"[from={origin_code}] 이동합={float(total_alpha)*100:.4f}%, 잔여={remaining*100:.4f}%"
        )

    return df, meta, preview_lines, summary_lines
