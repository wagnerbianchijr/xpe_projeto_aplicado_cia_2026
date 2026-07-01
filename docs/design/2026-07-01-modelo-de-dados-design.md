# Design — Modelo de Dados (TimescaleDB) · Serra Clara Bebidas S.A.

**Data:** 2026-07-01
**Componente:** `modelo-de-dados`
**Status:** aprovado (aguardando revisão do spec)

## Contexto

Solução em nuvem para coleta de dados IIoT da Serra Clara Bebidas S.A. Um simulador
Python atua como PLC, gera leituras de sensores e as insere num banco TimescaleDB na
Tiger Cloud. Um sistema web lê os dados via VPC Peering/Private Link e exibe indicadores
em duas abas: **Operational Hub** e **Performance Insights**.

Planta: três linhas de produção, uma de cada tipo — **sucos**, **águas saborizadas**,
**chás gelados**. O modelo usa `line_id`/`sensor_id` para permitir múltiplas linhas no
futuro sem refazer o schema.

## Decisões de design

- **Abordagem híbrida (dimensão + fato):** tabelas de referência normalizadas
  (`production_line`, `sensor`) + hypertable estreita (`sensor_reading`). Padrão IIoT do
  TimescaleDB: separa metadado de série temporal, mantém a hypertable enxuta para
  compressão, e adicionar um sensor é 1 linha em `sensor` (sem DDL).
- **Amostragem:** 1 leitura por sensor a cada 5s.
- **Escala:** ~10 sensores por linha × 3 linhas ≈ 30 sensores → ~518k linhas/dia,
  ~46M linhas em 90 dias.
- **Retenção:** raw 90 dias; continuous aggregates 1 ano.

## Sensores por linha

**Comuns às 3 linhas (8):** `temperature` (°C), `pressure` (bar), `flow` (L/min),
`tank_level` (%), `line_speed` (bpm), `production_count` (contador acumulado),
`ph` (pH), `ambient_temp` (°C).

**Específicos (2 por linha):**
- Sucos → `brix` (°Bx), `turbidity` (NTU)
- Águas saborizadas → `co2` (g/L), `conductivity` (µS/cm)
- Chás gelados → `infusion_temp` (°C), `turbidity` (NTU)

## Schema

### Dimensão: `production_line`

| coluna | tipo | nota |
|---|---|---|
| `line_id` | smallint PK | |
| `name` | text | ex.: "Linha Sucos 01" |
| `product_type` | text | `suco` \| `agua_saborizada` \| `cha_gelado` |
| `description` | text | |

Seed: 3 linhas (uma de cada `product_type`).

### Dimensão: `sensor`

| coluna | tipo | nota |
|---|---|---|
| `sensor_id` | int PK | |
| `line_id` | smallint FK → production_line | |
| `metric` | text | uma das métricas listadas acima |
| `unit` | text | °C, bar, L/min, %, bpm, °Bx, NTU, g/L, µS/cm, pH |
| `min_limit` | double precision | limite inferior da faixa normal |
| `max_limit` | double precision | limite superior da faixa normal |
| `sample_interval_s` | smallint DEFAULT 5 | intervalo esperado de amostragem (liveness) |
| `description` | text | |

Seed: ~30 sensores (8 comuns + 2 específicos por linha).

### Fato: `sensor_reading` (hypertable)

| coluna | tipo | nota |
|---|---|---|
| `time` | timestamptz NOT NULL | instante da leitura |
| `sensor_id` | int FK → sensor | |
| `value` | double precision | valor lido |
| `quality` | smallint DEFAULT 0 | flag de qualidade (0 = boa) |

- Hypertable em `time`, `chunk_interval = 12 horas` (~180 chunks em 90 dias, ~259k linhas/chunk).
- Índice: `(sensor_id, time DESC)`.
- Compressão: `segmentby = sensor_id`, `orderby = time DESC`, após **7 dias**.
- Retenção: drop de chunks raw após **90 dias**.

