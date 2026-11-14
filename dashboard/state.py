"""화면 상태 수명: 원자료 변경 → 편집·분석 초기화, 편집 → 분석 초기화."""

import hashlib
from pathlib import Path
from iolib.exports import collect_result_frames as collect_exports

__all__ = ["collect_exports", "invalidate_results", "reset_source", "source_revision"]

RESULT_KEYS = (
    "analysis",
    "network_result",
    "network_frames",
    "network_signature",
    "threshold",
    "threshold_input",
)


def invalidate_results(state):
    for key in RESULT_KEYS:
        state.pop(key, None)


def reset_source(state, signature):
    if state.get("source_signature") == signature:
        return False
    invalidate_results(state)
    state.pop("editor", None)
    for key in (
        "ratio_year",
        "ratio_target",
        "ratio_name",
        "threshold_input",
        "new_code",
        "new_name",
        "origin_code",
        "target_code",
        "transfer_alpha",
    ):
        state.pop(key, None)
    state["source_signature"] = signature
    return True


def source_revision(source):
    if hasattr(source, "getvalue"):
        return hashlib.sha256(source.getvalue()).hexdigest()
    if source is None:
        return None
    path = Path(source)
    stat = path.stat()
    return str(path.resolve()), stat.st_mtime_ns, stat.st_size
