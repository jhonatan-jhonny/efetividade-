import html

import streamlit as st


def source_badge(name: str, url: str | None, reference: str | None = None, quality: str = "complete"):
    icon = {"complete": "✓", "partial": "⚠", "estimated": "≈", "not_available": "—"}.get(quality, "")
    label = f"{icon} Fonte: {name}"
    link = f'<a href="{html.escape(url)}" target="_blank">{html.escape(label)}</a>' if url else html.escape(label)
    suffix = f" · referência {html.escape(reference)}" if reference else ""
    st.markdown(f'<div class="source-badge">{link}{suffix}</div>', unsafe_allow_html=True)

