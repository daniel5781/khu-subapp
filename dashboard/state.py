"""화면 상태 수명: 원자료 변경 → 편집·분석 초기화, 편집 → 분석 초기화."""

import hashlib
from pathlib import Path

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


def collect_exports(editor, analysis=None, network_frames=None):
    from iolib.analysis import partition_table

    if editor is None:
        return {}
    original = editor.original
    frames = {"uploaded_df": original.df, "uploaded_df_local": original.df_local}
    frames.update(
        {
            f"uploaded_{name}": frame
            for name, frame in partition_table(
                original.df, editor.params.first_idx, original.mid_ID_idx
            ).items()
        }
    )
    if analysis is not None:
        frames.update(analysis.frames)
        frames.update(network_frames or {})
    return frames
