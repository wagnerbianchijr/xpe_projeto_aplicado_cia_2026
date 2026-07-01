# Design — Simulador IIoT (Python) · Serra Clara Bebidas S.A.

**Data:** 2026-07-01
**Componente:** `simulador`
**Status:** aprovado (aguardando revisão do spec)

## Contexto

O `simulador` é o "PLC" da solução: um processo Python que gera leituras dos sensores
das três linhas de produção e as grava na hypertable `sensor_reading` do TimescaleDB na
Tiger Cloud (serviço `h3bmabyk97`). O objetivo imediato é validar a gravação de métricas
end-to-end e alimentar as views e continuous aggregates do componente `modelo-de-dados`.

O Tiger MCP não autentica no serviço; o simulador conecta direto via driver Python
(`psycopg` 3) usando um DSN lido de variável de ambiente.

## Decisões de design

- **Modo de execução:** contínuo. Loop que gera e grava uma leitura por sensor a cada
  5 segundos até receber SIGINT (Ctrl+C). Sem backfill nesta versão.
- **Geração:** random walk realista com reversão à média, mais anomalias raras
  (excursões fora de faixa → `alerta`) e dropouts ocasionais (sensor para de enviar →
  alimenta `sensor_liveness`). `production_count` é um contador monotônico.
- **Configuração:** variáveis de ambiente via arquivo `.env` git-ignored; nenhum segredo
  no repositório.
- **Estrutura:** módulos por responsabilidade; `generator.py` é puro (sem I/O), o que o
  torna testável sem banco (TDD).

## Estrutura de arquivos

```
simulador/
  .env.example      # modelo de config (versionado); .env real fica git-ignored
  requirements.txt  # psycopg[binary]>=3, python-dotenv
  config.py         # lê .env -> dataclass Settings
  catalog.py        # SELECT do catálogo `sensor` -> lista de SensorSpec
  generator.py      # PURO: estado por sensor + random walk + anomalias + dropouts
  writer.py         # insert em lote das leituras via psycopg3
  main.py           # loop: a cada tick gera -> grava; trata SIGINT
  tests/
    test_generator.py  # determinístico (seed fixo), sem banco
```

**Fronteiras:**

- `generator.py` não conhece banco nem relógio real. Recebe as specs dos sensores e um
  timestamp, devolve leituras. 100% testável com um `random.Random(seed)` injetado.
- `catalog.py` e `writer.py` isolam todo o I/O de banco.
- `main.py` é o único módulo com o loop temporal e o tratamento de sinais.

## Modelo de geração (`generator.py`)

**Estado por sensor** (dict em memória, chave `sensor_id`):

- `last_value` — último valor gerado (base do random walk).
- `dropout_until` — timestamp até quando o sensor está mudo, ou `None`.
- `counter` — apenas para `production_count` (acumulado monotônico).

**Por tick, para cada sensor:**

1. **Dropout ativo?** Se `now < dropout_until`, não emite leitura.
2. **Iniciar dropout?** Com probabilidade `p_dropout` (default 0.002 por leitura), define
   `dropout_until = now + rand(30..120s)` e não emite.
3. **`production_count`:** `counter += rand(1..8)`; emite o acumulado (ignora o random walk).
4. **Demais métricas — random walk:**
   - baseline `b = (min_limit + max_limit) / 2`; amplitude `r = max_limit - min_limit`.
   - passo: `last_value += gauss(0, r * 0.02)`, com reversão à média (puxa 5% em direção a `b`).
   - clamp em `[min_limit - folga, max_limit + folga]`, folga = `r * 0.1`.
5. **Anomalia?** Com probabilidade `p_anomaly` (default 0.005 por leitura), empurra o valor
   para fora de `[min_limit, max_limit]` (gera `alerta` no `sensor_status`).

**Sensores sem `max_limit`** (`production_count`) seguem o caminho 3, nunca 4/5.

**Determinismo:** todo o aleatório vem de um `random.Random(seed)` injetado. Mesmo seed e
mesma sequência de ticks produzem a mesma saída — base dos testes.

**Saída:** lista de tuplas `(time, sensor_id, value, quality)` prontas para o `writer`.
`quality` é sempre `0` nesta versão (a coluna existe para evolução futura — YAGNI).

## Configuração (`config.py`)

Lê `.env` via `python-dotenv` e monta uma dataclass `Settings`:

- `DATABASE_URL` — DSN psycopg (obrigatório). Nunca versionado.
- `TICK_SECONDS` — default 5.
- `SEED` — opcional; se ausente, usa aleatoriedade do sistema.
- `P_ANOMALY` — default 0.005.
- `P_DROPOUT` — default 0.002.

`.env.example` (versionado) documenta as chaves sem valores reais. `.env` entra no
`.gitignore`.

## Escrita (`writer.py`)

Insere em lote as ~30 leituras de cada tick numa única transação:

```sql
INSERT INTO sensor_reading (time, sensor_id, value, quality) VALUES (%s, %s, %s, %s)
```

via `psycopg` (execução multi-linha / `executemany`). Volume trivial (~30 linhas/5s).

## Loop e resiliência (`main.py`)

1. Carrega `Settings` -> conecta -> carrega catálogo -> inicializa estado do generator.
2. A cada tick: `generate(now)` -> `writer.insert(readings)` -> dorme até o próximo
   múltiplo de `TICK_SECONDS` (evita drift de agenda).
3. **SIGINT (Ctrl+C):** encerra o loop de forma limpa e fecha a conexão.

**Resiliência:**

- Erro transitório de banco (rede/timeout): log + retry com backoff exponencial curto;
  o loop não morre.
- Leitura em dropout **não** vira linha — é assim que `sensor_liveness` detecta o sensor mudo.

## Testes

- `test_generator.py` (TDD, sem banco): determinismo com seed fixo; reversão à média
  mantém o valor perto do baseline ao longo de muitos ticks; clamp respeita
  `[min - folga, max + folga]`; `production_count` é estritamente crescente; dropout, uma
  vez ativado, suprime emissões pela janela; anomalia produz valor fora de `[min, max]`.
- Escrita real validada por um smoke run manual contra `h3bmabyk97`: rodar alguns ticks,
  conferir linhas em `sensor_reading` e o comportamento de `sensor_status`/`sensor_liveness`.

## Interfaces com outros componentes

- **modelo-de-dados:** lê o catálogo `sensor` e escreve em `sensor_reading`. Depende do
  schema já implantado (feito).
- **web-system:** consumirá as views/CAs que este simulador alimenta.

## Fora de escopo (YAGNI)

- Backfill de histórico (só modo contínuo agora).
- Escrita concorrente / múltiplos processos (um processo basta para ~30 sensores a 5s).
- `quality` diferente de 0.
- Empacotamento como serviço/daemon (systemd, container) — roda via `python main.py`.
