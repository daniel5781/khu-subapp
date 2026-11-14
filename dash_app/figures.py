"""Plotly 차트 생성. 수치 계산·세션 갱신은 수행하지 않는다."""

import numpy as np
import pandas as pd
import networkx as nx
import plotly.graph_objects as go
from plotly.subplots import make_subplots

TEAL = "#087f8c"
RED = "#df6a4f"


def style(figure, title="", height=400):
    figure.update_layout(
        title={"text": title, "font": {"size": 17}},
        template="plotly_white",
        font={
            "family": "Arial, Apple SD Gothic Neo, Malgun Gothic, sans-serif",
            "color": "#24364b",
        },
        margin={"l": 50, "r": 25, "t": 55, "b": 45},
        height=height,
        paper_bgcolor="white",
        plot_bgcolor="white",
        hovermode="closest",
    )
    return figure


def empty_figure(message="분석을 실행하면 그래프가 표시됩니다."):
    figure = go.Figure()
    figure.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font={"color": "#7c8a9b"},
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return style(figure)


def scatter(frame, x_column, y_column, title, *, highlights=(), reference=None):
    figure = go.Figure()
    names = frame.iloc[:, 1].astype(str)
    codes = frame.iloc[:, 0].astype(str)
    x = pd.to_numeric(frame[x_column], errors="coerce")
    y = pd.to_numeric(frame[y_column], errors="coerce")
    selected = names.isin(highlights)
    for flag, label, color in ((False, "전체 산업", TEAL), (True, "선택 산업", RED)):
        mask = selected == flag
        if not mask.any():
            continue
        figure.add_trace(
            go.Scatter(
                x=x[mask].tolist(),
                y=y[mask].tolist(),
                mode="markers",
                name=label,
                text=names[mask].tolist(),
                customdata=codes[mask].tolist(),
                marker={"color": color, "size": 12 if flag else 9, "opacity": 0.85},
                hovertemplate=f"%{{text}} (%{{customdata}})<br>{x_column}: %{{x:.6g}}<br>{y_column}: %{{y:.6g}}<extra></extra>",
            )
        )
    for axis, values in (("x", x), ("y", y)):
        level = reference if reference is not None else float(values.mean())
        if np.isfinite(level):
            if axis == "x":
                figure.add_vline(x=level, line_dash="dash", line_color="#bac4ce")
            else:
                figure.add_hline(y=level, line_dash="dash", line_color="#bac4ce")
    figure.update_xaxes(title=str(x_column))
    figure.update_yaxes(title=str(y_column))
    return style(figure, title)


def fl_bl(analysis, highlights=()):
    if analysis is None:
        return empty_figure()
    frame = analysis.frames["FL_BL"].iloc[1:].rename(columns={"2": "FL", "3": "BL"})
    return scatter(
        frame, "FL", "BL", "전·후방 연쇄효과", highlights=highlights, reference=1
    )


def gdp(analysis):
    if analysis is None:
        return empty_figure()
    frame = analysis.frames["GDP"].iloc[1:].copy()
    frame["2"] = pd.to_numeric(frame["2"])
    frame = frame.nlargest(20, "2").sort_values("2")
    figure = go.Figure(
        go.Bar(
            x=frame["2"].tolist(),
            y=frame.iloc[:, 1].astype(str).tolist(),
            orientation="h",
            marker_color=TEAL,
            hovertemplate="%{y}<br>GDP 유발액: %{x:,.4f}<extra></extra>",
        )
    )
    figure.update_yaxes(automargin=True)
    return style(figure, "GDP 유발액 상위 20개 산업", 480)


def threshold_figure(result):
    if result is None:
        return empty_figure("경제지표 계산 후 임계값 진단을 확인할 수 있습니다.")
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(
            x=result.thresholds.tolist(),
            y=result.survival.tolist(),
            name="생존율",
            line_color=TEAL,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=result.slope_thresholds.tolist(),
            y=result.slope_changes.tolist(),
            name="변화율",
            line_color="#e1a541",
            opacity=0.6,
        ),
        secondary_y=True,
    )
    figure.add_vline(
        x=result.threshold,
        line_dash="dash",
        line_color=RED,
        annotation_text=f"제안 {result.threshold:.4f}",
    )
    figure.update_xaxes(title="임계값")
    figure.update_yaxes(title_text="생존율", secondary_y=False)
    figure.update_yaxes(title_text="기울기 변화", secondary_y=True)
    return style(figure, "Method A · 임계값 진단")


def series_figure(result):
    if result is None:
        return empty_figure("Method B를 적용하면 반복 과정이 표시됩니다.")
    info = result.info
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    figure.add_trace(
        go.Scatter(
            x=info["iterations"],
            y=info["densities"],
            name="연결 수",
            mode="lines+markers",
            line_color=TEAL,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=info["iterations"],
            y=info["ratios"],
            name="변화율",
            mode="lines+markers",
            line_color=RED,
        ),
        secondary_y=True,
    )
    return style(figure, f"Method B · {info['final_t']}회 반복")


def centrality_figure(network, kind, metric, highlights=()):
    if network is None:
        return empty_figure("네트워크를 추출하면 중심성 그래프가 표시됩니다.")
    frames = (
        network.weighted_centralities
        if kind == "weighted"
        else network.binary_centralities
    )
    if metric == "hits":
        return scatter(
            frames[4],
            "HITS Hubs",
            "HITS Authorities",
            "Hub · Authority",
            highlights=highlights,
        )
    return scatter(
        frames[5], "Constraint", "Efficiency", "구조적 공백", highlights=highlights
    )


def network_figure(network, template, kind="weighted"):
    if network is None:
        return empty_figure("네트워크를 추출하면 산업 간 연결이 표시됩니다.")
    graph = network.weighted_graph if kind == "weighted" else network.binary_graph
    positions = nx.spring_layout(graph, seed=42, weight=None)
    names = template.iloc[2:, 1].astype(str).tolist()
    codes = template.iloc[2:, 0].astype(str).tolist()
    edges = sorted(
        graph.edges(data=True), key=lambda item: item[2].get("weight", 1), reverse=True
    )
    visible = edges[:1200]
    x, y = [], []
    for start, end, _ in visible:
        x += [float(positions[start][0]), float(positions[end][0]), None]
        y += [float(positions[start][1]), float(positions[end][1]), None]
    figure = go.Figure(
        go.Scatter(
            x=x,
            y=y,
            mode="lines",
            line={"color": "#ccd5df", "width": 0.7},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    if len(visible) <= 150:
        for start, end, _ in visible:
            figure.add_annotation(
                x=float(positions[end][0]),
                y=float(positions[end][1]),
                ax=float(positions[start][0]),
                ay=float(positions[start][1]),
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=0.7,
                arrowwidth=0.7,
                arrowcolor="#b7c4d1",
                standoff=7,
            )
    figure.add_trace(
        go.Scatter(
            x=[float(positions[n][0]) for n in graph],
            y=[float(positions[n][1]) for n in graph],
            mode="markers",
            marker={
                "size": 13,
                "color": [float(graph.in_degree(n, weight="weight")) for n in graph],
                "colorscale": "Teal",
                "showscale": True,
            },
            text=[
                f"{names[n]} ({codes[n]})<br>유입 연결 {graph.in_degree(n)} · 유출 연결 {graph.out_degree(n)}"
                for n in graph
            ],
            hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        )
    )
    figure.update_xaxes(visible=False)
    figure.update_yaxes(visible=False)
    return style(
        figure, f"산업 네트워크 · {len(graph)}개 산업 / {len(edges)}개 연결", 500
    )
