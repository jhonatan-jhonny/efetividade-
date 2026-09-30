from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from components.cards import metric_card, unavailable_card
from components.charts import bar_chart, line_chart
from components.politician_card import politician_card
from components.source_badge import source_badge
from components.timeline import political_timeline
from database.connection import session_scope
from database.migrations import init_db
from database.models import Candidacy, DataQuality, ElectionResult, Indicator, Politician, Source
from repositories.indicator_repository import IndicatorRepository
from repositories.mandate_repository import MandateRepository
from repositories.municipality_repository import MunicipalityRepository
from repositories.source_repository import seed_sources
from services.camara import CamaraService
from services.connectors import CONNECTOR_STATUS
from services.ibge import IBGEService
from services.senado import SenadoService
from services.sinesp import SinespService
from services.tse import TSEService
from utils.formatting import calculate_change, format_currency, format_number, format_rate, per_100k
from utils.politics import canonical_office, ordered_offices
from utils.requests import ExternalServiceError

st.set_page_config(
    page_title="Raio-X Municipal",
    page_icon="◫",
    layout="wide",
    initial_sidebar_state="expanded",
)
css_path = Path(__file__).parent / "assets" / "style.css"
st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
init_db()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def state_name_map(rows: tuple[tuple[str, str], ...]) -> dict[str, str]:
    """Cache leve da camada de apresentação; dados oficiais permanecem no banco."""
    return dict(rows)


def quality_label(status: str) -> str:
    return {
        "complete": "✓ Disponível",
        "partial": "⚠ Parcial",
        "estimated": "≈ Estimado/calculado",
        "not_available": "— Indisponível",
    }.get(status, status)


def indicator_delta(repo, current, code: str, year: int) -> str | None:
    if current is None:
        return None
    previous = repo.get(current.codigo_ibge, code, year - 1)
    if not previous:
        return None
    change = calculate_change(
        current.value,
        previous.value,
        comparable=current.is_comparable and previous.is_comparable and current.methodology_version == previous.methodology_version,
    )
    return f"{change.percent:+.1f}% vs. {year - 1}" if change.comparable and change.percent is not None else None


def render_indicator_card(repo, item, label: str, formatter, year: int):
    if item is None or item.value is None:
        unavailable_card(label)
        return
    metric_card(
        label,
        formatter(item.value),
        delta=indicator_delta(repo, item, item.indicator_code, year),
        source=item.source.name,
        reference=str(item.year),
        quality=item.quality_status,
    )


def source_for(item):
    return item.source.name if item and item.source else "Fonte não informada"


def render_empty_connector(title: str, connector: str):
    info = CONNECTOR_STATUS[connector]
    st.info(f"{title}: ainda não sincronizado. Nenhum valor fictício é exibido.")
    st.caption(info["reason"])
    st.link_button("Consultar fonte oficial", info["official_source"])


