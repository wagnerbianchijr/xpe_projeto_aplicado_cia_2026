# Modelo de Dados (TimescaleDB) Implementation Plan


**Goal:** Build the TimescaleDB schema for Serra Clara Bebidas' IIoT solution — dimensions, a readings hypertable, hierarchical continuous aggregates, retention/compression policies, and support views — applied and validated directly on a Tiger Cloud service via the Tiger MCP.

**Architecture:** Hybrid dimension+fact model. `production_line` and `sensor` hold metadata; the narrow `sensor_reading` hypertable holds the time series. Continuous aggregates roll up hierarchically (raw → 1m → 15m → 30m → 1h). Views derive real-time status, out-of-range history, and sensor liveness. All DDL lives in ordered `.sql` files in `modelo-de-dados/sql/` for reproducibility and is executed on Tiger Cloud through `mcp__tiger__db_execute_query`.

**Tech Stack:** TimescaleDB on Tiger Cloud, SQL, Tiger MCP tools (`service_create`, `db_execute_query`, `service_get`).

---

## Conventions

- **SQL formatting:** leading commas, as in the existing project convention.
- **Target service:** use the existing Tiger Cloud service `h3bmabyk97` (db-73561, TIMESCALEDB). Every `mcp__tiger__db_execute_query` call uses `service_id = h3bmabyk97`. Where this plan writes `<SERVICE_ID>`, substitute `h3bmabyk97`.
- **"Test" = verification query.** For DDL, each task first runs a verification query proving the object is absent (fails/returns 0), then applies the SQL file, then re-runs the verification query proving it now exists/behaves correctly.
- **Every `.sql` file is applied by reading its contents and passing them as the `query` to `mcp__tiger__db_execute_query` (multi-statement is supported).**

## File Structure

- Create: `modelo-de-dados/sql/01_dimensions.sql` — `production_line`, `sensor` tables
- Create: `modelo-de-dados/sql/02_hypertable.sql` — `sensor_reading` table + `create_hypertable` + index
- Create: `modelo-de-dados/sql/03_compression_retention.sql` — compression settings + compression/retention policies
- Create: `modelo-de-dados/sql/04_continuous_aggregates.sql` — CAs 1m/15m/30m/1h
- Create: `modelo-de-dados/sql/05_ca_policies.sql` — CA refresh policies + CA retention policies
- Create: `modelo-de-dados/sql/06_views.sql` — `sensor_status`, `sensor_liveness`, `sensor_out_of_range_1h`
- Create: `modelo-de-dados/sql/07_seed.sql` — 3 lines + ~30 sensors
- Create: `modelo-de-dados/README.md` — apply order + how to run via Tiger MCP

---

### Task 1: Connect to the existing Tiger Cloud service

**Files:** none (infrastructure step)

- [ ] **Step 1: Confirm the service is reachable and TimescaleDB is available**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "h3bmabyk97",
  "query": "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
}
```
Expected: one row, `extname = timescaledb`, a 2.x `extversion`.
If this fails with `password authentication failed`, rotate the credential with
`mcp__tiger__service_update_password` (confirm with the user first), then retry.

- [ ] **Step 2: Confirm the service has none of our objects yet (avoid clobbering)**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "h3bmabyk97",
  "query": "SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('production_line','sensor','sensor_reading');"
}
```
Expected: `n = 0`. If not zero, stop and confirm with the user before proceeding.

- [ ] **Step 3: Record the service id in the component README**

Create `modelo-de-dados/README.md`:
```markdown
# modelo-de-dados

TimescaleDB schema for the Serra Clara Bebidas IIoT solution, applied to an
existing Tiger Cloud service via the Tiger MCP.

## Tiger Cloud service

- Service: `db-73561`
- service_id: `h3bmabyk97`

## Apply order

Apply the SQL files in numeric order via `mcp__tiger__db_execute_query`
(each file is idempotent-safe on a fresh service):

1. `sql/01_dimensions.sql`
2. `sql/02_hypertable.sql`
3. `sql/03_compression_retention.sql`
4. `sql/04_continuous_aggregates.sql`
5. `sql/05_ca_policies.sql`
6. `sql/06_views.sql`
7. `sql/07_seed.sql`

## Verify

See `docs/plans/2026-07-01-modelo-de-dados.md` for the per-object
verification queries.
```

