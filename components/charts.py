from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

NEUTRAL_BLUE = "#2457A7"


def line_chart(frame: pd.DataFrame, *, x: str, y: str, title: str, hover_data=None):
    fig = px.line(frame, x=x, y=y, markers=True, hover_data=hover_data or {}, title=title)
    fig.update_traces(line_color=NEUTRAL_BLUE, marker_color=NEUTRAL_BLUE)
    fig.update_layout(
        hovermode="x unified",
        margin=dict(l=10, r=10, t=55, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#E8EDF4")
    return fig


def bar_chart(frame: pd.DataFrame, *, x: str, y: str, title: str, color: str | None = None):
    fig = px.bar(frame, x=x, y=y, color=color, title=title)
    fig.update_layout(
        margin=dict(l=10, r=10, t=55, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_title_text="",
    )
    return fig

