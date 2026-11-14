"""저장된 작업을 화면 표시용 값으로 변환한다."""

from pathlib import Path
import pandas as pd
from dash import html
from . import figures, services
from .tables import grid_payload


def message(text, kind="info"):
    return html.Div(text, className=f"notice {kind}")


def choose(options, current, preferred=None):
    values = [option["value"] for option in options]
    return (
        current
        if current in values
        else preferred
        if preferred in values
        else values[0]
        if values
        else None
    )


def workspace_view(
    state, result_name=None, export_name=None, highlights=None, batch_year=None
):
    editor, analysis = state.editor, state.analysis
    frames = services.export_frames(state)
    options = [{"label": name, "value": name} for name in frames]
    rows, columns = grid_payload(editor.total if editor else None, "editor")
    count = editor.mid[0] - editor.params.first_idx[0] if editor else 0
    stats = analysis.statistics if analysis else {}
    metric_values = [
        ("산업 수", str(count)),
        ("편집 횟수", str(len(editor.operations)) if editor else "0"),
        ("GDP 유발액 합계", f"{stats['GDP_total']:,.2f}" if stats else "—"),
        ("부가가치 유발계수 합계", f"{stats['m_v_total']:,.4f}" if stats else "—"),
    ]
    metrics = [
        html.Div(
            [
                html.Div(label, className="metric-label"),
                html.Div(value, className="metric-value"),
            ],
            className="metric",
        )
        for label, value in metric_values
    ]
    summary = (
        f"{state.mode} · {Path(state.source_name).name}"
        if editor
        else "원자료를 불러오면 분석을 시작할 수 있습니다."
    )
    if editor and state.year is not None:
        summary += f" · {state.year}년"
    highlight_options, defaults = [], []
    if editor:
        row, col = editor.params.first_idx
        for code, name in editor.total.iloc[
            row : editor.mid[0], col - 2 : col
        ].itertuples(index=False, name=None):
            if str(name) not in {o["value"] for o in highlight_options}:
                highlight_options.append(
                    {"label": f"{name} ({code})", "value": str(name)}
                )
        defaults = [str(name) for names in editor.names.values() for name in names]
    valid_names = {o["value"] for o in highlight_options}
    highlights = [
        name
        for name in (highlights if highlights is not None else defaults)
        if name in valid_names
    ]
    preview = state.batch
    batch_rows, batch_columns = grid_payload(
        pd.DataFrame(preview.records) if preview and preview.records else None
    )
    years = preview.metadata.get("years", []) if preview else []
    year_options = [{"label": str(y), "value": y} for y in years]
    year_value = (
        preview.metadata.get("year")
        if preview and preview.records
        else batch_year
        if batch_year in years
        else None
    )
    batch_summary = (
        " · ".join(preview.summaries)
        if preview and preview.records
        else "연도를 선택한 뒤 미리보기를 다시 생성하세요."
        if preview and years
        else "파일을 선택하고 미리보기를 생성하세요."
    )
    analysis_summary = (
        "경제지표 계산이 완료됐습니다. 금액 단위는 원자료의 단위를 따릅니다."
        if analysis
        else "편집 탭에서 ‘경제지표 계산’을 실행하세요."
    )
    network_summary = "네트워크를 아직 추출하지 않았습니다."
    if state.network:
        graph = state.network.weighted_graph
        network_summary = f"Method {state.network_settings[0]} · 산업 {len(graph)}개 · 연결 {graph.number_of_edges()}개"
        if state.series:
            network_summary += (
                " · 연결 수 안정화 완료"
                if state.series.info["converged"]
                else " · 최대 반복 도달 (연결 수 미안정)"
            )
    return (
        summary,
        metrics,
        rows,
        columns,
        options,
        choose(options, result_name, "FL_BL"),
        options,
        choose(options, export_name, "GDP"),
        "\n".join(editor.logs) if editor and editor.logs else "편집 이력이 없습니다.",
        highlight_options,
        highlights,
        batch_rows,
        batch_columns,
        batch_summary,
        year_options,
        year_value,
        analysis_summary,
        network_summary,
    )


def chart_view(state, highlights, kind):
    template = state.analysis.frames["leontief_inverse"] if state.analysis else None
    return (
        figures.fl_bl(state.analysis, highlights or ()),
        figures.gdp(state.analysis),
        figures.threshold_figure(state.threshold),
        figures.series_figure(state.series),
        figures.network_figure(state.network, template, kind),
        figures.centrality_figure(state.network, kind, "hits", highlights or ()),
        figures.centrality_figure(state.network, kind, "holes", highlights or ()),
    )
