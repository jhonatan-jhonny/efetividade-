# Raio-X Municipal

Aplicação em Python + Streamlit para análise histórica de municípios brasileiros, com dados oficiais,
rastreabilidade por registro e separação explícita entre candidatura, resultado eleitoral, mandato previsto
e exercício efetivo de cargo.

O sistema privilegia precisão: ausência é `NULL`/“Não disponível”, nunca zero; indicadores não são
atribuídos causalmente a representantes; e séries incompatíveis não recebem variação automática.

## O que já funciona

- carga inicial da malha municipal vigente pela API de Localidades do IBGE, usando `codigo_ibge` como chave;
- população municipal pelo SIDRA (estimativas e Censo 2022 com metodologia identificada);
- PIB municipal e atividades econômicas pela tabela SIDRA 5938;
- PIB por habitante calculado e identificado como cálculo, com proveniência dos dois insumos;
- publicação municipal de segurança Sinesp/MJSP, baixada e filtrada sob demanda;
- candidaturas e votação nominal do TSE, em ZIP/CSV processado por chunks;
- mapeamento oficial código TSE ↔ código IBGE publicado pelo próprio TSE;
- deputados federais por UF e ano, com intervalos reconstruídos de eventos do histórico da Câmara;
- senadores por legislatura, mandato, exercício e suplência conforme XML oficial do Senado;
- banco SQLite local ou PostgreSQL via `DATABASE_URL`;
- cache persistente, retry/backoff HTTP, tratamento de JSON/XML, logs e estados de qualidade;
- dashboard com 11 abas, política e eleições reunidas e separadas por cargo, comparações, timeline e painel de cobertura;
- seleção simultânea de até 10 anos, comparação tabular/visual e URL compartilhável do período;
- CLI de sincronização e configuração para Render.

Conectores de INEP, DATASUS, Novo CAGED/RAIS e Siconfi estão descritos e delimitados na interface, mas
não fabricam dados. A implementação completa desses ETLs exige validar layouts por edição e regras de
compatibilidade antes de publicar valores.

## Fontes oficiais integradas

| Fonte | Uso | Estratégia |
|---|---|---|
| IBGE Localidades | municípios e UFs | API REST |
| IBGE/SIDRA | população, PIB e setores | API de Agregados v3 |
| MJSP/Sinesp | indicadores municipais de segurança | XLSX oficial sob demanda |
| TSE | códigos, candidaturas e votos | catálogo CKAN + ZIP/CSV em chunks |
| Câmara dos Deputados | deputados e eventos de exercício | API REST v2 |
| Senado Federal | mandatos, exercícios e suplentes | webservice XML |

URLs ficam centralizadas em `config/sources.py`. Cada indicador persiste fonte, referência original,
período, data de coleta, metodologia e qualidade.

## Arquitetura

```text
app.py                    interface principal
pages/                    perfil e administração
components/               cards, gráficos, timeline e fontes
config/                   settings e catálogo de fontes
database/                 modelos, conexão e criação do esquema
repositories/             consultas e persistência por domínio
services/                 clientes IBGE, Sinesp, TSE, Câmara e Senado
etl/                      normalização (joins sempre por código)
utils/                    HTTP, datas, formatação e logs
scripts/sync.py            sincronização por CLI
tests/                    regras históricas, cache e parsers
data/                     SQLite e downloads locais (ignorados no Git)
```

As principais entidades são `municipalities`, `sources`, `datasets`, `indicators`, `politicians`,
`parties`, `party_affiliations`, `candidacies`, `election_results`, `mandates`, `office_exercises`,
`political_events`, `sync_logs` e `data_quality`.

`office_exercises` é intervalar. Uma pessoa pode ter vários intervalos no mesmo cargo e todos os
intervalos que cruzam o ano consultado são retornados. Um resultado TSE não cria automaticamente um
registro de exercício.

## Instalação

Requer Python 3.11 ou superior.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Na primeira execução a aplicação cria `data/raiox.db`, consulta a lista oficial de municípios e já
permite abrir a interface. Os demais dados são carregados somente para os recortes solicitados.