## Continuous aggregates (hierárquicos)

Cadeia: **raw → 1m → 15m → 30m → 1h** (cada bucket é múltiplo exato do pai).

| CA | bucket | derivado de | uso |
|---|---|---|---|
| `sensor_reading_1m` | 1 min | `sensor_reading` (raw) | status recente, tendências curtas |
| `sensor_reading_15m` | 15 min | `sensor_reading_1m` | Operational Hub |
| `sensor_reading_30m` | 30 min | `sensor_reading_15m` | Operational Hub / Performance Insights |
| `sensor_reading_1h` | 1 h | `sensor_reading_30m` | Performance Insights, comparação entre linhas |

**Colunas por bucket:** `sum(value)`, `count(*)`, `min(value)`, `max(value)`,
`last(value, time)`. A média é recomputada como `avg = sum/count` em cada nível — reusar
`avg` de um CA-pai distorceria a média nos níveis superiores. Para `production_count`
(contador acumulado), produção do bucket = `max(value) - min(value)`.

**Políticas:**

| política | alvo | regra |
|---|---|---|
| refresh CA | 1m → 15m → 30m → 1h | contínuo, escalonado por nível |
| compressão | `sensor_reading` | após 7 dias |
| retenção raw | `sensor_reading` | drop após 90 dias |
| retenção agregados | 1m, 15m, 30m, 1h | manter 1 ano |

## Views de apoio

### Status normal/alerta (tempo real)

View que junta a última leitura (`last`) de cada sensor com `min_limit`/`max_limit`:
- `value` dentro da faixa → **normal**
- fora da faixa → **alerta**

### Fora-de-faixa (histórico)

View/consulta sobre os CAs comparando `min`/`max` do bucket com os limites do sensor;
conta buckets com violação por linha/sensor. Sem tabela extra.

### Liveness / sensores mudos

`sensor_liveness` — junta o catálogo `sensor` com `max(time)` da última leitura de cada
sensor, lido de `sensor_reading` cru (não do CA de 1m, que tem atraso de refresh):
- `seconds_since_last = now() - last_time`
- `is_failed = seconds_since_last > sample_interval_s × tolerância` (tolerância padrão 2 →
  falhou se sem dados há > 2× o intervalo esperado)

Alimenta o gráfico web de **sensores que falharam em enviar dados na última leitura**,
por linha. Detecção por *ausência* de linha, não por flag de qualidade.

## Fluxo de dados

```
simulador (Python, "PLC")
  └─ INSERT em lote em sensor_reading (sensor_id vindo do seed), a cada 5s
       └─ TimescaleDB @ Tiger Cloud
            ├─ compressão (7d) · retenção raw (90d)
            ├─ CAs 1m→15m→30m→1h (retidos 1 ano)
            └─ web-system lê via VPC Peering / Private Link
                 ├─ Operational Hub      → última leitura + status + liveness + CAs 1m/15m/30m
                 └─ Performance Insights → CAs 30m/1h, throughput, comparação entre linhas
```

## Interfaces com outros componentes

- **simulador:** lê o catálogo `sensor` (seed), gera valores realistas por métrica (ruído
  em torno de baseline, dentro/ocasionalmente fora dos limites) e injeta *dropouts*
  ocasionais (sensor para de enviar) para alimentar o gráfico de liveness. Insere em lote
  a cada 5s. Design detalhado no brainstorming do componente `simulador`.
- **terraform:** provisiona VPC, subnets e o peering/private link para o serviço Tiger
  Cloud consumido pelo `web-system`.
- **web-system:** consome as views (status, liveness) e os CAs (tendências, throughput)
  via VPC; renderiza as abas Operational Hub e Performance Insights.

## Fora de escopo (YAGNI)

- Múltiplas linhas por tipo de produto (o schema suporta, o seed não cria).
- Frequências de amostragem mistas (coluna `sample_interval_s` já preparada; seed usa 5s).
- Tabela dedicada de histórico de alertas (views cobrem a necessidade atual).
