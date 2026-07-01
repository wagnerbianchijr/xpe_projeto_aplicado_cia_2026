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
