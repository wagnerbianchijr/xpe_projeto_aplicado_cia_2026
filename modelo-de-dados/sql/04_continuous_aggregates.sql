-- Agregados contínuos hierárquicos: cru -> 1m -> 15m -> 30m -> 1h.
-- Cada nível mantém sum + count para que a média seja recalculada corretamente
-- nos níveis acima (média = sum_value / count_value). Throughput do
-- production_count = max - min.
--
-- materialized_only = false habilita a agregação em tempo real: as consultas
-- fazem UNION dos buckets materializados com uma agregação ao vivo das linhas
-- recentes ainda não materializadas, então o dashboard mostra dados atuais em
-- vez de esperar a política de refresh (que atrasa pelo seu end_offset).
-- Necessário para o gráfico do Performance Insights do web-system.

-- Nível 1: 1 minuto, a partir das leituras cruas.
CREATE MATERIALIZED VIEW sensor_reading_1m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
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

-- Nível 2: 15 minutos, a partir do agregado de 1m.
CREATE MATERIALIZED VIEW sensor_reading_15m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
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

-- Nível 3: 30 minutos, a partir do agregado de 15m.
CREATE MATERIALIZED VIEW sensor_reading_30m
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
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

-- Nível 4: 1 hora, a partir do agregado de 30m.
CREATE MATERIALIZED VIEW sensor_reading_1h
WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
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
