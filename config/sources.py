"""URLs oficiais centralizadas e metadados de atualização."""

IBGE_LOCALITIES = "https://servicodados.ibge.gov.br/api/v1/localidades"
IBGE_AGGREGATES = "https://servicodados.ibge.gov.br/api/v3/agregados"
CAMARA_API = "https://dadosabertos.camara.leg.br/api/v2"
SENADO_API = "https://legis.senado.leg.br/dadosabertos"
TSE_CKAN_API = "https://dadosabertos.tse.jus.br/api/3/action"
SINESP_YEAR_XLSX = (
    "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/"
    "estatistica/download/dnsp-base-de-dados/bancovde-{year}.xlsx/@@download/file"
)

SOURCE_DEFINITIONS = {
    "ibge": {
        "name": "IBGE / SIDRA",
        "organization": "Instituto Brasileiro de Geografia e Estatística",
        "url": "https://sidra.ibge.gov.br/",
        "api_url": IBGE_AGGREGATES,
        "update_frequency": "Conforme a pesquisa",
        "license": "Dados públicos oficiais",
    },
    "camara": {
        "name": "Dados Abertos da Câmara",
        "organization": "Câmara dos Deputados",
        "url": "https://dadosabertos.camara.leg.br/",
        "api_url": CAMARA_API,
        "update_frequency": "Online",
        "license": "Dados públicos oficiais",
    },
    "senado": {
        "name": "Dados Abertos do Senado",
        "organization": "Senado Federal",
        "url": "https://www12.senado.leg.br/dados-abertos/",
        "api_url": SENADO_API,
        "update_frequency": "Online",
        "license": "Dados públicos oficiais",
    },
    "tse": {
        "name": "Portal de Dados Abertos do TSE",
        "organization": "Tribunal Superior Eleitoral",
        "url": "https://dadosabertos.tse.jus.br/",
        "api_url": TSE_CKAN_API,
        "update_frequency": "Por eleição",
        "license": "Conforme o conjunto no portal",
    },
    "sinesp": {
        "name": "Dados Nacionais de Segurança Pública",
        "organization": "MJSP / Sinesp",
        "url": "https://www.gov.br/mj/pt-br/assuntos/sua-seguranca/seguranca-publica/estatistica",
        "api_url": SINESP_YEAR_XLSX,
        "update_frequency": "Conforme publicação do MJSP",
        "license": "Dados públicos oficiais",
    },
}

DATASET_TTLS = {
    "municipalities": 30 * 24 * 3600,
    "population": 180 * 24 * 3600,
    "gdp": 365 * 24 * 3600,
    "camara": 7 * 24 * 3600,
    "senado": 7 * 24 * 3600,
    "tse": 365 * 24 * 3600,
    "sinesp": 30 * 24 * 3600,
}