- [ ] **Step 4: Commit**
```bash
git add modelo-de-dados/README.md
git commit -m "modelo-de-dados: record existing Tiger Cloud service (h3bmabyk97)"
```

---

### Task 2: Dimension tables (`production_line`, `sensor`)

**Files:**
- Create: `modelo-de-dados/sql/01_dimensions.sql`

- [ ] **Step 1: Verify the tables do not exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT count(*) AS n FROM information_schema.tables WHERE table_name IN ('production_line','sensor');"
}
```
Expected: `n = 0`.

- [ ] **Step 2: Write the DDL file**

Create `modelo-de-dados/sql/01_dimensions.sql`:
```sql
-- Dimension tables: production lines and their sensor catalog.

CREATE TABLE production_line (
    line_id       smallint PRIMARY KEY
  , name          text     NOT NULL
  , product_type  text     NOT NULL
      CHECK (product_type IN ('suco', 'agua_saborizada', 'cha_gelado'))
  , description   text
);

CREATE TABLE sensor (
    sensor_id          int      PRIMARY KEY
  , line_id            smallint NOT NULL REFERENCES production_line (line_id)
  , metric             text     NOT NULL
  , unit               text     NOT NULL
  , min_limit          double precision
  , max_limit          double precision
  , sample_interval_s  smallint NOT NULL DEFAULT 5
  , description        text
  , CONSTRAINT sensor_limits_ck CHECK (max_limit IS NULL OR min_limit IS NULL OR max_limit >= min_limit)
);

CREATE INDEX sensor_line_id_idx ON sensor (line_id);
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `service_id = <SERVICE_ID>` and `query` set to the full contents of `modelo-de-dados/sql/01_dimensions.sql`.
Expected: success, no error.

- [ ] **Step 4: Verify the tables and columns exist**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT table_name, count(*) AS cols FROM information_schema.columns WHERE table_name IN ('production_line','sensor') GROUP BY table_name ORDER BY table_name;"
}
```
Expected: `production_line` → 4 cols, `sensor` → 8 cols.

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/01_dimensions.sql
git commit -m "modelo-de-dados: add production_line and sensor dimension tables"
```

---

### Task 3: Readings hypertable (`sensor_reading`)

**Files:**
- Create: `modelo-de-dados/sql/02_hypertable.sql`

- [ ] **Step 1: Verify the hypertable does not exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT count(*) AS n FROM timescaledb_information.hypertables WHERE hypertable_name = 'sensor_reading';"
}
```
Expected: `n = 0`.

- [ ] **Step 2: Write the DDL file**

Create `modelo-de-dados/sql/02_hypertable.sql`:
```sql
-- Fact hypertable: raw sensor readings.

CREATE TABLE sensor_reading (
    time       timestamptz      NOT NULL
  , sensor_id  int              NOT NULL REFERENCES sensor (sensor_id)
  , value      double precision NOT NULL
  , quality    smallint         NOT NULL DEFAULT 0
);

SELECT create_hypertable(
    'sensor_reading'
  , 'time'
  , chunk_time_interval => INTERVAL '12 hours'
);

CREATE INDEX sensor_reading_sensor_time_idx
    ON sensor_reading (sensor_id, time DESC);
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `query` = full contents of `modelo-de-dados/sql/02_hypertable.sql`.
Expected: `create_hypertable` returns a row like `(hypertable_id, 'public', 'sensor_reading', t)`.

