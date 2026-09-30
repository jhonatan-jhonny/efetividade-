import streamlit as st

from database.connection import session_scope
from database.migrations import init_db
from repositories.municipality_repository import MunicipalityRepository
from repositories.source_repository import seed_sources
from services.ibge import IBGEService
from utils.requests import ExternalServiceError

st.set_page_config(page_title="Administração · Raio-X", page_icon="◫", layout="wide")
init_db()
st.title("Administração e sincronização")
st.caption("Operações leves. Cargas grandes devem preferir `python -m scripts.sync`.")

with session_scope() as session:
    seed_sources(session)
    session.commit()
    repo = MunicipalityRepository(session)
    st.metric("Municípios cadastrados", repo.count())
    if st.button("Atualizar municípios pelo IBGE"):
        try:
            with st.spinner("Consultando a API oficial…"):
                count = IBGEService(session).sync_municipalities(force=True)
            st.success(f"{count} municípios atualizados.")
        except ExternalServiceError as exc:
            st.error(str(exc))
    st.code(
        """python -m scripts.sync --dataset ibge --municipio 3122306 --year 2022
python -m scripts.sync --dataset sinesp --municipio 3122306 --year 2022
python -m scripts.sync --dataset tse --uf MG --municipio 3122306 --year 2020
python -m scripts.sync --dataset camara --uf MG --year 2022
python -m scripts.sync --dataset senado --uf MG --year 2022""",
        language="bash",
    )

