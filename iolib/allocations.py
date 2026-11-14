"""산업별 백분율 입력을 검증된 일괄 편집 계획으로 변환한다."""

from decimal import Decimal, InvalidOperation
import pandas as pd
from .editing import _canon_code, validate_batch_edit


def sector_catalog(editor):
    row, col = editor.params.first_idx
    frame = editor.total.iloc[row : editor.mid[0], col - 2 : col].copy()
    frame.columns = ["code", "name"]
    frame["code"] = frame["code"].map(_canon_code)
    frame["name"] = frame["name"].astype(str)
    if frame["code"].eq("").any() or frame["code"].duplicated().any():
        raise ValueError("산업 코드는 비어 있지 않고 서로 달라야 합니다.")
    return frame.reset_index(drop=True)


def percentage_records(catalog, percentages, target_code, target_name):
    """빈 셀·0%는 제외한다. 모든 검증을 통과한 뒤에만 편집에 전달한다."""
    names = dict(zip(catalog["code"], catalog["name"]))
    rows = []
    for code, value in percentages.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        try:
            percent = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(
                f"{names.get(code, code)}: 비율은 0~100 사이의 숫자로 입력하세요."
            ) from exc
        if not percent.is_finite() or not 0 <= percent <= 100:
            raise ValueError(f"{names.get(code, code)}: 비율은 0~100% 범위여야 합니다.")
        if percent == 0:
            continue
        if code not in names:
            raise ValueError(f"원자료에서 산업 코드 {code}를 찾을 수 없습니다.")
        rows.append(
            {
                "from": code,
                "to": _canon_code(target_code),
                "to_name": str(target_name or "").strip(),
                "alpha": float(percent / 100),
            }
        )
    target_code = _canon_code(target_code)
    if not target_code or not str(target_name or "").strip():
        raise ValueError("새 산업의 코드와 이름을 입력하세요.")
    if target_code in names:
        raise ValueError(
            f"이미 있는 산업 코드입니다: {target_code}. 새 코드를 입력하거나 ‘기타 편집’에서 기존 산업 간 이동을 사용하세요."
        )
    if not rows:
        return []
    return validate_batch_edit(pd.DataFrame(rows)).to_dict("records")


def percentage_preview(records, catalog):
    names = dict(zip(catalog["code"], catalog["name"]))
    return pd.DataFrame(
        [
            {
                "산업 코드": r["from"],
                "출발 산업": names[r["from"]],
                "이동 비율 (%)": float(Decimal(str(r["alpha"])) * 100),
                "남는 비율 (%)": float((1 - Decimal(str(r["alpha"]))) * 100),
                "대상 산업": f"{r['to_name']} ({r['to']})",
            }
            for r in records
        ]
    )


def percentages_from_records(records, catalog):
    """파일의 단일 대상 계획을 입력표로 가져온다. 여러 대상은 별도 일괄 편집용."""
    frame = validate_batch_edit(pd.DataFrame(records))
    targets = frame[["to", "to_name"]].drop_duplicates()
    if len(targets) != 1:
        raise ValueError("입력표에는 하나의 대상 산업만 가져올 수 있습니다.")
    if frame["from"].duplicated().any():
        raise ValueError("같은 출발 산업이 여러 번 들어 있습니다.")
    target_code, target_name = targets.iloc[0].tolist()
    values = dict.fromkeys(catalog["code"], 0.0)
    values.update(
        {
            r["from"]: float(Decimal(str(r["alpha"])) * 100)
            for r in frame.to_dict("records")
        }
    )
    percentage_records(catalog, values, target_code, target_name)
    return values, target_code, target_name