with session_scope() as session:
    seed_sources(session)
    municipalities = MunicipalityRepository(session)
    try:
        if municipalities.count() < 5500:
            with st.spinner("Carregando a malha oficial de municípios do IBGE na primeira execução…"):
                IBGEService(session).sync_municipalities()
                session.flush()
    except ExternalServiceError as exc:
        st.error(str(exc))

    if municipalities.count() == 0:
        st.error("Não foi possível carregar os municípios. Verifique a conexão e tente novamente.")
        st.stop()

    params = st.query_params
    requested_uf = str(params.get("uf", "MG")).upper()
    requested_code = str(params.get("municipio", "3122306"))
    try:
        requested_year = int(params.get("ano", 2022))
    except (TypeError, ValueError):
        requested_year = 2022
    requested_years = []
    for raw_year in str(params.get("anos", requested_year)).split(","):
        try:
            requested_years.append(int(raw_year.strip()))
        except ValueError:
            continue

    state_rows = municipalities.states()
    state_names = state_name_map(tuple(state_rows))
    state_codes = [row[0] for row in state_rows]
    if requested_uf not in state_codes:
        requested_uf = "MG" if "MG" in state_codes else state_codes[0]

    st.sidebar.markdown("## Raio-X Municipal")
    st.sidebar.caption("Dados públicos oficiais, contexto histórico e rastreabilidade.")
    uf = st.sidebar.selectbox(
        "ESTADO",
        state_codes,
        index=state_codes.index(requested_uf),
        format_func=lambda code: f"{code} — {state_names.get(code, code)}",
    )
    city_rows = municipalities.by_state(uf)
    city_codes = [row.codigo_ibge for row in city_rows]
    if requested_code not in city_codes:
        preferred = next((m.codigo_ibge for m in city_rows if m.name == "Divinópolis"), city_codes[0])
        requested_code = preferred
    codigo_ibge = st.sidebar.selectbox(
        "MUNICÍPIO",
        city_codes,
        index=city_codes.index(requested_code),
        format_func=lambda code: next(m.name for m in city_rows if m.codigo_ibge == code),
    )
    years = list(range(datetime.now().year, 2001, -1))
    if requested_year not in years:
        requested_year = 2022
    requested_years = sorted({value for value in requested_years if value in years}) or [requested_year]
    selected_years_input = st.sidebar.multiselect(
        "ANOS",
        years,
        default=requested_years,
        max_selections=10,
        help="Selecione até 10 anos. Cards e detalhes usam o ano mais recente; a Visão Geral compara todos.",
    )
    if not selected_years_input:
        st.sidebar.warning("Selecione pelo menos um ano.")
    selected_years = sorted(selected_years_input or [requested_year])
    year = max(selected_years)
    analyze = st.sidebar.button(
        "ANALISAR MUNICÍPIO",
        type="primary",
        width="stretch",
        disabled=not selected_years_input,
    )
    st.sidebar.markdown("---")
    st.sidebar.caption("Ausência de registro nunca é convertida em zero.")

    if analyze:
        st.query_params.update(
            {
                "uf": uf,
                "municipio": codigo_ibge,
                "ano": str(year),
                "anos": ",".join(str(value) for value in selected_years),
            }
        )
        st.session_state["analyzed"] = True
    is_analyzed = analyze or st.session_state.get("analyzed", False) or bool(params.get("municipio"))

    city = municipalities.get(codigo_ibge)
    indicator_repo = IndicatorRepository(session)
    if is_analyzed:
        with st.spinner("Consultando cache e fontes oficiais necessárias…"):
            sync_errors = []
            service = IBGEService(session)
            for selected_year in selected_years:
                result = service.sync_core(codigo_ibge, selected_year)
                sync_errors.extend(result["errors"])
            session.flush()
        for error in dict.fromkeys(sync_errors):
            st.warning(error)

    population = indicator_repo.get(codigo_ibge, "population", year)
    gdp = indicator_repo.get(codigo_ibge, "gdp", year)
    gdp_pc = indicator_repo.get(codigo_ibge, "gdp_per_capita_calculated", year)

    st.markdown('<div class="city-kicker">Análise municipal histórica</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="city-title">{city.name}</div>', unsafe_allow_html=True)
    period_label = ", ".join(str(value) for value in selected_years)
    st.markdown(
        f'<div class="city-subtitle">{city.state_name or uf} · Código IBGE {city.codigo_ibge} · Anos analisados: <b>{period_label}</b> · Referência dos cards: <b>{year}</b></div>',
        unsafe_allow_html=True,
    )

    if not is_analyzed:
        st.info("Escolha estado, município e um ou mais anos; depois clique em **Analisar município**.")

    header_cols = st.columns(6)
    with header_cols[0]:
        render_indicator_card(indicator_repo, population, "População", lambda v: format_number(v), year)
    with header_cols[1]:
        render_indicator_card(indicator_repo, gdp, "PIB", lambda v: format_currency(v), year)
    with header_cols[2]:
        render_indicator_card(indicator_repo, gdp_pc, "PIB / habitante", lambda v: format_currency(v), year)
    with header_cols[3]:
        unavailable_card("Empregos", "Conector Novo CAGED preparado")
    with header_cols[4]:
        if city.area_km2:
            metric_card("Área", f"{format_number(city.area_km2, 1)} km²", source="IBGE")
        else:
            unavailable_card("Área")
    crimes = indicator_repo.category(codigo_ibge, "security", year)
    homicide = next((i for i in crimes if "HOMIC" in i.indicator_name.upper() and "TENT" not in i.indicator_name.upper()), None)
    with header_cols[5]:
        rate = per_100k(homicide.value if homicide else None, population.value if population else None)
        if rate is None:
            unavailable_card("Homicídios / 100 mil")
        else:
            metric_card("Homicídios / 100 mil", format_rate(rate), source="Sinesp/MJSP", reference=str(year), quality=homicide.quality_status)

    tab_names = [
        "Visão Geral", "Segurança", "Economia", "Emprego", "Educação", "Saúde",
        "Desenvolvimento", "Finanças Públicas", "Política e Eleições", "Comparar", "Fontes e Metodologia",
    ]
    tabs = st.tabs(tab_names)

    with tabs[0]:
        st.subheader("Síntese do período")
        overview = st.columns(4)
        with overview[0]:
            render_indicator_card(indicator_repo, population, "População", lambda v: format_number(v), year)
        with overview[1]:
            render_indicator_card(indicator_repo, gdp, "PIB", lambda v: format_currency(v), year)
        with overview[2]:
            render_indicator_card(indicator_repo, gdp_pc, "PIB per capita calculado", lambda v: format_currency(v), year)
        with overview[3]:
            if rate is not None:
                metric_card("Homicídios / 100 mil", format_rate(rate), source="Sinesp/MJSP", reference=str(year), quality=homicide.quality_status)
            else:
                unavailable_card("Homicídios / 100 mil")
        if population:
            summary = f"Em {year}, {city.name} tinha {format_number(population.value)} habitantes segundo {population.source.name}."
            if homicide and rate is not None:
                summary += f" Foram registrados {format_number(homicide.value)} eventos no indicador {homicide.indicator_name}, equivalentes a {format_rate(rate)}."
            st.markdown(f"**Resumo numérico:** {summary}")
        st.caption("O resumo descreve valores e variações matemáticas; não atribui causalidade a representantes.")

        if len(selected_years) > 1:
            st.subheader("Comparação dos anos selecionados")
            comparison_rows = []
            for selected_year in selected_years:
                selected_population = indicator_repo.get(codigo_ibge, "population", selected_year)
                selected_gdp = indicator_repo.get(codigo_ibge, "gdp", selected_year)
                selected_gdp_pc = indicator_repo.get(codigo_ibge, "gdp_per_capita_calculated", selected_year)
                selected_crimes = indicator_repo.category(codigo_ibge, "security", selected_year)
                selected_homicide = next(
                    (
                        item
                        for item in selected_crimes
                        if "HOMIC" in item.indicator_name.upper() and "TENT" not in item.indicator_name.upper()
                    ),
                    None,
                )
                comparison_rows.append(
                    {
                        "Ano": selected_year,
                        "População": selected_population.value if selected_population else None,
                        "PIB (R$)": selected_gdp.value if selected_gdp else None,
                        "PIB por habitante (R$)": selected_gdp_pc.value if selected_gdp_pc else None,
                        "Homicídios / 100 mil": per_100k(
                            selected_homicide.value if selected_homicide else None,
                            selected_population.value if selected_population else None,
                        ),
                    }
                )
            comparison_frame = pd.DataFrame(comparison_rows)
            st.dataframe(
                comparison_frame,
                hide_index=True,
                width="stretch",
                column_config={
                    "Ano": st.column_config.NumberColumn(format="%d"),
                    "População": st.column_config.NumberColumn(format="localized"),
                    "PIB (R$)": st.column_config.NumberColumn(format="R$ %.0f"),
                    "PIB por habitante (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Homicídios / 100 mil": st.column_config.NumberColumn(format="%.2f"),
                },
            )
            chart_columns = st.columns(2)
            population_frame = comparison_frame.dropna(subset=["População"])
            gdp_pc_frame = comparison_frame.dropna(subset=["PIB por habitante (R$)"])
            with chart_columns[0]:
                if not population_frame.empty:
                    st.plotly_chart(
                        line_chart(population_frame, x="Ano", y="População", title="População nos anos selecionados"),
                        width="stretch",
                        key="selected_years_population_chart",
                    )
            with chart_columns[1]:
                if not gdp_pc_frame.empty:
                    st.plotly_chart(
                        line_chart(gdp_pc_frame, x="Ano", y="PIB por habitante (R$)", title="PIB por habitante nos anos selecionados"),
                        width="stretch",
                        key="selected_years_gdp_pc_chart",
                    )

        st.subheader("Dados disponíveis para esta cidade")
        category_counts = dict(
            session.execute(
                select(Indicator.category, func.count(Indicator.id))
                .where(Indicator.codigo_ibge == codigo_ibge)
                .group_by(Indicator.category)
            ).all()
        )
        coverage_exercises = {
            item.id
            for selected_year in selected_years
            for item in MandateRepository(session).for_year(
                selected_year, codigo_ibge=codigo_ibge, uf=uf
            )
        }
        office_count = len(coverage_exercises)
        coverage = pd.DataFrame(
            [
                ("População", "complete" if population else "not_available"),
                ("PIB", "complete" if gdp else "not_available"),
                ("Segurança", "partial" if category_counts.get("security") else "not_available"),
                ("Educação", "complete" if category_counts.get("education") else "not_available"),
                ("Saúde", "complete" if category_counts.get("health") else "not_available"),
                ("Finanças", "complete" if category_counts.get("finance") else "not_available"),
                ("Política", "partial" if office_count else "not_available"),
            ],
            columns=["Área", "Situação"],
        )
        coverage["Cobertura"] = coverage["Situação"].map(quality_label)
        st.dataframe(coverage[["Área", "Cobertura"]], hide_index=True, width="stretch")

    with tabs[1]:
        st.subheader("Segurança pública")
        st.caption("Registros oficiais não são equivalentes à incidência real; cobertura e alimentação variam entre UFs e períodos.")
        if st.button("Sincronizar publicação municipal do Sinesp", key="sync_sinesp"):
            total = 0
            with st.spinner("Baixando/consultando as planilhas oficiais do MJSP…"):
                for selected_year in selected_years:
                    try:
                        total += SinespService(session).sync_municipality(codigo_ibge, selected_year)
                    except ExternalServiceError as exc:
                        st.warning(f"{selected_year}: {exc}")
                session.flush()
            if total:
                st.success(f"{total} indicadores oficiais carregados para os anos selecionados.")
        selected_crime_records = [
            item
            for selected_year in selected_years
            for item in indicator_repo.category(codigo_ibge, "security", selected_year)
        ]
        if not selected_crime_records:
            st.info("Sem dado municipal carregado para os anos selecionados. Isso não significa zero ocorrências.")
        else:
            rows = []
            for item in selected_crime_records:
                item_population = indicator_repo.get(codigo_ibge, "population", item.year)
                rows.append(
                    {
                        "Ano": item.year,
                        "Indicador": item.indicator_name,
                        "Total": item.value,
                        "Taxa / 100 mil": per_100k(item.value, item_population.value if item_population else None),
                        "Qualidade": quality_label(item.quality_status),
                        "Fonte": item.source.name,
                        "Referência": item.year,
                    }
                )
            crime_frame = pd.DataFrame(rows)
            st.dataframe(crime_frame, hide_index=True, width="stretch")
            available_crime_codes = list(dict.fromkeys(item.indicator_code for item in selected_crime_records))
            chosen = st.selectbox(
                "Indicador",
                available_crime_codes,
                format_func=lambda code: next(
                    item.indicator_name for item in selected_crime_records if item.indicator_code == code
                ),
            )
            series = [
                item
                for item in indicator_repo.series(codigo_ibge, chosen)
                if item.year in selected_years
            ]
            chart_rows = []
            for item in series:
                pop = indicator_repo.get(codigo_ibge, "population", item.year)
                chart_rows.append({"Ano": item.year, "Ocorrências": item.value, "Taxa": per_100k(item.value, pop.value if pop else None), "População usada": pop.value if pop else None, "Fonte": item.source.name})
            frame = pd.DataFrame(chart_rows)
            st.plotly_chart(
                line_chart(frame, x="Ano", y="Taxa", title="Taxa registrada por 100 mil", hover_data=["Ocorrências", "População usada", "Fonte"]),
                width="stretch",
                key="security_rate_chart",
            )
            first_crime = selected_crime_records[0]
            source_badge(
                first_crime.source.name,
                first_crime.source.url,
                period_label,
                first_crime.quality_status,
            )

    with tabs[2]:
        st.subheader("Economia")
        econ = indicator_repo.category(codigo_ibge, "economy", year)
        if econ:
            sector_codes = {"gdp_agriculture", "gdp_industry", "gdp_services", "gdp_public_admin"}
            sectors = [i for i in econ if i.indicator_code in sector_codes]
            if sectors:
                frame = pd.DataFrame({"Setor": [i.indicator_name.replace("Valor adicionado bruto a preços correntes da ", "").replace("Valor adicionado bruto a preços correntes dos ", "") for i in sectors], "R$": [i.value for i in sectors]})
                st.plotly_chart(
                    bar_chart(frame, x="Setor", y="R$", title=f"Valor adicionado por atividade — {year}"),
                    width="stretch",
                    key="economy_sectors_chart",
                )
            series = [
                item
                for item in indicator_repo.series(codigo_ibge, "gdp")
                if item.year in selected_years
            ]
            if series:
                frame = pd.DataFrame({"Ano": [i.year for i in series], "PIB (R$)": [i.value for i in series], "Fonte": [i.source.name for i in series]})
                st.plotly_chart(
                    line_chart(frame, x="Ano", y="PIB (R$)", title="PIB municipal — anos selecionados", hover_data=["Fonte"]),
                    width="stretch",
                    key="economy_gdp_history_chart",
                )
            if gdp:
                source_badge(gdp.source.name, gdp.source.url, str(gdp.year), gdp.quality_status)
        else:
            st.info("Sem PIB publicado para o ano selecionado. A série do PIB municipal tem defasagem de divulgação.")

    with tabs[3]:
        st.subheader("Emprego formal")
        render_empty_connector("Novo CAGED / RAIS", "caged")

    with tabs[4]:
        st.subheader("Educação")
        render_empty_connector("INEP / MEC", "inep")
        st.caption("IDEB será exibido apenas no ano efetivamente medido; não haverá interpolação silenciosa.")

    with tabs[5]:
        st.subheader("Saúde")
        render_empty_connector("DATASUS / Ministério da Saúde", "datasus")
        st.caption("O ano do dado e o ano selecionado serão sempre diferenciados.")

    with tabs[6]:
        st.subheader("Desenvolvimento")
        st.info("IDHM e componentes ainda não foram importados. O sistema não repete um IDHM censitário como se fosse anual.")
        st.link_button("Atlas do Desenvolvimento Humano", "http://www.atlasbrasil.org.br/")

    with tabs[7]:
        st.subheader("Finanças públicas")
        render_empty_connector("Tesouro / Siconfi / Finbra", "siconfi")

    with tabs[8]:
        st.subheader("Política e eleições")
        st.caption(
            "Tudo nesta área é organizado por cargo. Exercício confirmado e resultado eleitoral "
            "continuam separados para não apresentar candidatura como mandato."
        )

        election_years = [value for value in years if value % 4 == 0 and value <= 2024]
        past_elections = [value for value in election_years if value <= year]
        default_election = max(past_elections) if past_elections else election_years[-1]
        election_year = st.selectbox(
            "Eleição municipal de referência",
            election_years,
            index=election_years.index(default_election),
            key="politics_election_year",
        )

        col_sync_1, col_sync_2, col_sync_3 = st.columns(3)
        with col_sync_1:
            if st.button("Carregar deputados federais", width="stretch", key="sync_federal_deputies"):
                try:
                    with st.spinner("Reconstruindo eventos oficiais de exercício da Câmara…"):
                        service = CamaraService(session)
                        n = sum(service.sync_deputies(uf, selected_year) for selected_year in selected_years)
                        session.flush()
                    st.success(f"{n} intervalos processados para os anos selecionados.")
                except ExternalServiceError as exc:
                    st.warning(str(exc))
        with col_sync_2:
            if st.button("Carregar senadores", width="stretch", key="sync_senators"):
                try:
                    with st.spinner("Consultando mandatos e exercícios no Senado…"):
                        service = SenadoService(session)
                        n = sum(service.sync_senators(uf, selected_year) for selected_year in selected_years)
                        session.flush()
                    st.success(f"{n} intervalos processados para os anos selecionados.")
                except ExternalServiceError as exc:
                    st.warning(str(exc))
        with col_sync_3:
            if st.button("Importar eleição municipal", width="stretch", key="sync_tse"):
                try:
                    with st.spinner("Baixando e filtrando arquivos oficiais do TSE…"):
                        n = TSEService(session).sync_election(codigo_ibge, uf, election_year)
                        session.flush()
                    st.success(f"{n} candidaturas carregadas e separadas por cargo.")
                except (ExternalServiceError, OSError, ValueError) as exc:
                    st.warning(str(exc))

        mandate_repository = MandateRepository(session)
        exercises_by_id = {}
        for selected_year in selected_years:
            for exercise in mandate_repository.for_year(selected_year, codigo_ibge=codigo_ibge, uf=uf):
                exercises_by_id[exercise.id] = exercise
        exercises = list(exercises_by_id.values())

        candidate_rows = session.execute(
            select(Candidacy, Politician, ElectionResult)
            .join(Politician, Candidacy.politician_id == Politician.id)
            .outerjoin(ElectionResult, ElectionResult.candidacy_id == Candidacy.id)
            .where(Candidacy.codigo_ibge == codigo_ibge, Candidacy.election_year == election_year)
            .order_by(Candidacy.office, ElectionResult.votes.desc())
        ).all()

        offices = ordered_offices(
            [exercise.office for exercise in exercises]
            + [candidacy.office for candidacy, _, _ in candidate_rows]
        )
        for office in offices:
            office_exercises = [
                exercise for exercise in exercises if canonical_office(exercise.office) == office
            ]
            office_candidates = [
                row for row in candidate_rows if canonical_office(row[0].office) == office
            ]
            candidacy_count = len({candidacy.id for candidacy, _, _ in office_candidates})
            title = (
                f"{office} · {len(office_exercises)} exercício(s) confirmado(s) · "
                f"{candidacy_count} candidatura(s) em {election_year}"
            )
            with st.expander(
                title,
                expanded=office == "Prefeito" and bool(office_exercises or office_candidates),
            ):
                st.markdown("**Exercício confirmado nos anos analisados**")
                if office_exercises:
                    columns = st.columns(3)
                    for index, exercise in enumerate(office_exercises):
                        with columns[index % 3]:
                            politician_card(exercise)
                else:
                    st.caption("Nenhum intervalo de exercício confirmado foi carregado para este cargo.")

                st.markdown(f"**Candidaturas e resultados — eleição {election_year}**")
                if office_candidates:
                    frame = pd.DataFrame(
                        [
                            {
                                "Candidato": politician.name,
                                "Partido": candidacy.party,
                                "Número": candidacy.candidate_number,
                                "Turno": result.round if result else None,
                                "Votos": result.votes if result else None,
                                "%": result.vote_percentage if result else None,
                                "Situação": result.status if result else candidacy.totalization_status,
                            }
                            for candidacy, politician, result in office_candidates
                        ]
                    )
                    st.dataframe(frame, hide_index=True, width="stretch")
                else:
                    st.caption("Nenhuma candidatura importada para este cargo e eleição.")

        if candidate_rows:
            source = session.scalar(select(Source).where(Source.key == "tse"))
            source_badge(source.name, source.url, str(election_year), "complete")
        else:
            st.info("Nenhuma eleição foi importada para este município/ano.")

        st.subheader("Linha do tempo política")
        timeline_start = min(selected_years) if len(selected_years) > 1 else max(2002, year - 8)
        timeline_end = max(selected_years) if len(selected_years) > 1 else min(datetime.now().year, year + 4)
        timeline_items = mandate_repository.timeline(codigo_ibge, uf, timeline_start, timeline_end)
        fig = political_timeline(timeline_items, timeline_start, timeline_end)
        if fig:
            st.plotly_chart(fig, width="stretch", key="politics_timeline_chart")
        else:
            st.info("Carregue representantes para construir a linha do tempo.")
        st.warning(
            "Os dados mostram associações temporais. A presença de determinado representante durante "
            "um período não implica que alterações nos indicadores tenham sido causadas por ele."
        )

    with tabs[9]:
        st.subheader("Comparar municípios")
        st.caption(f"A comparação entre municípios abaixo usa o ano de referência dos cards: {year}.")
        options = [m.codigo_ibge for m in city_rows if m.codigo_ibge != codigo_ibge]
        compare_codes = st.multiselect(
            "Outros municípios da mesma UF (até 4)",
            options,
            max_selections=4,
            format_func=lambda code: next(m.name for m in city_rows if m.codigo_ibge == code),
        )
        metric = st.selectbox("Indicador comparável", ["population", "gdp", "gdp_per_capita_calculated"], format_func={"population": "População", "gdp": "PIB", "gdp_per_capita_calculated": "PIB por habitante calculado"}.get)
        if st.button("Comparar valores", key="compare"):
            with st.spinner("Sincronizando apenas os recortes escolhidos…"):
                service = IBGEService(session)
                for code in compare_codes:
                    service.sync_core(code, year)
                session.flush()
            all_codes = [codigo_ibge, *compare_codes]
            compare_rows = []
            for code in all_codes:
                item = indicator_repo.get(code, metric, year)
                municipality = municipalities.get(code)
                compare_rows.append({"Município": municipality.name, "Valor": item.value if item else None, "Disponibilidade": quality_label(item.quality_status) if item else "— Indisponível"})
            frame = pd.DataFrame(compare_rows)
            available = frame.dropna(subset=["Valor"])
            if not available.empty:
                st.plotly_chart(
                    bar_chart(available, x="Município", y="Valor", title=f"{dict(population='População', gdp='PIB', gdp_per_capita_calculated='PIB por habitante calculado')[metric]} — {year}"),
                    width="stretch",
                    key="municipality_comparison_chart",
                )
            st.dataframe(frame.sort_values("Valor", ascending=False, na_position="last"), hide_index=True, width="stretch")
            st.caption("Tabela ordenada exclusivamente pelo valor do indicador selecionado; não é ranking político.")

        st.subheader("Comparação histórica e mandatos")
        default_interval = (
            (min(selected_years), max(selected_years))
            if len(selected_years) > 1
            else (max(2002, year - 8), year)
        )
        start_year, end_year = st.slider(
            "Intervalo",
            2002,
            datetime.now().year,
            default_interval,
        )
        history = indicator_repo.series(codigo_ibge, metric, start_year, end_year)
        if history:
            frame = pd.DataFrame({"Ano": [i.year for i in history], "Valor": [i.value for i in history], "Qualidade": [quality_label(i.quality_status) for i in history]})
            st.plotly_chart(
                line_chart(frame, x="Ano", y="Valor", title="Indicador — anos sincronizados", hover_data=["Qualidade"]),
                width="stretch",
                key="historical_indicator_chart",
            )
        timeline_items = MandateRepository(session).timeline(codigo_ibge, uf, start_year, end_year)
        timeline_fig = political_timeline(timeline_items, start_year, end_year)
        if timeline_fig:
            st.plotly_chart(timeline_fig, width="stretch", key="comparison_timeline_chart")

    with tabs[10]:
        st.subheader("Fontes, atualização e metodologia")
        st.markdown(
            """
            **Taxa por 100 mil** = ocorrências ÷ população de referência × 100.000.

            Valores ausentes permanecem ausentes. Séries com mudança metodológica não recebem comparação automática.
            O PIB por habitante identificado como “cálculo da plataforma” usa PIB municipal e população oficial do mesmo ano;
            seu status é estimado/calculado, não uma publicação direta do SIDRA.

            **Política:** candidatura, resultado eleitoral, mandato previsto e exercício do cargo são entidades distintas.
            Câmara e Senado fornecem eventos/intervalos de exercício. Para cargos municipais, o resultado TSE sozinho recebe
            no máximo o estado `election_result_only` e não é mostrado como exercício confirmado.
            """
        )
        sources = list(session.scalars(select(Source).order_by(Source.name)))
        source_frame = pd.DataFrame(
            [
                {
                    "Fonte": s.name,
                    "Órgão": s.organization,
                    "Frequência": s.update_frequency,
                    "Última consulta da plataforma": s.last_checked,
                    "URL": s.url,
                }
                for s in sources
            ]
        )
        st.dataframe(source_frame, hide_index=True, width="stretch", column_config={"URL": st.column_config.LinkColumn("URL")})
        st.subheader("Conectores planejados sem dados fictícios")
        connector_frame = pd.DataFrame([{"Conector": name.upper(), "Estado": item["status"], "Motivo": item["reason"], "Fonte": item["official_source"]} for name, item in CONNECTOR_STATUS.items()])
        st.dataframe(connector_frame, hide_index=True, width="stretch", column_config={"Fonte": st.column_config.LinkColumn("Fonte")})
        st.caption(f"Última execução da interface: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}. A atualização da plataforma, da fonte e o período mais recente são conceitos distintos.")

