# web-system

Dashboard IIoT da **Serra Clara Bebidas S.A.** (FastAPI + HTMX + Chart.js).
Lê o Tiger Cloud (TimescaleDB, serviço `h3bmabyk97`) em modo **somente leitura**
e mostra indicadores operacionais e históricos.

## Telas

- **Visão geral** (`/`): cartões de KPI (OK / alerta / sem dados / falhos / linhas / produção do dia).
- **Operational Hub** (`/operational`): status por sensor em tempo real + sensores falhos, filtro por linha.
- **Performance Insights** (`/performance`): séries temporais dos agregados contínuos.
- **Detalhe do sensor** (`/sensor/{id}`): série com limites min/max + violações recentes.

## Configuração

Copie `.env.example` para `.env` (git-ignored) e defina `DATABASE_URL`:

    cp .env.example .env
    # edite DATABASE_URL

Variáveis: `DATABASE_URL` (obrigatória), `REFRESH_SECONDS` (padrão 5), `HOST`, `PORT`.

## Rodar

    python -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
    ./.venv/bin/python main.py      # http://127.0.0.1:8000

Ou via Uvicorn com reload em dev:

    ./.venv/bin/python -m uvicorn main:app --reload

## Testes

    ./.venv/bin/python -m pytest -v

Os testes usam duplês (`FakeDatabase`) e não exigem banco vivo.

## Deploy

`Dockerfile` empacota a app para deploy futuro em VPC (VPC Peering / Private Link
ao Tiger Cloud, provisionado pelo `terraform`):

    docker build -t serraclara-web .
    docker run -p 8000:8000 --env-file .env serraclara-web

## Arquitetura

`config.py` (env) → `db.py` (pool read-only + `fetch`) → `queries.py`
(SQL puro por indicador) → `app.py` (rotas FastAPI, páginas Jinja2 + fragmentos
HTMX + JSON p/ Chart.js). `aggregates.py` escolhe o agregado por janela e a
expressão de valor por métrica. `models.py` tipa os retornos.