- [ ] **Step 4: Verify the hypertable and chunk interval**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT h.hypertable_name, d.time_interval FROM timescaledb_information.hypertables h JOIN timescaledb_information.dimensions d ON d.hypertable_name = h.hypertable_name WHERE h.hypertable_name = 'sensor_reading';"
}
```
Expected: one row, `time_interval = 12:00:00` (12 hours).

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/02_hypertable.sql
git commit -m "modelo-de-dados: add sensor_reading hypertable (12h chunks)"
```

---

### Task 4: Compression and retention policies

**Files:**
- Create: `modelo-de-dados/sql/03_compression_retention.sql`

- [ ] **Step 1: Verify no compression/retention jobs exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT count(*) AS n FROM timescaledb_information.jobs WHERE hypertable_name = 'sensor_reading' AND proc_name IN ('policy_compression','policy_retention');"
}
```
Expected: `n = 0`.

- [ ] **Step 2: Write the DDL file**

Create `modelo-de-dados/sql/03_compression_retention.sql`:
```sql
-- Compression settings and lifecycle policies for raw readings.

ALTER TABLE sensor_reading SET (
    timescaledb.compress
  , timescaledb.compress_segmentby = 'sensor_id'
  , timescaledb.compress_orderby   = 'time DESC'
);

-- Compress chunks older than 7 days.
SELECT add_compression_policy('sensor_reading', INTERVAL '7 days');

-- Drop raw chunks older than 90 days.
SELECT add_retention_policy('sensor_reading', INTERVAL '90 days');
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `query` = full contents of `modelo-de-dados/sql/03_compression_retention.sql`.
Expected: two rows returned, each a numeric job id.

- [ ] **Step 4: Verify both policies exist**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT proc_name, config FROM timescaledb_information.jobs WHERE hypertable_name = 'sensor_reading' AND proc_name IN ('policy_compression','policy_retention') ORDER BY proc_name;"
}
```
Expected: two rows — `policy_compression` (config mentions `compress_after` / 7 days) and `policy_retention` (config mentions `drop_after` / 90 days).

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/03_compression_retention.sql
git commit -m "modelo-de-dados: add compression (7d) and retention (90d) policies"
```

---

### Task 5: Hierarchical continuous aggregates

**Files:**
- Create: `modelo-de-dados/sql/04_continuous_aggregates.sql`

- [ ] **Step 1: Verify no continuous aggregates exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT count(*) AS n FROM timescaledb_information.continuous_aggregates WHERE view_name LIKE 'sensor_reading_%';"
}
```
Expected: `n = 0`.

- [ ] **Step 2: Write the DDL file**

Create `modelo-de-dados/sql/04_continuous_aggregates.sql`:
```sql
-- Hierarchical continuous aggregates: raw -> 1m -> 15m -> 30m -> 1h.
-- Each level keeps sum + count so avg is recomputed correctly upstream
-- (avg = sum_value / count_value). production_count throughput = max - min.

-- Level 1: 1 minute, from raw readings.
CREATE MATERIALIZED VIEW sensor_reading_1m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 minute', time) AS bucket
  , sensor_id
  , sum(value)          AS sum_value
  , count(*)            AS count_value
  , min(value)          AS min_value
  , max(value)          AS max_value
  , last(value, time)   AS last_value
FROM sensor_reading
GROUP BY 1, 2
WITH NO DATA;

-- Level 2: 15 minutes, from the 1m aggregate.
CREATE MATERIALIZED VIEW sensor_reading_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '15 minutes', bucket) AS bucket
  , sensor_id
  , sum(sum_value)            AS sum_value
  , sum(count_value)          AS count_value
  , min(min_value)            AS min_value
  , max(max_value)            AS max_value
  , last(last_value, bucket)  AS last_value
FROM sensor_reading_1m
GROUP BY 1, 2
WITH NO DATA;

-- Level 3: 30 minutes, from the 15m aggregate.
CREATE MATERIALIZED VIEW sensor_reading_30m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '30 minutes', bucket) AS bucket
  , sensor_id
  , sum(sum_value)            AS sum_value
  , sum(count_value)          AS count_value
  , min(min_value)            AS min_value
  , max(max_value)            AS max_value
  , last(last_value, bucket)  AS last_value
