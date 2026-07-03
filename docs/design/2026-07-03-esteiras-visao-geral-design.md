# Esteiras na Visão Geral — Design

Complemento visual à aba **Visão Geral** do web-system: uma **esteira animada por linha
de produção** (3 no total) com um **farol de status** (verde/amarelo/vermelho) dando a
visão geral da produção de cada linha.

## Regra de status (por linha)

Derivada das views existentes (`sensor_status` + `sensor_liveness`), agregadas por linha:

- 🔴 **vermelho** — há algum sensor em `alerta` (valor fora dos limites).
- 🟡 **amarelo** — sem `alerta`, mas há sensores `sem_dados` ou falhos (liveness).
- 🟢 **verde** — todos `normal` e nenhum falho.

Precedência: `alerta` > (`sem_dados`/falho) > tudo ok.

## Componentes

### Dados (`queries.py` + `models.py`)

`line_overview(db) -> list[LineOverview]`:

```sql
SELECT
    pl.line_id
  , pl.name AS line_name
  , count(*) FILTER (WHERE ss.status = 'normal')    AS ok
  , count(*) FILTER (WHERE ss.status = 'alerta')    AS alerta
  , count(*) FILTER (WHERE ss.status = 'sem_dados') AS sem_dados
  , count(*) FILTER (WHERE sl.is_failed)            AS failed
FROM production_line pl
JOIN sensor_status ss   ON ss.line_id = pl.line_id
JOIN sensor_liveness sl ON sl.sensor_id = ss.sensor_id
GROUP BY pl.line_id, pl.name
ORDER BY pl.line_id
```

`LineOverview(line_id, line_name, ok, alerta, sem_dados, failed)` com uma propriedade
`status` que retorna `"vermelho" | "amarelo" | "verde"` pela regra acima.

### Rota / template (`app.py` + templates)

- `GET /api/lines` → renderiza `partials/lines.html` com a lista de `LineOverview`,
  envolto em `safe()`/`_DbError` (banner "sem conexão" em falha).
- `overview.html` ganha um container `#lines` com
  `hx-get="/api/lines" hx-trigger="load, refresh-tick from:body" hx-swap="innerHTML"`
  — atualiza junto com os KPIs (só dados, sem recarregar a página).

### Visual (`partials/lines.html` + `static/app.css`)

- **SVG inline** por linha (autocontido; sem assets externos → CSP-safe): correia com
  roletes e alguns itens (garrafas) sobre ela.
- **Animação CSS** (`@keyframes`): itens deslizam continuamente quando a linha está
  produzindo (verde/amarelo); quando **vermelho**, `animation-play-state: paused` e a
  correia fica esmaecida (parada).
- **Farol de status**: círculo colorido (verde `--ok` / amarelo `--warn` / vermelho
  `--bad`) com leve brilho/pulse.
- Rótulo com nome da linha + resumo (`ok / alerta / falhos`).
- Grid responsivo (`.conveyor-grid`, 3 colunas → empilha em telas estreitas).

## Testes

- `line_overview` via `FakeDatabase` (mapeamento + regra de status).
- `GET /api/lines` via `TestClient`: 3 linhas renderizadas, classes de status corretas,
  e caminho de banner no db-down.

## Deploy

O web-system roda no EC2 (código via S3). Após implementar e testar (FakeDatabase), o
deploy no dashboard público: `terraform apply` atualiza o objeto no S3, depois o EC2
re-baixa o código e reinicia o `websystem.service` (via SSM). Ajuste visual final
conferido no HTTPS do EC2.

## Fora de escopo (YAGNI)

- Interatividade/clique na esteira, métricas por item, throughput animado proporcional.
- Imagens raster; qualquer dependência/asset externo.
