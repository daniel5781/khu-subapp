"""Dash 콜백이 호출하는 작업 흐름. UI 컴포넌트와 무관하게 테스트한다."""

from dataclasses import replace
import hashlib
import numpy as np
from iolib import preprocessing
from iolib.session import EditingSession
from iolib.analysis import labeled_matrix
from iolib.network import analyze_threshold, extract_series_network
from iolib.network_analysis import analyze_network
from iolib.batch_upload import (
    inspect_batch_upload,
    prepare_batch_preview,
    infer_input_year,
)
from iolib.exports import collect_result_frames
from .models import Workspace, BatchPreview


def load_source(state, *, mode, source=None, year=None, first_idx=None):
    params = preprocessing.get_mode_params(mode)
    if mode == "Manual":
        if first_idx is None or any(not isinstance(x, int) or x < 2 for x in first_idx):
            raise ValueError("숫자 시작 행·열은 3 이상의 정수여야 합니다.")
        params = replace(params, first_idx=tuple(first_idx))
    if mode.startswith("US"):
        if year is None:
            raise ValueError("분석할 미국 자료의 연도를 선택하세요.")
        source = source if source is not None else preprocessing.us_use_file_path(mode)
    if source is None:
        raise ValueError("먼저 산업연관표 Excel 파일을 선택하세요.")
    loaded = preprocessing.load_workbook(
        source, mode, us_year=year, first_idx=first_idx if mode == "Manual" else None
    )
    return Workspace(
        revision=state.revision,
        editor=EditingSession.from_loaded(loaded, params),
        source_name=getattr(source, "name", str(source)),
        mode=mode,
        year=year,
    )


def require_editor(state):
    if state.editor is None:
        raise ValueError("원자료를 먼저 불러오세요.")
    return state.editor


def edit(state, operation):
    editor = require_editor(state).apply(operation)
    return replace(
        state,
        editor=editor,
        analysis=None,
        threshold=None,
        series=None,
        network=None,
        network_frames={},
        network_settings=None,
        batch=None,
    )


def analyze(state):
    result = require_editor(state).analyze()
    return replace(
        state,
        analysis=result,
        threshold=analyze_threshold(result.total.inverse),
        series=None,
        network=None,
        network_frames={},
        network_settings=None,
    )


def clear_network(state):
    return replace(
        state, network=None, series=None, network_frames={}, network_settings=None
    )


def extract_network(
    state, *, method, threshold=None, epsilon=1e-4, delta=0.01, max_iter=100
):
    if state.analysis is None:
        raise ValueError("경제지표 계산을 먼저 실행하세요.")
    matrix = state.analysis.total.inverse
    template = state.analysis.frames["leontief_inverse"]
    series, extras = None, {}
    if method == "A":
        if (
            threshold is None
            or not np.isfinite(float(threshold))
            or float(threshold) < 0
        ):
            raise ValueError("임계값은 0 이상의 유한한 숫자여야 합니다.")
        threshold = float(threshold)
        final = matrix.copy()
        final[final <= threshold] = 0
        np.fill_diagonal(final, 0)
        mask = (final > 0).astype(int)
        editor = require_editor(state)
        row, col = editor.params.first_idx
        extras = {
            "filtered_transactions": labeled_matrix(
                template,
                editor.total.iloc[row : editor.mid[0], col : editor.mid[1]].to_numpy(
                    float
                )
                * mask,
            ),
            "filtered_coefficients": labeled_matrix(
                template, state.analysis.total.coefficients * mask
            ),
        }
    elif method == "B":
        if (
            max_iter is None
            or isinstance(max_iter, bool)
            or int(max_iter) != max_iter
            or not 1 <= max_iter <= 500
        ):
            raise ValueError("최대 반복 횟수는 1~500의 정수여야 합니다.")
        series = extract_series_network(
            matrix, float(epsilon), float(delta), int(max_iter)
        )
        final = series.weighted
    else:
        raise ValueError("네트워크 추출 방식을 선택하세요.")
    result = analyze_network(final, template)
    return replace(
        state,
        network=result,
        series=series,
        network_frames={**result.frames, **extras},
        network_settings=(method, threshold, epsilon, delta, max_iter),
    )


def batch_signature(upload, year, code, name):
    return (
        hashlib.sha256(upload.getvalue()).hexdigest(),
        year,
        str(code).strip(),
        str(name).strip(),
    )


def prepare_batch(state, upload, *, year=None, target_code="6000", target_name="TMT"):
    editor = require_editor(state)
    if upload is None:
        raise ValueError("일괄 편집 파일을 선택하세요.")
    stem = state.source_name.rsplit(".", 1)[0]
    meta = inspect_batch_upload(upload, stem)
    if meta["format"] == "year_ratio":
        available = meta["years"]
        if year not in available:
            inferred = infer_input_year(editor.original.df, state.source_name)
            year = inferred if inferred in available else None
        if year is None:
            preview = BatchPreview(
                [], meta, batch_signature(upload, None, target_code, target_name), []
            )
            return replace(state, batch=preview)
    else:
        year = None
    codes = editor.total.iloc[
        editor.params.first_idx[0] : editor.mid[0], editor.params.first_idx[1] - 2
    ].tolist()
    frame, meta, _, summaries = prepare_batch_preview(
        upload,
        stem,
        year=year,
        target_code=target_code,
        target_name=target_name,
        source_codes=codes,
    )
    preview = BatchPreview(
        frame.to_dict("records"),
        meta,
        batch_signature(upload, year, target_code, target_name),
        summaries,
    )
    return replace(state, batch=preview)


def apply_batch(state, upload, *, year=None, target_code="6000", target_name="TMT"):
    preview = state.batch
    if preview is None or not preview.records or upload is None:
        raise ValueError("미리보기를 먼저 생성하세요.")
    if preview.metadata["format"] != "year_ratio":
        year = None
    if batch_signature(upload, year, target_code, target_name) != preview.signature:
        raise ValueError(
            "파일·연도·대상 값이 변경됐습니다. 미리보기를 다시 생성하세요."
        )
    identity = lambda records: tuple(
        sorted((r["from"], r["to"], float(r["alpha"])) for r in records)
    )
    if preview.metadata["format"] == "year_ratio" and any(
        op["type"] == "batch_apply"
        and identity(op["batch_records"]) == identity(preview.records)
        for op in require_editor(state).operations
    ):
        raise ValueError("같은 연도별 비율이 이미 적용됐습니다.")
    return edit(state, {"type": "batch_apply", "batch_records": preview.records})


def export_frames(state):
    return collect_result_frames(state.editor, state.analysis, state.network_frames)