FROM sensor_reading_15m
GROUP BY 1, 2
WITH NO DATA;

-- Level 4: 1 hour, from the 30m aggregate.
CREATE MATERIALIZED VIEW sensor_reading_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(INTERVAL '1 hour', bucket) AS bucket
  , sensor_id
  , sum(sum_value)            AS sum_value
  , sum(count_value)          AS count_value
  , min(min_value)            AS min_value
  , max(max_value)            AS max_value
  , last(last_value, bucket)  AS last_value
FROM sensor_reading_30m
GROUP BY 1, 2
WITH NO DATA;
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `query` = full contents of `modelo-de-dados/sql/04_continuous_aggregates.sql`.
Expected: success, no error (four materialized views created with no data).

- [ ] **Step 4: Verify all four CAs exist and are hierarchical where expected**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT view_name FROM timescaledb_information.continuous_aggregates WHERE view_name LIKE 'sensor_reading_%' ORDER BY view_name;"
}
```
Expected: four rows — `sensor_reading_15m`, `sensor_reading_1h`, `sensor_reading_1m`, `sensor_reading_30m`.

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/04_continuous_aggregates.sql
git commit -m "modelo-de-dados: add hierarchical continuous aggregates (1m/15m/30m/1h)"
```

---

### Task 6: Continuous aggregate refresh and retention policies

**Files:**
- Create: `modelo-de-dados/sql/05_ca_policies.sql`

- [ ] **Step 1: Verify no CA policies exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT count(*) AS n FROM timescaledb_information.jobs WHERE proc_name IN ('policy_refresh_continuous_aggregate','policy_retention') AND hypertable_name LIKE 'sensor_reading_%';"
}
```
Expected: `n = 0`.

- [ ] **Step 2: Write the DDL file**

Create `modelo-de-dados/sql/05_ca_policies.sql`:
```sql
-- Refresh policies (parent refreshes before child via increasing offsets)
-- and 1-year retention on every aggregate level.

-- 1m: refresh the last 10 minutes every minute.
SELECT add_continuous_aggregate_policy('sensor_reading_1m'
  , start_offset      => INTERVAL '10 minutes'
  , end_offset        => INTERVAL '1 minute'
  , schedule_interval => INTERVAL '1 minute');

-- 15m: refresh the last 2 hours every 5 minutes.
SELECT add_continuous_aggregate_policy('sensor_reading_15m'
  , start_offset      => INTERVAL '2 hours'
  , end_offset        => INTERVAL '15 minutes'
  , schedule_interval => INTERVAL '5 minutes');

-- 30m: refresh the last 4 hours every 15 minutes.
SELECT add_continuous_aggregate_policy('sensor_reading_30m'
  , start_offset      => INTERVAL '4 hours'
  , end_offset        => INTERVAL '30 minutes'
  , schedule_interval => INTERVAL '15 minutes');

-- 1h: refresh the last 8 hours every 30 minutes.
SELECT add_continuous_aggregate_policy('sensor_reading_1h'
  , start_offset      => INTERVAL '8 hours'
  , end_offset        => INTERVAL '1 hour'
  , schedule_interval => INTERVAL '30 minutes');

-- Retain every aggregate level for 1 year.
SELECT add_retention_policy('sensor_reading_1m',  INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_15m', INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_30m', INTERVAL '1 year');
SELECT add_retention_policy('sensor_reading_1h',  INTERVAL '1 year');
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `query` = full contents of `modelo-de-dados/sql/05_ca_policies.sql`.
Expected: eight rows returned (four refresh job ids + four retention job ids).

- [ ] **Step 4: Verify four refresh policies and four CA retention policies exist**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT proc_name, count(*) AS n FROM timescaledb_information.jobs WHERE proc_name IN ('policy_refresh_continuous_aggregate','policy_retention') AND hypertable_name LIKE 'sensor_reading_%' GROUP BY proc_name ORDER BY proc_name;"
}
```
Expected: `policy_refresh_continuous_aggregate` → 4, `policy_retention` → 4.

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/05_ca_policies.sql
git commit -m "modelo-de-dados: add CA refresh policies and 1y aggregate retention"
```