## Variáveis de ambiente

```dotenv
DATABASE_URL=
USE_MOCK_DATA=false
HTTP_TIMEOUT=30
APP_USER_AGENT=RaioXMunicipal/1.0 (contato: seu-email)
PORT=8501
```

- sem `DATABASE_URL`, usa SQLite em `data/raiox.db`;
- produção deve usar PostgreSQL (`postgresql+psycopg://...` também é aceito);
- `USE_MOCK_DATA` existe para desenvolvimento, mas nenhum mock é misturado à interface normal;
- não há credenciais no repositório e `.env` está no `.gitignore`.

## Sincronização por CLI

```bash
python -m scripts.sync --dataset municipalities
python -m scripts.sync --dataset ibge --municipio 3122306 --year 2022
python -m scripts.sync --dataset sinesp --municipio 3122306 --year 2022
python -m scripts.sync --dataset tse --uf MG --municipio 3122306 --year 2020
python -m scripts.sync --dataset camara --uf MG --year 2022
python -m scripts.sync --dataset senado --uf MG --year 2022
python -m scripts.sync --dataset all --uf MG --municipio 3122306 --year 2022
```

Use `--force` para ignorar o cache onde suportado. Downloads do TSE e Sinesp ficam em
`data/downloads/`; no Render esse diretório é apenas cache, nunca a fonte definitiva do dado persistido.

## Testes

```bash
pytest -q
```

A suíte cobre taxa por 100 mil, `NULL`, variação com base zero, normalização, ano bissexto, sobreposição
de mandato, múltiplos ocupantes no mesmo ano, cache, parsers IBGE/Câmara/TSE/Sinesp e filiação partidária
histórica.

## Deploy no Render

O arquivo `render.yaml` provisiona o serviço web e PostgreSQL. O processo inicia com:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

Dados importantes devem permanecer no PostgreSQL. Arquivos baixados no filesystem do Render são cache
recriável. Para volume e latência de produção, execute cargas grandes em um worker/cron separado.

## Limitações conhecidas e próximos conectores

- **Política municipal/estadual:** TSE comprova candidatura e resultado, não permanência diária no cargo.
  Prefeitos, vices, vereadores, governadores e deputados estaduais só devem aparecer em
  `office_exercises` após integração com a fonte oficial responsável, Diário Oficial ou outra evidência
  primária. Até lá a interface informa “sem exercício confirmado”.
- **Sinesp:** os arquivos VDE anuais atuais publicam UF e nome, mas não código IBGE. O conector aceita
  apenas correspondência exata do nome oficial normalizado dentro da mesma UF quando ela resolve um único
  código IBGE; casos ausentes ou ambíguos são recusados. O vínculo e os indicadores persistidos usam o
  código IBGE, recebem qualidade `partial` e mantêm a ressalva metodológica; ausência nunca vira zero.
- **TSE:** importações podem ser grandes. O arquivo é baixado uma vez, a leitura usa chunks e o município
  é relacionado por tabela oficial IBGE–TSE.
- **Câmara:** os eventos oficiais permitem intervalos reais, incluindo afastamento e retorno. A filiação
  mostrada no card é a do início do intervalo; eventos de troca permanecem no histórico da fonte.
- **Senado:** quando o XML não traz o nó de exercício, o intervalo da legislatura é marcado `partial`, não
  `verified`.
- **INEP, DATASUS, CAGED/RAIS e Siconfi:** módulos estão delimitados em `services/connectors.py`. Faltam os
  ETLs por layout/edição e testes de compatibilidade; nenhuma informação dessas fontes é simulada.

## Metodologia e neutralidade

Taxa por 100 mil:

```text
ocorrências / população de referência × 100.000
```

O dashboard não atribui nota a políticos, não declara qual gestão foi “melhor” e não transforma
correlação temporal em causalidade. Resultados eleitorais são históricos e oficiais; não há previsão.

