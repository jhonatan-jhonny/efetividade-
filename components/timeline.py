from __future__ import annotations

import pandas as pd
import plotly.express as px


def political_timeline(exercises, start_year: int, end_year: int):
    rows = []
    for item in exercises:
        rows.append(
            {
                "Cargo": item.office,
                "Pessoa": item.politician.name,
                "Início": max(item.start_date, pd.Timestamp(start_year, 1, 1).date()),
                "Fim": min(item.end_date or pd.Timestamp(end_year, 12, 31).date(), pd.Timestamp(end_year, 12, 31).date()),
                "Partido": item.party_at_start or "Não informado",
                "Verificação": item.verification_status,
            }
        )
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    fig = px.timeline(
        frame,
        x_start="Início",
        x_end="Fim",
        y="Cargo",
        color="Pessoa",
        hover_data=["Partido", "Verificação"],
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        margin=dict(l=10, r=10, t=25, b=10),
        legend_title_text="Representante",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig

