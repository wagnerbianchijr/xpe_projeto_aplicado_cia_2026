# web-system — Design

Dashboard web da solução IIoT da **Serra Clara Bebidas S.A.** Lê o Tiger Cloud
(TimescaleDB, serviço `h3bmabyk97`) e expõe indicadores operacionais e históricos.
Último componente após `simulador` (gerador) e `modelo-de-dados` (schema).

## Stack

- **Backend:** FastAPI + Uvicorn (Python 3, coerente com o simulador).
- **Banco:** psycopg 3 com pool assíncrono; acesso **somente leitura**.
- **Frontend:** Jinja2 (server-rendered) + HTMX (polling/refresh) + Chart.js (séries).
- **Conexão:** local via `DATABASE_URL` em `.env` (git-ignored, mesmo padrão do simulador).
  VPC Peering / Private Link é a arquitetura-alvo, entregue pelo `terraform`; não bloqueia este dev.
- **Idioma da UI:** pt-BR.
- **Deploy:** um container Uvicorn (Dockerfile incluído para deploy futuro em VPC).

## Estrutura (unidades isoladas, uma responsabilidade cada)

```
web-system/
  config.py       # lê DATABASE_URL, REFRESH_SECONDS, HOST/PORT (dotenv)
  db.py           # pool psycopg async; helper fetch() somente-leitura
  queries.py      # SQL puro (leading commas) -> funções tipadas; 1 função por indicador
  models.py       # dataclasses de retorno (KpiSummary, SensorStatusRow, TimeseriesPoint...)
  app.py          # FastAPI: rotas de página + rotas /api (fragmentos HTMX / JSON p/ Chart.js)
  templates/      # base.html, overview (KPIs), operational.html, performance.html,
                  # sensor_detail.html + partials
  static/         # css, chart.js init
  tests/          # pytest: queries.py com dados sintéticos, rotas via TestClient
  .env.example    # DATABASE_URL, REFRESH_SECONDS=5
  Dockerfile      # empacota p/ deploy futuro em VPC
  README.md
```

## Telas e fonte de dados

Todas as fontes já existem no schema (`modelo-de-dados`, completo).

| Tela | Rotas | Fonte |
|---|---|---|
| KPIs (header comum) | `/` + `GET /api/kpis` | agrega `sensor_status` + `sensor_liveness` |
| Operational Hub | `/operational` + `GET /api/operational` | `sensor_status`, `sensor_liveness`; filtro `line_id` |
| Performance Insights | `/performance` + `GET /api/timeseries` | `sensor_reading_1m/15m/30m/1h`, `sensor_out_of_range_1h` |
| Detalhe do sensor | `/sensor/{id}` + `GET /api/sensor/{id}/series` | agregado + limites de `sensor` |

### KPIs (Visão geral)

Cards no header comum a todas as abas: sensores OK vs em alerta (de `sensor_status`),
linhas ativas, sensores falhos (de `sensor_liveness`), produção total do dia
(soma de throughput dos sensores `production_count`).

### Operational Hub (tempo real)

Tabela de status por sensor (normal / alerta / sem_dados) com último valor e horário,
mais lista de sensores falhos (liveness). Filtro por `line_id`. Auto-refresh HTMX.

### Performance Insights (histórico)

Gráficos de série temporal por métrica a partir dos agregados contínuos, e destaque de
buckets com violação de limite (`sensor_out_of_range_1h`). Seleção de janela e linha.

### Detalhe do sensor

Drill-down de um sensor: gráfico da série com faixas de limite min/max, e histórico de
violações.

## Fluxo de dados

```
browser --HTMX polling (hx-trigger="every {REFRESH_SECONDS}s")--> FastAPI /api
  -> queries.py -> pool psycopg -> fragmento HTML (KPIs/tabelas) ou JSON (Chart.js)
```

Refresh padrão 5s (igual ao tick do simulador).

## Escolha de agregado (Performance)

Por janela solicitada:

- ≤ 1h  → `sensor_reading_1m`
- ≤ 6h  → `sensor_reading_15m`
- ≤ 24h → `sensor_reading_30m`
- > 24h → `sensor_reading_1h`

Cálculo por métrica:

- `production_count`: throughput do bucket = `max_value - min_value`.
- demais métricas: média = `sum_value / count_value`.

## Tratamento de erros

- Falha de conexão com o banco: páginas renderizam com banner "sem conexão com o banco"
  e indicadores vazios, sem quebrar. O simulador não precisa estar rodando.
- Sensor inexistente: HTTP 404.
- Pool com timeout curto para não travar requisições.

## Testes

pytest (padrão do simulador). Testar `queries.py` contra dados sintéticos e as rotas via
`TestClient` (mock do pool), sem exigir banco vivo no CI.

## Fora de escopo (YAGNI)

Autenticação, qualquer escrita no banco, VPC/deploy real (fica no `terraform`),
alertas/notificações.
