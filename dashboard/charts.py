"""공통 표·산점도·네트워크 표시."""

import io
import pandas as pd
import networkx as nx
import streamlit as st
from .tables import show_table
from .fonts import korean_font
from matplotlib.figure import Figure


def scatter(frame, x_column, y_column, title, key, highlights=(), reference=None):
    x = pd.to_numeric(frame[x_column], errors="coerce")
    y = pd.to_numeric(frame[y_column], errors="coerce")
    names = frame.iloc[:, 1].astype(str)
    selected = names.isin(highlights)
    fig = Figure(figsize=(10, 8))
    ax = fig.subplots()
    ax.scatter(x[~selected], y[~selected], facecolors="none", edgecolors="gray", s=80)
    if selected.any():
        ax.scatter(x[selected], y[selected], color="red", s=100)
        for xx, yy, label in zip(x[selected], y[selected], names[selected]):
            ax.text(
                xx, yy, label, fontsize=12, ha="right", fontproperties=korean_font()
            )
    ax.axvline(
        x.mean() if reference is None else reference, color="gray", linestyle="--"
    )
    ax.axhline(
        y.mean() if reference is None else reference, color="gray", linestyle="--"
    )
    ax.set(xlabel=str(x_column), ylabel=str(y_column), title=title)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    st.pyplot(fig)
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight")
    st.download_button(
        f"{title} 이미지 다운로드",
        buffer.getvalue(),
        f"{key}.png",
        "image/png",
        key=f"plot_{key}",
    )


def render_centralities(cents, prefix, highlights):
    tabs = st.tabs(
        [
            "Degree Centrality",
            "Betweenness Centrality",
            "Closeness Centrality",
            "Eigenvector Centrality",
            "Hub & Authority",
            "constraints&efficiencies",
        ]
    )
    for index, (tab, frame) in enumerate(zip(tabs, cents[:6])):
        with tab:
            show_table(frame)
            numeric = frame.iloc[:, 2:].apply(pd.to_numeric, errors="coerce")
            show_table(pd.DataFrame({"Mean": numeric.mean(), "Std": numeric.std()}))
            if index == 4:
                scatter(
                    frame,
                    "HITS Hubs",
                    "HITS Authorities",
                    f"Hub & Authority ({prefix})",
                    f"{prefix}_hits",
                    highlights,
                )
            if index == 5:
                scatter(
                    frame,
                    "Constraint",
                    "Efficiency",
                    f"Structural Hole ({prefix})",
                    f"{prefix}_structural",
                    highlights,
                )


def render_graph(graph, template):
    fig = Figure(figsize=(8, 6))
    ax = fig.subplots()
    positions = nx.spring_layout(graph, seed=42, weight=None)
    labels = dict(enumerate(template.iloc[2:, 0].astype(str)))
    nx.draw_networkx(
        graph, pos=positions, labels=labels, node_size=300, font_size=8, ax=ax
    )
    ax.set_title("Binary Directed Network")
    ax.axis("off")
    st.pyplot(fig)