---

### Task 7: Support views (status, liveness, out-of-range)

**Files:**
- Create: `modelo-de-dados/sql/06_views.sql`

- [ ] **Step 1: Verify the views do not exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT count(*) AS n FROM information_schema.views WHERE table_name IN ('sensor_status','sensor_liveness','sensor_out_of_range_1h');"
}
```
Expected: `n = 0`.

- [ ] **Step 2: Write the DDL file**

Create `modelo-de-dados/sql/06_views.sql`:
```sql
-- Support views for the web dashboard.

-- Real-time status: latest raw reading per sensor vs its operating limits.
CREATE VIEW sensor_status AS
SELECT
    s.sensor_id
  , s.line_id
  , s.metric
  , s.unit
  , lr.value
  , lr.time AS last_time
  , CASE
        WHEN lr.value IS NULL                                   THEN 'sem_dados'
        WHEN lr.value < s.min_limit OR lr.value > s.max_limit   THEN 'alerta'
        ELSE 'normal'
    END AS status
FROM sensor s
LEFT JOIN LATERAL (
    SELECT r.value, r.time
    FROM sensor_reading r
    WHERE r.sensor_id = s.sensor_id
    ORDER BY r.time DESC
    LIMIT 1
) lr ON true;

-- Liveness: sensors that missed their expected reading window.
-- is_failed when no data ever, or last reading older than 2x sample interval.
CREATE VIEW sensor_liveness AS
SELECT
    s.sensor_id
  , s.line_id
  , s.metric
  , lr.last_time
  , EXTRACT(EPOCH FROM (now() - lr.last_time)) AS seconds_since_last
  , (
        lr.last_time IS NULL
        OR now() - lr.last_time > make_interval(secs => s.sample_interval_s * 2)
    ) AS is_failed
FROM sensor s
LEFT JOIN LATERAL (
    SELECT max(r.time) AS last_time
    FROM sensor_reading r
    WHERE r.sensor_id = s.sensor_id
) lr ON true;

-- Out-of-range history: hourly buckets whose min/max breached the sensor limits.
CREATE VIEW sensor_out_of_range_1h AS
SELECT
    a.bucket
  , a.sensor_id
  , s.line_id
  , s.metric
  , (a.min_value < s.min_limit OR a.max_value > s.max_limit) AS violated
FROM sensor_reading_1h a
JOIN sensor s ON s.sensor_id = a.sensor_id;
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `query` = full contents of `modelo-de-dados/sql/06_views.sql`.
Expected: success, three views created.

- [ ] **Step 4: Verify the three views exist**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT table_name FROM information_schema.views WHERE table_name IN ('sensor_status','sensor_liveness','sensor_out_of_range_1h') ORDER BY table_name;"
}
```
Expected: three rows — `sensor_liveness`, `sensor_out_of_range_1h`, `sensor_status`.

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/06_views.sql
git commit -m "modelo-de-dados: add status, liveness, and out-of-range views"
```

---

### Task 8: Seed data (3 lines, ~30 sensors)

**Files:**
- Create: `modelo-de-dados/sql/07_seed.sql`

- [ ] **Step 1: Verify no dimension rows exist yet**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT (SELECT count(*) FROM production_line) AS lines, (SELECT count(*) FROM sensor) AS sensors;"
}
```
Expected: `lines = 0`, `sensors = 0`.

- [ ] **Step 2: Write the seed file**

Create `modelo-de-dados/sql/07_seed.sql`:
```sql
-- Seed: three production lines (one per product type) and their sensors.
-- 8 common sensors + 2 line-specific sensors per line = 30 sensors total.
-- sensor_id encodes line: line 1 -> 1xx, line 2 -> 2xx, line 3 -> 3xx.

