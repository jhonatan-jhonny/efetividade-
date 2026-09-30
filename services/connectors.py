"""Contratos explícitos para integrações da próxima etapa, sem fabricar dados."""

CONNECTOR_STATUS = {
    "inep": {
        "status": "prepared",
        "official_source": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos",
        "reason": "Microdados exigem ETL por edição e preservação do ano real do IDEB/Censo Escolar.",
    },
    "datasus": {
        "status": "prepared",
        "official_source": "https://datasus.saude.gov.br/transferencia-de-arquivos/",
        "reason": "Arquivos DBF/DBC exigem pipeline específico e validação por sistema de origem.",
    },
    "caged": {
        "status": "prepared",
        "official_source": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho",
        "reason": "Microdados mensais devem ser processados em lote e agregados por código municipal.",
    },
    "siconfi": {
        "status": "prepared",
        "official_source": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
        "reason": "Requer mapear demonstrativos/contas e compatibilidade metodológica entre exercícios.",
    },
    "rais": {
        "status": "prepared",
        "official_source": "https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho",
        "reason": "Arquivos anuais grandes exigem ETL incremental por UF.",
    },
}


def connector_status(name: str) -> dict:
    return CONNECTOR_STATUS.get(
        name,
        {"status": "unavailable", "official_source": None, "reason": "Conector não cadastrado."},
    )

