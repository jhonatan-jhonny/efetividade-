from __future__ import annotations

import html

import streamlit as st


def metric_card(
    label: str,
    value: str,
    *,
    delta: str | None = None,
    source: str | None = None,
    reference: str | None = None,
    quality: str | None = None,
) -> None:
    detail = " · ".join(part for part in (source, f"Ref. {reference}" if reference else None) if part)
    status = {"complete": "✓", "partial": "⚠", "estimated": "≈", "not_available": "—"}.get(quality or "", "")
    st.markdown(
        f"""
        <div class="metric-card">
          <div class="metric-label">{html.escape(status)} {html.escape(label)}</div>
          <div class="metric-value">{html.escape(value)}</div>
          <div class="metric-delta">{html.escape(delta or '')}</div>
          <div class="metric-source">{html.escape(detail)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def unavailable_card(label: str, reason: str = "Sem dado para este período.") -> None:
    metric_card(label, "Não disponível", delta=reason, quality="not_available")