INSERT INTO production_line (line_id, name, product_type, description) VALUES
    (1, 'Linha Sucos 01',            'suco',            'Linha de produção de sucos')
  , (2, 'Linha Águas Saborizadas 01','agua_saborizada', 'Linha de produção de águas saborizadas')
  , (3, 'Linha Chás Gelados 01',     'cha_gelado',      'Linha de produção de chás gelados');

-- Common sensors (present on every line). limits are operating ranges.
-- metric, unit, min, max templated per line below.
INSERT INTO sensor (sensor_id, line_id, metric, unit, min_limit, max_limit, sample_interval_s, description) VALUES
  -- Line 1 (sucos) common
    (101, 1, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (102, 1, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (103, 1, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (104, 1, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (105, 1, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (106, 1, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (107, 1, 'ph',               'pH',     3.0,  4.5, 5, 'pH do produto')
  , (108, 1, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Line 1 (sucos) specific
  , (109, 1, 'brix',             '°Bx',   10.0, 14.0, 5, 'Teor de açúcar (°Brix)')
  , (110, 1, 'turbidity',        'NTU',    0.0, 50.0, 5, 'Turbidez')
  -- Line 2 (águas saborizadas) common
  , (201, 2, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (202, 2, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (203, 2, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (204, 2, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (205, 2, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (206, 2, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (207, 2, 'ph',               'pH',     3.0,  4.5, 5, 'pH do produto')
  , (208, 2, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Line 2 (águas saborizadas) specific
  , (209, 2, 'co2',              'g/L',    4.0,  8.0, 5, 'CO2 dissolvido')
  , (210, 2, 'conductivity',     'µS/cm', 50.0,500.0, 5, 'Condutividade da água')
  -- Line 3 (chás gelados) common
  , (301, 3, 'temperature',      '°C',    70.0, 95.0, 5, 'Temperatura de pasteurização')
  , (302, 3, 'pressure',         'bar',    1.0,  3.5, 5, 'Pressão da linha de enchimento')
  , (303, 3, 'flow',             'L/min', 20.0, 60.0, 5, 'Vazão de enchimento')
  , (304, 3, 'tank_level',       '%',     10.0, 95.0, 5, 'Nível do tanque de mistura')
  , (305, 3, 'line_speed',       'bpm',  200.0,600.0, 5, 'Velocidade da linha (garrafas/min)')
  , (306, 3, 'production_count', 'count',  0.0, NULL, 5, 'Contador acumulado de produção')
  , (307, 3, 'ph',               'pH',     3.0,  6.0, 5, 'pH do produto')
  , (308, 3, 'ambient_temp',     '°C',    15.0, 30.0, 5, 'Temperatura ambiente')
  -- Line 3 (chás gelados) specific
  , (309, 3, 'infusion_temp',    '°C',    80.0, 98.0, 5, 'Temperatura de infusão')
  , (310, 3, 'turbidity',        'NTU',    0.0, 50.0, 5, 'Turbidez');
```

- [ ] **Step 3: Apply the file**

Run `mcp__tiger__db_execute_query` with `query` = full contents of `modelo-de-dados/sql/07_seed.sql`.
Expected: success; 3 rows into `production_line`, 30 rows into `sensor`.

- [ ] **Step 4: Verify seed counts and per-line sensor distribution**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT (SELECT count(*) FROM production_line) AS lines, (SELECT count(*) FROM sensor) AS sensors, (SELECT count(DISTINCT line_id) FROM sensor) AS lines_with_sensors;"
}
```
Expected: `lines = 3`, `sensors = 30`, `lines_with_sensors = 3`.

- [ ] **Step 5: Commit**
```bash
git add modelo-de-dados/sql/07_seed.sql
git commit -m "modelo-de-dados: seed 3 lines and 30 sensors"
```

---

### Task 9: End-to-end behavioral smoke test

**Files:** none (validation against inserted sample data)

This task proves the views and aggregates behave correctly using a small,
controlled set of readings, then cleans up so the table is empty for the simulator.

- [ ] **Step 1: Insert controlled sample readings**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "INSERT INTO sensor_reading (time, sensor_id, value, quality) VALUES (now(), 101, 85.0, 0), (now(), 102, 5.0, 0), (now() - INTERVAL '1 minute', 103, 40.0, 0);"
}
```
Expected: 3 rows inserted. (sensor 101 in range → normal; sensor 102 value 5.0 > max 3.5 → alerta; sensor 103 last reading 1 min old.)

- [ ] **Step 2: Verify real-time status classification**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT sensor_id, status FROM sensor_status WHERE sensor_id IN (101,102) ORDER BY sensor_id;"
}
```
Expected: `101 → normal`, `102 → alerta`.

- [ ] **Step 3: Verify liveness flags stale/absent sensors**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT (SELECT is_failed FROM sensor_liveness WHERE sensor_id = 101) AS s101_fresh, (SELECT is_failed FROM sensor_liveness WHERE sensor_id = 103) AS s103_stale, (SELECT is_failed FROM sensor_liveness WHERE sensor_id = 108) AS s108_never;"
}
```
Expected: `s101_fresh = false` (just reported), `s103_stale = true` (1 min > 2×5s), `s108_never = true` (never reported).

- [ ] **Step 4: Verify the 1m continuous aggregate materializes on demand**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "CALL refresh_continuous_aggregate('sensor_reading_1m', now() - INTERVAL '10 minutes', now() + INTERVAL '1 minute'); SELECT sensor_id, count_value, sum_value / count_value AS avg_value FROM sensor_reading_1m WHERE sensor_id = 101;"
}
```
Expected: one row for sensor 101 with `count_value >= 1` and `avg_value = 85.0`.

- [ ] **Step 5: Clean up sample data**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "TRUNCATE sensor_reading; CALL refresh_continuous_aggregate('sensor_reading_1m', now() - INTERVAL '10 minutes', now() + INTERVAL '1 minute');"
}
```
Expected: success; `sensor_reading` empty, aggregate re-refreshed to reflect the empty range.

- [ ] **Step 6: Final verification — full object inventory**

Run `mcp__tiger__db_execute_query`:
```json
{
  "service_id": "<SERVICE_ID>",
  "query": "SELECT (SELECT count(*) FROM timescaledb_information.hypertables WHERE hypertable_name = 'sensor_reading') AS hypertables, (SELECT count(*) FROM timescaledb_information.continuous_aggregates WHERE view_name LIKE 'sensor_reading_%') AS caggs, (SELECT count(*) FROM information_schema.views WHERE table_name IN ('sensor_status','sensor_liveness','sensor_out_of_range_1h')) AS views, (SELECT count(*) FROM sensor) AS sensors;"
}
```
Expected: `hypertables = 1`, `caggs = 4`, `views = 3`, `sensors = 30`.

- [ ] **Step 7: Commit the completed component doc**

Update `modelo-de-dados/README.md` to add a "Status: complete" line and the verified object inventory, then:
```bash
git add modelo-de-dados/README.md
git commit -m "modelo-de-dados: mark schema complete and record verified inventory"
```

---

## Notes for the implementer

- **Hierarchical CA refresh order:** a child CA (e.g. 15m) only sees data already materialized in its parent (1m). In production the staggered refresh policies handle this; in the Task 9 smoke test we refresh the 1m level explicitly. If you ever need 15m/30m/1h populated immediately, refresh them in order (1m → 15m → 30m → 1h).
- **`avg` is never stored.** Always compute `sum_value / count_value` in queries and in the web layer. This keeps averages correct across the hierarchy.
- **Retention on CAs vs raw:** raw drops at 90 days, aggregates at 1 year. The web dashboard's long-range views (Performance Insights) must read from the aggregates, not raw, for data older than 90 days.
- **`production_count` throughput:** compute `max_value - min_value` per bucket for production; do not use `sum`/`avg` on that metric.
