"""편집 화면의 초안, 적용, 실행 취소. Streamlit 위젯과 독립적으로 검증한다."""

from dataclasses import dataclass, replace
from uuid import uuid4
import unicodedata
import pandas as pd
from iolib.session import EditingSession
from iolib.allocations import (
    sector_catalog,
    percentage_records,
    percentages_from_records,
)
from .state import invalidate_results

HISTORY_LIMIT = 10


@dataclass(frozen=True)
class AlphaDraft:
    base: EditingSession
    percentages: dict
    target_code: str = "6000"
    target_name: str = "TMT"
    applied_percentages: dict | None = None
    applied_target: tuple | None = None

    def records(self):
        return percentage_records(
            sector_catalog(self.base),
            self.percentages,
            self.target_code,
            self.target_name,
        )

    @property
    def dirty(self):
        if self.applied_percentages is None:
            return any(
                value not in (None, "", 0, 0.0) for value in self.percentages.values()
            )
        return (
            self.percentages != self.applied_percentages
            or (self.target_code.strip(), self.target_name.strip())
            != self.applied_target
        )

    def applied_copy(self):
        if self.applied_percentages is None:
            return self
        return replace(
            self,
            percentages=dict(self.applied_percentages),
            target_code=self.applied_target[0],
            target_name=self.applied_target[1],
        )


@dataclass(frozen=True)
class EditSnapshot:
    editor: EditingSession
    draft: AlphaDraft | None


def ensure_draft(state):
    if state.get("alpha_draft") is None:
        editor = state["editor"]
        catalog = sector_catalog(editor)
        existing = set(catalog["code"])
        code = 6000
        while str(code) in existing:
            code += 1
        state["alpha_draft"] = AlphaDraft(
            editor, dict.fromkeys(catalog["code"], 0.0), str(code)
        )
    return state["alpha_draft"]


def invalidate_grid(state):
    for key in ("_alpha_grid_view", "_alpha_grid_seed", "_alpha_grid_key"):
        state.pop(key, None)


def rebuild_alpha_widgets(state):
    invalidate_grid(state)
    state["_alpha_reset_widgets"] = True


def prepare_widgets(state):
    if state.pop("_alpha_reset_widgets", False):
        for key in ("alpha_target_code", "alpha_target_name", "alpha_search"):
            state.pop(key, None)


def grid_seed(state, catalog, search=""):
    # 행 번호로 저장된 편집을 다른 산업에 재사용하지 않도록 검색 시 새 키를 쓴다.
    query = unicodedata.normalize("NFKC", search).strip().casefold()
    mask = catalog.apply(
        lambda row: (
            query
            in unicodedata.normalize("NFKC", f"{row['code']} {row['name']}").casefold()
        ),
        axis=1,
    )
    visible = catalog.loc[mask].copy()
    signature = tuple(visible["code"])
    if state.get("_alpha_grid_view") != signature:
        values = state["alpha_draft"].percentages
        visible["percent"] = pd.Series(
            [values.get(code, 0.0) for code in visible["code"]],
            index=visible.index,
            dtype=float,
        )
        state["_alpha_grid_seed"] = visible.reset_index(drop=True)
        state["_alpha_grid_view"] = signature
        state["_alpha_grid_key"] = "alpha_grid_" + uuid4().hex
    return state["_alpha_grid_seed"].copy(), state["_alpha_grid_key"]


def capture_grid_changes(state, key, seed):
    if key != state.get("_alpha_grid_key") or state.get("alpha_draft") is None:
        return
    values = dict(state["alpha_draft"].percentages)
    values.update(
        {
            row.code: None if pd.isna(row.percent) else row.percent
            for row in seed.itertuples(index=False)
        }
    )
    for position, changes in state.get(key, {}).get("edited_rows", {}).items():
        position = int(position)
        if 0 <= position < len(seed) and "percent" in changes:
            values[seed.iloc[position]["code"]] = changes["percent"]
    state["alpha_draft"] = replace(state["alpha_draft"], percentages=values)


def snapshot(state):
    draft = state.get("alpha_draft")
    return EditSnapshot(state["editor"], draft.applied_copy() if draft else None)


def commit(state, editor, *, draft=None, message="편집을 적용했습니다."):
    state["undo_stack"] = (state.get("undo_stack", []) + [snapshot(state)])[
        -HISTORY_LIMIT:
    ]
    state["redo_stack"] = []
    state["editor"] = editor
    state["alpha_draft"] = draft
    invalidate_results(state)
    rebuild_alpha_widgets(state)
    state["workspace_notice"] = ("success", message)


def apply_operation(state, operation, message="편집을 적용했습니다."):
    editor = state["editor"].apply(operation)
    commit(state, editor, message=message)


def apply_alpha(state):
    draft = ensure_draft(state)
    records = draft.records()
    if not records:
        raise ValueError("한 개 이상의 산업에 0%보다 큰 비율을 입력하세요.")
    if not draft.dirty:
        return False
    # 같은 분리 전 기준표에서 계산하여 비율 수정이 누적 적용되지 않게 한다.
    result = draft.base.apply({"type": "batch_apply", "batch_records": records})
    saved = replace(
        draft,
        applied_percentages=dict(draft.percentages),
        applied_target=(draft.target_code.strip(), draft.target_name.strip()),
    )
    commit(
        state,
        result,
        draft=saved,
        message=f"{len(records)}개 산업의 비율을 {draft.target_name}에 반영했습니다.",
    )
    return True


def import_alpha(state, records):
    draft = ensure_draft(state)
    values, code, name = percentages_from_records(records, sector_catalog(draft.base))
    state["alpha_draft"] = replace(
        draft, percentages=values, target_code=code, target_name=name
    )
    rebuild_alpha_widgets(state)
    state["workspace_notice"] = (
        "info",
        "비율을 입력표로 가져왔습니다. 필요하면 수정한 뒤 적용하세요.",
    )


def remove_alpha_split(state):
    draft = ensure_draft(state)
    if draft.applied_percentages is None:
        return False
    cleared = replace(
        draft,
        percentages=dict.fromkeys(draft.percentages, 0.0),
        applied_percentages=None,
        applied_target=None,
    )
    commit(
        state,
        draft.base,
        draft=cleared,
        message="현재 분리를 해제하고 분리 전 표로 돌아왔습니다.",
    )
    return True


def undo(state):
    if not state.get("undo_stack"):
        return False
    previous = state["undo_stack"][-1]
    state["redo_stack"] = (state.get("redo_stack", []) + [snapshot(state)])[
        -HISTORY_LIMIT:
    ]
    state["undo_stack"] = state["undo_stack"][:-1]
    state["editor"], state["alpha_draft"] = previous.editor, previous.draft
    invalidate_results(state)
    rebuild_alpha_widgets(state)
    state["workspace_notice"] = (
        "info",
        "마지막 편집을 취소했습니다. 경제지표는 다시 계산하세요.",
    )
    return True


def redo(state):
    if not state.get("redo_stack"):
        return False
    following = state["redo_stack"][-1]
    state["undo_stack"] = (state.get("undo_stack", []) + [snapshot(state)])[
        -HISTORY_LIMIT:
    ]
    state["redo_stack"] = state["redo_stack"][:-1]
    state["editor"], state["alpha_draft"] = following.editor, following.draft
    invalidate_results(state)
    rebuild_alpha_widgets(state)
    state["workspace_notice"] = (
        "info",
        "편집을 다시 실행했습니다. 경제지표는 다시 계산하세요.",
    )
    return True


def reset_edits(state):
    editor = state["editor"]
    commit(
        state,
        EditingSession.from_loaded(editor.original, editor.params),
        message="원본 표로 돌아왔습니다. 실행 취소로 이전 편집을 복원할 수 있습니다.",
    )


def calculate(state):
    try:
        result = state["editor"].analyze()
    except (ValueError, TypeError, IndexError, ArithmeticError):
        invalidate_results(state)
        raise
    invalidate_results(state)
    state["analysis"] = result
    state["_next_view"] = "경제지표"
    state["workspace_notice"] = ("success", "현재 편집표의 경제지표 계산을 마쳤습니다.")
