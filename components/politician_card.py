from __future__ import annotations

import html

import streamlit as st


def politician_card(exercise) -> None:
    person = exercise.politician
    end = exercise.end_date.strftime("%d/%m/%Y") if exercise.end_date else "em aberto"
    start = exercise.start_date.strftime("%d/%m/%Y")
    party = exercise.party_at_start or "partido não informado"
    photo = (
        f'<img src="{html.escape(person.photo_url)}" class="politician-photo" />'
        if person.photo_url
        else '<div class="politician-placeholder">sem foto</div>'
    )
    st.markdown(
        f"""
        <div class="politician-card">
          {photo}
          <div>
            <div class="politician-office">{html.escape(exercise.office)}</div>
            <div class="politician-name">{html.escape(person.name)}</div>
            <div class="politician-meta">{html.escape(party)} · {html.escape(exercise.titularity or 'titularidade não informada')}</div>
            <div class="politician-meta">{start} → {end}</div>
            <div class="politician-verification">{html.escape(exercise.verification_status)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

