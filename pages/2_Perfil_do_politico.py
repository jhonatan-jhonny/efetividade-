from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import select

from database.connection import session_scope
from database.migrations import init_db
from database.models import Candidacy, ElectionResult, OfficeExercise, Politician

st.set_page_config(page_title="Perfil do político · Raio-X", page_icon="◫", layout="wide")
css = Path(__file__).resolve().parents[1] / "assets" / "style.css"
st.markdown(f"<style>{css.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
init_db()

st.title("Perfil do político")
st.caption("Histórico factual proveniente das fontes oficiais já sincronizadas.")
query_id = st.query_params.get("politico")

with session_scope() as session:
    people = list(session.scalars(select(Politician).order_by(Politician.name)))
    if not people:
        st.info("Nenhum político foi sincronizado ainda. Use as abas Política ou Eleições na página principal.")
        st.stop()
    ids = [p.id for p in people]
    default = ids.index(int(query_id)) if query_id and str(query_id).isdigit() and int(query_id) in ids else 0
    person_id = st.selectbox("Buscar político", ids, index=default, format_func=lambda pid: next(p.name for p in people if p.id == pid))
    st.query_params["politico"] = str(person_id)
    person = session.get(Politician, person_id)
    left, right = st.columns([1, 5])
    with left:
        if person.photo_url:
            st.image(person.photo_url, width=150)
    with right:
        st.header(person.name)
        if person.civil_name and person.civil_name != person.name:
            st.caption(f"Nome civil: {person.civil_name}")
        st.caption(f"Identificador na fonte: {person.external_source}:{person.external_id}")

    st.subheader("Exercício de cargos")
    exercises = list(session.scalars(select(OfficeExercise).where(OfficeExercise.politician_id == person_id).order_by(OfficeExercise.start_date.desc())))
    if exercises:
        st.dataframe(pd.DataFrame([{"Cargo": e.office, "UF": e.uf, "Município IBGE": e.codigo_ibge, "Início": e.start_date, "Fim": e.end_date, "Partido no início": e.party_at_start, "Situação": e.verification_status, "Motivo de saída": e.end_reason} for e in exercises]), hide_index=True, width="stretch")
    else:
        st.info("Nenhum intervalo de exercício confirmado foi carregado.")

    st.subheader("Resultados eleitorais")
    rows = session.execute(select(Candidacy, ElectionResult).outerjoin(ElectionResult, ElectionResult.candidacy_id == Candidacy.id).where(Candidacy.politician_id == person_id).order_by(Candidacy.election_year.desc())).all()
    if rows:
        st.dataframe(pd.DataFrame([{"Ano": c.election_year, "Cargo": c.office, "Partido": c.party, "Número": c.candidate_number, "Votos": r.votes if r else None, "%": r.vote_percentage if r else None, "Situação": r.status if r else c.totalization_status} for c, r in rows]), hide_index=True, width="stretch")
    else:
        st.info("Nenhuma candidatura foi carregada.")

